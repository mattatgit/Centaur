#!/usr/bin/env bash
# CI only: an isolated native Wayland session, never the user's desktop.
set -euo pipefail
[[ $# == 2 ]] || { echo 'Usage: check-gtk4-wayland.sh PACKAGE NEW_REPORT_DIRECTORY' >&2; exit 2; }
package=$(realpath "$1")
reports=$(realpath -m "$2")
: "${XDG_RUNTIME_DIR:?A private runtime directory is required}"
config=$(mktemp)
sway_log=$(mktemp)
sway_pid=''
keyboard_pid=''
cleanup() {
    if [[ -n $keyboard_pid ]]; then
        kill "$keyboard_pid" 2>/dev/null || true
        wait "$keyboard_pid" 2>/dev/null || true
    fi
    if [[ -n $sway_pid ]]; then
        kill "$sway_pid" 2>/dev/null || true
        wait "$sway_pid" 2>/dev/null || true
    fi
    mkdir -p "$reports"
    cp "$sway_log" "$reports/compositor.log"
    rm -f "$config" "$sway_log"
}
trap cleanup EXIT
cat > "$config" <<'CONF'
output HEADLESS-1 mode 1280x900
seat seat0 fallback true
default_border none
focus_follows_mouse no
for_window [app_id="org.centaur.Gtk4EmbeddingTest"] floating enable, border none
CONF
unset DISPLAY WAYLAND_DISPLAY SWAYSOCK
export WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1
sway --unsupported-gpu -c "$config" > "$sway_log" 2>&1 &
sway_pid=$!
shopt -s nullglob
for _ in {1..100}; do
    ipc_sockets=("$XDG_RUNTIME_DIR"/sway-ipc.*.sock)
    for candidate in "$XDG_RUNTIME_DIR"/wayland-*; do
        if [[ -S $candidate ]]; then export WAYLAND_DISPLAY=${candidate##*/}; break; fi
    done
    if [[ ${#ipc_sockets[@]} -gt 0 && -n ${WAYLAND_DISPLAY:-} ]]; then
        export SWAYSOCK=${ipc_sockets[0]}
        break
    fi
    kill -0 "$sway_pid" 2>/dev/null || { cat "$sway_log" >&2; exit 1; }
    sleep 0.1
done
: "${SWAYSOCK:?The disposable compositor did not start}"
# Give the otherwise input-less headless seat a persistent keyboard before GTK
# discovers it. Individual wtype commands then exercise real Wayland key events.
wtype -k Shift_L -s 120000 >> "$sway_log" 2>&1 &
keyboard_pid=$!
for _ in {1..100}; do
    inputs=$(swaymsg -t get_inputs -r)
    if [[ $inputs == *keyboard* ]]; then break; fi
    kill -0 "$keyboard_pid" 2>/dev/null || { cat "$sway_log" >&2; exit 1; }
    sleep 0.1
done
[[ $inputs == *keyboard* ]] || { echo 'No test keyboard was attached.' >&2; exit 1; }
export GDK_BACKEND=wayland CENTAUR_GTK4_TEST_BACKEND=wayland CENTAUR_GTK4_TEST_UNDECORATED=1
"$package/bin/centaur-gtk4-check" "$reports"
