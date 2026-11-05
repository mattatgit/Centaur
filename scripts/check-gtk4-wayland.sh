#!/usr/bin/env bash
# CI only: an isolated native Wayland session, never the user's desktop.
set -euo pipefail
[[ $# == 3 ]] || { echo 'Usage: check-gtk4-wayland.sh PACKAGE NEW_REPORT_DIRECTORY TEST_SEAT' >&2; exit 2; }
package=$(realpath "$1")
reports=$(realpath -m "$2")
test_seat=$(realpath "$3")
: "${XDG_RUNTIME_DIR:?A private runtime directory is required}"
config=$(mktemp)
sway_log=$(mktemp)
sway_pid=''
pointer_pid=''
cleanup() {
    if [[ -n $pointer_pid ]]; then
        kill "$pointer_pid" 2>/dev/null || true
        wait "$pointer_pid" 2>/dev/null || true
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
# Keep physical-like input devices and one fixed keymap throughout the test.
export CENTAUR_GTK4_TEST_SEAT="$XDG_RUNTIME_DIR/centaur-test-seat.sock"
"$test_seat" "$CENTAUR_GTK4_TEST_SEAT" >> "$sway_log" 2>&1 &
pointer_pid=$!
for _ in {1..100}; do
    inputs=$(swaymsg -t get_inputs -r)
    if [[ $inputs == *keyboard* && $inputs == *pointer* ]]; then break; fi
    kill -0 "$pointer_pid" 2>/dev/null || { cat "$sway_log" >&2; exit 1; }
    sleep 0.1
done
[[ $inputs == *keyboard* && $inputs == *pointer* ]] || { echo 'Test input devices were not attached.' >&2; exit 1; }
export GDK_BACKEND=wayland CENTAUR_GTK4_TEST_BACKEND=wayland CENTAUR_GTK4_TEST_UNDECORATED=1
"$package/bin/centaur-gtk4-check" "$reports"
