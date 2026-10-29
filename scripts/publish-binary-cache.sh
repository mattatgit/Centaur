#!/usr/bin/env bash
# CI only: publish a checked package, then download its entire signed closure
# into an empty store. No compiler, original runner store or unsigned import
# can satisfy that download verification.
set -euo pipefail

if [ "$#" -ne 4 ]; then
  echo "Usage: $0 RESULT WORK_DIRECTORY SYSTEM SOURCE_REVISION" >&2
  exit 2
fi
: "${CENTAUR_CACHIX_CACHE:?Set the Cachix cache name}"
: "${CACHIX_AUTH_TOKEN:?Set a per-cache write token in the CI secret}"
if [[ ! "$CENTAUR_CACHIX_CACHE" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo 'Invalid Cachix cache name.' >&2
  exit 2
fi
if [[ ! "$4" =~ ^[a-f0-9]{40}$ ]]; then
  echo 'The source revision must be the full checked Git commit.' >&2
  exit 2
fi
output=$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve(strict=True))' "$1")
work_directory=$2
system=$3
revision=$4
current_system=$(nix eval --raw --impure --expr builtins.currentSystem)
if [ "$current_system" != "$system" ]; then
  echo "Expected native runner $system, got $current_system." >&2
  exit 1
fi
for executable in centaur centaur-host centaur-preview centaur-network centaur-update centaur-cache-setup; do
  test -x "$output/bin/$executable"
done
# Refuse a reused verification directory: its store must genuinely be empty.
mkdir "$work_directory"
mkdir "$work_directory/metadata"
metadata="$work_directory/metadata"
cache_url="https://${CENTAUR_CACHIX_CACHE}.cachix.org"
nix path-info --recursive "$output" | LC_ALL=C sort > "$metadata/closure-paths.txt"
QT_QPA_PLATFORM=offscreen "$output/bin/centaur" --version > "$metadata/version.txt"
curl --fail --silent --show-error --retry 3 \
  "https://app.cachix.org/api/v1/cache/$CENTAUR_CACHIX_CACHE" > "$metadata/cache.json"
public_keys=$(python3 - "$metadata/cache.json" "$CENTAUR_CACHIX_CACHE" <<'PY'
import json, sys
cache = json.load(open(sys.argv[1]))
assert cache.get('name') == sys.argv[2], 'Cache name does not match'
assert cache.get('isPublic') is True, 'The distribution cache must be public'
keys = cache.get('publicSigningKeys', [])
assert keys and all(isinstance(key, str) and ':' in key for key in keys), 'No public signing key'
print(' '.join(keys))
PY
)
python3 - "$metadata/version.txt" "$revision" <<'PY_VERSION'
import pathlib, sys
version = pathlib.Path(sys.argv[1]).read_text().strip()
build_id = version.rsplit('+', 1)[-1]
assert len(build_id) >= 7 and sys.argv[2].startswith(build_id), 'Executable does not identify the checked source revision'
PY_VERSION
# Check existence in this cache, not in upstream caches that Cachix may
# count as present. The official client still uploads and signs every NAR.
python3 scripts/push-full-cachix-closure.py "$CENTAUR_CACHIX_CACHE" "$output"
# A direct cache-to-empty-store copy must fetch every referenced object from
# Cachix. Signature checks remain enabled; no fallback caches or builders.
nix copy --from "$cache_url" --to "$work_directory/verification-store" \
  --option trusted-public-keys "$public_keys" --option require-sigs true \
  --option substituters '' --max-jobs 0 --builders '' "$output"
nix store verify --store "$work_directory/verification-store" --all \
  --option trusted-public-keys "$public_keys" --option substituters '' --sigs-needed 1
nix path-info --store "$work_directory/verification-store" --recursive "$output" \
  | LC_ALL=C sort > "$work_directory/downloaded-closure.txt"
cmp "$metadata/closure-paths.txt" "$work_directory/downloaded-closure.txt"
python3 - "$metadata" "$output" "$system" "$revision" <<'PY'
import datetime, json, pathlib, sys
folder, output, system, revision = sys.argv[1:]
folder = pathlib.Path(folder)
cache = json.loads((folder / 'cache.json').read_text())
manifest = {
    'schemaVersion': 1,
    'sourceRevision': revision,
    'system': system,
    'version': (folder / 'version.txt').read_text().strip(),
    'storePath': output,
    'installable': 'github:mattatgit/Centaur/' + revision,
    'cacheUrl': cache['uri'],
    'publicSigningKeys': cache['publicSigningKeys'],
    'closurePathCount': len((folder / 'closure-paths.txt').read_text().splitlines()),
    'verifiedSignedClosureDownload': True,
    'publishedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
(folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
key_list = ' '.join(json.dumps(key) for key in cache['publicSigningKeys'])
(folder / 'cache-config.nix').write_text(
    '{ ... }: {\n  nix.settings = {\n'
    '    experimental-features = [ "nix-command" "flakes" ];\n'
    '    extra-substituters = [ ' + json.dumps(cache['uri'] + '?priority=30') + ' ];\n'
    '    extra-trusted-public-keys = [ ' + key_list + ' ];\n'
    '  };\n}\n')
PY
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "### Published Centaur for $system"
    echo "- Commit: $revision"
    echo "- Cache: $cache_url"
    echo "- Package: \`$output\`"
    echo '- Full closure downloaded into an empty store with signature checks enabled and no builds.'
    echo '- Download the distribution metadata for the public cache key and NixOS configuration.'
  } >> "$GITHUB_STEP_SUMMARY"
fi
