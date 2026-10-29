#!/usr/bin/env bash
# Dedicated Centaur package profile. No builds, sudo, application-data edits,
# credential copies or OS rebuilds. See docs/BINARY_DISTRIBUTION.md.
set -euo pipefail

die() { echo "$*" >&2; exit 1; }
[[ $EUID != 0 ]] || die 'Run Centaur as your normal desktop user, without sudo.'
[[ $(uname -s) == Linux ]] || die 'This helper is for Linux desktops.'
(( BASH_VERSINFO[0] > 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] >= 4) )) \
    || die 'This helper needs Bash 4.4 or later (included in current NixOS).'
profile="$HOME/.local/state/nix/profiles/centaur"
settings="${XDG_CONFIG_HOME:-$HOME/.config}/centaur-launcher"
data_dir="${XDG_DATA_HOME:-$HOME/.local/share}/Centaur/Centaur"
[[ ! -f $settings/data-dir ]] || IFS= read -r data_dir < "$settings/data-dir"
omp=${CENTAUR_AGENT:-}
[[ -n $omp || ! -f $settings/omp-path ]] || IFS= read -r omp < "$settings/omp-path"
save_settings=0
command=update
reference='github:mattatgit/Centaur?ref=codex/native-prototype'
while (( $# )); do
    case $1 in
        update|start|status) command=$1; shift ;;
        --omp|--data-dir|--revision)
            (( $# >= 2 )) || die "Missing value for $1."
            case $1 in
                --omp) omp=$2; save_settings=1 ;;
                --data-dir) data_dir=$2; save_settings=1 ;;
                --revision)
                    [[ $2 =~ ^[a-f0-9]{40}$ ]] || die 'Use the full published Git commit for --revision.'
                    reference="github:mattatgit/Centaur/$2"
                    ;;
            esac
            shift 2 ;;
        --help|-h)
            echo 'Usage: centaur-update [update|start|status] [--omp /path/to/omp] [--data-dir /absolute/path] [--revision FULL_COMMIT]'
            exit 0 ;;
        *) die "Unknown option: $1" ;;
    esac
done
[[ $data_dir == /* && $data_dir != *$'\n'* ]] || die 'The data directory must be one absolute path.'
data_dir=$(realpath -m -s -- "$data_dir")
if [[ -z $omp && -x $HOME/.local/bin/omp ]]; then omp="$HOME/.local/bin/omp"; fi
if [[ -z $omp ]]; then omp=$(command -v omp || true); fi
if [[ -n $omp ]]; then
    [[ $omp == /* && $omp != *$'\n'* && -x $omp ]] || die "OMP executable not found: $omp. Nothing was changed."
    export CENTAUR_AGENT="$omp"
fi

# Examine only our own processes; do not print their arguments or credentials.
matching_processes() {
    local kind=$1 entry executable index
    local -a arguments
    for entry in /proc/[0-9]*; do
        [[ -O $entry && -r $entry/cmdline ]] || continue
        arguments=()
        mapfile -d '' -t arguments < "$entry/cmdline" 2>/dev/null || continue
        (( ${#arguments[@]} )) || continue
        executable=${arguments[0]##*/}
        if [[ $kind == windows ]]; then
            case $executable in centaur|.centaur-wrapped) echo "${entry##*/}" ;; esac
        else
            case $executable in centaur-host|.centaur-host-wrapped) ;; *) continue ;; esac
            for (( index=1; index+1<${#arguments[@]}; index++ )); do
                if [[ ${arguments[index]} == --data-dir && ${arguments[index+1]} == "$data_dir" ]]; then
                    echo "${entry##*/}"; break
                fi
            done
        fi
    done
    return 0
}
launch() {
    [[ -x $profile/bin/centaur ]] || die 'Centaur is not installed yet. Run centaur-update first.'
    [[ -n ${DISPLAY:-}${WAYLAND_DISPLAY:-} ]] || die 'Open a terminal in your graphical desktop to launch Centaur.'
    if (( save_settings )); then
        install -d -m 0700 "$settings"
        printf '%s\n' "$data_dir" > "$settings/data-dir"
        if [[ -n $omp ]]; then printf '%s\n' "$omp" > "$settings/omp-path"; fi
    fi
    echo "Starting Centaur. Agent: ${omp:-not installed on this machine (guests can use the remote host)}"
    # The profile now roots the package. Do not leave the temporary download
    # root behind when exec replaces this shell (EXIT traps do not run on exec).
    if [[ -n ${work_directory:-} ]]; then
        rm -rf "$work_directory"
        trap - EXIT
    fi
    # Close the helper lock before starting the app or its detached host.
    flock -u 9
    exec 9>&-
    exec "$profile/bin/centaur" --data-dir "$data_dir" --demo
}
if [[ $command == status ]]; then
    nix --version
    if [[ -x $profile/bin/centaur ]]; then
        QT_QPA_PLATFORM=offscreen "$profile/bin/centaur" --version
        echo "Installed package: $(readlink -f "$profile")"
    else echo 'Centaur is not installed in the dedicated profile.'; fi
    echo "Data directory: $data_dir"
    echo "Agent: ${omp:-not installed on this machine}"
    echo "Background host PIDs: $(matching_processes host)"
    exit 0
fi
command -v nix >/dev/null || die 'Nix was not found.'
command -v flock >/dev/null || die 'The system flock command was not found; stop here for review.'
install -d -m 0700 "$HOME/.local/state/centaur-updater"
exec 9> "$HOME/.local/state/centaur-updater/lock"
flock -n 9 || die 'Another Centaur launch/update helper is already running.'
if [[ $command == start ]]; then launch; fi
[[ -n ${DISPLAY:-}${WAYLAND_DISPLAY:-} ]] || die 'Run the update from a terminal in your graphical desktop.'
[[ -z $(matching_processes windows) ]] || die 'Close all Centaur windows on this computer, then run the update again.'
[[ ! -e $profile || -L $profile ]] || die 'The dedicated profile is an unexpected directory/file. Stop here for review.'
if [[ -e $profile ]]; then
    [[ -x $profile/bin/centaur && -x $profile/bin/centaur-host ]] || die 'This profile is not a Centaur installation. Nothing was changed.'
    for executable in "$profile"/bin/*; do
        case ${executable##*/} in
            centaur|centaur-host|centaur-preview|centaur-network|centaur-update|centaur-cache-setup) ;;
            *) die 'The dedicated Centaur profile contains other programs. Stop here so they can be preserved.' ;;
        esac
    done
