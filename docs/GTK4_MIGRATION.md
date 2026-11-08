# GTK4 migration and embedding experiment

Agreed direction, 5 November 2026: both Centaur and generated apps use GTK4. Casilda is a candidate for Linux embedding, **not an approved production dependency**. Native macOS embedding remains unresolved. GTK4 does not prescribe libadwaita or Centaur's visual identity.

## Preserved baseline and branch

- Working Qt branch: **`codex/native-prototype`**, retained at `3d24d11e959c1c6ec8c16df5b1c3e4bd7183e450` when migration began.
- Independent Landline VM acceptance build: **`08d166a5acb994f38fb5171ad3c6555c6137fbf0#landline-embedding-test`**. Continue that experiment independently; it is Rust/egui inside the Qt host, not this GTK4 test.
- Migration branch: **`codex/gtk4-migration`**. The first isolated experiment is `c5fbcd6799d3c75b3f9242f1553d1389ffaed9ba`.
- Active package: `packages.aarch64-linux.gtk4-embedding-test`; launcher `centaur-gtk4-test`. It contains a GTK4 host and a separately running GTK4 interaction fixture, **not the migrated Centaur product**. The branch's default package remains the Qt baseline until integration is ready.
- Current machine: ARM64 NixOS in UTM on the Mac mini. Do not build/install for the Air. Establish the remote client's environment before adding a target.

The migration branch does not update the Qt branch or replace any installed profile. GTK experiment builds do not compile Centaur's Qt package or Landline. The normal Qt build workflow is limited to the Qt branch; the GTK experiment has its own ARM64 workflow. Documentation-only commits do not start app builds.

## Phase 1: prove the embedding boundary

`gtk4/embedding/host.py` creates a minimal GTK4 host. `backend.py` contains the replaceable backend boundary and Casilda adapter; the fixture's GTK widgets and actions live in `probe.py`. Python/PyGObject is used for this bounded experiment, not selected as the production migration language.

The adapter creates Casilda without a public display socket and passes a connected Wayland FD to the child. It forces GTK's Wayland backend and removes inherited desktop display addresses. The child uses fresh temporary config/data/cache directories. A normal close or SIGTERM stops/reaps the app process group before disposing the compositor and temporary files. Restart stops the prior process before starting another. This is process/data isolation, not an execution sandbox; the app has the user's normal permissions.

The test opens no Centaur projects, collaboration identities or OMP credentials and never calls the ordinary update helper. The host's extra text field is for focus/clipboard testing, not a replacement chat implementation. The canvas has no extra app frame. Phase 2 will define the final centred presentation, clipping and subtle shadow.

### Pinned candidate and known limitations

The first candidate used the original lock's **Casilda 1.2.2**, GTK **4.22.4** and wlroots **0.20.2**. The newer evaluation below pins a separate package set; it does not upgrade the Qt/Landline inputs. Use the runtime versions recorded by the corresponding test, not the original baseline versions.

Upstream's [1.6 release source and changelog](https://gitlab.gnome.org/jpu/casilda/-/blob/1.6.0/CHANGELOG.md) introduce host clipboard/drag-and-drop integration and popup/focus fixes. Its [build definition](https://gitlab.gnome.org/jpu/casilda/-/blob/1.6.0/meson.build) requires GTK 4.24, unavailable in the initially inspected main/pinned Nix package sets. The newer evaluation below obtains a coherent newer stack through a separate input. Do not silently upgrade the Qt baseline, lower the upstream GTK requirement or claim 1.2.2 provides those fixes. Options after baseline evidence: package a compatible newer GTK/Casilda pair as an isolated dependency, backport carefully with tests, or evaluate another embedding backend.

Casilda's inspected public API provides socket/client launching and GtkScrollable behaviour, not an app-dimension/zoom/window-management API. Its virtual output responds to widget allocation. Centaur must keep logical dimensions separate from presentation and validate transformed input and popups; adding a zoom dropdown alone is insufficient. A client can request transient or additional windows; main-window centring, popup extents, multi-window handling and clipping need explicit tests. A successful first render cannot approve the dependency.

### Automated evidence

