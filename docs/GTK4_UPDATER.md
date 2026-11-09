# GTK4 in-app updates

The GTK4 preview has a small **App** section at the top of Settings. It shows
the running version and short commit, an **Update app** button, and inline
availability/progress/error text. Opening Settings checks once; clicking the
button checks again if necessary and installs an available update. There is no
unattended installation or separate update-management screen.

The workspace also exposes the same updater in the chat footer. Its left-aligned
version button replaces the former author/keyboard-hint text. Hovering or
keyboard-focusing it shows **Update app** without changing its width. An 8px
round badge uses the agent avatar's `#ccff00` when a verified newer publication
is available. Clicking runs the same check/download/idle-gated restart as Settings;
both actions are disabled during a check or update. Status and download MB appear
to the right, right-aligned and wrapping when necessary. Errors remain visible
there instead of requiring a switch to Settings. Routine availability/up-to-date
text stays out of the footer unless the user asks to check.

Availability is checked in the background shortly after launch and then every
15 minutes, as well as through the existing Settings action. These checks never
install automatically. A footer-initiated update restores the workspace and chat
drafts; an update from Settings restores Settings. Older resume records retain
their existing Settings fallback. The button is 24px high with the existing
small Inter version style; its circular badge is 8×8px.

While downloading, the existing inline status shows live compressed payload
bytes, for example **Downloaded 123.4 of 468.5 MB** (decimal MB, one decimal
place). Nix's remote path metadata supplies compressed sizes; an offline local
query excludes already installed objects. Only HTTP NAR transfer activities
count towards the counter, not metadata requests or uncompressed store writes.
Parallel transfers and retries are combined per NAR URL without double-counting.
Progress is written at most five times per second and the Settings view reads
it through the existing transaction status. If size metadata is unavailable,
the transferred MB still update without an invented total. Once copying ends,
the status changes to **Download complete. Verifying the update…** before the
existing signature/content checks and safe restart. Verification never counts
as additional downloaded bytes.

The helper belongs to the version that starts an update. Consequently the
download that first installs this counter still uses the previous version's
status; subsequent downloads use the live counter. This does not change the
update feed/protocol, profile activation, signature checks or recovery path.

An existing build without this feature needs one normal, precompiled update
through **Centaur Install** first. Subsequent normal updates use Settings.
That initial setup should launch through the dedicated GTK profile rather than
a shortcut pinned to an older store path; the Qt shortcut stays separate.
Current testing is ARM64 NixOS in UTM, using the existing GTK profile and Cairo
launch environment. The Air and macOS are outside this implementation.

## Installation boundary

- Branch: `codex/gtk4-migration`.
- Package: `gtk4-preview`; executable: `centaur-gtk4`.
- Dedicated profile: `~/.local/state/nix/profiles/centaur-gtk4`.
- Existing GTK data directory is passed through exactly as launched; the
  standard location is `~/.local/share/Centaur/GTK4`.
- Updater state/journal: `$XDG_STATE_HOME/centaur-gtk4-updater`, defaulting to
  `~/.local/state/centaur-gtk4-updater`. Transactions are private to the user.

The running window must belong to that dedicated profile, and the profile must
contain only the GTK4 package's programs. The updater rejects the default Qt
data paths, symlink aliases of them and a custom Qt data path recorded by the
existing Qt launcher. It does not change the preserved Qt profile, launcher,
projects or system configuration.

Existing permanent Cachix trust is a prerequisite, as in the current VM setup.
The updater never requests sudo, changes daemon trust, disables signature
verification or rebuilds NixOS. Missing trust causes a recoverable download
failure and belongs in Centaur Install's one-time setup guidance.

## Publication and discovery

The existing CI publisher uploads the complete signed closure to
`https://mattatgit-centaur.cachix.org`, downloads it into an empty store and
verifies every signature. GTK metadata additionally identifies update protocol
1, the GTK branch and the source commit timestamp.

After ordinary unit/service/native checks, signed publication and the real
in-app update acceptance test succeed, CI atomically updates the JSON body of
the public GitHub prerelease tagged **`gtk4-preview`**. This is one development
stream, not a channel selector. Clients read:

`https://api.github.com/repos/mattatgit/Centaur/releases/tags/gtk4-preview`

The body names an immutable store path and source revision. The moving branch
tip is never evaluated by the updater. An unpublished, failed, stale, wrong
architecture, wrong package or unsupported-protocol build is not offered.
Source timestamps prevent an older published build being offered as an upgrade;
identical revisions are reported as up to date.

CI needs its existing Cachix secret and the workflow's standard `GITHUB_TOKEN`
with `contents: write` for prerelease metadata. No client token or new user
credential is required. If repository policy prohibits release writes, cache
publication can succeed while discovery stays on the previous working build;
the failed publication step must be addressed before calling the update ready.

