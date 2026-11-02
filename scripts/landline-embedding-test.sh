#!/usr/bin/env bash
# Packaged launcher. Nix supplies these immutable executable/runtime paths.
set -euo pipefail
: "${CENTAUR_TEST_CENTAUR:?Use the packaged centaur-landline-test launcher}"
: "${CENTAUR_TEST_LANDLINE:?Use the packaged centaur-landline-test launcher}"
arguments=(--native-app-test "$CENTAUR_TEST_LANDLINE" --native-app-size 320x672)
software=0
while (( $# )); do
    case $1 in
        --smoke-test) arguments+=(--native-app-smoke-test); shift ;;
        --software) software=1; shift ;;
        --screenshot)
            (( $# >= 2 )) || { echo 'A screenshot path is required.' >&2; exit 2; }
            arguments+=(--screenshot "$2"); shift 2 ;;
        --help|-h)
            echo 'Usage: centaur-landline-test [--software] [--smoke-test] [--screenshot /path/image.png]'
            echo 'Starts Landline inside a temporary Centaur workshop. Agent editing is disabled.'
            exit 0 ;;
        *) echo "Unknown test option: $1" >&2; exit 2 ;;
    esac
done
if (( software )); then
    : "${CENTAUR_TEST_MESA_VENDOR:?The packaged software-rendering driver is missing}"
    : "${CENTAUR_TEST_MESA_DRIVERS:?The packaged software-rendering driver is missing}"
    export QT_QUICK_BACKEND=software LIBGL_ALWAYS_SOFTWARE=1
    export __EGL_VENDOR_LIBRARY_FILENAMES="$CENTAUR_TEST_MESA_VENDOR"
    export LIBGL_DRIVERS_PATH="$CENTAUR_TEST_MESA_DRIVERS"
fi
exec "$CENTAUR_TEST_CENTAUR" "${arguments[@]}"
