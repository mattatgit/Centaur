#!/usr/bin/env bash
# NixOS escape hatch when the original system configuration is unavailable.
# Run check as the desktop user; enable/disable require root once.
set -euo pipefail

cache_url='https://mattatgit-centaur.cachix.org?priority=30'
cache_key=mattatgit-centaur.cachix.org-1:ouvsfGud6lFrvNNxpE1S5yGkNFm9J2WKtnIm38OSQ58=
config=/etc/nix/centaur-cache.conf
# NixOS normally links /etc/systemd/system into the read-only store. The
# persistent control path is a separate, documented systemd drop-in load path.
override_root=/etc/systemd/system.control
dropin="$override_root/nix-daemon.service.d/90-centaur-cache.conf"
legacy_dropin=/etc/systemd/system/nix-daemon.service.d/90-centaur-cache.conf
marker='# Managed by Centaur cache setup v1'

die() { echo "$*" >&2; exit 1; }
config_text() {
    printf '%s\n' "$marker" \
        "extra-substituters = $cache_url" \
        "extra-trusted-public-keys = $cache_key" \
        'require-sigs = true'
}
dropin_text() {
    printf '%s\n' "$marker" '[Service]' \
        "Environment=\"NIX_CONFIG=include $config\""
}
same_file() { cmp -s "$1" <("$2"); }
select_dropin() {
    # Retain an earlier successful installation rather than layering overrides.
    if [[ -e $legacy_dropin || -L $legacy_dropin ]]; then
        [[ ! -e $dropin && ! -L $dropin ]] || die 'Two Centaur overrides exist. Stop here for review.'
        dropin=$legacy_dropin
        override_root=/etc/systemd/system
    fi
    [[ -z ${SYSTEMD_UNIT_PATH:-} ]] || die 'A custom SYSTEMD_UNIT_PATH is set. Stop here for review.'
    systemd-analyze --system unit-paths | grep -Fx "$override_root" >/dev/null \
        || die "This system does not list $override_root as a supported unit path. Stop here for review."
}
check_location() {
    # Inspect the nearest existing ancestor without creating anything. Root's
    # -w test alone does not reliably identify read-only mounts/store symlinks.
    local parent=$1 resolved mount_options
    while [[ ! -e $parent && ! -L $parent ]]; do parent=$(dirname "$parent"); done
    [[ -d $parent ]] || die "Expected a directory at $parent. Stop here for review."
    resolved=$(realpath -e "$parent")
    [[ $resolved != /nix/store && $resolved != /nix/store/* ]] \
        || die "$parent resolves into the read-only Nix store. No setup changes were made."
    mount_options=$(findmnt --noheadings --output OPTIONS --target "$parent") \
        || die "Could not check the filesystem containing $parent. Stop here for review."
    [[ ",$mount_options," != *,ro,* ]] || die "$parent is on a read-only filesystem. No setup changes were made."
    if (( EUID == 0 )); then
        [[ -w $parent ]] || die "$parent is not writable. No setup changes were made."
    fi
}
check() {
    [[ $(uname -s) == Linux && -f /etc/NIXOS ]] || die 'This cache setup is for NixOS only.'
    [[ -d /run/systemd/system ]] || die 'The system is not running systemd. Stop here and share this message.'
    [[ $(systemctl show nix-daemon.service -p LoadState --value) == loaded ]] || die 'Nix daemon service not found.'
    [[ $(systemctl show nix-daemon.service -p User --value) =~ ^(root)?$ ]] || die 'The Nix daemon has a custom service user. Stop here.'
    select_dropin
    check_location "$(dirname "$config")"
    check_location "$(dirname "$dropin")"
    # Never overwrite an unrelated file, symlink or existing NIX_CONFIG.
    for path in "$config" "$dropin"; do
        [[ ! -L $path ]] || die "Existing symlink at $path; stop here for review."
    done
    if [[ -e $config ]]; then same_file "$config" config_text || die "Existing custom $config; stop here for review."; fi
    if [[ -e $dropin ]]; then same_file "$dropin" dropin_text || die "Existing custom $dropin; stop here for review."; fi
    local environment
    environment=$(systemctl show nix-daemon.service -p Environment --value)
    if [[ $environment == *NIX_CONFIG=* ]]; then
        [[ -f $dropin && $environment == *"\"NIX_CONFIG=include $config\""* ]] \
            || die 'The daemon already has NIX_CONFIG settings. Stop here so they can be preserved.'
    fi
    [[ -z $(systemctl show nix-daemon.service -p EnvironmentFiles --value) ]] \
        || die 'The daemon uses an environment file. Stop here so its settings can be reviewed.'
    local property value
    for property in PassEnvironment UnsetEnvironment; do
        value=$(systemctl show nix-daemon.service -p "$property" --value)
        [[ $value != *NIX_CONFIG* ]] || die "The daemon uses $property for NIX_CONFIG. Stop here for review."
    done
    # A command-line setting could override the added configuration.
    value=$(systemctl show nix-daemon.service -p ExecStart --value)
    [[ $value != *--option* && $value != *--substituters* && $value != *--trusted-public-keys* && $value != *--no-require-sigs* ]] \
        || die 'The daemon has custom command-line settings. Stop here for review.'
    echo "Nix daemon checks passed. Persistent override: $dropin"
    echo 'No system rebuild is needed. The sudo setup step will verify file creation.'
}

case ${1:-check} in
    check) check ;;
    enable)
        [[ $EUID == 0 ]] || die 'Run this step with sudo, after the check passes.'
        check
        # Register rollback before touching either file. Refuse unrelated files
        # above; restore exactly the pre-existing managed-file state on failure.
        had_config=0; had_dropin=0
        config_written=0; dropin_written=0; daemon_touched=0
        config_temporary=; dropin_temporary=
        [[ ! -e $config ]] || had_config=1
        [[ ! -e $dropin ]] || had_dropin=1
        rollback() {
            local status=$?
            local recovery_failed=0
            trap - EXIT
            set +e
            [[ -z $config_temporary ]] || rm -f "$config_temporary"
            [[ -z $dropin_temporary ]] || rm -f "$dropin_temporary"
            if (( status != 0 )); then
                if (( had_dropin == 0 && dropin_written )); then rm -f "$dropin" || recovery_failed=1; fi
                if (( had_config == 0 && config_written )); then rm -f "$config" || recovery_failed=1; fi
                if (( dropin_written )); then systemctl daemon-reload || recovery_failed=1; fi
                if (( daemon_touched )); then systemctl restart nix-daemon.service || recovery_failed=1; fi
                if (( recovery_failed )); then
                    echo 'Setup failed and recovery needs review. Share the full output before proceeding.' >&2
                else
                    echo 'Setup failed; the previous cache configuration was retained/restored.' >&2
                fi
            fi
            exit "$status"
        }
        trap rollback EXIT
        [[ -d /etc/nix ]] || install -d -m 0755 /etc/nix
        dropin_directory=$(dirname "$dropin")
        [[ -d $dropin_directory ]] || install -d -m 0755 "$dropin_directory"
        # Stage BOTH files before replacing either managed configuration file.
        config_temporary=$(mktemp /etc/nix/.centaur-cache.XXXXXX)
        dropin_temporary=$(mktemp "$dropin_directory/.centaur-cache.XXXXXX")
        config_text > "$config_temporary"
        dropin_text > "$dropin_temporary"
        chmod 0644 "$config_temporary" "$dropin_temporary"
        mv "$config_temporary" "$config"
        config_temporary=; config_written=1
        mv "$dropin_temporary" "$dropin"
        dropin_temporary=; dropin_written=1
        systemctl daemon-reload
        loaded_dropins=$(systemctl show nix-daemon.service -p DropInPaths --value)
        read -r -a loaded_paths <<< "$loaded_dropins"
        override_loaded=0
        for path in "${loaded_paths[@]}"; do
            [[ $path != "$dropin" ]] || override_loaded=1
        done
        (( override_loaded )) || die 'Systemd did not load the Centaur override. The daemon was not restarted.'
        daemon_touched=1
        systemctl restart nix-daemon.service
        systemctl is-active --quiet nix-daemon.service
        # Check the actual new daemon environment, not just systemd's plan.
        daemon_pid=$(systemctl show nix-daemon.service -p MainPID --value)
        [[ $daemon_pid =~ ^[1-9][0-9]*$ ]] || die 'Nix daemon PID was not found.'
        tr '\0' '\n' < "/proc/$daemon_pid/environ" | grep -Fx "NIX_CONFIG=include $config" >/dev/null \
            || die 'The new daemon did not receive the cache configuration.'
        trap - EXIT
        echo 'Centaur cache enabled permanently. Signature checking remains enabled.'
        echo 'Return to your normal desktop user for installation and updates.'
        ;;
    disable)
        [[ $EUID == 0 ]] || die 'Run this step with sudo.'
        [[ $(uname -s) == Linux && -f /etc/NIXOS ]] || die 'This cache setup is for NixOS only.'
        select_dropin
        check_location "$(dirname "$config")"
        check_location "$(dirname "$dropin")"
        # Removing a manually managed override must never remove someone else's.
        [[ ! -L $config && ! -L $dropin ]] || die 'Unexpected symlink; stop here for review.'
        if [[ -e $config ]]; then same_file "$config" config_text || die "Custom $config; stop here."; fi
        if [[ -e $dropin ]]; then same_file "$dropin" dropin_text || die "Custom $dropin; stop here."; fi
        rm -f "$dropin" "$config"
        systemctl daemon-reload
        systemctl restart nix-daemon.service
        echo 'Centaur cache override removed. Other Nix settings were left in place.'
        ;;
    *) die 'Usage: centaur-cache-setup.sh [check|enable|disable]' ;;
esac