## Download, activation and recovery

1. A detached `centaur-gtk4-update` helper acquires a per-user updater lock and
   roots the existing package for recovery.
2. `nix copy` obtains the exact package from Cachix. Existing local paths get
   that cache's signatures with `nix store copy-sigs`; recursive verification
   then requires the pinned Cachix key for the entire closure. Contents and
   signatures are checked, and the executable's version must match metadata.
3. Every Nix operation disables local and remote builders, disables fallback
   builds and keeps signature verification enabled. Profile activation uses
   the existing script's proven offline `nix build --profile` mechanism on an
   already-realised store path. No source/flake evaluation is needed.
4. The window stays usable while downloading. Activation waits for requests,
   validation, queues, joins, invitations, remote outboxes, active drawing and
   pending chat submissions to finish. Unsent chat drafts are saved in the
   private restart record.
5. After the window exits, the authoritative host atomically checks again that
   it is idle and no other local window remains. It closes only on success.
   A host that cannot be contacted must also be confirmed stopped through its
   lock; uncertainty aborts the update. The helper never force-kills an agent.
6. Nix switches the GTK profile atomically. The new window starts with the same
   data path, OMP executable, desktop/rendering environment and saved drafts.
   Its background host temporarily rejects new operations until the window
   acknowledges its version, mapped window and local-service connection.
   Remote requests are disconnected without acknowledgement during this gate,
   retaining their outboxes for retry after reconnect.
7. Successful acknowledgement releases the host and records completion. A
   startup failure stops the staged instance, restores the previous profile
   generation and opens the old package. A receipt-write failure after a
   healthy host has resumed does not roll back active work.

Downloads and verification finish before closing the old window. Failure there
leaves the current profile and host untouched. External changes to the profile
during download are not overwritten. Existing project sources, conversations,
preferences, collaboration identities, credentials and OMP authentication files
are neither copied to a new data root nor edited by the helper.

Nix profile generations, a rooted previous package and `recovery.json` retain a
recovery path. If the Nix daemon fails during rollback or the helper itself is
terminated, the prior store package and transaction logs remain available. The
helper's `--recover` maintenance mode restores the recorded previous profile
without builds; use Centaur Install for exception-specific recovery guidance.
Do not remove the transaction's roots or manually delete profile generations
while recovery is needed.

This does not add persistence to arbitrary generated-app in-memory state or
introduce project-schema migrations. Those remain separate work. Updates close
and restart the embedded application, using its existing data-persistence
behaviour.

## Automated verification

Python transaction tests cover discovery/pinning, older or invalid manifests,
failed download/signature validation, busy-host refusal, profile-switch failure,
startup crash/timeout, failed release, successful rollback, failed rollback with
retained recovery records, concurrent profile changes and protection of Qt/custom
data paths. Existing installation-helper tests retain their GNU/Nix environment.

ARM64 CI also exercises real GTK Settings with an older fixture package and a
temporary HOME/profile. Only that fixture's generated launcher redirects
discovery to a local release JSON; the released application has no feed override.
The candidate is the actual signed package already published to Cachix. The
test clicks **Update app**, verifies/copies real Nix store objects, switches the
real profile, observes the new GTK process/version and checks that project,
chat, preferences and Qt sentinels remain intact. It also tests the real host's
startup token, idle gate and refusal to interrupt an active agent.

CI advertising runs only after that acceptance passes. The manifest and
screenshots identify the tested immutable build; hands-on VM results must be
recorded separately from these automated results.

## Verified build — 9 November 2026

Immutable source: `6a9300f787ff8effe3374e0ce665a62b4fe79254`.
Version: `Centaur GTK4 0.4.0-preview+6a9300f`.
Installable:
`github:mattatgit/Centaur/6a9300f787ff8effe3374e0ce665a62b4fe79254#gtk4-preview`.
Store path:
`/nix/store/lk74lyib0hmkd1hv6fhn8yflnhqvgdra-centaur-gtk4-preview-0.4.0-preview`.

