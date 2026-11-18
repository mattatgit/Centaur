# Centaur GTK4 — V2 completion and polish

This pass implements the eleven-item Pass 2 handoff against owner-accepted
`0.4.0-preview+eb38227`. Project-sharing UX and generated Landline icon
alignment remain outside this change. Installation and hands-on acceptance
belong in Installer / Centaur Install; engineering verification does not mark
owner acceptance complete.

Published signed preview: **`0.4.0-preview+4144bb8`**, immutable source
`4144bb82a8c93724e94f88fc405d087aa7c4f80b`.
Both [product/update](https://github.com/mattatgit/Centaur/actions/runs/44261678103)
and [embedding](https://github.com/mattatgit/Centaur/actions/runs/44261678189)
workflows passed. The [public feed receipt](evidence/gtk4-v2-pass2-2026-11-18/ci-final/public-feed-verification.json)
confirms exact equality with the verified signed artifact, including source,
version, store path and all 613 closure paths.
The [release verification](evidence/gtk4-v2-pass2-2026-11-18/release-verification.json)
records artifact digests, test boundaries and preservation status.

## Design and implementation

The source is the original [V2 board](https://www.figma.com/design/9RnuP79pD007wjhTdXZ5WW/Centaur?node-id=43-689)
and [Create/Import waiting board](https://www.figma.com/design/9RnuP79pD007wjhTdXZ5WW/Centaur?node-id=67-3421).
The implementation uses native GTK4 widgets, the bundled Inter fonts and
original Figma artwork. No replacement SVGs were drawn.

| Item | Implementation and independent check |
| --- | --- |
| Updater | Original 16px grey, green, progress and checkmark exports (`44:1898`), right-aligned version chip (`44:1929`), and 288px restart-warning modal (`43:1327`). Both entry points require **Yes, update** before creating a transaction; **Not now** creates none. Native input checks cover all four states, keyboard access, static arrow/rotating original stroke and reduced motion. The signed updater core remains unchanged. |
| Chat scrollbar | Reserved width with opacity controlled by actual wheel, keyboard and native scrollbar input. GTK gestures observe presses without claiming the range's sequence. Unchanged message rows remain parented so arrivals preserve keyboard focus and text selection. Checks exercise wheel movement, thumb drag/hold/release, keyboard scrolling, inactivity, unchanged chat width and preserved reader position during concurrent activity. |
| Comment pointer | Tail connects at the composer's top-right rounded corner. The existing six-zoom, pane/window resize, pan, cross-boundary, send and guest synchronisation checks exercise the same targeting protocol. |
| Screenshots | Cached screenshots fit inside a minimum 24px inset while preserving aspect ratio. The inset contracts when a slot cannot accommodate it. Cache generation and original clay fallback remain intact; native geometry checks inspect the rendered image rectangle. |
| Working animation | Original supplied SVG and one-second timing remain unchanged. Isolated original frames use weighted additive coverage before compositing, preventing shared green pixels from becoming translucent during a crossfade. Pixel checks compare common ink at endpoints/midpoint and exercise clock playback, idle/unmap and reduced motion. |
| Source actions | A healthy imported preview no longer displays source/retry controls above the composer after an edit. Retry remains available for interrupted initial imports; **Change source**, **Open source** and, where applicable, **Open adaptation** belong to the project menu. Open source resolves to the saved `source/` directory, independently of an exported adaptation. Native import tests intercept the real directory-launch URI using a disposable file viewer. |
| Sidebar identity | Hover/press no longer paints a rectangular block. Native click, Tab/Return activation and focus indication remain. The existing “This device” caption remains; Host/Guest labels are deferred. |
| Card hover | Figma's 0/0/25px, 12% black shadow (`68:2477`) replaces the text-fill change. Padding lives inside the scroll viewport so leading/trailing shadows are not clipped. Pixel and geometry checks verify elevation, unchanged text fill and unchanged card bounds, alongside the existing responsive grid checks. |
| Window close | Original `78a93.svg`, white default artwork and grey hover artwork; GTK retains the real close action and full rectangular 32px target. Native tests include eight outer target points, hover, disabled/inactive states, platform focus policy, drag, resize, tiling and fullscreen restoration. |
| Saved badge | Figma's 127×32 header badge (`51:1601`) appears only after acknowledged changes. Initial reads and unchanged values do not manufacture success; pending and failed saves retain their own status. A ten-second display resets after another save, followed by a 400ms frame-clock fade, with reduced-motion support. |
| Waiting panels | Both operations use the original `dc3c7.png` and `f83cd.svg` in a 304×256 panel centred in the full canvas, with the original 128px illustration, exact headings and supporting text. Panels appear only during real work and resolve on completion, question, cancellation or failure. The chronological chat activity tile stays independent. |

The three added icon exports and exact source-node/hash records are in
`assets/figma/v2/pass2/source-map.json`. All 64 earlier V2 exports and the
owner-supplied animation retain their original hashes. The animation SHA-256 is
`b976ac19686b3c3c59d29291fb9a9a1bf7b43f74464270d6cbb2c3c68234f78c`.

The progress icon rotates only the original SVG's named `stroke` layer;
[librsvg's layer renderer](https://gnome.pages.gitlab.gnome.org/librsvg/Rsvg-2.0/method.Handle.render_layer.html)
retains document coordinates. The working animation follows the supplied
one-second SVG rather than the older illustrative two-second chat animation
embedded in the waiting board.

## Create prompt and lifecycle

The Create form previously stored its Prompt as a description without sending
it to the agent. The owner explicitly approved using that prompt to create the
app. Non-empty GTK Create prompts now enter the existing addressed-message
queue exactly once. A persisted `creationPending` flag prevents execution of
the starter while the requested app is being made. It clears only after normal
native validation and source application succeed. Cancellation, failure and
questions preserve the project and allow an ordinary agent-message retry.
An empty prompt retains the existing starter behaviour. Qt creation is unchanged.

The agent's focused-edit protocol remains in force for existing apps. Initial
creation requests can return a complete first bundle; normal edits still use
source-hash-bound changes. The absolute 180-second per-response deadline,
cancellation, broker bounds, validation and conflict handling remain intact.
General model terminal access is disabled.

## Engineering evidence

Engineering runs use disposable profiles and isolated Wayland sessions inside
the ARM64 NixOS UTM VM. The standard regression driver also checks collaboration,
history/conflicts, cancellation, imports, native application execution and
responsive layouts. Release checks run through the existing ARM64 signed-cache
workflow, including the real updater before the update is advertised.

A real `openai-codex/gpt-6.1-sol` Create request produced a small counter app and
mapped its native preview in **17.98 seconds**, with one submitted prompt,
observable progress, no failure diagnostics and no remaining waiting panel.
A real edit to a private copy of the accepted Landline project completed in
**6.363 seconds**, using one focused `app.ui` edit; `app.py` and `style.css`
remained unchanged. Its native preview mapped with no stray composer-area
source action and with source management present in the project menu.
These are individual successful runs, not a guarantee of deterministic model
output or semantic correctness for arbitrary generated apps.
The live model runs used an earlier presentation candidate; the final
coordinator/agent C++ hashes match those runs. The final presentation uses
the deterministic native regression fixtures.

The Landline receipt's retained `brokerResults` field describes copied project
diagnostics; it does not establish a new broker operation in the title-edit
request. The current-run event/response aggregates are recorded separately.
No raw provider stream, private reasoning, credentials, owner source bundle or
owner conversation is exported in the evidence.

The VM's intermittent resolver issue is handled only in disposable regression
Git configuration, using a router-resolved IPv4 address and normal verified
GitHub HTTPS. Owner Git/DNS settings are unchanged. The existing normal-network
release CI remains required.

The final [VM receipt](evidence/gtk4-v2-pass2-2026-11-18/vm-verification.json)
records **37 product checks, 19 embedding checks and 94 Python checks with zero
skips**. All three service suites passed against matching C++ sources, as
recorded in the [source contract](evidence/gtk4-v2-pass2-2026-11-18/source-contract.json).
Workflow and shell checks passed. The final
[Landline receipt](evidence/gtk4-v2-pass2-2026-11-18/integration/landline-source-verification.json)
records `linux-nix` commit `205fc1185335dc1c85b359af7673f6e5d7653222`, independently
matched to the remote ref, with `LandlineNix/`, its Cargo manifest and Rust entry
point present. macOS Swift files are also present on that same verified branch.

One intermediate disposable-input run missed a guest drawing gesture. The
same canvas implementation passed the subsequent standard runs; no specific
product root cause is assigned to that single miss. A separate reproducible
keyboard-reader failure was fixed by retaining unchanged message widgets,
which now preserve focus, selection and position when messages arrive.

Relevant final screenshots: [updater warning](evidence/gtk4-v2-pass2-2026-11-18/footer/settings-warning.png),
[Create waiting](evidence/gtk4-v2-pass2-2026-11-18/integration/pass2-create-waiting.png),
[Import waiting](evidence/gtk4-v2-pass2-2026-11-18/integration/pass2-import-waiting.png),
[card hover](evidence/gtk4-v2-pass2-2026-11-18/integration/pass2-project-hover.png),
[saved badge](evidence/gtk4-v2-pass2-2026-11-18/integration/pass2-settings-saved.png),
[comment pointer](evidence/gtk4-v2-pass2-2026-11-18/integration/comment-100-placed.png)
and [edited import](evidence/gtk4-v2-pass2-2026-11-18/integration/pass2-imported-edit-no-stray-button.png).
The final release passed the existing signed publication gates. The exact
advertised package also passed all **12 signed updater checks** in disposable
ARM64 NixOS profiles: both entry points completed real profile switches,
restarts and startup acknowledgements. The
[final VM receipt](evidence/gtk4-v2-pass2-2026-11-18/signed-final/verification.json)
and [package comparison](evidence/gtk4-v2-pass2-2026-11-18/signed-final/package-verification.json)
record the exact version and match to verified code/original artwork.

The first release attempt's new Settings updater check clicked an App control
below the visible viewport. The gate stopped publication and the advertised
feed stayed on `eb38227`. The checker now scrolls the full Settings page before
activation. That test-only correction passed all 12 real signed updater checks
on NixOS, including separate footer and Settings transactions, against signed
candidate `22c4009`. The VM used a disposable copy of public Nix package
metadata to avoid its cold-cache lookup delay. Signature verification, the
empty-store real download check, profile switches and startup acknowledgements
were unchanged. No owner profile was activated.

## Acceptance boundary

The owner's GTK4 and Qt profiles, existing projects/conversations, collaboration
identities, OMP credentials/configuration and model settings are preserved.
No release is installed or activated on the owner's profile by this work.
Private engineering profiles and release-test fixtures are separate.

No unresolved design mismatch was observed in the final reviewed screenshots.
Native GNOME hands-on acceptance remains pending; disposable Sway evidence
does not substitute for it.

GNOME desktop interaction and visual acceptance remain in Centaur Install.
The new confirmation belongs to the new version: the accepted `eb38227`
binary starts an update directly when its existing action is clicked, so the
new warning cannot appear retroactively during that first upgrade. Acceptance
of the new available-update modal must use a genuine later update or the
disposable engineering fixture; the owner feed must not be fabricated.
