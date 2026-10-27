#!/usr/bin/env bash
# Exercise the same empty-store/signature checks as publication without needing
# a hosted cache or production token. FIXTURE must already exist in the store.
set -euo pipefail
if [ "$#" -ne 1 ]; then
  echo "Usage: $0 STORE_PATH" >&2
  exit 2
fi
fixture=$1
work_directory=$(mktemp -d /tmp/centaur-cache-check.XXXXXX)
work_directory=$(cd "$work_directory" && pwd -P)
cleanup() {
  chmod -R u+w "$work_directory"
  rm -rf "$work_directory"
}
trap cleanup EXIT
umask 077
nix key generate-secret --key-name centaur-cache-test-1 > "$work_directory/signing-key"
public_key=$(nix key convert-secret-to-public < "$work_directory/signing-key")
nix copy --to "file://$work_directory/cache?secret-key=$work_directory/signing-key&compression=zstd" "$fixture"
nix copy --from "file://$work_directory/cache" --to "$work_directory/download" \
  --option trusted-public-keys "$public_key" --option require-sigs true \
  --option substituters '' --max-jobs 0 --builders '' "$fixture"
nix store verify --store "$work_directory/download" --all \
  --option trusted-public-keys "$public_key" --option substituters '' --sigs-needed 1
nix path-info --recursive "$fixture" | LC_ALL=C sort > "$work_directory/expected"
nix path-info --store "$work_directory/download" --recursive "$fixture" \
  | LC_ALL=C sort > "$work_directory/actual"
cmp "$work_directory/expected" "$work_directory/actual"
# Explicit verification must reject the same store when no signing key is trusted.
if nix store verify --store "$work_directory/download" --all \
    --option trusted-public-keys '' --option substituters '' --sigs-needed 1 \
    > "$work_directory/untrusted.log" 2>&1; then
  echo 'The negative signature check unexpectedly succeeded.' >&2
  exit 1
fi
if ! grep -Eiq 'untrusted|signature' "$work_directory/untrusted.log"; then
  cat "$work_directory/untrusted.log" >&2
  exit 1
fi
echo 'Signed closure download passed; removing trust caused verification to fail.'
