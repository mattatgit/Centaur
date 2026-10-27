# Current state

## Agreed direction

Centaur and the apps it produces are native. Target NixOS and modest hardware. One project represents one repository and one app. The two main views are projects and collaborative app building. The workspace contains a main canvas, a comfortably wide chat sidebar, Draw and Comment (Dialogue's Arrow behaviour). No activity rail. Start with Dialogue's restrained visual style and adapt it for families later. The default agent mention is @centaur and is configurable.

The agreed deployment direction is a standalone native app, beginning with **Install this app on this computer** on NixOS: its own launcher, persistent app data and an installed release that stays stable while authors continue editing. Family sharing and explicit release updates follow later; distributing an app does not itself synchronise family data. These features are not implemented yet. See [Architecture](ARCHITECTURE.md) for the deployment stages, runtime boundaries and font packaging considerations.

## First prototype

Focus on two experiments: a native app operating inside Centaur's frame, and an agent negotiating instructions from multiple authors. The intended complete loop is conversation → clarified direction → accepted change → native app revision inside the canvas.

Implemented as C++17 / Qt Quick 6.8+, with a separate Qt Quick client and a nested Wayland compositor on Linux. A macOS build is provided for native shell development, with an explicit Linux-only placeholder for embedding. Project state is stored locally, source versions use Git, and native windows connect over QLocalSocket to an authoritative background host; invited computers join individual projects over pinned TLS.

App edits and rewinds keep the same project identity. Starter opening (`--demo`) is resolved atomically by the shared host: reuse the most recently updated visible project, or create one only when the host has none. This fixes additional windows creating unwanted starter projects before their initial project list arrived. Existing project folders are retained; projects with matching names may contain different work.

Project cards form a responsive grid of one to five columns, sized against the scroll viewport with approximately 260 logical pixels as the minimum card width and 32-pixel gaps. Extra rows scroll vertically. The Project view allows windows down to 360 logical pixels wide, using the compact icon sidebar on narrow windows; the canvas/chat workspace retains its 1,000-pixel minimum. The empty state fits the same available width.

The agent adapter invokes omp without tools and expects a clarification or proposed QML source. Its stdin is redirected to `QProcess::nullDevice()` so OMP receives EOF before handling the argument/file prompt; leaving QProcess's default pipe open causes OMP startup to wait until Centaur's three-minute timeout. A regression test uses an executable that reads stdin to EOF before replying, including repeated requests on the same Agent.

Making a request is approval to carry it out. Compatible proposals are checked and applied automatically, without an approval click. Only a genuine conflict between active requirements pauses for agreement by the affected authors. The model must explicitly classify each proposal as `conflict: null` or provide a conflict reason and at least two distinct known authors. The coordinator validates that metadata and enforces agreement only for those authors. Other contributors do not have a veto merely because they chatted or drew something. New explicit agent directions and sketches invalidate pending work, which is retried against the latest conversation. Ordinary chat can continue without starving the agent; discussion of a pending conflict still invalidates its agreements. Old unfinished proposals made under the previous everyone-agrees policy are cleared on upgrade rather than silently applied. Model conflict detection and mediation quality still need evaluation with family conversations.

Revision counters remain internal for synchronization, drawing context and checkpoints. The canvas, project cards, old-message labels and routine completion messages no longer display numbered app revisions; old generated revision announcements are also rendered without their numbers. The agent receives the 100 most recent Git checkpoint descriptions/dates and can answer history questions or return a structured `restore` request. The coordinator retrieves the exact source from a reachable checkpoint in that project's Git history, validates it, and saves it as a new checkpoint. It never resets Git or substitutes model-generated source for a rewind, and conflicts still require agreement by the affected authors. All saved Git history is retained beyond the bounded model context.

The workspace omits the “Canvas” label and idle “Try the app…” hint. Its chat header is “Chat”, with the configurable agent name and last reported model in smaller grey text below. Omp runs in JSON print mode; Centaur incrementally consumes its event stream, retains only the final assistant text for the existing response contract, and reads provider/model metadata from assistant events. Model metadata is saved per project and shared between windows; no model name is guessed before the first report. Stderr and raw event transcripts stay out of shared chat. Plain JSON replies remain supported for explicit test doubles/wrappers.

A small Centaur software version appears at the bottom right of the chat footer, on the same line as the author/keyboard hint. It includes the source revision in Nix builds (for example, `v0.1.1+abcdef0`) so screenshots identify the running build. Modified Nix checkouts are marked dirty where revision metadata is available; direct CMake builds default to `+dev` and can set `CENTAUR_BUILD_ID`. The same version is returned by `centaur --version`. This identifies Centaur itself, not the project's internal app revision.

Centaur and the separate native example/preview/checker use bundled Inter 4.1 as their default font, with Regular, SemiBold and Bold available without installing fonts on the host. Sizes and weights are retained. Other scripts and symbols can use system fallback fonts. Explicit font choices in saved app QML are respected. The licence and upstream asset hashes are included in the repository and release package.

Collaboration now supports project invitations across reachable local-network computers, authenticated identities, encrypted transport, cached local previews and reconnects. A separate background host survives UI closure. Only the host needs OMP. [LAN collaboration](LAN_COLLABORATION.md) records the user flow, setup, recovery and limitations. Native QML remains trusted code; internet access, accounts and generated-app data synchronisation are not implemented.

## Deliberate boundaries

- The initial app framework is Qt Quick; arbitrary native frameworks are not yet supported.
- Local display names remain selectable. Remote participants have stable credentials and host-assigned names; no cloud accounts yet.
- Source, conversation and marks are shared; each window has its own live app interaction state.
- No sandbox around generated native QML yet. Run trusted local projects as an ordinary user.
- Canvas fitting is fixed to one app frame. Infinite panning, frame resizing and a dedicated history browser are follow-up work; history questions and rewinds currently go through chat.
- Test doubles validate coordination; they do not establish that the live model resolves disagreements well.

## Next evidence needed

The current interactive Linux test environment is an ARM64 NixOS VM under UTM on an Apple Silicon Mac mini. The user confirmed that native embedding/input and a live authenticated omp request through Centaur work after the stdin EOF fix. Next, test compatible requests applying automatically and real conflicts requiring only the affected authors' agreement. `docs/OMP_NIXOS_SETUP.md` covers updating and launching with an existing omp binary.

On the NixOS Air, manually exercise focus, typing, checkbox input, menus/dialogs, relaunch, drawing overlays and app scaling. Then configure a real omp session and test compatible requests, contradictory requirements, mid-run corrections, and reopening a settled decision. Measure resources on target hardware.

## Validation and target machine — 22 October 2026

The native macOS interface has been compiled, rendered and visually inspected. Both main views load without QML warnings. Coordination tests and the packaged Nix build pass on aarch64-darwin. Tests use explicit agent doubles and do not call a live provider.

The x86_64-linux Nix package and all three Linux suites pass in GitHub Actions at code commit `edd4733`: core coordination, both UI views, and native embedding. The embedding test verifies that a separate process supplies an actual rendered Wayland buffer and receives a mouse click through the canvas; it also exits cleanly. The lifecycle fix releases client views before terminating the client and before QML teardown. [Passing Linux run](https://github.com/mattatgit/Centaur/actions/runs/39709315047).

The target test machine is an older MacBook Air running NixOS. Development stays on the faster Mac; the Air is for Linux embedding, interaction and resource measurements. `docs/TESTING_ON_NIXOS.md` gives the prototype-branch launch command and test procedure. Linux CI runs the actual native surface and mouse-input smoke test; physical GPU behaviour and live model negotiation still need the Air pass.

## Dialogue UI integration — 27 October 2026

The native shell now follows the Dialogue management sidebar and workspace chrome. Projects, Design Systems and Settings use the original 32-pixel SVG geometry, matching default, hover, focus and selected colours. The sidebar is 216 pixels wide, or a 72-pixel icon rail on narrow management windows. As in Dialogue, the workspace uses the full window width; its icon-only home control and Projects → project breadcrumb return to the gallery. Inter remains Centaur's typeface.

The workspace has a two-position Interact/Build switch. Interact passes canvas input to the native app and keeps chat available for conversation between people and agent mentions. Build exposes Draw, Comment and Undo; Comment keeps Centaur's arrow annotation behaviour. The canvas/chat split keeps its existing 430-pixel initial chat width and resizable divider. Author labels display the default bot as Centaur rather than @centaur; mentions still use @centaur.

Grid preferences match Dialogue: initially off, size 8 (range 2–64), colour #BAE6FF and opacity 50% (0–100%). The original SVG grid button toggles a native, non-interactive overlay aligned to the app frame. Settings change grid colour, size and opacity. Preferences and the display name persist in preferences.ini under the selected data directory, separately from project source/history. Agent login and model selection remain managed by OMP; Settings shows the host's executable availability and the selected project's reported model, and allows renaming its agent. Clicking the chat author footer opens Settings without destroying the native preview; Back to app returns to it. Project repository, restart and archive actions are available there too.

Design Systems reproduces Dialogue's empty-state copy and original suitcase PNG. Import remains unavailable. Deploy is a styled placeholder explaining that deployment is not available yet; it does not publish or install anything. The user approved the original PNG and temporary icons: Build reuses Dialogue's Comment state SVGs, while Draw and Undo keep their previous text glyphs until replacement SVGs arrive. No missing SVG artwork was redrawn. Asset provenance and the original Dialogue licence are in assets/dialogue/.

Checks exercise all four views, chat visibility and pointer routing in both modes, preferences persistence/clamping, native SVG masking, and grid alignment without intercepting app input. Linux also retains the native Wayland buffer/input smoke test.

Project cards have a small original Dialogue three-dot menu with Rename and Delete. Rename changes only the existing project's display name; source, conversation and history keep their identity. Delete requires a separate confirmation and removes the project from all local windows, stopping any open preview. The host refuses deletion during an agent request or app validation. Deleted folders move atomically to `trash/<project-id>` under the data directory for manual recovery; no restore UI is provided yet. Archive in Settings retains its existing behaviour.


## Local-network collaboration — 27 October 2026

Version 0.2 adds Invite/Join project, single-use 20-minute invitations, private membership storage, project-scoped TLS snapshots, host-enforced permissions, sequence/acknowledgement handling, persistent queued agent requests, offline connection status/draft retention, Leave and Stop sharing. No new SVG artwork is introduced. The native preview loads synced accepted source from a separate guest cache; shared cards do not become duplicate local projects.

Automated checks cover separate data directories, guest-originated agent changes, authored drawing/chat, conflict identity enforcement, cross-project denial, used-invitation rejection, certificate pin mismatch, duplicate commands, reconnect with the same member identity, and a detached host completing requests after its UI closes. Linux additionally checks that an app delivered over TLS from a separate background host renders in a guest compositor and receives mouse input. Physical VM/Air connectivity and live OMP remain manual acceptance work.
