#!/usr/bin/env bash
# Exercise real Nix profile migration/atomic failure/rollback without compiling
# or installing Centaur, and without changing the user's normal profile.
set -euo pipefail
[[ $# == 1 && $1 == /nix/store/* && -d $1 ]] || { echo 'Usage: check-centaur-profile.sh CACHED_PACKAGE' >&2; exit 2; }
fixture=$1
work_directory=$(mktemp -d "${TMPDIR:-/tmp}/centaur-profile-check.XXXXXX")
trap 'rm -rf "$work_directory"' EXIT
profile="$work_directory/centaur"
options=(--extra-experimental-features 'nix-command flakes' --max-jobs 0 --builders '' --option fallback false)
# Simulate the dedicated profile created by the old installation guide.
nix "${options[@]}" --offline profile install --profile "$profile" "$fixture"
original=$(readlink -f "$profile")
# Migrate atomically to a single-package build profile. Retain generation 1.
nix "${options[@]}" --offline build --no-link --profile "$profile" "$fixture"
[[ $(readlink -f "$profile") == "$fixture" ]]
if nix "${options[@]}" --offline build --no-link --profile "$profile" \
    /nix/store/00000000000000000000000000000000-missing-centaur-fixture \
    > "$work_directory/missing.log" 2>&1; then
    echo 'An unavailable package unexpectedly succeeded.' >&2; exit 1
fi
[[ $(readlink -f "$profile") == "$fixture" ]]
nix "${options[@]}" profile rollback --profile "$profile"
[[ $(readlink -f "$profile") == "$original" ]]
echo 'Existing profile migrated; unavailable package left it unchanged; rollback restored its original generation.'
