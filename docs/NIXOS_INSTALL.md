# Install and update Centaur on ARM64 NixOS

Start with the [root README](../README.md#install-on-arm64-nixos). This guide adds detail for the GTK4 preview on ARM64 NixOS (`aarch64-linux`).

Run the commands as your normal user in a terminal on your graphical desktop. You need Nix with flakes, `curl` and `python3`. The one-time cache setup also needs `sudo`. If you're unsure which architecture you have, run `uname -m`. This guide applies when it prints `aarch64`.

## 1. Enable the signed binary cache

The public Cachix cache holds Centaur's precompiled packages. Cache access requires no Cachix account or source checkout. If your Nix daemon already trusts this cache, continue to step 2.

Download the [cache setup helper](../scripts/centaur-cache-setup.sh) and run its read-only check.

```sh
curl -fsSL https://raw.githubusercontent.com/mattatgit/Centaur/main/scripts/centaur-cache-setup.sh \
  -o "$HOME/centaur-cache-setup.sh" &&
  bash "$HOME/centaur-cache-setup.sh" check
```

If you see **Nix daemon checks passed**, wait for any other Nix operations to finish, then enable the cache.

```sh
sudo bash "$HOME/centaur-cache-setup.sh" enable
```

The helper adds the public cache URL and signing key to the Nix daemon through a dedicated systemd override. It keeps existing caches and signature checks enabled. It checks for conflicting settings and writable locations, stages both files, and verifies the override before restarting the daemon. It then checks that the restarted daemon is using the cache configuration. If setup fails, the helper attempts to restore the previous configuration. No NixOS rebuild is needed.

If the helper stops for review, keep its output and stop at that step. If the machine already has a maintained declarative NixOS configuration, its administrator can apply the [Centaur cache module](../packaging/centaur-cache.nix) through that configuration.

## 2. Install the current preview

Run the whole block together. It reads the [public GTK4 preview release manifest](https://github.com/mattatgit/Centaur/releases/tag/gtk4-preview), checks for a verified ARM64 release and installs the exact published revision of `gtk4-preview` into the dedicated `centaur-gtk4` profile.

```sh
(
  INSTALLABLE="$(curl -fsSL \
    https://api.github.com/repos/mattatgit/Centaur/releases/tags/gtk4-preview \
    | python3 -c '
import json, re, sys

try:
    release = json.load(sys.stdin)
    manifest = json.loads(release["body"])
    revision = manifest["sourceRevision"]
    installable = f"github:mattatgit/Centaur/{revision}#gtk4-preview"
    valid = (
        release["tag_name"] == "gtk4-preview"
        and release["draft"] is False
        and release["prerelease"] is True
        and manifest["system"] == "aarch64-linux"
        and manifest["packageAttribute"] == "gtk4-preview"
        and manifest["verifiedSignedClosureDownload"] is True
        and re.fullmatch(r"[0-9a-f]{40}", revision)
        and manifest["installable"] == installable
    )
except (KeyError, TypeError, ValueError):
    valid = False

if not valid:
    sys.exit("Could not find a verified Centaur GTK4 release for ARM64.")
print(installable)
')" || exit 1

  PROFILE="$HOME/.local/state/nix/profiles/centaur-gtk4"
  mkdir -p "$(dirname "$PROFILE")" &&
    nix --extra-experimental-features 'nix-command flakes' --refresh \
      --max-jobs 0 --builders '' --option fallback false --option require-sigs true \
      build --no-link --profile "$PROFILE" "$INSTALLABLE"
)
```

For this Centaur install, Nix requires valid signatures and disables local compilation, remote builders and fallback builds. If a required binary is unavailable, installation stops.

## 3. Set up the host and open Centaur

Before the first launch, install OMP on the computer that will host agent requests. Guests using a host's agent can go straight to launch. See [Set up the Centaur agent](OMP_NIXOS_SETUP.md#install-omp-on-the-host).

```sh
"$HOME/.local/state/nix/profiles/centaur-gtk4/bin/centaur-gtk4"
```

The first launch from this profile registers **Centaur GTK4** in your desktop's application menu. Use that shortcut for future launches. It follows the installed profile as Centaur updates.

On the host, open **Settings → LLM and Model** to [connect a provider and choose a model](OMP_NIXOS_SETUP.md#connect-a-provider-and-choose-a-model). Centaur keeps its projects and conversations in `~/.local/share/Centaur/GTK4` by default.

## Update from Centaur

- In **Settings → App**, click **Check for updates** or **Update app** if a newer release is already available.
- In a project, use the green **Update available** icon at the bottom of the chat panel. The installed version appears at the right of the footer.

In the restart prompt, choose **Yes, update** to download the signed package or **Not now** to defer. Centaur restarts when it can do so safely. Let active agent requests and project work finish if Centaur asks you to wait. Earlier GTK4 previews can start the download as soon as you click **Update app**.

Updates use the same data folder and preserve projects, conversations and settings. OMP credentials stay with OMP. Your desktop shortcut continues to open the updated profile.

The [release evidence](CURRENT.md) covers signed downloads into an empty test store, updater checks in disposable profiles and checks on an existing ARM64 NixOS VM. A complete first installation on a fresh NixOS machine is a separate hands-on check.

## Troubleshooting

- **Cache setup stops.** Keep the helper's full message for whoever manages the machine. It stops when it finds an unsupported or conflicting Nix daemon configuration.
- **Release check or download fails.** Check that GitHub and Cachix are reachable, confirm step 1 succeeded, and retry. If Nix reports an untrusted cache or missing signature, keep that error and check the daemon's cache setup.
- **The menu entry is missing or opens an older build.** Launch once using the profile command above, then look for **Centaur GTK4** in the application menu. If you use your own shortcut, point it to the profile command above.
- **An update fails.** Read the message beside the update button. If the app closes, reopen it from the desktop menu or the profile command above. The updater attempts to restore the previous version if the new one cannot start.
