# Easy installation and updates on NixOS

This guide is for both the Intel MacBook Air and the ARM64 NixOS VM. It uses the public `mattatgit-centaur` cache and the existing dedicated profile:

```text
~/.local/state/nix/profiles/centaur
```

Setup is once per computer. Afterwards, close Centaur and run:

```sh
~/.local/bin/centaur-update
```

The helper downloads first, stops the old background host, switches the installed version and opens Centaur. It disables local and remote builders and keeps signature checking enabled. If the new package is not published, it fails without stopping the host or replacing the installation. Wait for the wanted revision's **Publish x86_64-linux** and **Publish aarch64-linux** jobs in [GitHub Actions](https://github.com/mattatgit/Centaur/actions/workflows/native.yml) before updating. A branch can move ahead of publication.

## Start with the Air, then repeat on the VM

Work as your normal desktop user, in a terminal inside the graphical desktop. Please share each step's result and check it before moving to the next one. Do not paste all steps at once.

### 1. Inspect the existing installation

```sh
nix --version
readlink -f /etc/nix/nix.conf
systemctl show nix-daemon.service -p FragmentPath -p DropInPaths -p ActiveState
```

The Air was confirmed on 29 October 2026 to use Nix 2.28.4, an active `nix-daemon.service`, a store-backed `nix.conf` and no reported service drop-ins. Its missing `/etc/nixos/configuration.nix` is **not needed for this procedure**. The VM must be checked separately.

Do not replace `/etc/nix/nix.conf`, edit its store target or attempt a NixOS rebuild just to install Centaur. A lone `/etc/nixos/centaur-cache.nix` does not enable anything unless the real system configuration imports it and is applied. Restoring the Air's original system configuration remains a separate maintenance task.

### 2. Download and check the cache helper (no changes yet)

```sh
curl --fail --location --retry 3 \
  'https://raw.githubusercontent.com/mattatgit/Centaur/refs/heads/codex/native-prototype/scripts/centaur-cache-setup.sh' \
  --output "$HOME/centaur-cache-setup.sh" && \
  bash "$HOME/centaur-cache-setup.sh" check
```

Expected: **Nix daemon checks passed. No system rebuild is needed.**

The downloaded script is [reviewable in the repository](../scripts/centaur-cache-setup.sh). For a reviewed, fixed version, replace `refs/heads/codex/native-prototype` in either download URL in this guide with that version's full Git commit. Downloads require `curl` but no source checkout, Cachix client, Cachix account or write token.

If the helper asks for review, stop and share its message. It refuses existing custom cache files, service environment files, conflicting `NIX_CONFIG` settings and custom daemon flags rather than overwriting them. This is a deliberately limited setup for the standard NixOS service, not a universal configuration editor.

### 3. Enable permanent cache trust

Do this when no other Nix installation/update is running: this one-time step restarts Nix's background service.

```sh
sudo bash "$HOME/centaur-cache-setup.sh" enable
```

Expected: **Centaur cache enabled permanently. Signature checking remains enabled.**

It adds just two root-owned files:

- `/etc/nix/centaur-cache.conf`: the public cache URL/key, with `require-sigs = true`.
- `/etc/systemd/system/nix-daemon.service.d/90-centaur-cache.conf`: tells the existing Nix daemon to read that extra file through `NIX_CONFIG`.

It retains the normal Nix configuration and standard caches. It does not add you to `trusted-users`, grant passwordless sudo, disable signatures or rebuild NixOS. It checks the restarted daemon's actual environment and removes newly added files if setup fails. Running it again is safe. These files persist across reboot; an OS configuration-management tool may replace service configuration later, so recheck if an OS change breaks downloads.

The trust is installed in the **daemon**, not in the user's `~/.config/nix/nix.conf`. User-side `nix config show` alone therefore does not prove daemon trust. Adding the public key only to the user configuration cannot grant an untrusted user that permission.

### 4. Download the update helper

```sh
curl --fail --location --retry 3 \
  'https://raw.githubusercontent.com/mattatgit/Centaur/refs/heads/codex/native-prototype/scripts/centaur-update.sh' \
  --output "$HOME/centaur-update.sh"
```

Close all local Centaur windows. Let agent work finish and let collaborators know the host will briefly disconnect. Choose the command for this computer:

**MacBook Air:**

```sh
bash "$HOME/centaur-update.sh"
```

**ARM64 VM, using its existing OMP installation:**

```sh
bash "$HOME/centaur-update.sh" --omp /home/matt/.local/bin/omp
```

