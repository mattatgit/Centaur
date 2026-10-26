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
7. Ask for two small app changes, such as a blue background followed by a green one. There should be no numbered revision badges on the canvas or project card, no version labels on earlier messages, and no routine numbered version announcements.
8. Ask “@centaur what did we change earlier?” The reply should describe the saved changes without changing the app. Then ask to go back to before the green background. The earlier source should return after its native check, and the green version should remain in history so it can be restored later. Reopen the project and repeat a history question to check persistence.
9. The chat header should read **Chat**, with the agent name and reported provider/model on the smaller grey line. Before the first agent request, “Model not reported yet” is expected. After a request, verify that the actual model appears in both windows; renaming the agent should update the name in that line. There should be no “Canvas” heading or idle “Try the app…” hint.

The automatic Linux test separately requires an actual client buffer and a mouse-input round trip through the canvas. It cannot establish how the physical GPU behaves or whether the app feels responsive on the Air.

## Two authors

Typography should be Inter in project cards, chat, buttons, fields, menus/dialogs and the example app, without installing Inter in NixOS. Existing app source inherits the preview runtime's default unless it explicitly selects another family. Check that larger headings and 12.5-point chat remain readable, the divider still resizes correctly, and no text is unexpectedly clipped. Shapes used as toolbar symbols may come from a fallback font.

Use the commands under “Two authors, one computer” in the README, with the same `--data-dir` in both terminals. Choose different author names. Keep the hosting window open.

With a fresh data directory, start both windows with `--demo`. Both should open the same single starter project. Make an app change, return to Projects in both windows, and reopen it: there should still be one project with the saved change. Restart both windows with the same directory and `--demo` and check that the project is reused. **New project** should still create a separate app intentionally. Older unwanted starter projects remain separate saved folders; do not delete them until you have checked which contains the work you want.

To connect the live agent, follow [Omp NixOS Setup](OMP_NIXOS_SETUP.md). Then try:

- Matt: “Keep the navigation minimal.”
- Saori: “All six sections must be easy to reach. @centaur, what do you suggest?”
- If the requests are compatible and the direction is clear, the agent should check/apply a small change without anyone clicking approval. A clarification question is appropriate if it needs more direction.
- Test a genuine conflict next: Matt asks for the shared screen to be solid blue with no colour switch, then Saori asks for that same screen to be solid red with no colour switch and mentions `@centaur`.
- The agent should explain the incompatible requirements and ask a focused question or propose a compromise. A compromise waits for **Agree to compromise** from Matt and Saori. One person's acceptance is insufficient; an unrelated third contributor should not be asked to agree.
- Repeat, but send another message while the agent is thinking or checking the candidate app. Its old result should not be applied.
- Reopen Centaur with a partly accepted conflict proposal. The previous acceptance should persist; the other affected author can complete the agreement. An unfinished proposal from the older approval-every-change version is cleared on upgrade; ask for that change again.

Record what the model misunderstood as well as the code result. Passing the coordination tests does not establish mediation quality.

## Graphics compatibility

The usual launch uses hardware acceleration. If the older GPU fails to initialize, try this diagnostic path:

```sh
QT_QUICK_BACKEND=software nix run 'github:mattatgit/Centaur?ref=codex/native-prototype' -- --demo
```

Software rendering is a fallback for investigation, not a claim of better performance. Note whether each path works and how typing/drawing feels.

## Resource measurements

With Centaur and its native app open, inspect both processes in the system monitor. Nix's installed executables may appear as `.centaur-wrapped` and `.centaur-preview-wrapped`. Note the Air's model, RAM, desktop session and GPU, then record idle CPU/RAM and how drawing, resizing and app relaunch feel. Test both the first cold launch and a subsequent warm launch.
