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

The unchanged `flake.lock` supplies **Casilda 1.2.2**, GTK **4.22.4** and wlroots **0.20.2**. Its source is fixed by the existing Nix package's source hash. Use the actual runtime/metadata recorded by CI if that lock is intentionally updated later.

Upstream's [1.6 release source and changelog](https://gitlab.gnome.org/jpu/casilda/-/blob/1.6.0/CHANGELOG.md) introduce host clipboard/drag-and-drop integration and popup/focus fixes. Its [build definition](https://gitlab.gnome.org/jpu/casilda/-/blob/1.6.0/meson.build) requires GTK 4.24, unavailable in the inspected current/pinned Nix package sets. Do not silently upgrade the Qt baseline, lower the upstream GTK requirement or claim 1.2.2 provides those fixes. Options after baseline evidence: package a compatible newer GTK/Casilda pair as an isolated dependency, backport carefully with tests, or evaluate another embedding backend.

Casilda's inspected public API provides socket/client launching and GtkScrollable behaviour, not an app-dimension/zoom/window-management API. Its virtual output responds to widget allocation. Centaur must keep logical dimensions separate from presentation and validate transformed input and popups; adding a zoom dropdown alone is insufficient. A client can request transient or additional windows; main-window centring, popup extents, multi-window handling and clipping need explicit tests. A successful first render cannot approve the dependency.

### Automated evidence

[GTK4 embedding experiment workflow](../.github/workflows/gtk4-embedding.yml) builds only the ARM64 experiment. The checker uses a disposable Xvfb display, with a real Wayland child inside Casilda. It requires the child's coloured marker in a screenshot of the host window; verifies separate PID/private display, click, keyboard/text, scrolling, popup, modal dialog, host/client focus, unchanged app dimensions on host resize, restart and child shutdown. It records both directions of clipboard transfer separately; a known clipboard failure does **not** become an approved capability or silently disappear from the report. `casilda_approved` remains false.

Evidence artifacts contain `embedded.png`, host/client JSON and `summary.json`. Only a passing core check may publish this isolated test package to Cachix; publication verifies the full signed closure in an empty store with no builders. Publishing the experiment is not approving Casilda or claiming full Phase 1 acceptance. Local macOS checks establish Python/process isolation, workflow syntax and Nix evaluation, not GTK/Wayland rendering.

### VM acceptance gate

Guided installation and results belong in **Centaur Cloud → Centaur Install**. Use a separate `centaur-gtk4-test` profile only after the ARM64 job and signed publication succeed. Do not replace the regular Centaur profile or the separate Landline test profile. Use the exact successful manifest revision, not a moving branch head.

Record the machine, source revision, GTK/Casilda versions, desktop scale and default/software renderer. Inspect the screenshot and test:

1. Native app appears inside the host, with no separate desktop window or extra surrounding box; app controls remain reachable.
2. Click the button; type/edit/select text, including ordinary keyboard shortcuts. Scroll the list with mouse and touchpad where available.
3. Open the menu popup, choose its action, open the modal dialog and dismiss with Escape. Check focus returns correctly; check edge-positioned popups and repeated opening.
4. Alternate typing in the host field and app field. Copy/paste host→app and app→host; record failures. Test external desktop clipboard separately in the actual Wayland session.
5. Resize the host smaller/larger and check app dimensions, input, clipping and focus. This does not yet test preview zoom.
6. Restart repeatedly, then close. Confirm no orphan or duplicate app process. Relaunch creates a fresh temporary environment. Check failed startup/child exit produces a recoverable status.
7. Check keyboard layout/IME, display scaling, graphics resource use and multi-window behaviour on the VM. CI's X11-host/software-rendering result does not establish these Wayland desktop capabilities.

**Gate:** document limitations and choose a suitable candidate/version before proceeding with full integration. Host clipboard support is a known unresolved requirement for the packaged candidate. If it blocks acceptance, improve or replace the backend rather than declaring Phase 1 complete.

## First ARM64 result (5 November 2026)

[Run 41955179810](https://github.com/mattatgit/Centaur/actions/runs/41955179810), source `704b5dd11e472a88dc843281aec81855922f9790`, built successfully and ran the native app in the disposable Linux display. I inspected the screenshot: the separate GTK4 app is visible centred inside the GTK4 host, with its entry/buttons/scrollable list, and no extra preview frame. The automated checker passed rendering/private display, pointer/keyboard/text, scrolling, popup action, modal dialog, host/client focus and host resizing without changing app dimensions.

**Rejected for adoption in this tested form:** clipboard transfer failed in both directions. At Restart app, the host aborted with wlroots' `surface_handle_resource_destroy` assertion that `surface->events.commit.listener_list` must be empty. The subsequently launched child could not initialise its display because the compositor had died. This is an observed Casilda/wlroots lifecycle failure, not established evidence that a newer version fixes it. The test correctly failed; no GTK test package was published. Screenshot/summary/host-state evidence is artifact `13382891642`. A later diagnostic change also retains pre-restart client state and requires a clean host exit.

Do not ask the owner to install this failed candidate or replace the working Qt/Landline test. Phase 1 has demonstrated basic feasibility but **has not passed the suitability gate**. Next evaluate the lifecycle failure with upstream fixes/a compatible newer GTK–Casilda pair; rerun these checks and require both clipboard directions and clean restart/shutdown before adopting it. If these cannot be met, evaluate another embedding backend. Phase 2/3 integration remains gated on that outcome.

## Phase 2: independent preview viewport

The reusable viewport owns actual app dimensions, zoom, placement, clipping and pan offsets. The backend owns native surfaces, display/input delivery and lifecycle. Keep Casilda-specific objects out of application/project logic.

Provide **50%, 75%, 100%, 125%, 150% and Fit**, default **100%**. Fit changes presentation only. The app is centred directly on the canvas, with no visible frame; a subtle shadow is permitted. A small/large app keeps its logical resolution and responsive layout when zoom changes. Host allocation, desktop DPI and preview zoom are independent inputs. Provide panning/scrolling for oversized previews and stable zoom anchoring.

Test pointer-coordinate mapping, click/drag, selection, keyboard focus, scrolling, popups, dialogs and app interaction at every zoom and after host resizing. Overlays/grid/captured agent context must share the same transform and remain aligned. Clip preview content appropriately while retaining usable popup/dialog behaviour. Reuse these behavioural tests for future embedding backends. No zoom controls are implemented by Phase 1.

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
