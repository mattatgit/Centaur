# Pass 1: agent progress and timeout diagnostics

Baseline: signed GTK4 `0.4.0-preview+7a94994`. Engineering runtime tests use only
ARM64 NixOS under UTM; installation and owner acceptance remain in Installer
(Centaur Install). No preview is activated on the owner's profile.

## Investigation before changes

The owner PTT request was recorded at `2026-11-17T23:29:42.002Z`; the timeout
message followed at `23:32:54.367Z`. The project reports
`openai-codex/gpt-6.1-sol`, Landline `linux-nix` commit
`205fc1185335dc1c85b359af7673f6e5d7653222`, with its preview already active.
The VM uses OMP `18.12.6`. This read-only inspection did not change project data
or credentials. The historical project has no persisted intermediate-event
telemetry, so the provider's exact state at that failure is not recoverable from
the existing timeout text alone.

`Agent` imposes an absolute 180,000ms timer for each OMP invocation. Its literal
timeout message matches the owner's error. It reads JSONL stdout but ignores
`message_update` and retry events, retains only completed assistant text/model,
does not drain stderr, and kills only the immediate QProcess on timeout/cancel.
It parses proposals after process exit; it cannot itself apply a proposal.

OMP's [print-mode implementation](https://github.com/can1357/oh-my-pi/blob/61311abb5abad892ce4e62dbd78fe06791f20ae8/packages/coding-agent/src/modes/print-mode.ts)
emits intermediate events in `--mode json`, including incremental message events.
It can also wait for idle/advisor work and disposal after the main response.
New diagnostics must distinguish those observed phases without exposing message
deltas, thinking, errors containing secrets, or raw provider payloads. Progress
must come from actual events or accurately labelled waiting information.

The deadline will remain bounded; this pass does not extend it to conceal a
failure. The activity entry will be part of the scrolling conversation, updated
in place and correlated with its request/run. Source-unchanged assertions require
an actual source comparison. Detailed safe failure information must be available
inside Centaur rather than requiring terminal logs.

## Deferred Pass 2 design record

- The updater icon's four states, animated ring and version chip follow Figma.
  **Clicking an available update opens the restart-warning modal first. The
  update starts only after explicit confirmation; the owner may defer it.**
- Hide the chat scrollbar except while scrolling.
- Attach the comment pointer to the composer's top-right corner.
- Keep 24px project-thumbnail inset where possible without image distortion.
- Review the working animation's slight opacity flash separately. Preserve its
  original artwork and current animation during this progress pass.

## Implemented behaviour

The working tile is a child of the chronological message list, anchored when the
logical request starts. It keeps the original animation/widget across progress
and concurrent human messages. Host inspection continuations reuse the logical
request while each OMP invocation receives a distinct run ID. Activity is
ephemeral host state, also sent to collaborators; it is never saved as a series
of chat messages. Completion, failure, cancellation and known disconnection
remove the activity. Run-qualified callbacks reject obsolete results.

Captions describe observed lifecycle events: starting, waiting, preparing or
receiving a response, retrying and finishing. Import captions identify the actual
broker operation, and validation is shown only while the native checker runs.
After 60 seconds the tile includes elapsed time; a quiet response becomes
“Still waiting for the agent…” without claiming a stall or disconnection.
Following the conversation survives asynchronous GTK layout, while native wheel,
keyboard and scrollbar input preserve the position of a reader further up.

The 180-second per-invocation deadline is unchanged. Standard error is drained
and counted without retaining its contents. A separate process session allows
timeout/cancellation to terminate the invocation's process group. Safe metadata
distinguishes Centaur's response deadline, a deadline after `agent_end`, startup,
exit, invalid response, output limit and OMP-reported error. It records the
request/run, selected or reported model, elapsed time, last observed phase/event,
event/update/retry counts and channel byte counts. It cannot determine a
provider's internal state from a quiet pipe.

Failures have an in-app **Request details** action with selectable/copyable
metadata. Raw deltas, private thinking, stderr and provider error text never
enter activity, shared history or the details report. The coordinator compares
the authoritative saved app source before/after the logical request; it claims
“Your saved app is unchanged” only when that comparison succeeds and matches.
General terminal access and the fixed diagnostic sandbox policy are unchanged.

## Real-agent investigation and remaining uncertainty

A read-only OMP connection probe on ARM64 NixOS used the same print-mode/no-tool
flags and `openai-codex/gpt-6.1-sol`, in a disposable directory with the existing
login. Startup/turn events arrived within 0.34 seconds, incremental response
events began at 2.58 seconds, and the final answer/`agent_end`/clean exit arrived
around 66 seconds. Only event names, timing, counts and the expected-answer
boolean were retained; no provider transcript was exported.

This establishes that the installed integration can authenticate, select that
model and stream progress. The historical timeout's terminating layer is
Centaur's fixed invocation timer. Whether the original PTT response was still
generating, waiting on its provider, retrying, or waiting for OMP shutdown remains
unknown because the old build did not retain lifecycle telemetry. This pass
makes those future observations available; it does not claim to repair an
unproven provider fault or guarantee that every request finishes within the
existing limit.

The real OMP integration also passed through Centaur's native UI in a disposable
project: waiting changed to receiving a response, the informational answer
completed in 2.61 seconds, the animation stopped, and saved source/revision
remained unchanged. No login/logout, credential copying or model-setting writes
were performed.

## Engineering verification

[Curated ARM64 NixOS UTM evidence](evidence/gtk4-agent-progress-2026-11-18/manifest.json)
records all 29 native product checks, 94 Python tests with the actual packaged
sandbox and zero skips, all three service suites, and 19 embedding checks.
The native checks exercise one chronological tile, genuine processing/text/retry
events, stable widget and animation identity, no progress-message clutter,
natural scrolling, reader-position retention during concurrent chat/completion,
safe failure details copied through the focused app, Stop and immediate recovery.
Existing collaboration, conflicts, restoration, drawings, settings and real
Landline `linux-nix` source/commit checks also pass.

Short programmatic test deadlines exercise quiet waiting, active streaming and
post-`agent_end` shutdown separately. They verify the terminating layer, bounded
cleanup of the process group, a subsequent request, and unchanged-source claims
both with and without an external source change. The production deadline has no
new environment override. Public reports exclude secret canaries and thinking.

The full native run uses candidate 8; candidate 9 only makes the two generic file
captions scope-neutral and updates their Python expectation. The real UI probe
uses the same runtime before a checker-only native pointer-acknowledgement fix.
The final immutable release is also gated by both existing ARM64 workflows.
The VM's intermittent GitHub resolver problem still requires a disposable Git
DNS fixture for functional import tests, with normal HTTPS verification; neither
the product nor the owner's Git/network settings receive that override.

Signed-release metadata and the Installer handoff follow publication. Engineering
success does not mark the owner's acceptance complete.
