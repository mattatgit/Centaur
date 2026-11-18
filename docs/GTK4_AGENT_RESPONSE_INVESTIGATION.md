# Long-running GTK agent response investigation

18 November 2026. Investigation work on `codex/agent-response-investigation`
was tested only on ARM64 NixOS under UTM. It is now published as signed preview
**`0.4.0-preview+eb38227`** after exact-source ARM64 release CI. No release was
installed or activated on the owner's VM. Installation and hands-on acceptance
remain in Installer (Centaur Install). Pass 2 visual refinements remain deferred.

## Established cause and attribution

Centaur's existing response contract required a complete three-file GTK bundle
for an ordinary edit. A disposable reproduction of the owner's PTT request,
using the installed `31220c4` service, OMP `18.12.6` and
`openai-codex/gpt-6.1-sol`, continuously emitted that replacement until Centaur's
180-second deadline terminated it. The response reached `app.py` at 28.636s,
`app.ui` at 81.254s and `style.css` at 170.227s, without completing the JSON.
There was one OMP turn, no OMP tool execution, no retry and no broker inspection
cycle. This establishes an unnecessarily expensive Centaur output contract as
the reproduced bottleneck. There was no observed tool loop or stalled pipe.

The 1,176,724 bytes counted by Centaur were JSON event-stream bytes, including
framing and echoed messages. The observer's last safe sample at 179.169s held
32,060 answer-text bytes, 8,169 text deltas and eight private-processing deltas.
It did not retain private reasoning or raw provider output. Chunk counts are
not token counts. Streaming activity alone did not establish useful progress.

The input was also unnecessarily large. The current app was 31,411 bytes, but
the reproduced prompt was 152,527 bytes: acquisition context occupied 74,404
bytes and historical diagnostic context roughly 27 KB. Most acquisition
excerpts were macOS Swift files in the correct mixed repository. The saved
import was `linux-nix` at `205fc1185335dc1c85b359af7673f6e5d7653222`, with
`LandlineNix/` and its original artwork present. Mac files did not establish a
wrong-branch import.

The owner's historical prompt was 150,400 bytes. This reproduction preserved
the app and selected project context but used a new private project ID and Git
baseline, and included subsequent conversation state. It was not a byte-exact
replay of that historical payload. The original incomplete response was not
retained, so its exact content and provider-internal behaviour remain unknown.
The reproduced protocol problem is proven; an upstream provider fault in the
original run is not established.

## Changes

Ordinary GTK edits can return a bounded `patch` response instead of repeating
unchanged files. Each patch names the SHA-256 of the exact current bundle and
contains 1–12 ordered, unique exact-text replacements in `app.py`, `app.ui` or
`style.css`. Unknown fields, unsafe filenames, stale hashes, missing or
ambiguous matches, no-ops and oversized changes are rejected. Reconstruction
is atomic and then follows the existing native validation and contributor
conflict/agreement path. Full proposals remain available for new apps and
actual wholesale replacements. This adds no command execution or filesystem
tool to the model.

For an imported GTK app with a ready preview, the prompt retains the current
bundle, conversation, decisions, source inventory and import facts. It omits
acquisition-time excerpts, historical broker results and public failure
metadata attached to older messages. Current-request broker evidence remains
available across continuations, correlated by the logical request ID and
bounded by the existing result limits. Stored conversations, source copies
and diagnostic history are not rewritten. Before-preview import context is
unchanged.

The working tile can now report an actual microphone-artwork read and reception
of a focused change. The latter requires an anchored protocol header; arbitrary
model text and reasoning cannot become a status caption. Request details
separate JSON event-stream bytes from answer bytes and include safe text,
private-processing, turn and tool counters, without exposing their contents.

The absolute **180-second per-OMP-response limit remains**. A precise Qt timer
avoids early coarse-timer expiry. Activity does not reset the deadline; Stop
and process-group cleanup remain bounded. The fix reduces unnecessary work
rather than extending execution. Large first-time app generation can still
reach the limit and would need a separately justified policy change.

## Useful completion, including a rejected intermediate result