[GTK4 embedding experiment workflow](../.github/workflows/gtk4-embedding.yml) builds only the ARM64 experiment. The current checker uses a disposable native Wayland/Sway display, with another Wayland child inside Casilda. Earlier baseline runs used Xvfb; the X11 driver remains for comparison. It requires the child's coloured marker in a screenshot of the host window; verifies separate PID/private display, click, keyboard/text, scrolling, popup, modal dialog, host/client focus, unchanged app dimensions on host resize, restart and child shutdown. It records both directions of clipboard transfer separately. The newer candidate requires both to pass; the initial baseline only recorded the known failure. `casilda_approved` remains false.

Evidence artifacts contain `embedded.png`, host/client JSON and `summary.json`. Only passing rendering/interaction, clipboard and lifecycle checks may publish this isolated test package to Cachix; publication verifies the full signed closure in an empty store with no builders. Publishing the experiment is not approving Casilda or claiming full Phase 1 acceptance. Local macOS checks establish Python/process isolation, workflow syntax and Nix evaluation, not GTK/Wayland rendering.

### VM acceptance gate

Guided installation and results belong in **Centaur Cloud → Centaur Install**. Use a separate `centaur-gtk4-test` profile only after the ARM64 job and signed publication succeed. Do not replace the regular Centaur profile or the separate Landline test profile. Use the exact successful manifest revision, not a moving branch head.

Record the machine, source revision, GTK/Casilda versions, desktop scale and default/software renderer. Inspect the screenshot and test:

1. Native app appears inside the host, with no separate desktop window or extra surrounding box; app controls remain reachable.
2. Click the button; type/edit/select text, including ordinary keyboard shortcuts. Scroll the list with mouse and touchpad where available.
3. Open the menu popup, choose its action, open the modal dialog and dismiss with Escape. Check focus returns correctly; check edge-positioned popups and repeated opening.
4. Alternate typing in the host field and app field. Copy/paste host→app and app→host; record failures. Test external desktop clipboard separately in the actual Wayland session.
5. Resize the host smaller/larger and check app dimensions, input, clipping and focus. This does not yet test preview zoom.
6. Restart repeatedly, then close. Confirm no orphan or duplicate app process. Relaunch creates a fresh temporary environment. Check failed startup/child exit produces a recoverable status.
7. Check keyboard layout/IME, display scaling, graphics resource use and multi-window behaviour on the VM. CI's headless/software-rendering result does not establish the VM's real desktop, input-method and GPU behaviour.

**Gate:** document limitations before proceeding with full integration. The initial candidate failed clipboard/lifecycle checks. The patched newer candidate passed the tested VM functionality below; this is evidence for continuing the experiment, not approval to replace production Qt Centaur.

## First ARM64 result (5 November 2026)

