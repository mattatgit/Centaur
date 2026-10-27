# Testing on the MacBook Air running NixOS

Keep editing on the faster Mac. Use the Air as the native embedding and resource test machine.

## Install and update a precompiled package

Follow [Binary distribution](BINARY_DISTRIBUTION.md) for the one-time public-cache configuration, installation, future profile updates and proof that no compilation takes place. The cache and CI write credential must be activated first; successful build checks alone do not publish binaries.

After the cache is configured and the wanted commit is published, a one-off cache-only launch is:

```sh
nix --refresh run --max-jobs 0 --builders '' --option fallback false \
  'github:mattatgit/Centaur?ref=codex/native-prototype' -- --demo
```

This fails if the package cannot be substituted, rather than compiling on the Air. Nix chooses x86_64-linux on the Air and aarch64-linux on the ARM64 VM. No source checkout or ChatGPT installation is needed to run Centaur.

## What to try first

In Projects, create several distinct test projects and resize the window. Cards should tile left to right, from one column at narrow widths up to five on wide screens, with additional rows scrolling vertically and no horizontal scrolling. Check the compact heading, New project button and empty state at 360 logical pixels wide. Opening a project should still show the canvas/chat workspace at its existing minimum width.

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

The bottom-right chat footer shows Centaur's software version and build revision on the same line as “Chatting as…”. It should remain visible when narrowing the chat panel; the author/keyboard hint can elide and its full text is available on hover. `centaur --version` should report the same identifier. This is independent of the generated app's internal revision history.

Use the commands under “Two authors, one computer” in the README, with the same `--data-dir` in both terminals. Choose different author names. The background host survives closing the first window.

With a fresh data directory, start both windows with `--demo`. Both should open the same single starter project. Make an app change, return to Projects in both windows, and reopen it: there should still be one project with the saved change. Restart both windows with the same directory and `--demo` and check that the project is reused. **New project** should still create a separate app intentionally. Older unwanted starter projects remain separate saved folders; do not delete them until you have checked which contains the work you want.

To connect the live agent, follow [Omp NixOS Setup](OMP_NIXOS_SETUP.md). Then try:

- Matt: “Keep the navigation minimal.”
- Saori: “All six sections must be easy to reach. @centaur, what do you suggest?”
- If the requests are compatible and the direction is clear, the agent should check/apply a small change without anyone clicking approval. A clarification question is appropriate if it needs more direction.
- Test a genuine conflict next: Matt asks for the shared screen to be solid blue with no colour switch, then Saori asks for that same screen to be solid red with no colour switch and mentions `@centaur`.
- The agent should explain the incompatible requirements and ask a focused question or propose a compromise. A compromise waits for **Agree to compromise** from Matt and Saori. One person's acceptance is insufficient; an unrelated third contributor should not be asked to agree.
- Repeat, but send an explicit new agent direction while it is thinking or checking the candidate app. Stale work should be retried against the latest conversation; ordinary chat should continue without starving the request.
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

## Dialogue navigation and input modes

- Check Projects, Design Systems and Settings, including the compact sidebar on a narrow window. Compare SVG icon and label colours for default, pointer hover, keyboard focus and selection; primary buttons scale on hover, while the mode switch does not.
- Design Systems should show the original suitcase image and empty-state text. Import stays disabled.
- In a project, Interact keeps chat usable while clicks/typing reach the native app. Build shows only Draw, Comment and Undo in its bottom toolbar. Switch modes repeatedly and send human messages in each. Bot author labels read Centaur; @centaur mentions still address the agent.
- Toggle the grid, edit its size (2–64), colour and opacity in Settings, and restart. Defaults on a fresh data directory are off, 8 points, #BAE6FF and 50%. The grid must not take pointer input from the app.
- Open Settings from the chat author footer and return with Back to app. The native app should remain running. Check the reported executable/model, change your name and agent mention, and try the project actions. Names and grid preferences should survive a restart.
- Deploy should explain that deployment is not available yet; it must not publish or install the app.
- On a project card, hover the three-dot button: a rounded background should appear. Open it by click or keyboard and check Rename/Delete; clicking it must not open the project. Outside click and Escape dismiss the menu. Rename should preserve the app and conversation, update another local window and survive restart. Delete must first show the project's name in a confirmation; Cancel/Escape must keep it. Confirm deletion while another window has that project open: that window should return to Projects and stop its preview, leaving other projects intact.


## Collaboration across computers

Follow [LAN collaboration](LAN_COLLABORATION.md) for the two-machine setup and acceptance checklist. Automated network tests use temporary data and loopback TLS, including a background host. Linux `network-native-embedding` additionally verifies the received app renders and receives input; it does not prove that a particular VM address/firewall is reachable from the Air.
