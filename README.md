# Centaur

Centaur is a native, collaborative workspace for building GTK4 applications. Each project combines a live app preview, canvas drawing and comments, a shared conversation, and Git-backed history.

Create an application, import an existing GitHub repository or local folder, and invite others to build with you. Centaur's AI agent helps investigate projects and make changes through conversation.

**Centaur is preview software.** The signed GTK4 release workflow targets ARM64 and x86-64 NixOS. Standalone app deployment, the design-system library and macOS releases are planned.

## Install on NixOS

Run these commands from a terminal in your graphical desktop, as your normal user. You'll need Nix with flakes, `curl`, `python3`, and `sudo` for the initial cache setup.

No source checkout or Cachix account is required.

### 1. Configure the binary cache

This is a one-time setup so Nix can download Centaur's signed, precompiled packages.

```sh
curl -fsSL https://raw.githubusercontent.com/mattatgit/Centaur/main/scripts/centaur-cache-setup.sh \
  -o "$HOME/centaur-cache-setup.sh"

bash "$HOME/centaur-cache-setup.sh" check
sudo bash "$HOME/centaur-cache-setup.sh" enable
```

The check makes no changes. Enabling the cache restarts the Nix daemon but does not rebuild NixOS.

If the check rejects your system configuration, don't force it. You can instead use the [Centaur NixOS cache module](packaging/centaur-cache.nix) with your existing declarative configuration.

### 2. Install Centaur

Install the latest signed preview for your machine into the dedicated Nix profile. The command selects the ARM64 or x86-64 release and disables local compilation. [Install the current preview](docs/NIXOS_INSTALL.md#2-install-the-current-preview)

### 3. Set up the AI agent (host computer only)

Centaur uses [oh-my-pi (OMP)](https://github.com/can1357/oh-my-pi) as its underlying AI runtime.

Install OMP before launching Centaur on a computer that will host agent requests. For Nix 2.30 or newer:

```sh
nix --extra-experimental-features 'nix-command flakes' \
  profile add github:can1357/oh-my-pi
```

For older Nix versions, use `profile install` instead of `profile add`. See the [OMP installation instructions](https://github.com/can1357/oh-my-pi#install) for other methods.

Guest computers joining a shared Centaur project do not need their own OMP installation.

### 4. Launch Centaur

```sh
"$HOME/.local/state/nix/profiles/centaur-gtk4/bin/centaur-gtk4"
```

The first launch registers Centaur in your desktop application launcher.

Once running, open **Settings → LLM and Model** to connect your preferred AI provider and select a model.

Your projects are stored by default in `~/.local/share/Centaur/GTK4`.

## Getting started

From Projects, choose **Create**, **Import** or **Join**.

Within a project, use **Interact** to operate the running application or **Build** to draw, comment and request changes. Mention `@centaur` in chat when you want the agent to work on the application.

To collaborate across computers, use **Invite** to generate a secure, single-use invitation code.

## Updating Centaur

Once installed, Centaur can update itself. Use **Update app** in Settings or the version control at the bottom of the chat panel.

Updates download verified packages, restart Centaur and preserve your existing project data.

## Documentation

See the [project documentation](docs/README.md) for architecture and development information, or [Current state](docs/CURRENT.md) for the latest verified implementation and known limitations.
