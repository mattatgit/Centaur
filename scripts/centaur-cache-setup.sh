#!/usr/bin/env bash
# NixOS escape hatch when the original system configuration is unavailable.
# Run check as the desktop user; enable/disable require root once.
set -euo pipefail

cache_url='https://mattatgit-centaur.cachix.org?priority=30'
cache_key=mattatgit-centaur.cachix.org-1:ouvsfGud6lFrvNNxpE1S5yGkNFm9J2WKtnIm38OSQ58=
config=/etc/nix/centaur-cache.conf
dropin=/etc/systemd/system/nix-daemon.service.d/90-centaur-cache.conf
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
check() {
    [[ $(uname -s) == Linux && -f /etc/NIXOS ]] || die 'This cache setup is for NixOS only.'
    [[ -d /run/systemd/system ]] || die 'The system is not running systemd. Stop here and share this message.'
    [[ $(systemctl show nix-daemon.service -p LoadState --value) == loaded ]] || die 'Nix daemon service not found.'
    [[ $(systemctl show nix-daemon.service -p User --value) =~ ^(root)?$ ]] || die 'The Nix daemon has a custom service user. Stop here.'
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
    echo 'Nix daemon checks passed. No system rebuild is needed.'
}

case ${1:-check} in
    check) check ;;
    enable)
        [[ $EUID == 0 ]] || die 'Run this step with sudo, after the check passes.'
        check
        # Register rollback before touching either file. Refuse unrelated files
        # above; restore exactly the pre-existing managed-file state on failure.
        had_config=0; had_dropin=0
        [[ ! -e $config ]] || had_config=1
        [[ ! -e $dropin ]] || had_dropin=1
        rollback() {
            local status=$?
            trap - EXIT
            if (( status != 0 )); then
                (( had_dropin == 1 )) || rm -f "$dropin"
                (( had_config == 1 )) || rm -f "$config"
                systemctl daemon-reload || true
                systemctl restart nix-daemon.service || true
                echo 'Setup failed; the previous cache configuration was retained/restored.' >&2
            fi
            exit "$status"
        }
        trap rollback EXIT
        [[ -d /etc/nix ]] || install -d -m 0755 /etc/nix
        [[ -d /etc/systemd/system/nix-daemon.service.d ]] || install -d -m 0755 /etc/systemd/system/nix-daemon.service.d
        temporary=$(mktemp /etc/nix/.centaur-cache.XXXXXX)
        config_text > "$temporary"
        chmod 0644 "$temporary"
        mv "$temporary" "$config"
        temporary=$(mktemp /etc/systemd/system/nix-daemon.service.d/.centaur-cache.XXXXXX)
        dropin_text > "$temporary"
        chmod 0644 "$temporary"
        mv "$temporary" "$dropin"
        systemctl daemon-reload
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