[Run 41955179810](https://github.com/mattatgit/Centaur/actions/runs/41955179810), source `704b5dd11e472a88dc843281aec81855922f9790`, built successfully and ran the native app in the disposable Linux display. I inspected the screenshot: the separate GTK4 app is visible centred inside the GTK4 host, with its entry/buttons/scrollable list, and no extra preview frame. The automated checker passed rendering/private display, pointer/keyboard/text, scrolling, popup action, modal dialog, host/client focus and host resizing without changing app dimensions.

**Rejected for adoption in this tested form:** clipboard transfer failed in both directions. At Restart app, the host aborted with wlroots' `surface_handle_resource_destroy` assertion that `surface->events.commit.listener_list` must be empty. The subsequently launched child could not initialise its display because the compositor had died. This is an observed Casilda/wlroots lifecycle failure, not established evidence that a newer version fixes it. The test correctly failed; no GTK test package was published. Screenshot/summary/host-state evidence is artifact `13382891642`. A later diagnostic change also retains pre-restart client state and requires a clean host exit.

Do not ask the owner to install this failed candidate or replace the working Qt/Landline test. Phase 1 has demonstrated basic feasibility but **has not passed the suitability gate**. Next evaluate the lifecycle failure with upstream fixes/a compatible newer GTK–Casilda pair; rerun these checks and require both clipboard directions and clean restart/shutdown before adopting it. If these cannot be met, evaluate another embedding backend. Phase 2/3 integration remains gated on that outcome.

## Newer candidate: native Wayland checks passed (5 November 2026)

The newer candidate uses **Casilda 1.6.0 with two experimental Centaur patches** (package version `1.6.0-centaur2`), **GTK 4.24.0**, GLib **2.90.0** and Pango **1.58.2**. The GTK stack is isolated through the additional `gtk-nixpkgs` input at Nixpkgs `b0cafddb6da84ccdbe4debc8f2779c287bcff9a8` (staging-next snapshot). The original `nixpkgs` and Landline locked inputs were compared and are unchanged. No upstream version requirement is lowered.

Casilda's upstream 1.6.0 archive is content-pinned with `sha256-1Iq0RKte56gg69MRlEhfu5aWc+Vl7HgopS7RGIrf59w=`. It is compiled against the matching GTK stack with explicit DRM/Pixman/X11 dependencies. The GTK stack is downloaded as precompiled dependencies; no Intel build is involved.

The first newer build (`3ad9ebe`, run 41956442483) succeeded, then encountered a missing D-Bus test configuration. `f316a94` realises that configuration explicitly. Its X11-host follow-up rendered and exited cleanly but failed capitalisation: “Embedded input” arrived as “embedded input”. The uppercase requirement was retained.

The disposable native Wayland driver uses Sway, grim and a small CI-only input-seat fixture. The fixture keeps one pointer, one keyboard and one fixed US keymap throughout the test, avoiding input-less headless seats and per-command virtual keymap changes. Host decorations are disabled only in CI to keep coordinate origins unambiguous; normal VM windows retain their decorations. This does not touch the user's desktop.

Two patches remain local to this optional Casilda derivation:

- [Initial keymap](../packaging/patches/casilda-initial-keymap.patch): load the existing host keyboard map before nested-client focus, rather than waiting for a future layout-change notification. This restored letters on the fixed-layout Wayland test seat.
- [Ordered event state](../packaging/patches/casilda-key-event-state.patch): use the current key event's modifier snapshot and advance wlroots keyboard state in event order. Reading the device's latest global state could observe a later queued event and lose Shift/Control. This addresses the observed capitalisation and shortcut failure; it is not an upstream-approved patch.

**Automated pass:** source **`a02d0b8751f7a779d73e5316555c1a102631efa6`**, [ARM64 run 41959595774](https://github.com/mattatgit/Centaur/actions/runs/41959595774). The native Wayland host and separate native Wayland app passed screenshot/pointer/keyboard/capitalisation/text, scrolling, popup action, modal dialog, host/client focus, unchanged app dimensions on host resize, **both clipboard directions**, three restarts with rendering/input afterwards, normal host exit (0), and child shutdown. I inspected the screenshot: the GTK4 app is visible centred inside the host without an extra preview frame. Evidence artifact: `13384398488` (`summary.json`, screenshot, host/client state and compositor log).

The full ARM64 job succeeded, including signed-cache publication and a download of all **303 runtime paths** into an empty store with normal signature verification and builders disabled. Distribution artifact `13384752639` records the exact installable `github:mattatgit/Centaur/a02d0b8751f7a779d73e5316555c1a102631efa6#gtk4-embedding-test` and package `/nix/store/86d89zzxxpapbyi1jp88zh2jvvgi82l7-centaur-gtk4-embedding-test-0.1.0`. Use a separate `centaur-gtk4-test` profile in Centaur Install. First launch with `GSK_RENDERER=cairo` to match the verified software-rendering path; assess the default renderer separately after that baseline works. Casilda remains experimental and `casilda_approved` remains false for production adoption; the tested VM acceptance scope is recorded below. The X11 path has not been revalidated with the patched candidate; this pass establishes the native Wayland/software-rendering path. Remaining checks after the VM result below include IME/alternative layouts, Num Lock and fractional desktop scaling. Default/hardware rendering remains separate from the verified Cairo path. No zoom controls or full product migration are implemented by this result.

## ARM64 UTM VM hands-on acceptance (5 November 2026)

Owner-reported hands-on results from **Centaur Install**, on the **ARM64 NixOS VM in UTM**, using immutable source [`a02d0b8751f7a779d73e5316555c1a102631efa6`](https://github.com/mattatgit/Centaur/commit/a02d0b8751f7a779d73e5316555c1a102631efa6) with **`GSK_RENDERER=cairo`**. This is the minimal isolated GTK4/Casilda embedding experiment, not full-product acceptance.

**Passed:**

- Embedded GTK4 sample display; clicks/buttons, scrolling, popups and modal dialog.
- Text input and focus; Shift+Arrow selection, Caps Lock and Ctrl+A.
- Clipboard in both directions between embedded and host fields, and between the embedded app and a KDE editor.
- Popup positioning near the window edge; host resize functionality and continued interaction.
- Three repeated restarts; close/relaunch with fresh temporary data; clean process exit (`pgrep` produced no output).

**Observed issue:** the sample app stays at a fixed position when the host window resizes instead of remaining centred. Resize functionality passed; centred placement remains unresolved.

**Not tested:** alternative keyboard layout/IME, Num Lock and fractional scaling. These findings establish only the tested VM/software-rendering behaviour; they do not establish full Phase 1 coverage or approve Casilda for production. The default renderer was not assessed by this run.

**Scope preserved:** Qt Centaur and other profiles, OMP, projects and credentials were not altered. No Air testing was performed.

## Phase 2: independent preview viewport

The reusable viewport owns actual app dimensions, zoom, placement, clipping and pan offsets. The backend owns native surfaces, display/input delivery and lifecycle. Keep Casilda-specific objects out of application/project logic.

Provide **50%, 75%, 100%, 125%, 150% and Fit**, default **100%**. Fit changes presentation only. The app is centred directly on the canvas, with no visible frame; a subtle shadow is permitted. A small/large app keeps its logical resolution and responsive layout when zoom changes. Host allocation, desktop DPI and preview zoom are independent inputs. Provide panning/scrolling for oversized previews and stable zoom anchoring.

Test pointer-coordinate mapping, click/drag, selection, keyboard focus, scrolling, popups, dialogs and app interaction at every zoom and after host resizing. Overlays/grid/captured agent context must share the same transform and remain aligned. Clip preview content appropriately while retaining usable popup/dialog behaviour. Reuse these behavioural tests for future embedding backends. No zoom controls are implemented by Phase 1.

### Phase 2 native ARM64 checks passed (5 November 2026)

`6154f42` adds `viewport_model.py` (toolkit-independent app dimensions/zoom/pan geometry) and `viewport.py` (GTK widget allocation/snapshot/input transform). The compositor has a fixed logical stage with popup padding; host resize changes the outer transform instead of relying on Casilda to reposition an existing toplevel. The app remains centred at zero pan. Explicit zoom levels are 50/75/100/125/150%, default 100%, plus Fit; Fit recomputes on host resize. Middle-button drag pans an oversized preview and Centre resets pan. Zoom uses a viewport-centre anchor. GTK receives the same child allocation transform used for rendering and input; app dimensions stay fixed. The preview is clipped to the canvas with a subtle content shadow and no added frame.

**Automated pass:** immutable source **`90dad3aa23ce341e4aa2bc1af1ace05272798ca9`**, [ARM64 run 41965950586](https://github.com/mattatgit/Centaur/actions/runs/41965950586), evidence artifact `13388105009`. The native Wayland/Cairo run checks actual green-marker pixels against the expected composition after host resize and at every scale, not just reported geometry. All six modes passed button input, text/keyboard focus, select-all selection, continuous left-button slider dragging, scrolling, popup actions and modal dialogs. The oversized 125/150% cases also passed middle-button panning. Fit recomputed and recentred after another host resize. App dimensions remained **460 × 600 logical pixels** throughout. Both clipboard directions, three restarts with input/rendering, normal host exit and child shutdown passed. Screenshots at 50%, 150% and Fit were inspected.

Signed-cache publication also succeeded. Distribution artifact `13387338442` records `github:mattatgit/Centaur/90dad3aa23ce341e4aa2bc1af1ace05272798ca9#gtk4-embedding-test`, package `/nix/store/mhkjvb5pqmxwp5nn6qlbxry7bx2ypjy7-centaur-gtk4-embedding-test-0.1.0` and a successful empty-store download/signature verification of all **303 runtime paths**, with builders disabled.

Six local tests passed (four viewport geometry tests plus two backend/lifecycle tests), along with Python compilation, workflow lint and shell checks. The test seat now sends correctly normalised Wayland wheel steps and real pointer motion during drags; Sway cursor warps did not produce drag-motion delivery. The app fixture includes a slider and reports native selection bounds so these checks exercise actual interaction.

### Phase 2 ARM64 UTM VM hands-on acceptance (5 November 2026)

Owner-reported **hands-on acceptance of the isolated viewport**, from **Centaur Install**, on **ARM64 NixOS (KDE) in UTM**. Tested the precompiled isolated `gtk4-embedding-test` at immutable source [`90dad3aa23ce341e4aa2bc1af1ace05272798ca9`](https://github.com/mattatgit/Centaur/commit/90dad3aa23ce341e4aa2bc1af1ace05272798ca9), using the separate test profile with **`GSK_RENDERER=cairo`**. These results are separate from the earlier `a02d0b8` baseline above.

**Passed:**

- At **100%**, the sample stays centred throughout host resizing, addressing the fixed-position issue observed in the earlier baseline.
- **50%, 75%, 100%, 125% and 150%** zoom all preserve the sample's internal layout.
- **Fit** responds to host resizing.
- At **150%**, middle-button panning reveals clipped regions; **Centre** resets the position while keeping **150%** zoom.
- At **150%**, buttons work, and the slider follows the pointer normally until dragged too far beyond an endpoint (see the issue below).
- At **150%**, keyboard typing and **Ctrl+A** work; scrolling works.
- At **150%**, the popup is correctly placed and its action can be selected.
- At **150%**, the modal dialog appears; **Escape** dismisses it and its background shadow disappears completely.
- At **150%**, clipboard transfer works in both directions: embedded app → host and host → embedded app.
- **Restart app** retains **150%** zoom and the restarted app continues responding to input.
- Clean shutdown: `pgrep -af 'centaur-gtk4-test|gtk4-sample'` produced **no output**.

**Observed issue — slider drag disengages beyond an endpoint:** dragging the pointer too far beyond a slider endpoint disengages the drag. Returning toward the middle while keeping the mouse button held does not resume dragging. Reproduced at **both 150% and 100%**, so the observation is not confined to a zoomed viewport. The automated continuous-drag pass above does not establish this endpoint/return behaviour.

**Visual observation:** the modal dialog's background shadow looks unusual. Dismissal and complete shadow removal passed; the appearance is recorded for visual review.

**Not tested in this hands-on run:** panning specifically at **125%**, alternative keyboard layout/IME, Num Lock, fractional desktop scaling, default/GPU rendering, native macOS embedding or production migration. The 125% pan result above is automated evidence only. Native CI uses one sample app and a disposable fixed-US-layout display; arbitrary generated apps remain outside this result. Overlays/grid/agent context and the full GTK Centaur shell are not yet integrated.

**Acceptance boundary:** this records the tested isolated viewport's hands-on behaviour, with the slider issue still open. It is **not full Centaur acceptance, approval of a Qt replacement or approval of Casilda for production**. Normal Qt Centaur, Landline and OMP were unchanged; no Air, production-package, credential or project changes were part of this acceptance. The earlier `a02d0b8` findings remain preserved separately.

## Phase 3: incremental Centaur integration

| Existing boundary | Reuse/migration plan |
| --- | --- |
| Host/session coordinator, projects/history and agreement | Preserve authoritative writer, request queue, conflict policy, checkpoints and data identity. Much of `src/session.*`, `workspace.*` and related logic uses QtCore; do not mistake non-visual Qt code for toolkit-free code. A temporary QtCore host service behind the existing newline-JSON local socket is an option while the GTK shell is built. Decide the final host port separately. |
| Shared chat, invitations and networking | Keep protocol/authentication, host-owned authorship, certificate pinning, Iroh transport, reconnect and credentials on the host. `networking/` is already Rust and can remain a separate helper. Reuse network/coordination tests. |
| OMP | Preserve authentication/provider paths and negotiation behaviour. Separate the GTK generation response/schema and validation from the existing QML adapter before accepting GTK source. |
| App format, checks, history and distribution | Define a versioned GTK project contract with source/assets and a separate-process validator/runner. Preserve existing Qt projects; explicit migration is required. Do not feed GTK proposals to the QML checker or distribute only one file when assets/modules are required. |
| GTK shell | Move project management/chat/controls incrementally, with regression checks against the preserved Qt behaviour. Continue keeping chat visible in Interact and Build. |
| Design systems | Separate app behaviour/content from GTK presentation. Plan reusable GTK widgets/templates, CSS, design tokens, component conventions, layout rules and versioned project selection. GtkBuilder/Blueprint and language bindings remain choices to evaluate; do not build a full library/editor yet. |

Run existing core, network and Iroh regressions when changing those boundaries; retain the Qt UI/embedding suites on the preserved implementation as comparison evidence. New GTK tests must establish equivalent outcomes, including stale/failed generation recovery and multi-user collaboration. GTK4 does not resolve native macOS embedding; do not claim platform parity.


### Phase 3 development frontend and GTK app path

The migration branch now implements a native GTK4 shell with project cards and confirmed deletion, navigation, chat, Interact/Build, drawing/comment arrows/Undo, grid controls and the tested viewport. It uses the original Centaur/Dialogue SVG assets, approved Design Systems PNG, and bundled Inter/Inter Tight. Chat stays visible in both modes. No final design-system library or deploy flow is implemented.

A temporary newline-JSON C++ bridge reuses Controller/Session/SharedProject, preserving project coordination, OMP requests, conflict agreements, Git checkpoints, TLS/pinning, invitations, reconnect/outbox and Iroh. The GTK package builds only that retained service layer and its checker/tests, excluding the Qt frontend and Qt Wayland compositor. Qt libraries remain service dependencies; a complete Qt removal is not claimed. Service/transport source and Cargo.lock are content-keyed, and verified service closures are cached after their regressions pass, so GTK-only fixes can reuse them.

New projects use the typed `App.gtk.json` bundle, with separate Python behaviour, GtkBuilder layout and GTK CSS. GTK proposals use a separate response field and checker. The existing coordinator validates before committing, rejects mismatched formats, leaves the current app intact on errors, and restores exact saved bundles. Compatible requests apply without an additional author approval; only real conflicting requirements require the affected authors' agreement. Guests receive the complete authenticated bundle and run their own GTK preview. Older clients must advertise GTK support before joining these projects. See [the project contract and acceptance boundary](GTK4_PROJECT_FORMAT.md).

The launcher is `centaur-gtk4`, package `gtk4-preview`, default data directory `~/.local/share/Centaur/GTK4`. Normal Qt profiles, projects, identity and credentials are not migrated or overwritten. OMP retains the existing home/profile credentials and executable search path. The original Qt branch remains preserved; the GTK package is a development preview rather than a production replacement.

The open slider endpoint/return issue is addressed by an experimental Casilda implicit-pointer-grab patch (`1.6.0-centaur3`). Native regressions now leave the original surface and return with the button still held at 100% and 150%. The viewport's outer shadow is confined to app bounds rather than wrapping modal dimming; the native modal screenshot was inspected. These fixes still need their corresponding hands-on VM confirmation.

Local validation passed the nine Python bundle/viewport/backend tests and the three service suites (38 core, 8 network, 7 Iroh test cases). Native ARM64 embedding checks pass all zoom levels, endpoint-return capture, focus/input, popups/dialogs, clipboard, restarts and shutdown. The full native product integration and signed-cache publication passed as recorded below. A fixture agent is used in CI; it does not establish live OMP/provider acceptance or physical remote-client use.


**Phase 3 automated acceptance:** immutable source **`e082a941a52ca63f778e1cb538acf4c4f8a36b42`**, [ARM64 integration run 41980178912](https://github.com/mattatgit/Centaur/actions/runs/41980178912), evidence artifact **`13393287845`**. The actual GTK UI created a project, embedded its separate GTK app, invited/joined a second independently stored profile and exchanged attributed chat. Build mode kept chat visible; drawing and Undo synchronised. A guest's fixture-agent request passed the native GTK checker, updated both previews without an extra approval and retained a single project. Its canvas PNG reached the host. Invalid CSS preserved source, revision and both previews. A genuine conflict waited for both affected authors, then updated both apps. An exact historical bundle was restored on both profiles. Leaving/reopening the same project stopped/recreated its preview, and frontend, app and isolated host shutdown passed. `summary.json` records `passed: true`; the screenshots of the rendered workspace, host and guest were inspected.

CI keeps the two windows visible side by side on a disposable 2560×1000 Wayland display, avoiding desktop occlusion/frame throttling when checking both rendered previews. It is not a physical two-machine or internet acceptance run. Source/network state propagates independently of which window has focus. All six viewport modes and the new endpoint-return drag regression also passed in the same job. The [standalone embedding run](https://github.com/mattatgit/Centaur/actions/runs/41980178910) passed separately.

**Verified distribution:** artifact **`13393996028`**, `Centaur GTK4 0.4.0-preview+e082a94`, installable **`github:mattatgit/Centaur/e082a941a52ca63f778e1cb538acf4c4f8a36b42#gtk4-preview`**, store path `/nix/store/v653pz40gy7a5wf11l9vsgy9mba8p00z-centaur-gtk4-preview-0.4.0-preview`. All **531 runtime paths** were downloaded into an empty store and signature-verified with builders disabled; `verifiedSignedClosureDownload` is true. Use this immutable source, not a later documentation-only branch tip. The Qt branch was rechecked at `3d24d11e959c1c6ec8c16df5b1c3e4bd7183e450` and remains unchanged.

**Remaining acceptance:** Matt's hands-on frontend and live OMP results for this immutable preview are recorded below. A physical remote client still needs hands-on testing once its platform is established. Use a separate GTK development profile/data directory through Centaur Install; stop only the GTK host before updating that profile. This result does not migrate existing Qt projects or approve production replacement. Comprehensive design systems, generated-app data synchronisation, deployment, native macOS embedding, IME/alternative layouts, Num Lock, fractional display scaling and GPU/default-renderer acceptance remain outside this result.

### Phase 3 ARM64 UTM VM hands-on acceptance (recorded 9 November 2026)

Matt's owner-reported hands-on results from **Centaur Install**, on **ARM64 NixOS (KDE) in UTM**, for the **first integrated GTK4 Phase 3 preview** at immutable source [`e082a941a52ca63f778e1cb538acf4c4f8a36b42`](https://github.com/mattatgit/Centaur/commit/e082a941a52ca63f778e1cb538acf4c4f8a36b42), version **`0.4.0-preview+e082a94`**, on **`codex/gtk4-migration`**. These findings are separate from the earlier isolated `a02d0b8` and `90dad3a` acceptance records above and from the automated integration evidence.

**Passed:**

- Installed the precompiled preview in its isolated GTK4 profile and launched with **`GSK_RENDERER=cairo`**.
- Created **GTK4 Test** and reopened the same project.
- The native GTK4 app was visibly embedded alongside chat; basic input and interaction worked.
- A live OMP request, **`@centaur Change the visible heading A little space for us. to Family Planner, leaving everything else as it is`**, automatically changed the visible heading to **Family Planner** in the same project.
- **Family Planner** remained after **Restart app** and after reopening the project.
- **75%** and **150%** zoom displayed correctly, with correct centring and clicks.
- **Fit** scaled the preview as the host window resized.
- At **150%**, middle-button panning and **Centre** reset worked.
- In **Build**, drawing and **Undo** worked inside the embedded app, and chat remained usable. Switching back to **Interact** restored app interaction.

**Observed issues and incomplete workflows:**

- **Drawing clips at the embedded-app boundary:** a stroke started inside the app clipped exactly at its boundary and could not continue into the surrounding canvas. The drawing/Undo pass above covers drawing inside the app only.
- **Arrow commenting has the same boundary restriction:** only the arrow marker was observed. A complete comment-text entry/save workflow was not verified. Matt also reported that the comment workflow is unfinished in Qt.
- **Runtime to-do state was lost:** a user-added to-do disappeared on agent regeneration and on **Restart app**, while the agent's source change to **Family Planner** persisted. The cause was not established; in-memory fixture state is a possible explanation, not a verified diagnosis. This does not establish generated-app user-data persistence or synchronisation.
- **No user-visible History interface was found.** The retained backend has Git/checkpoint support, and historical-bundle restore has automated evidence above; neither establishes an available History UI. No hands-on history browsing or restore workflow passed in this run.
- **Visual refinement remains:** Matt found the interface visually rough and in need of design refinement.

**Acceptance boundary and limitations:** this records the verified behaviour of this exact preview on the tested VM/Cairo path, with the issues above still open. **No hands-on multiuser remote-client test was performed, and no comprehensive GTK production acceptance was performed.** The two-profile CI result remains automated evidence only. Other checks and limitations retain the scope of their earlier records; this run does not establish hands-on confirmation of the slider endpoint/return or modal-shadow fixes, default/GPU rendering, other desktop scales/layouts/IME, native macOS embedding or arbitrary generated apps. It does not approve a production Qt replacement or Casilda for production.

**Scope preserved:** this acceptance record requires no changes to the production Qt profile, VM installation, OMP path or credentials, application code or release configuration. The earlier `a02d0b8` and `90dad3a` records remain unchanged.
