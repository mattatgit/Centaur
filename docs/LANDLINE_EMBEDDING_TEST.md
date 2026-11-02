# Landline native embedding test

This is an isolated experiment before project import. It runs the real Rust/egui Landline client inside Centaur's private Wayland compositor. It does not convert Landline to QML or add agent editing of its Rust source.

## Source and package

- Landline: `mattatgit/landline`, `linux-nix` commit **`205fc1185335dc1c85b359af7673f6e5d7653222`**. Its original flake, Cargo lock and sources are retained through a pinned optional flake input.
- Active package: `packages.aarch64-linux.landline-embedding-test`. The Intel output is retained but its automated builds/testing are paused.
- Launcher: `centaur-landline-test`. Default Centaur installation/launch behaviour is unchanged. Landline is not a dependency of the default Centaur package.
- The package includes Centaur and references Landline's complete runtime, plus a Mesa software-rendering option. Each app uses the Mesa driver from its own pinned Nix runtime, avoiding incompatible libraries across the two builds. Landline's licence and source revision are included under `share/centaur-landline-test`.

The local source copy used for inspection is `build-imports/landline-linux-nix`, ignored by Centaur's Git repository. The distributable test uses the pinned public input, not that local folder.

## Isolation and limitations

The test opens a fresh temporary workshop containing one test project and an explanatory chat message. Centaur runs its test host in-process, not through the normal background host. Agent execution, invitations, project creation and deployment controls are disabled for this experiment. It does not use the installed Centaur profile, projects, conversation records, provider credentials or collaboration identities.

The child Landline process receives separate temporary `XDG_CONFIG_HOME`, `XDG_DATA_HOME` and `XDG_CACHE_HOME` directories. Its profile and Iroh key are therefore separate from normal Landline. These test records persist during Restart app within this workshop and are discarded when the test window closes normally. Temporary directories may need cleanup after a forced crash/power loss. The workshop is not a sandbox: the native app retains the desktop user's normal permissions, including device access if its controls are used.

Landline is launched directly, with no `App.qml` argument. Its Wayland display points to Centaur's private socket; inherited `DISPLAY` and `WAYLAND_SOCKET` are removed to prevent falling back to a standalone X11/desktop window. The canvas frame is **320 × 672 logical pixels**, respecting Landline's minimum size. Normal QML projects retain their existing 520 × 640 frame and margins. Frame/board layout and annotations follow the selected size.

Native readiness follows a compositor surface with actual buffer content, rather than depending on the Qt preview's `CENTAUR_READY` log marker. Child stdout and stderr are drained. Closing Centaur stops the native app before compositor teardown.

## Automated build and publication

[Landline embedding test](../.github/workflows/landline-embedding.yml) builds on a native ARM64 Linux runner only (updated 2 November 2026). It runs launcher checks, builds the pinned Landline client and Centaur (including Centaur's normal package tests), then requires an actual external-app buffer inside the compositor. A headless screenshot is uploaded for inspection; inspect it before handing the build to a tester. The automated external-app check establishes buffer receipt and process lifetime, **not correct visible composition, keyboard/pointer usability, microphone audio or agent source editing**.

The unchanged upstream Landline client is cached separately after its own package build/check phase succeeds, so integration-test fixes do not require compiling Rust again. This does not publish the Centaur test bundle or claim embedding works. Only after the ARM64 integration checks pass does that same runner publish the complete test closure to the existing public Centaur Cachix cache and verify a fresh download into an empty store. Both the normal and experimental workflows currently target ARM64 only. Do not ask a tester to install a revision before its full job, including publication verification, succeeds.

Distribution metadata names the `landline-embedding-test` package attribute and exact Centaur source commit. The default Centaur installable does not include this launcher. Use the experimental manifest's immutable `installable`, rather than the moving branch head, for the first test.

## Guided machine test

Machine-specific commands and results belong in **Centaur Cloud → Centaur Install**. Test on the ARM64 NixOS VM; the Air is no longer a test target. Verify cache trust and a successful corresponding publication before proceeding. No extra Cachix write credential is needed on a tester's machine.

Install into a separate profile, **not** the ordinary Centaur profile, with all builders disabled and normal signature checking required. Fill in the verified manifest's exact source revision:

```sh
nix --extra-experimental-features 'nix-command flakes' --refresh build \
  --no-link --profile "$HOME/.local/state/nix/profiles/centaur-landline-test" \
  --max-jobs 0 --builders '' --option fallback false --option require-sigs true \
  --extra-substituters 'https://mattatgit-centaur.cachix.org?priority=30' \
  'github:mattatgit/Centaur/FULL_VERIFIED_CENTAUR_COMMIT#landline-embedding-test'
```

Then, from a terminal in the graphical desktop:

```sh
"$HOME/.local/state/nix/profiles/centaur-landline-test/bin/centaur-landline-test"
```

If the default graphics path fails, capture the error first and try the explicitly packaged software-rendering mode as a separate diagnostic:

```sh
"$HOME/.local/state/nix/profiles/centaur-landline-test/bin/centaur-landline-test" --software
```

Do not repeatedly change desktop/EGL settings or compile on the test machine to work around a failed test. Share the launch output and screenshot for development investigation.

## Acceptance sequence

1. Confirm the temporary workshop says **Landline embedding test** and the full Landline UI appears **inside** the canvas, with no separate Landline desktop window or clipped bottom controls.
2. In Interact mode, open Landline's title menu and profile sheet. Edit the test display name, save and dismiss the sheet. This checks pointer, keyboard, focus and in-app overlays without needing another Landline peer or pressing push-to-talk.
3. Alternate typing in Centaur's chat and Landline's profile field. Input should reach the focused app only. Agent editing remains unavailable.
4. Switch to Build, draw/comment over the app, undo and return to Interact. Marks should remain aligned and the app should resume receiving input.
5. Resize Centaur smaller and larger. The test frame retains Landline's required logical dimensions and scales with the canvas; input and drawing remain aligned. Arbitrary resizing of Landline's own fixed-layout UI is not part of this milestone.
6. Use Settings → Restart app, then return to the workspace. Landline should remap once and retain its test profile during this workshop.
7. Close the test window. Confirm no Landline test process continues and the normal Centaur projects, agent and collaboration are still available. Relaunching the test starts a fresh workshop/profile.

Record machine, Centaur commit, Landline commit, default/software rendering, screenshot and any failed step. Microphone/audio, peer networking, imported multi-file editing/history and sharing Landline source are later milestones.