The helper checks the OMP executable before changing anything and remembers that path for future helper launches. It never installs OMP, signs in again or copies its credentials. The Air does not need OMP to use the VM's shared agent.

For a custom Centaur data directory, add `--data-dir /the/existing/absolute/path` at this step. Otherwise the helper uses `${XDG_DATA_HOME:-$HOME/.local/share}/Centaur/Centaur`, the normal Linux location. It remembers a supplied directory for later launches. Do not guess a different directory: using a new location would open a different workshop.

The helper supports first installation and existing older pinned installations. It uses Nix's atomic `build --profile` operation to manage this **single-package** profile going forward, retaining old profile generations. Do not use `nix profile upgrade --all` for this profile after migration; use the helper. Your ordinary Nix profile is unaffected. An existing dedicated profile containing unrelated programs is refused for review.

### 5. Check the installed result

```sh
~/.local/bin/centaur-update status
```

Share the version, data directory and agent path it reports. Also check that your projects/conversations are present, that the Air can rejoin the VM's project and that a small request still reaches the VM's agent. `status` does not send an agent request or print credentials.

The helper is included in the package. A short link in `~/.local/bin` follows the stable profile, so future Centaur packages also update the helper. An unrelated existing file at that shortcut is retained; in that case use `~/.local/state/nix/profiles/centaur/bin/centaur-update` instead.

## Everyday use

Close local Centaur windows and wait for current agent work to finish. One command downloads the new package, restarts the host and launches it:

```sh
~/.local/bin/centaur-update
```

To open the installed version without updating:

```sh
~/.local/bin/centaur-update start
```

The VM's remembered OMP path is used by both commands. A desktop shortcut should run `centaur-update start` using the full path printed above; a shortcut that launches the raw app directly does not read the helper's remembered OMP path. Updating/replacing an existing desktop shortcut is a separate guided step after installation is verified.

## How this avoids local compilation

Every package download and profile switch sets `--max-jobs 0`, `--builders ''` and `--option fallback false`. Signature checking is explicitly required; the helper supplies the public cache URL but does not try to grant itself trust. Nix still evaluates the small flake source and checks its lockfile. Missing binaries cause failure rather than compilation.

The download normally shows `copying path ... from 'https://mattatgit-centaur.cachix.org'`. If paths are already on disk there may be nothing to copy. Successful execution with those flags proves that no compiler ran for the package; a full locally cached package alone does not test new network downloads. CI separately verifies every published closure in an empty store with trusted signatures; see [Binary distribution](BINARY_DISTRIBUTION.md#prove-it-is-downloading-binaries).

The downloaded candidate stays rooted until the atomic switch is complete. The second step switches to that exact store path, offline, so a moving development branch cannot change the candidate midway through the update. Previous profile generations remain available until explicitly deleted/garbage-collected. No application-data migration, cleanup or reset is performed by the helper.

## If something goes wrong

Stop and share the helper's message. A cache miss may mean publication is still running; retry once both Publish jobs succeed. A download failure leaves both the installed version and existing host alone. If the profile switch fails after the host stops, reopen the old installation with `bash "$HOME/centaur-update.sh" start`.

To deliberately install a retained published commit instead of branch head:

```sh
bash "$HOME/centaur-update.sh" --revision FULL_40_CHARACTER_COMMIT
```

The selected package must include the helper. Older releases without it can be recovered from existing profile generations. If rollback is needed, review the target generation first with `nix --extra-experimental-features nix-command profile history --profile "$HOME/.local/state/nix/profiles/centaur"`; close local windows and stop the current host before a guided rollback. Retaining package generations is not a backup or rollback of project data. The updater does not delete project or collaboration records, OMP files or existing backups.

The one-time service override can be removed using:

```sh
sudo bash "$HOME/centaur-cache-setup.sh" disable
```

This removes only the exact files managed by this helper and restarts Nix. It does not uninstall Centaur or remove app data. If the machine's original NixOS configuration is found later, the cache can instead be incorporated through [the existing NixOS module](../packaging/centaur-cache.nix), followed by a normal managed system update and removal of the temporary service override. Do not do that until the machine's actual configuration is understood.

Technical references: [Nix configuration sources, `NIX_CONFIG` and additive settings](https://nix.dev/manual/nix/2.24/command-ref/conf-file.html), [systemd service environment](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html#Environment=), [Nix binary caches and signature trust](https://nix.dev/guides/recipes/add-binary-cache.html).
