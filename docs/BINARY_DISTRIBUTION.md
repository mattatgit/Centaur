# Precompiled Centaur for NixOS

Centaur's distribution workflow builds the current native package on native **x86_64-linux** and **aarch64-linux** GitHub runners. The package includes **centaur**, **centaur-host**, **centaur-preview** and the native **centaur-network** Iroh helper, bundled fonts, Qt/Wayland and every other runtime dependency in its Nix closure. No separate Rust, Cargo or Iroh installation is needed on downloading machines.

The public cache is **`mattatgit-centaur`**. Its verified public URL/key are available in [the ready-to-use NixOS configuration](../packaging/centaur-cache.nix). The first publication still requires a successful Publish job: a green build with skipped Publish jobs does not mean the package has been uploaded.

## One-time maintainer setup

1. Sign in at [Cachix](https://app.cachix.org/) and create a **public** cache. A suitable name is `mattatgit-centaur` if available; use your actual chosen name throughout. Choose Cachix-managed signing rather than bringing a private signing key.
2. In that cache's settings, create a **per-cache write token**, restricted to this cache. Keep it private. Public downloads need no token, and the Air does not need this credential or a Cachix account.
3. Open [Centaur's Actions variables](https://github.com/mattatgit/Centaur/settings/variables/actions) and add repository variable **`CENTAUR_CACHIX_CACHE`** with the cache name only, such as `mattatgit-centaur`.
4. Open [Centaur's Actions secrets](https://github.com/mattatgit/Centaur/settings/secrets/actions) and add repository secret **`CACHIX_AUTH_TOKEN`** with the write token. Do not put it in a chat, commit, NixOS configuration or launch script.
5. In [Actions → Native prototype](https://github.com/mattatgit/Centaur/actions/workflows/native.yml), choose **Run workflow** and select **`codex/native-prototype`**. The workflow file must be present on the repository's default branch for GitHub's manual Run workflow button to be available. Otherwise, pushing a normal commit on the prototype branch triggers it too.
6. Wait for both **Check** jobs and both **Publish** jobs to succeed. Future pushes to the prototype branch publish automatically after both architecture checks and the distribution-tooling checks pass.

No GitHub personal access token, OpenAI credential or separate signing-key secret is needed for publication. Keep enough Cachix storage available for both architectures and the releases you want to retain. Rotate/revoke the cache write token in Cachix and replace the GitHub secret if necessary.

Each successful Publish job uploads a small artifact named `centaur-distribution-x86_64-linux` or `centaur-distribution-aarch64-linux`. It contains:

- `manifest.json`: exact source commit, package version, store path, cache URL and verified-download status.
- `cache-config.nix`: the actual public cache URL and signing keys, ready to import into NixOS.
- `closure-paths.txt`: all runtime paths verified in the cache.
- `cache.json` and `version.txt`: public cache metadata and the executable's reported version.

Artifacts contain no credentials. They expire after 30 days; the binaries themselves live in Cachix independently of GitHub artifact retention.

## Install or update on NixOS

Use [the step-by-step installation guide](NIXOS_INSTALL.md). It covers the Air's missing NixOS source configuration, checks each machine independently, enables permanent daemon trust without a system rebuild, and installs the download-only update helper. Future updates use `~/.local/bin/centaur-update`; it keeps the existing data directory and OMP executable.

The helper manages the existing dedicated profile at `~/.local/state/nix/profiles/centaur` with Nix's atomic single-package profile switch. This also supports installations originally pinned to an older immutable commit. After migration, use the helper rather than `nix profile upgrade`. Download failures leave the old host running; a realised candidate is selected before the host stops and the exact package is activated offline. Standard signature verification stays enabled, with local and remote builders disabled.

Only a machine hosting agent requests needs OMP. The Air can use the VM's shared agent without installing OMP; see [collaboration](LAN_COLLABORATION.md).

### Alternative for a machine with a known, maintained NixOS configuration

[packaging/centaur-cache.nix](../packaging/centaur-cache.nix) remains available for administrators who already know how that machine's NixOS configuration is managed. Import it into the real configuration, retain existing imports and apply the normal system update for that installation. Do not assume `/etc/nixos/configuration.nix` exists, create a replacement OS configuration or replace the store-backed `/etc/nix/nix.conf` just to enable Centaur's cache. Copying the module to `/etc/nixos` alone does not activate it.

## Prove it is downloading binaries

Before installing, inspect the plan:

```sh
nix --refresh build --dry-run --no-link --max-jobs 0 --builders '' \
  'github:mattatgit/Centaur?ref=codex/native-prototype'
```

For a package not already installed, expect paths to be **fetched**, including Centaur from your Cachix URL. The dry run is informational; the actual cache-only install/build is the stronger test:

```sh
nix --refresh build --no-link --print-out-paths -L \
  --max-jobs 0 --builders '' --option fallback false \
  'github:mattatgit/Centaur?ref=codex/native-prototype'
```

Successful completion cannot compile locally with these flags. Logs normally include `copying path ... from 'https://YOUR-CACHE.cachix.org'`. If paths are already installed, Nix may have nothing to download; that is expected. To independently check that the server has the exact package, use the store path and cache URL from `manifest.json`:

```sh
nix path-info --store 'https://YOUR-CACHE.cachix.org' --recursive \
  /nix/store/STORE-PATH-FROM-THE-MANIFEST
```

The uploader checks whether each dependency exists in this particular Cachix cache, rather than accepting Cachix’s bulk-query shortcut for paths in the standard Nix cache. The official Cachix client still handles compression, uploads and managed signatures.

CI performs a stronger check after every upload: it downloads the whole closure directly from Cachix into an **empty isolated store**, requires valid signatures, supplies no fallback caches/builders, and compares the downloaded path list with the built closure. Publish fails if any dependency or trusted signature is missing.

For a reproducible install, replace the moving branch reference in the install/run command with the manifest's immutable reference, for example `github:mattatgit/Centaur/FULL-COMMIT-SHA`. A profile installed at an immutable commit stays pinned; use the update helper for routine updates from the development branch.

## If the cache-only installation fails

- Check that **Publish x86_64-linux** succeeded for the exact revision, not merely that Check jobs passed. Before cache setup, Publish jobs are deliberately skipped.
- Check that the daemon cache setup succeeded, or that the machine’s real NixOS configuration imports/applies `centaur-cache.nix`. A user-side public key or an unapplied module does not establish daemon trust.
- Use the published commit from `manifest.json` if the branch has moved ahead of its latest successful publication.
- Keep `flake.lock` unchanged. A different nixpkgs revision, dirty checkout, package override or different architecture produces a different store path.
- Retry with `--refresh` after publication to bypass stale negative cache lookups. Cache removal/retention can also make an old commit unavailable; rerun its trusted build/publication or select a retained published commit.

No application source files are modified by this distribution workflow. CI runs the existing network, coordination, UI and both native embedding tests on each Linux architecture. Pull requests and other branches cannot access the publication token or publish packages. Publication runners realise the same locked package again after the complete Check matrix passes, then upload explicitly; no failed-test outputs are uploaded by a post-build hook.

References: [Cachix setup and tokens](https://docs.cachix.org/getting-started), [complete runtime closure uploads](https://docs.cachix.org/pushing), [Nix cache configuration](https://nix.dev/guides/recipes/add-binary-cache.html), [Nix copy and signature checking](https://nix.dev/manual/nix/2.35/command-ref/new-cli/nix3-copy).