fi
old_package=$(readlink -f "$profile" 2>/dev/null || true)
work_directory=$(mktemp -d "${TMPDIR:-/tmp}/centaur-update.XXXXXX")
trap 'rm -rf "$work_directory"' EXIT
nix_options=(--extra-experimental-features 'nix-command flakes'
    --max-jobs 0 --builders '' --option fallback false --option require-sigs true
    --extra-substituters 'https://mattatgit-centaur.cachix.org?priority=30')
echo 'Downloading the published Centaur package. Compilation is disabled.'
if ! nix "${nix_options[@]}" --refresh build --no-update-lock-file \
    --out-link "$work_directory/candidate" "$reference"; then
    die 'Download failed. The installed version and background host were not changed. Check cache setup and successful publication, then retry.'
fi
candidate=$(readlink -f "$work_directory/candidate")
for executable in centaur centaur-host centaur-preview centaur-network centaur-update; do
    [[ -x $candidate/bin/$executable ]] || die "The download is missing $executable. Nothing was changed."
done
QT_QPA_PLATFORM=offscreen "$candidate/bin/centaur" --version
[[ -z $(matching_processes windows) ]] || die 'A Centaur window opened during the download. Close it and retry; the profile and host were not changed.'
echo 'Download complete. Restarting the Centaur background host.'
host_binary="$candidate/bin/centaur-host"
[[ ! -x $old_package/bin/centaur-host ]] || host_binary="$old_package/bin/centaur-host"
"$host_binary" --stop --data-dir "$data_dir"
for (( attempt=0; attempt<30; attempt++ )); do
    [[ -n $(matching_processes host) ]] || break
    sleep 0.1
done
[[ -z $(matching_processes host) ]] || die 'The old host did not stop. The installed profile was not changed; stop here for review.'
# Build's --profile uses Nix's locked, atomic generation switch. Using the
# already-realised store path prevents a moving branch changing mid-update.
# This also migrates old immutable-commit profile installs without duplicates.
if ! nix "${nix_options[@]}" --offline build --no-link --profile "$profile" "$candidate"; then
    die 'The profile switch failed. Reopen the previous version with centaur-update start; no project data was changed.'
fi
# Short command follows the stable profile, so future packages update the helper.
install -d "$HOME/.local/bin"
shortcut="$HOME/.local/bin/centaur-update"
if [[ ! -e $shortcut || ( -L $shortcut && $(readlink "$shortcut") == "$profile/bin/centaur-update" ) ]]; then
    ln -sfn "$profile/bin/centaur-update" "$shortcut"
fi
echo 'Centaur updated. Future updates: ~/.local/state/nix/profiles/centaur/bin/centaur-update'
if [[ -L $shortcut && $(readlink "$shortcut") == "$profile/bin/centaur-update" ]]; then
    echo 'Short command: ~/.local/bin/centaur-update'
else
    echo 'An existing ~/.local/bin/centaur-update was preserved; use the profile command above.'
fi
launch