The first patch candidate completed in 73.101s and passed native construction,
but physical interaction testing caught incorrect generated behaviour: it
connected `Gtk.GestureClick::stopped` to the release handler, returning the
button to red about 400ms into a continued hold. A passive native event trace
distinguished that callback from the actual release. GTK documents that
[`stopped`](https://docs.gtk.org/gtk4/signal.GestureClick.stopped.html) can occur
when click-count time/distance thresholds expire, including between press and
[`released`](https://docs.gtk.org/gtk4/signal.GestureClick.released.html).

Generic GTK guidance now distinguishes those signals and requires reuse of
repository SVG bytes. Two fresh model runs completed the original request in
**60.577s and 73.210s**, including the broker's original `mic_on.svg` read. Their
initial prompts were 56,158 bytes and their follow-up prompts 58,387 bytes. The
final patch answers were 4,001 and 4,628 bytes. Each changed revision 3 to 4,
preserved `app.ui` exactly and used three edits across Python and CSS. There
were no OMP retries or native OMP tool executions.

Both unmodified generated results passed native physical input checks in a
private compositor: red/muted at rest, green with the original mic-on artwork
at 400ms and after 1.2 seconds of continued hold, then red on release inside
and outside the button. The exact original SVG bytes were embedded. No manual
app-code correction was used to obtain these passes. This proves useful
completion for two fresh runs, not deterministic success for every model task.

| At rest | Held past the click threshold |
|---|---|
| ![Red muted PTT](evidence/gtk4-agent-response-2026-11-18/native-final/ptt-idle-button.png) | ![Green mic-on PTT](evidence/gtk4-agent-response-2026-11-18/native-final/ptt-still-held-button.png) |

## Verification and preservation

[Curated evidence](evidence/gtk4-agent-response-2026-11-18/manifest.json) records
the baseline, successful requests, native interaction and exact tested source
hashes. The final candidate passed 29 product checks, 19 embedding checks and
94 Python checks with the actual packaged sandbox and zero skips. All three
service suites passed with the final C++ source. Tests cover stale/ambiguous
and atomic patch handling, preserved context, normal conflict agreement,
timeout/cancellation recovery and metadata privacy.

The full native regression initially exposed a test-harness race: Enter could
precede asynchronous clipboard paste. The checker now waits for a test-only
draft hash receipt before posting. It then verifies the exact stored message.
No normal editor or clipboard behaviour changed. Candidate 3 contains that
checker fix; its C++ service source is identical to candidate 2. The reusable
probe scripts received later safety/launcher fixes and were exercised in the
VM separately; their exact final hashes are recorded.

All runtime work used ARM64 NixOS under UTM, private XDG profiles and disposable
project copies. The functional GitHub import regression used a private Git DNS
fixture for the VM's known intermittent resolver problem, with normal verified
HTTPS. No owner DNS or Git setting changed. Owner app and state hashes were
verified unchanged after every real request and at cleanup. Existing model
settings, OMP configuration/credentials, identities and the separate Qt
installation were preserved. General model terminal access remains disabled.
All 64 original V2 asset hashes and the owner's animation hash still match.

Only aggregate lifecycle/shape metadata and cropped PTT images are exported.
Private project copies remain local to disposable VM storage until cleanup;
no source bundle, conversation, credentials or raw reasoning is included in
the evidence. Reusable engineering probes are
`scripts/investigate-agent-edit.py`, `scripts/observe-omp-stream.py` and
`scripts/check-ptt-interaction.py` with `scripts/ptt-probe-app.py`. Their CLI
help describes required built-package/disposable-compositor inputs; these are
engineering checks, not installation instructions.

The investigation did not publish or activate a release. The subsequent signed
publication is recorded below. Automated engineering success does not change
the owner's partially verified concurrent-message tile-position result from
Pass 1. Further installation and acceptance belong in Centaur Install.

## Signed release — 18 November 2026

The owner subsequently authorised publication of the verified fix. Immutable
source **`eb382277e3dd84dab6fc6d555341569462a5c32f`** merges investigation commit
`1becefc670c73ecf91b3c5e0583b6352ba67c0b9` with remote main
`12e677d564011bd3a2dcf2c15ebd1a2f7e12d3e0`. `README.md` is the only difference
from the tested investigation commit; its separate change is preserved. All
recorded final UTM code/script hashes still match. The published version is
**Centaur GTK4 `0.4.0-preview+eb38227`**, store
`/nix/store/w3ay72cqv9ybwghg5v3yc75kqj28dqbr-centaur-gtk4-preview-0.4.0-preview`.

Both [product/update CI](https://github.com/mattatgit/Centaur/actions/runs/44232399512)
and [standalone embedding CI](https://github.com/mattatgit/Centaur/actions/runs/44232399503)
passed for that exact immutable source. They verify the retained three service
suites, 29 product checks, 19 embedding checks and all 11 real signed-updater
checks. Publication downloaded all **613 closure paths** into an empty CI store
and verified their signatures with builds disabled. All four downloaded CI
evidence archives match their GitHub artifact SHA-256 digests. An unauthenticated
read of the public update feed exactly matches the complete verified manifest,
including revision, version, store path, signing keys and timestamp.

Release CI runs on `ubuntu-24.04-arm` using the pinned Nix toolchain and private
stores/profiles. Its initial Python run reports 94 tests with one skip; the
actual packaged-sandbox check was already included in the prior 94-test,
zero-skip UTM run on identical runtime source. The real-model PTT checks belong
to that investigation, not a new model invocation against the final version
wrapper. [Release verification](evidence/gtk4-agent-response-2026-11-18/release-verification.json)
and [manifest](evidence/gtk4-agent-response-2026-11-18/release-manifest.json)
record these boundaries explicitly.

No VM commands, downloads, installations or profile activations were performed
for this publication. The prior owner installation was verified as `31220c4`;
existing projects, conversations, model settings, OMP configuration/credentials,
identities and Qt remain outside this release work. General model terminal
access stays disabled, the absolute 180-second response limit remains and Pass 2
is still deferred. Installation and hands-on acceptance stay in Centaur Install.
