# Omp NixOS Setup

Use these steps on the MacBook Air or in a NixOS VM to connect Centaur to a real agent.

Centaur currently needs **oh-my-pi (`omp`) installed and signed in separately**. There is no agent sign-in screen inside Centaur yet. Run the commands as your normal desktop user, from a terminal in the graphical desktop.

## 1. Install omp

If an existing installation (including a precompiled binary) already answers requests, keep it and skip to step 3. There is no need to reinstall it through Nix.

```sh
nix --extra-experimental-features 'nix-command flakes' \
  profile add github:can1357/oh-my-pi
```

If your Nix version does not recognise `profile add`, use:

```sh
nix --extra-experimental-features 'nix-command flakes' \
  profile install github:can1357/oh-my-pi
```

Check that the executable is available:

```sh
omp --version
```

If the command is not found after installation, open a new terminal and try again.

See the [upstream Nix installation instructions](https://github.com/can1357/oh-my-pi#install).

## 2. Sign in and select a model

Start omp:

```sh
omp
```

Inside omp:

1. Enter `/login` and choose your model provider. Follow its browser sign-in or API-key instructions.
2. Enter `/model` and select your default model. Choose one that accepts images, since Centaur sends screenshots with its requests.
3. Send a short message to confirm that the model responds, then exit omp.

With a hosted provider, the model runs remotely; the Air does not need to run a model locally. Credentials are managed by omp, not entered into Centaur's chat or project files.

See the [upstream authentication instructions](https://github.com/can1357/oh-my-pi/blob/main/docs/providers.md#oauth-vs-api-key-and-provider-scoped-logins).

## 3. Check a non-interactive request

From the terminal:

```sh
omp -p --no-session --no-tools "Reply with exactly: Agent connected"
```

This should produce a real model response containing `Agent connected`. If it fails, resolve the sign-in or model selection problem in omp before continuing.

## 4. Restart Centaur with omp connected

Centaur's background host retains the OMP executable/model environment from when it started. Coordinate the restart with collaborators, close **all** local Centaur windows and stop the old host before reopening with the new environment. Closing windows alone does not stop that host.

For the precompiled profile, use the [binary distribution update procedure](BINARY_DISTRIBUTION.md#future-updates). To restart an existing installed host without changing the package:

```sh
"$HOME/.local/state/nix/profiles/centaur/bin/centaur-host" --stop \
  --data-dir "$HOME/.local/share/Centaur/Centaur"
```

Substitute the actual data directory if using `--data-dir`. From a source checkout, use `./result/bin/centaur-host` after `nix build`. The next launch starts the background host with the new environment.

Launch Centaur from the same terminal:

```sh
CENTAUR_AGENT="$(command -v omp)" \
  nix --extra-experimental-features 'nix-command flakes' \
  run 'github:mattatgit/Centaur?ref=codex/native-prototype' -- --demo
```

Keep using the same desktop user that signed in to omp. This launch explicitly tells Centaur which omp executable to use.

To fetch an updated Centaur build, use:

```sh
CENTAUR_AGENT="$(command -v omp)" \
  nix --refresh --extra-experimental-features 'nix-command flakes' \
  run 'github:mattatgit/Centaur?ref=codex/native-prototype' -- --demo
```

## 5. Try a change

Open a project and send:

> @centaur change the app's title to Family planner.

The agent should ask a question or make the change after checking its native QML. Making the request is your approval; compatible changes need no extra click. Only genuinely conflicting requests pause for agreement: Centaur explains the conflict, and only the affected authors use **Agree to compromise** before that change is applied.

## If it does not work

- **`omp` is not found:** check that `omp --version` works in the terminal used to launch Centaur.
- **The terminal request fails:** reopen omp, check `/login` and the default `/model`, then repeat step 3.
- **The terminal request succeeds but Centaur times out after three minutes:** versions before the stdin fix left OMP's input pipe open. OMP waited for EOF before processing the request. Follow step 4 to close local windows, stop the background host and launch the updated build; reinstalling omp or signing in again is not needed for this bug. If omp is outside `PATH`, replace `$(command -v omp)` with its absolute path, for example `/home/matt/.local/bin/omp`.
- **The terminal request works but Centaur fails:** close every local Centaur window, stop the background host as described in step 4, and relaunch. Record the exact error shown in Centaur and your `omp --version` output so we can investigate the integration.
- **The reply is unreadable:** record Centaur's error and the selected model. Centaur requires a structured response from omp; a successful terminal conversation alone does not verify that response format.

For native app and collaboration checks on the Air, continue with [Testing on NixOS](TESTING_ON_NIXOS.md).
