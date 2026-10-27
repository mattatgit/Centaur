# Precompiled Centaur for NixOS

Centaur's distribution workflow builds the existing v0.2 package on native **x86_64-linux** and **aarch64-linux** GitHub runners. The package includes **centaur**, **centaur-host** and **centaur-preview**, bundled fonts, Qt/Wayland and every other runtime dependency in its Nix closure. Application behaviour is unchanged.

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

## Configure the Air to trust the cache

Use [the ready-to-use configuration](../packaging/centaur-cache.nix), or download the **x86_64-linux** distribution artifact from a successful Publish job and use its `cache-config.nix`. Copy the file into `/etc/nixos/centaur-cache.nix`, and add it to your existing NixOS `imports` list:

```nix
imports = [
  ./hardware-configuration.nix
  ./centaur-cache.nix
];
```

Keep any other existing imports. The generated file enables flakes and adds the public substituter and signing key without replacing the standard NixOS cache. Its structure is:

```nix
{ ... }: {
  nix.settings = {
    experimental-features = [ "nix-command" "flakes" ];
    extra-substituters = [ "https://YOUR-CACHE.cachix.org?priority=30" ];
    extra-trusted-public-keys = [ "YOUR-ACTUAL-CACHIX-PUBLIC-KEY" ];
  };
}
```

Use the real values from the artifact or Cachix's cache settings; the placeholders above are not valid configuration. Apply the configuration:

```sh
sudo nixos-rebuild switch
```

This is a one-time Nix daemon configuration step. Subsequent Centaur installs/updates run as your ordinary user. A public signing key is safe to share; its corresponding private write/signing credentials stay off the Air. Signature checking remains enabled.

The same cache configuration also works on the ARM64 NixOS VM. Nix chooses that machine's ARM64 package automatically.

## Initial installation without compiling

Wait for publication of the branch revision you want. In the Air's graphical desktop, install into a dedicated Centaur profile:

```sh
nix --refresh profile install \
  --profile "$HOME/.local/state/nix/profiles/centaur" \
  --max-jobs 0 --builders '' --option fallback false \
  'github:mattatgit/Centaur?ref=codex/native-prototype'
```

Launch the installed app:

```sh
"$HOME/.local/state/nix/profiles/centaur/bin/centaur" --demo
```

The dedicated profile also contains `centaur-host` and `centaur-preview`. Qt, Wayland, fonts, Git and OpenSSL are downloaded as runtime dependencies; they do not need separate installation. The current user's projects and preferences remain in their existing data directory.

`--max-jobs 0` disables local builds and `--builders ''` disables remote builders for this command. If the required binary is missing, the command fails rather than compiling. A pending or failed publication therefore cannot unexpectedly make the Air compile Centaur. Nix still fetches the small flake source/lock data to identify the exact package; that is evaluation, not compilation.

Only a machine hosting agent requests needs a working OMP installation. The Air can join the VM's shared project without installing OMP; see [LAN collaboration](LAN_COLLABORATION.md).

For a one-off launch without installing a profile, after configuring the cache:

```sh
nix --refresh run --max-jobs 0 --builders '' --option fallback false \
  'github:mattatgit/Centaur?ref=codex/native-prototype' -- --demo
```

## Future updates

Wait for the new revision's Publish jobs to succeed. Close Centaur's local windows. Since v0.2 has a background host, stop the old host before replacing the installed profile:

```sh
"$HOME/.local/state/nix/profiles/centaur/bin/centaur-host" --stop \
  --data-dir "$HOME/.local/share/Centaur/Centaur"

nix --refresh profile upgrade \
  --profile "$HOME/.local/state/nix/profiles/centaur" --all \
  --max-jobs 0 --builders '' --option fallback false

"$HOME/.local/state/nix/profiles/centaur/bin/centaur" --demo
```

Substitute your actual data directory if using `--data-dir`. Coordinate a host restart with connected collaborators. `--all` here applies only to the dedicated Centaur profile, not your other installed packages. A failed update leaves the previous profile generation available; relaunch it if publication is not ready yet.

A desktop shortcut can launch the stable profile path shown above. Updating the profile changes what that shortcut runs, without downloading or building on each click.

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

CI performs a stronger check after every upload: it downloads the whole closure directly from Cachix into an **empty isolated store**, requires valid signatures, supplies no fallback caches/builders, and compares the downloaded path list with the built closure. Publish fails if any dependency or trusted signature is missing.

For a reproducible install, replace the moving branch reference in the install/run command with the manifest's immutable reference, for example `github:mattatgit/Centaur/FULL-COMMIT-SHA`. A profile installed at an immutable commit stays pinned; use the moving branch reference for automatic profile upgrades.

## If the cache-only installation fails

- Check that **Publish x86_64-linux** succeeded for the exact revision, not merely that Check jobs passed. Before cache setup, Publish jobs are deliberately skipped.
- Check that NixOS imported `centaur-cache.nix` and was rebuilt. An untrusted user cannot make the daemon trust a new cache merely by passing a public key at launch.
- Use the published commit from `manifest.json` if the branch has moved ahead of its latest successful publication.
- Keep `flake.lock` unchanged. A different nixpkgs revision, dirty checkout, package override or different architecture produces a different store path.
- Retry with `--refresh` after publication to bypass stale negative cache lookups. Cache removal/retention can also make an old commit unavailable; rerun its trusted build/publication or select a retained published commit.

No application source files are modified by this distribution workflow. CI runs the existing network, coordination, UI and both native embedding tests on each Linux architecture. Pull requests and other branches cannot access the publication token or publish packages. Publication runners realise the same locked package again after the complete Check matrix passes, then upload explicitly; no failed-test outputs are uploaded by a post-build hook.

References: [Cachix setup and tokens](https://docs.cachix.org/getting-started), [complete runtime closure uploads](https://docs.cachix.org/pushing), [Nix cache configuration](https://nix.dev/guides/recipes/add-binary-cache.html), [Nix copy and signature checking](https://nix.dev/manual/nix/2.35/command-ref/new-cli/nix3-copy).
