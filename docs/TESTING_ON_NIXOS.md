# Testing on the MacBook Air running NixOS

Keep editing on the faster Mac. Use the Air as the native embedding and resource test machine. The prototype source is small; Nix normally substitutes the Qt dependencies from its binary caches instead of compiling Qt on the Air.

## First launch

From a terminal in the Air's graphical desktop:

```sh
nix run 'github:mattatgit/Centaur?ref=codex/native-prototype' -- --demo
```

If flakes are not enabled in the current Nix configuration:

```sh
nix --extra-experimental-features 'nix-command flakes' \
  run 'github:mattatgit/Centaur?ref=codex/native-prototype' -- --demo
```

This fetches the prototype branch and builds/tests Centaur before opening it. The first download will take longer than later launches. No source checkout or ChatGPT installation is needed just to run Centaur.

For updates, run the same command with `--refresh` immediately after `nix`:

```sh
nix --refresh run 'github:mattatgit/Centaur?ref=codex/native-prototype' -- --demo
```

## What to try first

1. The frame should show the working **Our everyday** native app. Add a task and tick a checkbox.
2. Switch focus between the task field and Centaur's chat field. Typing should go to the selected field.
3. Open the app's **•••** menu and its About dialog. Dismiss them and return to the canvas.
4. Draw over and outside the app, add a Comment arrow, undo a mark, then switch back to Use app. The app should still receive clicks normally.
5. Resize Centaur and drag the divider beside the chat. Check that the app and marks stay aligned and input still lands where expected.
6. Restart the app and return to Projects. Reopen it; messages, source and marks should persist.

The automatic Linux test separately requires an actual client buffer and a mouse-input round trip through the canvas. It cannot establish how the physical GPU behaves or whether the app feels responsive on the Air.

## Two authors

Use the commands under “Two authors, one computer” in the README, with the same `--data-dir` in both terminals. Choose different author names. Keep the hosting window open.

To connect the live agent, follow [Omp NixOS Setup](OMP_NIXOS_SETUP.md). Then try:

- Matt: “Keep the navigation minimal.”
- Saori: “All six sections must be easy to reach. @centaur, what do you suggest?”
- Continue the discussion until the direction is clear, then ask for a proposal.
- Accept it in each author's window. The app should change only once everyone has accepted.
- Repeat, but send another message while the agent is thinking. Its old result should not be applied.

Record what the model misunderstood as well as the code result. Passing the coordination tests does not establish mediation quality.

## Graphics compatibility

The usual launch uses hardware acceleration. If the older GPU fails to initialize, try this diagnostic path:

```sh
QT_QUICK_BACKEND=software nix run 'github:mattatgit/Centaur?ref=codex/native-prototype' -- --demo
```

Software rendering is a fallback for investigation, not a claim of better performance. Note whether each path works and how typing/drawing feels.

## Resource measurements

With Centaur and its native app open, inspect both processes in the system monitor. Nix's installed executables may appear as `.centaur-wrapped` and `.centaur-preview-wrapped`. Note the Air's model, RAM, desktop session and GPU, then record idle CPU/RAM and how drawing, resizing and app relaunch feel. Test both the first cold launch and a subsequent warm launch.
