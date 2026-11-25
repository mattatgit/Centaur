# Current state

## Composer polish queued after owner testing on 966074c

The owner verified image recall on the ARM64 VM and x86-64 Framework in Sharing Test, including a follow-up that explicitly excluded Figma. Explicit private-reader access was untested.

- Measure the interval from Send to visible feedback on image messages. Show a pending state immediately and distinguish upload from agent processing.
- Use the lighter remove-button treatment when hovering a thumbnail and the darker treatment directly over the X.
- Set image-preview spacing to 16 px and check mixed image and Figma chip wrapping as the composer narrows.
- Refine keyboard focus outlines while keeping the focused control readily identifiable.
- Review a secondary location for **Request details** on agent errors while keeping diagnostics available.

## V2 polish follow-up — 19 November 2026

Signed preview **`0.4.0-preview+ff58f74`** comes from
`ff58f74d19e5e4c2c7751a46c1d5abc658506826`. It adds timed updater receipts,
Projects/Edit motion that keeps the selected preview running, the sliding
Interact/Build indicator, and hover avatars drawn from the shared project
roster. The VM passed 40 native product checks, 19 embedding checks, 94 Python
tests and three service suites. Both signed updater transactions passed in
CI and in disposable ARM64 NixOS profiles. The advertised feed matches the
verified signed package. Installation and acceptance remain in Centaur Install.
[Technical evidence and screenshots](GTK4_V2_FOLLOWUP.md)

## V2 completion and polish — 18 November 2026

Published signed preview: **`0.4.0-preview+4144bb8`**, immutable source
`4144bb82a8c93724e94f88fc405d087aa7c4f80b`. All eleven Pass 2 items are
implemented using original Figma assets and the supplied animation. A supplied
Create prompt now starts app creation through the existing bounded agent queue,
as explicitly approved by the owner. Unchanged chat rows preserve keyboard
focus, text selection and reader position during message arrivals.