[Product/update CI 42556610224](https://github.com/mattatgit/Centaur/actions/runs/42556610224)
and [embedding CI 42556610246](https://github.com/mattatgit/Centaur/actions/runs/42556610246)
passed. Updater evidence is artifact `13648150224`; product UI evidence is
`13647531789`; signed distribution metadata is `13647143362`. The updater
receipt records `phase: complete` and version `0.4.0-preview+6a9300f`; the native
summary records `passed: true`. Screenshots of availability and the restarted
Settings version/status were inspected. The final log contains no GTK warnings,
criticals or Python tracebacks.

The native test clicked the button in the older `0000000` fixture, switched a
real dedicated profile to this candidate, restarted the real GTK frontend and
restored the same project/conversation. Preferences, TLS certificates/keys,
sharing metadata, an OMP credential sentinel and the Qt profile/data sentinel
were unchanged. A separate real host verified the startup-token gate and
refused both another-window and active-agent shutdown attempts.

All 22 GTK/Python tests pass, including simulated download/signature, activation,
startup and recovery failures; the existing 21 installation-helper tests also
pass under the GNU/Nix development environment. Retained core/network/Iroh and
native product/embedding regressions passed in ARM64 CI. Failure-injection tests
use temporary profiles and subprocess doubles; the successful GUI restart uses
the real Nix store/profile and Cachix signatures. That candidate is already
realised in the CI store. Separately, publication verified a fresh download of
all **531 runtime paths** into an empty store with builders disabled and signature
checks enabled (`verifiedSignedClosureDownload: true`).

The public `gtk4-preview` prerelease body was read back and names this exact
source/path after successful acceptance. No extra user token is required;
the workflow's scoped built-in GitHub token successfully published discovery.
Hands-on acceptance for this initial build was pending at publication. No real OMP/provider request,
physical remote-client update, power-loss recovery or production replacement is
claimed by these automated results. Initial installation guidance stays in
Centaur Install; subsequent normal updates use the Settings button.

## Live download counter — verified 9 November 2026

The owner subsequently reported the `55ae238` update and canvas-boundary fixes
working on the ARM64 UTM VM. This is owner-reported hands-on acceptance, separate
from CI. The counter's hands-on review awaits a future download started from a
version containing it.

Counter source: `e48a4e088a935e1420eb5a60fbb196e865534cd1`.
Version: `Centaur GTK4 0.4.0-preview+e48a4e0`.
Store path:
`/nix/store/wvfxfgivrr6hija365b4abc8vrmi5x7a-centaur-gtk4-preview-0.4.0-preview`.
[Product/update CI 42562980792](https://github.com/mattatgit/Centaur/actions/runs/42562980792)
and [standalone embedding CI 42562980675](https://github.com/mattatgit/Centaur/actions/runs/42562980675)
passed. All 32 Python checks passed, including streamed subprocess events before
exit, parallel/retried transfers, compressed totals excluding present paths,
malformed/unknown progress, failed downloads and timeouts. Core/network/Iroh,
the two-profile drawing/arrow regressions and real Settings activation/restart
also passed.

Updater artifact `13650153592` includes a real Cachix download of a signed,
reference-free package into an empty store. Its byte counter recorded
`0 / 71848` then `71848 / 71848`, matching the compressed file size. The local
streaming test additionally observed intermediate bytes before process exit;
the same signed download on the development Mac reported `0`, `1360`, `71848`.
This checks progress transport/accounting without removing any installed path.
The GUI update candidate remains already realised in CI, as described above.

Separately, signed distribution artifact `13650263299` verifies the complete
**531-path** GTK runtime closure in an empty store with all builders disabled.
Native product evidence: `13650148570`. The public `gtk4-preview` release feed
was read back and advertises this exact source/path. No protocol or machine
configuration changes are required. Update guidance remains in Centaur Install.

## Workspace footer updater — verified 9 November 2026

Published source: `8fe72143bb0328f16a1ac2caa28aaeca2a1b03d6`, version
`Centaur GTK4 0.4.0-preview+8fe7214`.
Store path:
`/nix/store/fwf0if0nlfwi346kf7xpivnipnxw30l4-centaur-gtk4-preview-0.4.0-preview`.
[Product/update CI 42566202750](https://github.com/mattatgit/Centaur/actions/runs/42566202750)
and [standalone embedding CI 42566202804](https://github.com/mattatgit/Centaur/actions/runs/42566202804)
passed. The release feed was read back and names this exact source/path.

Updater evidence `13652080009` checks background availability from the workspace,
the badge's actual 8×8px allocation, left alignment with the composer, unchanged
button bounds on hover, native keyboard traversal, and real footer-triggered
profile activation/restart. The workspace and project/conversation return after
restart, with the availability badge cleared. Both update entry points are
disabled during the transaction. Availability, hover and running screenshots
were inspected. Footer status samples match the Settings updater's messages,
including preparation, verification and waiting for idle; the already-realised
CI candidate makes the byte-counter phase too brief to require observing it in
the GUI. The independent signed fresh-store transfer still verifies real byte
accounting, and the streamed-output Python tests verify intermediate progress.

All 32 Python checks and native product/embedding regressions passed. Native
product evidence: `13651920612`. Signed distribution evidence: `13651592456`;
the complete 531-path closure was verified in an empty store with builders
disabled. The native click helper now waits for allocation to settle after page
navigation, avoiding the stale project-card rectangle seen in the initial run.
Hands-on VM review of this footer remains pending; use Centaur Install for the
one normal Settings update that introduces it. Later updates can start from the
version button in the workspace.
