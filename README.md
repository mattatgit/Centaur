# Centaur

A native workshop for families to build native apps together. One project is one Git repository and one app. A shared canvas and conversation are the workspace.

This is the first rough prototype. The interface is C++ / Qt Quick. On Linux, a nested Wayland compositor displays a **separate native app process** inside the canvas and forwards input to it.

## Run on NixOS

With Nix flakes enabled, from this repository:

```sh
nix run .
```

The first build downloads Qt and the compiler. Subsequent launches reuse the built package. To immediately open a starter project:

```sh
nix run . -- --demo
```

Centaur needs a graphical Linux session and its normal `XDG_RUNTIME_DIR`. It runs as your ordinary user; creating projects does not require rebuilding the operating system. Each window opens its own private Wayland socket, so Centaur can run inside an existing Wayland desktop or an X11 session.

## Try the prototype

1. Create a project. This makes a local Git repository with a working `App.qml`, initial checkpoint and README.
2. On Linux, use the starter app inside the canvas: add a task, tick a checkbox, open the menu and dialog.
3. Choose **Draw** to sketch, or **Comment** to drag an arrow towards a feature. Switch back to **Use app** to interact. Undo removes your last mark. Press Escape to return to the app.
4. Chat with another author. Mention **@centaur** when you want an agent response. You can change your name and the agent's name from the name button at the top right.
5. The agent can ask a question or propose an implementation. Each contributor since the last change accepts the proposal with **Agree & build**. New messages or drawings invalidate an outstanding proposal.
6. Once everyone accepts, Centaur checks the candidate QML in another process, saves a Git checkpoint and restarts the native preview. A candidate that fails its QML check leaves the existing app untouched.

The chat sidebar is resizable, starts at 430 logical pixels, and uses 12.5-point message text. There is no activity rail; decisions and progress appear in the chat.

## Two authors, one computer

The first collaboration transport is an OS-user-only local socket. Open two windows with the same data directory and choose different author names:

```sh
CENTAUR_AUTHOR=Matt nix run . -- --data-dir "$PWD/.centaur-data" --demo
```

In another terminal:

```sh
CENTAUR_AUTHOR=Saori nix run . -- --data-dir "$PWD/.centaur-data"
```

The first window hosts the shared session. Both windows see the same projects, conversation, marks, proposal and accepted app revision. Their in-app interaction state is independent. Keep the first window open; if it closes, reopen both windows to resume from disk.

This proves authored collaboration and coordination locally. Networking between computers, authenticated family membership and shared live app interaction are not implemented yet. Display names are prototype identities.

## Connect the agent

Centaur uses **oh-my-pi (`omp`)**, the same agent runtime used by Dialogue. Install it and sign in using its normal setup. Launch Centaur with `omp` on `PATH`, or supply its executable explicitly:

```sh
CENTAUR_AGENT=/path/to/omp nix run .
```

Optionally set `CENTAUR_MODEL` to an omp model identifier. No provider keys are stored in Centaur projects. If omp is unavailable or cannot authenticate, Centaur reports that in the chat; it does not substitute simulated agent replies.

For this experiment the agent receives the authored conversation, accepted decisions, current QML, revision-tagged drawing geometry and a canvas image captured when it is mentioned. It returns a clarification or a complete proposed `App.qml`. The coordinator owns file writes, validation, agreement and checkpoints. Omp runs without tools, project rules, skills or discovered extensions; it cannot edit the project directly through this integration.

This deliberately limits the first generated apps to Qt Quick `Item` / `Rectangle` roots with built-in modules. They can also run independently with `centaur-preview /path/to/App.qml`. Generating arbitrary native application frameworks and larger compiled projects comes later.

## Build and test

```sh
nix develop
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug
cmake --build build -j 4
ctest --test-dir build --output-on-failure
./build/centaur --demo
```

Or build and run the package checks in Nix's sandbox:

```sh
nix build -L
```

Tests cover project persistence and Git checkpoints, two local native clients exchanging authored messages, proposal quorum and invalidation, valid source application and rejection of broken QML. The UI smoke test loads both main views. Linux builds also run an embedding smoke test that starts a separate Qt Quick process and requires it to create a surface inside Centaur's compositor. These tests do not call a live model.

For the older MacBook Air running NixOS, see [the target-machine test guide](docs/TESTING_ON_NIXOS.md).

On a Linux machine without a graphical desktop, use:

```sh
mkdir -p /tmp/centaur-runtime
chmod 700 /tmp/centaur-runtime
XDG_RUNTIME_DIR=/tmp/centaur-runtime QT_QPA_PLATFORM=offscreen \
  QT_QUICK_BACKEND=software ./build/centaur --embedding-smoke-test
```

macOS builds support native interface and coordination development. The canvas clearly states that app embedding requires Linux; it does not simulate a live embedded preview.

## Modest hardware

- C++ and Qt Quick; no Chromium, browser server or JavaScript service runtime.
- One app process per open workspace and one agent request at a time per local host.
- Event-driven drawing, a virtualized recent-message list, bounded live drawing geometry, and no continuous canvas animation or visual effects.
- Model inference runs through the configured provider; no local language model is required.
- Hardware acceleration is the normal path. `QT_QUICK_BACKEND=software` provides a compatibility test path; it needs benchmarking on the actual target hardware.

We have not established a minimum RAM/CPU specification. Measure idle CPU, resident memory, drawing latency, preview responsiveness and rebuild time on the intended entry-level machine before claiming a hardware floor.

## Project data

The default data location is Qt's per-user application data directory (normally `~/.local/share/Centaur/Centaur` on Linux). `--data-dir` selects a different location. Each project is stored at `projects/<uuid>/`:

- `App.qml` and Git history: accepted native app source.
- `.centaur/state.json`: shared conversation state, marks, accepted decisions and pending proposal.
- `.centaur/conversation.jsonl`: full append-only conversation record; the UI keeps the most recent 250 messages in live state.
- `.centaur/context-*.png`: canvas images used as model context.
- `.centaur/previous.qml`: source before the last applied change.
- `.centaur/annotations-v*.json`: drawings preserved with the revision they describe. A new app revision starts with a clear canvas.

Back up the whole project folder, including `.centaur/`; collaboration data is intentionally excluded from the generated app's Git repository. Archive hides a project from the project view and keeps its files.

## Implementation map

- `src/workspace.*`: projects, persistence and app Git checkpoints.
- `src/session.*`: authoritative local collaboration host and the agreement/build coordinator.
- `src/agent.*`: omp invocation and structured proposals.
- `src/controller.*`: native UI bindings and preview lifecycle.
- `src/inkitem.*`: native freehand and arrow rendering/input.
- `qml/`: project view, canvas, chat and Linux Wayland compositor.
- `templates/App.qml`: the independently running native starter app.

Qt Wayland Compositor is offered under GPLv3 or a commercial Qt license; the project's distribution licensing decision is still open. See [Qt's module documentation](https://doc.qt.io/qt-6/qtwaylandcompositor-index.html).