ARM64 NixOS UTM verification passed 37 product checks, 19 embedding checks,
94 Python checks with zero skips and matching retained service suites. Both
[product/update](https://github.com/mattatgit/Centaur/actions/runs/44261678103)
and [embedding](https://github.com/mattatgit/Centaur/actions/runs/44261678189)
CI passed. The exact signed package passed all 12 updater checks in disposable
NixOS profiles, including confirmed updates from both Settings and the footer.
The public feed exactly matches the verified artifact and its 613 signed closure
paths. [Technical details and screenshots](GTK4_V2_PASS2.md) distinguish the final
checks, earlier live model runs, test-only correction and VM metadata fixture.

No owner profile was activated. Existing data, credentials/configuration,
identities and Qt remain preserved; general model terminal access stays disabled.
Installation and GNOME hands-on acceptance remain in Centaur Install. Sharing UX
and generated Landline icon alignment remain deferred.

## Long-running agent response investigation — 18 November 2026

Published signed preview: **`0.4.0-preview+eb38227`**, immutable source
`eb382277e3dd84dab6fc6d555341569462a5c32f`. It integrates tested investigation
commit `1becefc` with remote main `12e677d`, preserving the separate README
change. The investigation reproduced the PTT timeout: Centaur required a full
three-file replacement for a small edit and
included roughly 100 KB of old import context. The reply was still serializing
the bundle when the deadline ended it; no tool/retry loop was observed.
Focused, source-hash-bound edits and current-request context completed two
fresh PTT tasks in 60.577s and 73.210s. Native physical input checks verified a
green held button using the original repository mic-on SVG, including a hold
past the click threshold and release outside the button. The 180-second
absolute response limit and bounded cancellation remain in place.

Prior ARM64 NixOS UTM checks passed 29 product checks, 19 embedding checks,
94 Python checks with zero skips and all three service suites. The exact merged
source passed both [product/update](https://github.com/mattatgit/Centaur/actions/runs/44232399512)
and [standalone embedding](https://github.com/mattatgit/Centaur/actions/runs/44232399503)
workflows, including native regression, all 11 signed-updater checks and an
empty-store download/signature check of all 613 closure paths. The public feed
exactly matches the verified distribution manifest. [Release evidence](evidence/gtk4-agent-response-2026-11-18/release-verification.json)
records artifact digests, source preservation and CI/UTM test boundaries.

No VM access, download, installation or activation was performed for publication.
The owner's installation was last verified as `0.4.0-preview+31220c4` after the
investigation; owner data/configuration remain preserved. Acceptance stays in
Centaur Install and Pass 2 remains deferred.
[Findings, fixes and limits](GTK4_AGENT_RESPONSE_INVESTIGATION.md) distinguish
the reproduced orchestration problem from uncertainty about the original
provider response and record the intermediate generated-code error caught by
useful-completion testing.

## Agent progress and timeout diagnostics — 18 November 2026

Published signed preview: **`0.4.0-preview+31220c4`**, immutable source
`31220c4b3a365f1c3419d4085f63022ed25afe00`. The original working animation now
appears in the chronological chat flow. Observable OMP/broker events update one
tile in place; prolonged waits show honest elapsed information. Readers retain
their scroll position during concurrent chat. Failures offer safe, copyable
Request details, and unchanged-app claims require a source comparison. The
180-second per-OMP-response limit remains bounded and unchanged.

Both [product/update](https://github.com/mattatgit/Centaur/actions/runs/44210383784)
and [standalone embedding](https://github.com/mattatgit/Centaur/actions/runs/44210383947)
workflows passed. ARM64 NixOS UTM verification passed 29 native product checks,
94 Python tests with the packaged sandbox and zero skips, all three service
suites, 19 embedding checks, a real OMP UI request and all 11 signed-updater
checks in a disposable profile. All 613 signed closure paths, the exact final
version and original animation bytes were verified in the VM; the release feed
matches its artifact. [Release evidence](evidence/gtk4-agent-progress-2026-11-18/release-verification.json)
records exact boundaries and a transient VM Cachix connection failure that
recovered without configuration changes.

The historical PTT failure was terminated by Centaur's invocation timer; the old
build did not record enough telemetry to establish the provider's state. This
release improves future diagnosis without claiming to repair an unproven
upstream fault. No owner profile was activated, and existing data, OMP
configuration, identities, Qt and NixOS settings remain preserved. General
model terminal access stays disabled. Installation and owner acceptance remain
in Centaur Install. [Details](GTK4_AGENT_PROGRESS.md).

Pass 2 remains deferred. Its available-update icon must open the restart-warning
modal before starting an update, require confirmation and allow deferral; this
Pass 1 release leaves updater controls unchanged.

## V2 four-fix polish — 17 November 2026

Published signed preview: **`0.4.0-preview+7a94994`**, immutable source
`7a949941c3429904662eeab581a586c1a2143d1c`. The original working SVG now animates
under the VM's GNOME motion policy and respects reduced motion; source inspection
is in the imported project's options menu; provider row/action hovers match the
original Figma variants and support keyboard focus; Centaur's own native tooltips
are removed with accessible names/descriptions preserved.

Both [product/update](https://github.com/mattatgit/Centaur/actions/runs/44030232587)
and [standalone embedding](https://github.com/mattatgit/Centaur/actions/runs/44030232553)
workflows passed. ARM64 NixOS UTM verification passed all 27 native product checks,
all 92 Python tests including the packaged sandbox, retained service regressions,
embedding and all 11 signed-updater checks. All 613 signed closure paths and the
exact published version/original SVG were verified inside the VM; the advertised
feed matches its artifact. [Release evidence](evidence/gtk4-polish-2026-11-17/release-verification.json)
records exact revisions and test boundaries, including the disposable VM DNS and
package-metadata fixtures. Owner profiles/data, OMP credentials/configuration,
collaboration identities, Qt and NixOS settings are unchanged. General model
terminal access remains disabled. [Details](GTK4_V2_POLISH.md).

Installation and hands-on acceptance remain in Installer (Centaur Install), one
step at a time; automated success does not mark owner acceptance complete.

## Native V2 interface — 17 November 2026

Published signed preview: **`0.4.0-preview+9680f97`**, immutable source `9680f97902ed359974dfbe13736fc72d83109ca2`. Both [product/update](https://github.com/mattatgit/Centaur/actions/runs/44019986166) and [standalone embedding](https://github.com/mattatgit/Centaur/actions/runs/44019986162) workflows passed. All 613 closure paths passed empty-store signature verification, the advertised feed exactly matches the signed artifact, and the final package plus original animation were verified inside ARM64 NixOS without activating the owner’s profile. [Release verification](evidence/gtk4-v2-2026-11-17/release-verification.json) distinguishes the complete VM signed-update test of runtime-equivalent `a6c4894` from the final checker-only revision. Hands-on acceptance remains in Centaur Install.

The [approved V2 interface](GTK4_V2_UI.md) is implemented on `main`, with a recoverable pre-change tag at `checkpoint/pre-v2-ui-2026-11-17`. It uses the original Figma exports and the owner's complete SVG animation without editing their bytes. Native integrated chrome, the left chat/right canvas layout, project screenshots and menus, Create/Import/Join/Invite/Delete forms and automatic Settings saving replace the prototype presentation. Provider/model settings use supported OMP RPC and Centaur-owned preferences; existing credentials, projects, conversations, collaboration identities, Qt installation and the verified sandbox remain intact. General model terminal access stays disabled.

[ARM64 NixOS UTM evidence](evidence/gtk4-v2-2026-11-17/manifest.json) records all 92 Python tests including the actual packaged sandbox, all three service suites, the six-zoom embedding regressions and the complete native product/import flow. The native test verifies Stop/recovery, actual avatar persistence, dynamic model selection, numeric autosave, collaboration, comments/drawings, conflicts/restoration and real Landline `linux-nix` commit `205fc1185335dc1c85b359af7673f6e5d7653222` with Linux source context. The normal VM resolver intermittently failed outside Centaur; the successful functional import run used a disposable Git DNS fixture with normal real-GitHub HTTPS verification. That is test infrastructure, not a product DNS repair. The unmodified normal-network path remains gated by release CI; the VM's resolver issue and hands-on acceptance stay in Centaur Install.

## Main checkpoint before the UI pass — 16 November 2026

The owner selected the GTK4 direction as the project's main line. GitHub's
default branch and this checkout now use `main`, created from `7127a25` with
all existing history. The annotated tag
`checkpoint/phase4-sandbox-2026-11-16` preserves that verified Phase 4 state.
The main-branch setup is checkpointed as `checkpoint/pre-ui-2026-11-16`.
The earlier GTK4 and Qt branches remain intact.

This promotion changes workflow gates, source metadata and documentation;
application code and the verified sandbox policy are unchanged. GTK4 product
and embedding workflows now follow `main`. Protocol-1 manifests retain the
historical `branch: codex/gtk4-migration` channel identifier so installed
updaters still accept signed releases; `sourceBranch: main` and the immutable
revision identify new source. Cache signatures, publication checks and update
recovery remain required. Installation/acceptance stay in Centaur Install.

Both main workflows passed: [product/update](https://github.com/mattatgit/Centaur/actions/runs/43806726257)
and [embedding](https://github.com/mattatgit/Centaur/actions/runs/43806726218).
The signed checkpoint build is `0.4.0-preview+7c18d30`; all 613 closure paths
passed empty-store signature checks, native integration and the Settings update
transaction passed, and the public feed exactly matched the downloaded signed
manifest. [Checkpoint evidence](evidence/main-checkpoint-2026-11-16.json)
records the source, tags, preserved branches and checks. No owner profile was
changed for this repository checkpoint.

The next planned work is a proper UI pass. This checkpoint does not start that
redesign or claim full Landline Rust/egui/Iroh/audio integration. The separate Qt
installation, existing projects/conversations, identities and OMP configuration
remain preserved. The following dated entries retain their original branch and
release context.

## Phase 4 sandbox broker integration — 16 November 2026

The owner authorised connecting the verified boundary to the import broker,
keeping general terminal access disabled. The broker now supports fixed
`runtime_version` (packaged Python/Git/GCC) and `validate_manifest` (JSON/TOML
syntax) operations. Application code chooses executable paths and arguments;
there is no shell, arbitrary command, project evaluation, dependency installation
or repair/build tool. A private snapshot contains only selected policy-filtered
text, never the original source tree. Source/adaptation scopes remain separate.

The production runner and engineering adversaries share the same boundary engine
and native seccomp policy. All resource/isolation controls are required per job.
The existing coordinator binds results to attempt/epoch/request/operation IDs,
rejects stale completions, retains bounded private observations, and routes
findings through normal chat. Isolation failure disables these tools for the
attempt; static inspection remains available. OMP still receives `--no-tools`
and `--no-extensions`. Run preview permissions are unchanged.

Verified only on ARM64 NixOS under UTM: 88 Python checks, all 18 boundary checks,
core/network/Iroh suites, product build and live OMP investigation passed. An
additional supervisor-death regression caught InterruptedError being swallowed
by Python's selector loop. The final handler raises RuntimeError so whole-cgroup
cleanup runs: SIGTERM took 0.064 seconds; SIGKILL left no descendants after the
independent deadline (7.991 seconds). The live agent used both fixed tools and
read-only inspection to diagnose malformed JSON, identify two unfamiliar apps
and an absent prerequisite, without executing project code or changing originals.
The exact packaged broker and shared-engine bytes matched the tested source.

[Policy and limits](IMPORT_ISOLATION.md) and
[raw evidence/source hashes](evidence/import-sandbox-phase4/) record the scope.
Published **0.4.0-preview+0ddbd19** through the existing tested, signed Cachix
workflow. The [product run](https://github.com/mattatgit/Centaur/actions/runs/43803326626)
and [embedding run](https://github.com/mattatgit/Centaur/actions/runs/43803326579)
passed. All 613 closure paths passed empty-store signature verification;
native import/collaboration and Settings update/data/Qt preservation checks
passed. Landline again used linux-nix at
`205fc1185335dc1c85b359af7673f6e5d7653222`, with LandlineNix source in the agent
context. The public feed exactly matches the signed manifest. A binary-only
UTM download verified both fixed diagnostics and exact installed broker/engine
bytes without switching any owner profile. [Release evidence](evidence/import-sandbox-phase4/release-verification.json)
separates publication from hands-on acceptance. The installed
owner profile remains `0.4.0-preview+e8d627c` during engineering tests. Projects,
conversations, OMP configuration/credentials, identities and Qt installation
were preserved. Installation and hands-on acceptance remain in **Centaur Install**.
Repairs, preparation exports, network grants and general builds are later work.

## Import diagnostic agent review — 16 November 2026

The owner's Architecture + Design handoff establishes general import diagnosis,
isolated diagnostics and controlled repairs as the next import direction.
[Phase 1 review](IMPORT_DIAGNOSTICS.md) recommends extending the existing
host-owned inspection loop with typed broker operations and structured recovery,
then proving ARM64 isolation before enabling commands. That Phase 1 increment
changed documentation only; the Phase 2 implementation is recorded below.
At review time the UTM display was inactive, so installed OMP/sandbox
capabilities were unverified. At that point the last observed installation was
`dbadb0c`, and the separate published `aa64982` update had no owner confirmation
in **Centaur Install**. Later acceptance and Phase 3 evidence are recorded below.

## Phase 2 import diagnostics — 16 November 2026

Implemented on `codex/gtk4-migration`, following explicit owner
authorisation. OMP's built-in tools/extensions remain disabled. The coordinator
accepts typed inspection requests and uses a separate Python broker for bounded,
read-only listing, line-range reads and literal search. Recorded source facts
and structured failures are supplied privately to the agent, including failures
before a source copy exists. Original source, adaptations and accepted previews
remain separate; no terminal/build/install capability is added.

All file operations share a secret/path policy and open through directory
descriptors without following symlinks. Operations omit special files and bound
entries, scan bytes, result size and time. Results identify truncation and
omissions; directory cursors detect changes. Acquisition uses the same policy
and descriptor access for local source copying. Source files are treated as data.
Local Git preservation copies only bounded object/ref data into host-created
bare metadata; it does not run Git against source-controlled configuration.
External alternates are not followed, and unavailable history is reported
separately from the working source's availability.

The host binds worker completions to the project attempt and operation ID,
rejects stale agent results, retains observations/actions privately, and routes
questions through normal chat. Interrupted work keeps diagnostic state. The
network allowance is reserved before starting acquisition and survives a host
restart. A transient acquisition failure may receive one agent-directed retry
of the host's saved source, within six total network attempts; ordinary worker
retries count toward that same allowance. Nontransient failures and exhausted
budgets cannot be retried automatically. Manual source retry remains an explicit
user action preserving project/conversation identity and earlier attempts.

Inspection has eight rounds per conversational step, duplicate-request rejection,
and bounded retained results. An explicit human response starts a new inspection
step, without resetting acquisition retry counters. Failed preparation operations
also have a bounded failure-investigation chain. Raw helper stderr, host paths
and credential-helper details remain outside shared chat and model context.

All 84 Python checks passed on the actual ARM64 NixOS UTM VM, followed by a
successful retained service Nix build with core/network/Iroh checks enabled.
Coverage includes pagination beyond the initial inventory, unfamiliar/multiple
app fixtures, hostile build instructions treated as data, local Git configuration
and alternates, secrets, traversal, symlink replacement, special files, limits,
original-file hashes, model-facing failures, same-source budgets, continuations,
duplicate requests, restart and cancellation. The cancellation regression exposed
a stale published busy gate after discarding a late worker result; the final VM
run passed after adding the gate refresh and bounded cancellation cleanup.

Live OMP (`openai-codex/gpt-6.1-sol`) separately passed two disposable scenarios:
inspection used list/search/read to identify two unfamiliar applications and a
missing runtime, then asked which app to work on. Recovery received a synthetic
DNS failure before any source existed, requested the permitted retry, retained
the exact saved URL/ref and shared budget, and investigated the resulting source.
The recovery acquisition was fault-injected test data, not a claim of a real
GitHub network outage. Both checks proved original-file hashes unchanged, no
project-code execution, no accepted preview created and terminal/extensions
still disabled. [VM evidence and file hashes](evidence/import-diagnostics-phase2/)
separate these results from hands-on acceptance.

Published **0.4.0-preview+e8d627c** through the existing tested, signed Cachix
workflow. The [product/service/import/updater run](https://github.com/mattatgit/Centaur/actions/runs/43793539315)
and [standalone embedding run](https://github.com/mattatgit/Centaur/actions/runs/43793539331)
passed. Native import verification again selected Landline `linux-nix` at
`205fc1185335dc1c85b359af7673f6e5d7653222`, with `LandlineNix` source in the agent
context. All 579 closure paths passed the empty-store signed download check;
Settings update and profile/data/Qt preservation checks passed before feed
publication. The public feed exactly matched the signed distribution manifest.
The owner's VM was not updated during testing, and the temporary server is
stopped. Installation instructions and hands-on acceptance stay in
**Centaur Install**; automated results do not establish owner acceptance.

## Phase 3 import isolation proof — 16 November 2026

The owner authorised ARM64 NixOS UTM isolation/resource verification before
enabling diagnostic commands. A separate pinned engineering package passed all
18 checks on the actual VM as an ordinary user. It combines mandatory Bubblewrap
namespaces, a native seccomp allowlist, individual read-only runtime closure
mounts, a read-only fixture, bounded tmpfs scratch and effective systemd user
cgroup controls. Measured limits were 128 MiB/no swap, 32 tasks, 25% of one CPU,
8 MiB aggregate scratch, 1 MiB/file, 32 KiB retained output and eight seconds.
Exhaustion/throttling, credential/socket/descriptor denial, unknown commands,
unavailable boundaries and daemon cleanup after cancellation, timeout and client
death passed. Original fixture hashes were unchanged.

[Policy, measurements and integration gate](IMPORT_ISOLATION.md) and
[raw VM evidence](evidence/import-isolation-phase3/) describe the exact scope.
This adds a standalone proof package and does not register diagnostic commands,
change preview permissions or update the installed app/profile. Production
fixed-command lifecycle integration and preparation/repair policy remain work
for later enablement. No new product build/feed was published for this proof.
The final 18-check run includes an explicit pipe handshake proving the detached
child has installed SIGTERM ignore before cancellation/deadline tests, and
atomic publication of the supervisor status record. Its source hashes match
the checkout and transferred archive. The temporary transfer server is stopped.

**Centaur Install** has now confirmed installed `0.4.0-preview+e8d627c` and the
owner reported a basically functional, rough GTK4 adaptation of Landline's UI.
That provisional acceptance does not establish a complete Rust/egui port or
underlying Iroh/audio functionality. Existing projects, conversations, OMP
configuration/credentials, identities and the separate Qt installation were
preserved during this verification. Installation and hands-on acceptance
continue in **Centaur Install**.

## Review baseline

Documentation review snapshot: `f2f72577b90edf23c8266b15a1a07905e017c066`, declaring v0.3.0, on `codex/native-prototype` as inspected on 28 October 2026. The handover's verified v0.2.0 build `09c573d` is an earlier baseline.

The [Actions run for this exact commit](https://github.com/mattatgit/Centaur/actions/runs/40624011510) completed successfully: distribution-tooling checks, x86_64-linux and aarch64-linux package checks, and both architecture publication jobs. This is inspected CI evidence, not a new local or physical acceptance run.

The owner's reported Air/ARM64 VM LAN test establishes invitation/join, shared chat and live agent requests. Existing validation notes also record automated public-relay operation. Physical use across different networks, real conflict mediation and target-device resource measurements still need acceptance evidence. Historical sections below retain their original scope and dates; their older pending-test wording is superseded by later dated results where applicable.

The design-system library/import, selectable systems and standalone generated-app deployment remain unimplemented. The current app-source contract is one `App.qml`. See [Requirements](REQUIREMENTS.md), [Design systems](DESIGN_SYSTEMS.md) and [Decisions](DECISIONS.md) for agreed direction, proposals and open work.

## Agreed direction

Centaur and the apps it produces are native. Target Linux/NixOS and macOS clients, with NixOS and modest hardware as the initial delivery and testing focus. One project represents one repository and one app. The two main views are projects and collaborative app building. The workspace contains a main canvas, a comfortably wide chat sidebar, Draw and Comment (Dialogue's Arrow behaviour). No activity rail. Use Dialogue's restrained visual style as the current prototype reference; Centaur's final identity remains open and separate from generated-app design systems. The default agent mention is @centaur and is configurable.

The agreed deployment direction is a standalone native app, beginning with **Install this app on this computer** on NixOS: its own launcher, persistent app data and an installed release that stays stable while authors continue editing. Family sharing and explicit release updates follow later; distributing an app does not itself synchronise family data. These features are not implemented yet. See [Architecture](ARCHITECTURE.md) for the deployment stages, runtime boundaries and font packaging considerations.

## First prototype

Focus on two experiments: a native app operating inside Centaur's frame, and an agent negotiating instructions from multiple authors. The intended complete loop is conversation → clarified direction → accepted change → native app revision inside the canvas.

Implemented as C++17 / Qt Quick 6.8+, with a separate Qt Quick client and a nested Wayland compositor on Linux. A macOS build is provided for native shell development, with an explicit Linux-only placeholder for embedding. Project state is stored locally, source versions use Git, and native windows connect over QLocalSocket to an authoritative background host; invited computers join individual projects over pinned TLS, directly on the LAN or carried by the native Iroh helper.

App edits and rewinds keep the same project identity. Starter opening (`--demo`) is resolved atomically by the shared host: reuse the most recently updated visible project, or create one only when the host has none. This fixes additional windows creating unwanted starter projects before their initial project list arrived. Existing project folders are retained; projects with matching names may contain different work.

Project cards form a responsive grid of one to five columns, sized against the scroll viewport with approximately 260 logical pixels as the minimum card width and 32-pixel gaps. Extra rows scroll vertically. The Project view allows windows down to 360 logical pixels wide, using the compact icon sidebar on narrow windows; the canvas/chat workspace retains its 1,000-pixel minimum. The empty state fits the same available width.

The agent adapter invokes omp without tools and expects a clarification or proposed QML source. Its stdin is redirected to `QProcess::nullDevice()` so OMP receives EOF before handling the argument/file prompt; leaving QProcess's default pipe open causes OMP startup to wait until Centaur's three-minute timeout. A regression test uses an executable that reads stdin to EOF before replying, including repeated requests on the same Agent.

Making a request is approval to carry it out. Compatible proposals are checked and applied automatically, without an approval click. Only a genuine conflict between active requirements pauses for agreement by the affected authors. The model must explicitly classify each proposal as `conflict: null` or provide a conflict reason and at least two distinct known authors. The coordinator validates that metadata and enforces agreement only for those authors. Other contributors do not have a veto merely because they chatted or drew something. New explicit agent directions and sketches invalidate pending work, which is retried against the latest conversation. Ordinary chat can continue without starving the agent; discussion of a pending conflict still invalidates its agreements. Old unfinished proposals made under the previous everyone-agrees policy are cleared on upgrade rather than silently applied. Model conflict detection and mediation quality still need evaluation with family conversations.

Revision counters remain internal for synchronization, drawing context and checkpoints. The canvas, project cards, old-message labels and routine completion messages no longer display numbered app revisions; old generated revision announcements are also rendered without their numbers. The agent receives the 100 most recent Git checkpoint descriptions/dates and can answer history questions or return a structured `restore` request. The coordinator retrieves the exact source from a reachable checkpoint in that project's Git history, validates it, and saves it as a new checkpoint. It never resets Git or substitutes model-generated source for a rewind, and conflicts still require agreement by the affected authors. All saved Git history is retained beyond the bounded model context.

The workspace omits the “Canvas” label and idle “Try the app…” hint. Its chat header is “Chat”, with the configurable agent name and last reported model in smaller grey text below. Omp runs in JSON print mode; Centaur incrementally consumes its event stream, retains only the final assistant text for the existing response contract, and reads provider/model metadata from assistant events. Model metadata is saved per project and shared between windows; no model name is guessed before the first report. Stderr and raw event transcripts stay out of shared chat. Plain JSON replies remain supported for explicit test doubles/wrappers.

A small Centaur software version appears at the bottom right of the chat footer, on the same line as the author/keyboard hint. It includes the source revision in Nix builds (for example, `v0.1.1+abcdef0`) so screenshots identify the running build. Modified Nix checkouts are marked dirty where revision metadata is available; direct CMake builds default to `+dev` and can set `CENTAUR_BUILD_ID`. The same version is returned by `centaur --version`. This identifies Centaur itself, not the project's internal app revision.

Centaur and the separate native example/preview/checker use bundled Inter 4.1 as their default font, with Regular, SemiBold and Bold available without installing fonts on the host. Sizes and weights are retained. Other scripts and symbols can use system fallback fonts. Explicit font choices in saved app QML are respected. The licence and upstream asset hashes are included in the repository and release package.

Centaur v0.3 adds Iroh internet connectivity alongside the working LAN transport. Invite defaults to peer-to-peer, with a Local network only option. A bundled native Rust helper shares one persistent endpoint per data directory, uses direct/relay connections and carries the existing pinned TLS/project authentication protocol. A separate background host survives UI closure; only that host needs OMP. [Collaboration](LAN_COLLABORATION.md) records invitations, installation, recovery and the cross-network acceptance test. Native QML remains trusted code; cloud accounts, host migration, offline authoring and generated-app data synchronisation are not implemented.

## Iroh validation (28 October 2026)

The macOS development build passes the existing core, network and UI suites plus the new Iroh suite. Real helper processes exercise concurrent guests, a second window sharing one guest endpoint, mixed LAN/Iroh participation, a source change through a test agent, invitation replay, wrong TLS pins, revocation, reconnect, background-host survival and legacy membership upgrades. The Rust helper's frame/address/private-key tests and strict Clippy checks pass. The Nix package builds and installs all four executables.

An additional integration run with direct IP transports disabled passed through the public n0 relays: multiple guests, a test-agent source change, rejection/revocation and host restart. No provider credentials or real project data were used. Physical operation on different networks with the Air and NixOS VM remains the next user acceptance test; Linux CI verifies the native Wayland paths separately.

## Deliberate boundaries

- The initial app framework is Qt Quick; arbitrary native frameworks are not yet supported.
- Local display names remain selectable. Remote participants have stable credentials and host-assigned names; no cloud accounts yet.
- Source, conversation and marks are shared; each window has its own live app interaction state.
- No sandbox around generated native QML yet. Run trusted local projects as an ordinary user.
- Canvas fitting is fixed to one app frame. Infinite panning, frame resizing and a dedicated history browser are follow-up work; history questions and rewinds currently go through chat.
- Test doubles validate coordination; they do not establish that the live model resolves disagreements well.

## Next evidence needed

On 28 October 2026 the owner confirmed invitation/join, chat and live agent requests between the Intel NixOS Air and ARM64 NixOS VM over the local network. Test the Iroh build across two different networks next, including relay fallback and recovery.

The current interactive Linux test environment is an ARM64 NixOS VM under UTM on an Apple Silicon Mac mini. The user confirmed that native embedding/input and a live authenticated omp request through Centaur work after the stdin EOF fix. Next, test compatible requests applying automatically and real conflicts requiring only the affected authors' agreement. The [Qt prototype's OMP guide](https://github.com/mattatgit/Centaur/blob/3d24d11e959c1c6ec8c16df5b1c3e4bd7183e450/docs/OMP_NIXOS_SETUP.md) covers updating and launching with an existing omp binary.

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


## Binary distribution workflow — 27 October 2026

GitHub Actions checks the unchanged v0.2 package on native x86_64-linux and aarch64-linux runners. After both pass, trusted pushes/manual runs on codex/native-prototype can publish each complete runtime closure to a public Cachix cache and verify a fresh signed download. The package includes Centaur, centaur-host and centaur-preview. Public installation metadata records the commit, cache key, package path and verified closure. See [Binary distribution](BINARY_DISTRIBUTION.md).

First publication requires a public Cachix cache, repository variable CENTAUR_CACHIX_CACHE and per-cache write secret CACHIX_AUTH_TOKEN. Until configured, publication is skipped with a setup note; a passing CI build does not claim a cache upload. Air/VM installation commands explicitly disable builders so missing binaries cannot cause local compilation. Application functionality and flake platform outputs are unchanged.


## Typography and window tidy-up (29 October 2026)

The chat header no longer has the standalone C badge. The model line formats names such as `openai-codex/gpt-6.1-sol` as “OpenAI Codex · GPT 6.1 Sol”; unavailable runtime status takes priority over saved model details. Message avatars remain. Text sizes and weights are retained pending design review: heading 14 pt/600, model 10.5 pt/400, messages and composer 12.5 pt/400, author 10.5 pt/600, time/footer 9 pt/400 and version 8.5 pt/400.

Inter Tight is bundled for text above 12 pt; Inter remains at or below 12 pt. The starter and agent guidance follow the same split. The GNOME/Wayland frame patch matches bottom corners to the existing native 12 px top corners, and a bottom-right hover target invokes native diagonal resizing. The OS title bar and controls remain native.

## Guided NixOS installation/update helpers (29 October 2026)

The owner confirmed Centaur v0.3.0 (`2cef110`) runs from precompiled packages on both the Intel NixOS Air and ARM64 UTM VM, using the dedicated Centaur profile. The VM's agent remains `/home/matt/.local/bin/omp`. The Air's original NixOS configuration is unavailable; read-only diagnostics confirmed Nix 2.28.4, a store-backed `nix.conf` and an active standard Nix daemon unit with no reported drop-ins. The VM's configuration is not yet diagnosed.

The Linux package now includes download-only update and reversible daemon cache-setup helpers, with a [step-by-step guide for the Qt prototype](https://github.com/mattatgit/Centaur/blob/3d24d11e959c1c6ec8c16df5b1c3e4bd7183e450/docs/NIXOS_INSTALL.md). Existing pinned profile installations can migrate without duplicate entries. Downloads finish before host shutdown; the exact downloaded package is activated atomically, and the helper remembers OMP/data paths separately without rewriting private application records. Shell/workflow checks, simulated failure-path tests and a real Nix profile migration/failure/rollback check run in distribution CI. Local validation used Bash 5/GNU tools and Nix 2.35.2 on macOS in isolated test directories. The service operations are simulated in local tests, not a claim of physical NixOS setup success; guided cache activation and end-to-end updating on the Air and VM remain acceptance work.

The initial `c6f4c91` helper's Air compatibility check passed but setup failed because `/etc/systemd/system` is read-only. Subsequent device diagnostics confirmed Nix remained active and systemd 257.6 explicitly lists `/etc/systemd/system.control` as a persistent unit load path. The corrected helper uses that path, refuses read-only mounts/store-backed targets before changes, stages both files first and requires the exact drop-in to be loaded before restarting. Recovery reports any cleanup errors and avoids restarting for failures before the daemon was touched. Added regression cases model the generated directory, missing load paths, immutable targets, unloaded overrides and legacy successful setups. Distribution CI additionally runs the production setup logic against a disposable real systemd service, with private test paths and a fixture identity; this never reconfigures the runner's actual Nix daemon. Physical Air/VM setup remains a separate guided acceptance check.

## Centaur Mark V1 (29 October 2026)

The owner's supplied SVG replaces the four-dot placeholder in the sidebar, workspace navigation and packaged desktop icon. The file is preserved byte-for-byte with its original colour, transparency and viewBox; [provenance and checksum](../packaging/README.md) identify the source. The UI uses the existing native SVG renderer, retaining the Projects action, hover animation and focus outline. The native window uses the same icon, with the Linux desktop identity matching `centaur.desktop`.

The native build and existing UI smoke checks passed locally on macOS at normal and 2× scale. Screenshots confirmed the mark in both navigation layouts. Physical desktop launcher appearance remains a Linux desktop check.

## Single-line chat status (29 October 2026)

The separate guest connection row is removed. One 10.5 pt regular Inter subtitle combines **Guest connected** or **Host online** with the actual reported provider/model, with no redundant “shared project” label. It stays on one line and elides at narrow widths; the full text and model ID remain available on hover. Connection labels follow the real host/guest connection state, preserving connecting/disconnected messages and agent-unavailable display. Read-only guest details remain in the tooltip.

The native build, UI smoke checks (including an unavailable agent) and the two-client network suite passed locally on macOS. Checks cover both connection-role labels and the subtitle's single-line text and size; the header was also visually inspected in a native UI screenshot.

## Landline embedding experiment preparation (2 November 2026)

An optional Linux test package pins Landline `linux-nix` commit `205fc1185335dc1c85b359af7673f6e5d7653222`, a Rust/egui app with Wayland enabled. It launches directly in a temporary Centaur workshop with a 320 × 672 frame, separate Landline profile/key/cache paths, agent editing disabled and sharing/deploy controls unavailable. The normal Centaur profile and default QML preview remain separate. Native readiness follows an actual compositor buffer, including for apps without the Qt readiness marker.

The package and per-architecture CI workflow are prepared with complete signed-cache publication and a headless external-app render check. Local macOS checks cover compilation, the existing four test suites and launcher argument/environment tests; they do not establish Linux egui embedding. Actual Landline rendering in Linux CI and physical VM/Air input/lifecycle acceptance must be recorded separately. The next manual step belongs in Centaur Install once the architecture's build, embedding check and signed-download publication have succeeded. See [Landline embedding test](LANDLINE_EMBEDDING_TEST.md).

Both ARM64 and Intel integration jobs at **`08d166a5acb994f38fb5171ad3c6555c6137fbf0`** passed in [run 41383494150](https://github.com/mattatgit/Centaur/actions/runs/41383494150), each with one live external-app surface, no QML warnings and a visually inspected screenshot showing Landline inside the canvas. All 310 runtime paths per architecture were downloaded from Cachix into an empty store and signature-verified. The initial EGL failure was fixed by giving Landline the Mesa driver from its own older pinned runtime, separate from Centaur's driver. The Qt decoration dependency is now keyed by patch contents so unrelated source edits can reuse it. The VM's guided pointer/keyboard/resize/restart test has been handed to Centaur Install; it remains a physical acceptance check before testing the Air.


## Active target and GTK4/scaling direction (2 November 2026)

The owner has stopped Air testing. Automated package checks/publication and the Landline embedding workflow now target ARM64 Linux only, matching the Mac mini’s UTM NixOS VM. Existing Intel flake outputs and historical cache records remain; new Intel builds are disabled. The remote client will test collaboratively, with their target architecture still to be established. Documentation-only changes no longer trigger app builds, and superseded runs on a branch are cancelled.

The client’s developer plans to replace the Qt work with GTK4, including native app presentation in the canvas. The prepared VM experiment at `08d166a` remains the Qt implementation and can be tested now. No GTK4 migration or zoom controls have been implemented in this update.

The latest **Architecture + Design** chat was read in full (four turns, including its latest zoom and typography discussions). Its toolkit-independent viewport requirements are recorded in [Architecture](ARCHITECTURE.md#preview-dimensions-and-canvas-zoom), R17–R19 and D14: default 100%, 50/75/100/125/150% zoom separate from actual app dimensions, correct input/overlay alignment, panning/clipping and a stable zoom anchor. Fit to canvas remains an additional proposal. The present automatic board fit is not equivalent to these controls. GTK4 compositor/embedding choices remain open with the client.


## GTK4 migration branch and Phase 1 experiment (5 November 2026)

The working Qt branch remains `codex/native-prototype` at `3d24d11`. Migration starts separately on `codex/gtk4-migration`. The Landline VM experiment at `08d166a` is independent. Both Centaur and generated apps are now agreed to target GTK4; Fit is agreed alongside 50/75/100/125/150% zoom, default 100%, and centred app presentation without an extra frame.

The isolated `gtk4-embedding-test` package adds a GTK4/PyGObject host, replaceable Casilda adapter and separate GTK4 interaction fixture. It has temporary child data paths and process lifecycle control. The current pinned Casilda 1.2.2/GTK 4.22.4 pair is an evaluation candidate; upstream 1.6 adds host clipboard integration but requires GTK 4.24. This is a known suitability risk, not an approved dependency or a completed migration. Existing host, collaboration, OMP, projects and generation contracts are unchanged.

Local checks passed for Python compilation, FD/data isolation and shutdown/error handling, workflow/shell lint and ARM64 Nix evaluation. The first ARM64 package at `c5fbcd6` built successfully; its disposable test session failed before launch because the Nix D-Bus configuration was not supplied. `704b5dd` fixes that setup. Its ARM64 run demonstrated separate-app rendering (screenshot inspected), clicking, typing, scrolling, popups, dialogs, focus and host resize without changing app dimensions. Clipboard failed both directions, and Restart app aborted the compositor with a wlroots surface-listener assertion. The candidate failed suitability checks and was not published. No VM acceptance or GTK migration success is claimed; Phase 2/3 integration remains gated on resolving these limitations. See [GTK4 migration](GTK4_MIGRATION.md) for the three phases, clipboard limitation, current boundaries and VM acceptance gate.


## Newer GTK4/Casilda candidate (5 November 2026)

The isolated newer package uses GTK 4.24.0, GLib 2.90.0, Pango 1.58.2 and Casilda 1.6.0 with two experimental Centaur patches for initial keymap setup and ordered modifier delivery (`1.6.0-centaur2`). The original Qt/Landline inputs and working branch remain intact. CI now supplies a disposable native Wayland/Sway display and a persistent input seat with a fixed US keymap, matching the target display protocol without driving the user's desktop.

At `a02d0b8`, [ARM64 run 41959595774](https://github.com/mattatgit/Centaur/actions/runs/41959595774) passed rendering (screenshot inspected), pointer/keyboard/capitalisation, scrolling, popup/dialog, focus, resize without app-dimension changes, clipboard both ways, three restarts with rendering/input, normal host exit and child shutdown. The full job and signed-cache publication succeeded; all 303 runtime paths were downloaded into an empty store and signature-verified. The immutable `a02d0b8#gtk4-embedding-test` build subsequently passed the owner-reported VM checks listed below. This is an experimental embedding candidate, not a completed GTK migration or approved production dependency. See [the evidence and limitations](GTK4_MIGRATION.md#newer-candidate-native-wayland-checks-passed-5-november-2026).

## Owner-reported GTK4 VM acceptance and viewport work (5 November 2026)

The owner reports a **PASS** for the tested functionality in immutable `a02d0b8`, ARM64 NixOS under UTM, `GSK_RENDERER=cairo`: embedding, mouse/buttons/scroll/popups/dialogs, text/focus, clipboard both ways including KDE, Shift+Arrow, Caps Lock, Ctrl+A, edge popup placement, resizing with interaction, three restarts, fresh temporary data after reopening and clean shutdown without orphans. Normal Centaur projects/OMP/credentials remain unchanged. IME/other layouts, Num Lock and fractional scaling remain untested. This does not approve replacing production Qt Centaur.

The app remained anchored at its initial position when resizing the host. Experimental viewport work at `6154f42` addresses that by keeping the compositor stage fixed and applying an independent centred allocation transform, with 50/75/100/125/150% (100% default), Fit, middle-drag panning, Centre and canvas clipping/shadow. At immutable `90dad3a`, [ARM64 native CI](https://github.com/mattatgit/Centaur/actions/runs/41965950586) passed actual screenshot positioning, unchanged logical app dimensions, all six zoom modes with click/text/selection/drag/scroll/popup/dialog interaction, panning, Fit after resize, clipboard both ways, three restarts and clean shutdown. Six local tests and workflow/shell checks also pass. The exact build is published to the signed cache, with all 303 runtime paths verified through an empty-store download with builders disabled. The owner subsequently reported the `90dad3a` VM centring/scaling pass, with slider endpoint capture and dialog-shadow appearance noted for follow-up; see the detailed hands-on record. See [the migration record](GTK4_MIGRATION.md).


## GTK4 Phase 3 implementation (5 November 2026)

The separate `gtk4-preview` package now contains a native GTK4 frontend and GTK4 app-generation path using the retained coordination/network/OMP service. It includes projects, chat, Interact/Build, drawing/Undo/grid, invitations, the tested scaling viewport, typed GTK bundles, native construction checks and exact checkpoint restoration. Default test data is separate from normal Qt Centaur. See [the migration evidence](GTK4_MIGRATION.md) and [project format](GTK4_PROJECT_FORMAT.md). Production adoption, physical remote-client acceptance and live OMP testing of the new GTK generation path remain acceptance work.

At immutable **`e082a94`**, [native ARM64 integration CI](https://github.com/mattatgit/Centaur/actions/runs/41980178912) passed project creation/embedding, two isolated profiles with invitation/join and attributed chat, Build-mode drawing/Undo, guest-originated agent changes and canvas-image transfer, automatic compatible changes, conflict-only agreement, invalid-source preservation, exact history restore, project reopening and clean shutdown. The fixture-agent result is not live OMP/provider acceptance. Screenshots were inspected. The full development package is published to the signed cache, with all **531 runtime paths** verified by an empty-store download with builders disabled. Exact source, package path and artifacts are recorded in [the migration evidence](GTK4_MIGRATION.md). The next step is hands-on testing of this first integrated GTK frontend on the ARM64 VM, via Centaur Install; existing Qt profiles/data/credentials remain unchanged.
