# Import diagnostic agent: architecture review

16 November 2026. Phase 1 review of `codex/gtk4-migration` at `c1522bd`.
The owner's Architecture + Design handoff establishes the product direction;
the transport, sandbox and schemas below are engineering recommendations, not
implemented capabilities. No new runtime or release accompanies this review.

## Recommendation

Extend the existing authoritative host with a typed import tool broker. Keep
OMP's general tools disabled. Initially connect the broker through Centaur's
existing JSON request/continuation contract; a second listening service or an
OMP RPC migration is unnecessary for read-only inspection. Keep policy separate
from transport so RPC host tools can use the same broker later.

The first useful increment is bounded directory browsing, file reads and literal
search, recorded source/Git facts, structured failures delivered to the agent,
and bounded recovery through existing deterministic import operations. It does
not require running imported code, interpreting build files or enabling a shell.

Evaluate Bubblewrap plus systemd user-service resource controls before adding
commands. Refuse execution when isolation is unavailable. Repair/build support
is a subsequent milestone, not an automatic consequence of inspection.

## What exists

| Component | Inspected behaviour | Consequence |
| --- | --- | --- |
| `src/agent.cpp` | Runs OMP in print/JSON mode, with `--no-tools`, `--no-skills`, `--no-rules`, `--no-extensions`, `--no-lsp` and `--no-session`. Parses a final structured reply; bounds output and time. | The model cannot currently launch terminal tools. Centaur interprets requests. OMP remains a trusted host process with its existing provider credentials. |
| `src/session.cpp` | Serialises agent work, persists requests, checks epochs, mediates conflicts and validates generated apps before acceptance. An import `inspect` reply invokes the host worker and queues a continuation. | Reuse this authority and queue. Tool results must not become an alternate route to accepted app changes. |
| `src/session_import.cpp` | Owns import jobs, source settings, attempt directories and local diagnostics. Acquisition failure becomes a chat error and a failed import; it does not queue the agent with that failure. | Failures before a source copy exists currently stop the investigation. |
| `gtk4/embedding/source_import.py` | Deterministic URL/ref resolution, selected-branch verification, bounded copying, separate bare history, safe file excerpts and adaptation staging. No project build, package installation or source execution during inspection. | Retain acquisition in application code; do not ask the model to reproduce Git commands. |
| Current inspection | Initial inventory of up to 1,500 paths, manifest-first excerpts, up to 12 reads per round and eight rounds. Source and adaptation have separate contexts. | Useful foundation, but no paginated directory listing, search or line-range reads. The heuristic cannot discover every framework or app. |
| Current Git failures | Bounded transient retries; local redacted operation/category/exit/attempt/detail diagnostics. Raw stderr is excluded from model context and collaboration. | Preserve that privacy boundary. Add a deliberately smaller structured model-facing failure, rather than forwarding the log. |
| Restart and collaboration | Source settings/queues survive restart; interrupted copy/inspection is marked interrupted. Private `importLocal` is removed from shared snapshots and model requests. | Persist broker progress privately and publish only safe findings. Restart must recheck permissions and stale results. |
| Local sources | Projects imports use the initiating machine's local host. Remote source paths are rejected. | There is no guest-to-host folder transfer protocol to reuse. Do not treat a remote absolute path as host authority. |

Imported source, staged adaptations and accepted previews already have separate
locations. They are not yet an OS-isolated execution workspace. Run preview
still executes native code with the user's permissions; this review does not
change that behaviour or claim preview sandboxing.

The last directly observed VM version is `0.4.0-preview+dbadb0c`. The published
signed build is `0.4.0-preview+aa64982`; **Centaur Install** has no owner
confirmation of that update yet. During this review UTM displayed “Display
output is not active”, so installed OMP features and kernel/cgroup capabilities
were not verified. No macOS runtime tests were substituted.

## OMP facilities and connection choice

Upstream was inspected at
[`61311abb5abad892ce4e62dbd78fe06791f20ae8`](https://github.com/can1357/oh-my-pi/commit/61311abb5abad892ce4e62dbd78fe06791f20ae8).
That is research evidence, not the installed VM's version.

- [RPC host tools](https://github.com/can1357/oh-my-pi/blob/61311abb5abad892ce4e62dbd78fe06791f20ae8/docs/rpc.md) let an embedding host register schemas with `set_host_tools`, receive `host_tool_call`/cancellation frames, and return results. Centaur could supply the broker behind this transport without giving OMP filesystem or command authority.
- The [SDK](https://github.com/can1357/oh-my-pi/blob/61311abb5abad892ce4e62dbd78fe06791f20ae8/docs/sdk.md) supports custom tools and restricted sessions. `toolNames` alone is not an allowlist: SDK use needs `restrictToolNames`, with explicit restricted custom-tool opt-in. This would add a JS/SDK integration to the existing C++ adapter.
- [Extensions](https://github.com/can1357/oh-my-pi/blob/61311abb5abad892ce4e62dbd78fe06791f20ae8/docs/extensions.md) and [custom tools](https://github.com/can1357/oh-my-pi/blob/61311abb5abad892ce4e62dbd78fe06791f20ae8/docs/custom-tools.md) can execute host code. Their registration and approval hooks are not an OS sandbox or Centaur project authorisation.

Keep the current adapter for Phase 2. It already supports the required sequence:
model proposes a typed operation, coordinator validates it, worker returns a
bounded result, coordinator persists it, model continues. This avoids coupling
the first improvement to an OMP upgrade or reworking the queue/conflict pipeline.

Before any RPC migration, probe the installed runtime in a temporary project,
verify host-tool registration/cancellation and built-in-tool exclusion, pin a
supported minimum version, and retain fail-closed behaviour for older runtimes.
RPC would change transport and cancellation handling, not permission policy.

## Broker ownership and data contract

`Session` owns policy and dispatch. A separate import-diagnostics module
implements bounded operations, using host-chosen roots. The model supplies
relative selectors only; it cannot supply a root, executable, environment,
credential, shell string or permission grant.

Bind every action to project ID, import attempt/storage ID, epoch, request ID and
operation ID. Check them at dispatch and before accepting results, for **all**
modes. Currently only stage/bundle results have an explicit epoch check;
acquisition and reads need attempt-aware stale-result handling too. Ignore late
completions after source changes, cancellation or project removal.

Suggested result envelope: `schemaVersion`, `operationId`, `operation`, `scope`,
`ok`, `data`, `error`, `truncated`, and a host-generated continuation cursor.
`error` contains a stable code/category, failed stage, exit status when relevant,
attempt count, retry eligibility and `sourceAvailable`. Distinguish “not copied”
from “missing in the selected source”, “not inspected” and “omitted by policy”.
Never infer absence from a truncated inventory.

Store bounded action summaries/results under private `importLocal` state;
keep detailed redacted stdout/stderr in the owner-only diagnostic log. The model
gets the typed result and only authorised source excerpts. Shared progress gets
short findings, selected source identity and questions, without host paths,
credential-helper output, raw errors, local configuration or provider secrets.
Imported instructions and tool output remain untrusted evidence. Prompt rules
help reasoning; independent broker checks enforce authority.

## Smallest useful Phase 2

| Operation | Automatic scope and limits |
| --- | --- |
| `list` | Deterministically sorted directory entries under source/adaptation; paginated results and explicit truncation. No traversal into excluded or symlink directories. |
| `read` | Bounded relative files and line ranges, with returned line numbers, truncation and omission reasons. Retain binary/secret filtering. |
| `search` | Literal text only initially, with bounded files, bytes, matches, line length and elapsed time. No model-supplied regular expressions or external search process. |
| `source_facts` | Host-recorded provenance, selected ref/commit/directory, copy limits/omissions, observed branch list and any safely captured local Git facts, labelled by time and availability. No fabricated working-tree status. |
| `diagnostics` | Bounded structured failures and action summaries, including acquisition failures when there is no readable source yet. |
| `retry` | A host-validated request for a known deterministic operation, only within original source/ref authorisation and a persisted retry budget. Never an arbitrary command or changed source path. |

Use one path resolver and secret policy for listing, reads and search. Validate
request types/lengths and reject absolute paths, `..`, NULs, symlinks, special
files and escapes. Resolve/open without following links and check file identity
through descriptors; string prefix/resolve checks alone do not protect against
replacement races. Do not expose `.centaur`, history configuration or unrelated
parents. Escape control characters and bound output before JSON or prompts.

Treat source as a broker-read-only snapshot. Repairs eventually use a **new**
preparation copy, retaining the imported snapshot and provenance; generated GTK
bundles/adaptations remain separate. No tool writes the original folder or Git
remote. Capture selected local working bytes and Git facts consistently or label
them as a changing-source observation. Git worktree `.git` files and unavailable
history need an explicit unsupported/unavailable result, never traversal to an
external Git directory. The first increment can return recorded Git facts;
complete history inspection follows as a fixed, neutral Git operation.

Retain current acquisition limits. Suggested new-tool ceilings are 200 directory
entries/page, 12 files/read, 24 KB/file, 96 KB/result, 100 search matches and a
short worker deadline. Bound persisted context and total actions per
investigation too. Return “limit reached” with a narrower next step rather than
restarting the model indefinitely. Exact ceilings need ARM64 measurements.

## Failure and recovery workflow

Persist a structured failure before queuing investigation, even if acquisition
never produced files. The model sees `sourceAvailable: false`; listing a
nonexistent copy returns that fact without host fallback. Use a short message
such as “I couldn't copy the source. I'm checking what happened.” Do not stream
logs into chat.

Retain original source settings privately. Retry acquisition, inspection or
preparation as appropriate; repeating inspection must not recopy the source.
Acquisition retries use fresh staging and publish only a complete verified
snapshot. Preserve previous attempts, adaptations, conversation and accepted app.
The agent cannot silently change branch, folder, URL or commit policy; a genuine
choice uses the existing composer and deterministic source controls.

Persist retry counters and evidence fingerprints across model rounds/restarts.
Count existing worker transient attempts toward an overall budget; do not
multiply three worker retries by eight agent rounds. An automatic retry may use
a fresh bounded connection check as new evidence, within that budget. Repeated
auth/certificate/path/ref failures with unchanged evidence pause for the relevant
user decision or environment correction. Never ask for tokens in chat, disable
TLS checks, change DNS or invoke an interactive credential helper as an agent
diagnostic. Existing deterministic acquisition can retain its authorised use of
the importing account's Git access.

On restart, retain completed observations/questions, mark in-flight work
interrupted and revalidate attempt/capabilities before resuming. Do not replay
a build, dependency download or future approval automatically. Keep ordinary
conversation usable. Add explicit import-response states to composer routing so
a failed acquisition can receive an answer without an incidental `@` mention or
bypassing the queue.

## Phase 3 isolation recommendation

Use packaged, pinned Bubblewrap as the filesystem/process boundary, launched by
the host in a bounded transient systemd user service. This candidate design
requires a VM probe and adversarial tests; it is not validated isolation. The
[Bubblewrap project](https://github.com/containers/bubblewrap/blob/main/README.md)
leaves policy to its caller.

Construct an empty root with only the selected read-only source and required
runtime closure mounted. Use private PID/IPC/user/network namespaces, minimal
devices/proc, empty temporary home, cleared environment, closed inherited
descriptors and a new session. Exclude host home, Centaur/OMP state, user sockets,
D-Bus, SSH agent, Nix daemon socket and the host root. Default to no network.
Future repairs get a separate writable copy. Apply an ARM64-tested seccomp
policy before enabling untrusted execution.

Use [systemd resource controls](https://github.com/systemd/systemd/blob/main/man/systemd.resource-control.xml)
for memory, task and CPU limits, plus bounded runtime/output and
[control-group termination](https://github.com/systemd/systemd/blob/main/man/systemd.kill.xml)
for descendants. Verify effective cgroup controls; a timeout/process group alone
does not contain daemonised children, memory exhaustion or fork bombs. Budget
disk/temp writes too: memory and per-file limits do not bound total disk use.
A quota-backed or size-limited scratch area with controlled export is required
before general builds.

Start with fixed operations and trusted executable paths: bounded Git facts and
compiler/runtime version probes. Clear Git configuration/env, disable hooks,
fsmonitor, pagers, external diff/textconv and credential helpers; avoid reading
original repository configuration. Use only managed object data and host-chosen
arguments. “Git diagnostic” is not permission for arbitrary flags/fetches/hooks.

Do not classify `cargo metadata`, `npm install`, `make -n`, language imports,
project scripts, Nix evaluation/development shells or builds as static inspection.
[Nix develop](https://nix.dev/manual/nix/2.34/command-ref/new-cli/nix3-develop.html)
provides a build environment and can run phases; it is not this isolation
boundary. Nix-backed preparation needs a separate dependency/store design rather
than exposing the host daemon and credentials to project code.

Refuse execution if namespaces, resource delegation, scratch limits or policy
cannot be established. Never fall back to ordinary `QProcess`. Phase 2 needs no
root helper, VM security changes or machine-wide installation.

## Repairs, collaboration and remaining choices

Repair proposals stay separate from accepted app source. Preserve conflict
identification, affected-author agreement, epoch checks, GTK validation, invalid
output recovery and additive Git checkpoints. Future build outputs must pass
bounded export/validation; do not import arbitrary symlinks, sockets or build
directories into trusted state.

Future elevated approval must be host-verifiable and bound to authenticated
author, project/attempt, exact action, writable scope, network policy and expiry.
A model saying “approved”, imported text or an unrelated collaborator's “yes”
cannot grant it. Use the composer with a persisted pending action; define
local-owner versus collaborator authority before enabling elevated actions.

| Open choice | Required evidence or decision |
| --- | --- |
| Installed OMP compatibility | Actual VM version/capability probe. Upstream documentation alone is insufficient for RPC adoption. |
| ARM64 sandbox support | Prove user namespaces, cgroup delegation, effective controls, cancellation and fail-closed behaviour under UTM/GNOME. |
| Dependencies/network | Define exact download grants, offline caches, quota/store ownership and egress policy. No inherited credentials or blanket internet shell. |
| Guest-selected folders | Retain local-owner import until a bounded selected-source transfer protocol exists with provenance, authentication and size checks. |
| Output formats | Inspection can identify any framework. This adds no Rust/Nix execution or preview backend; ask which app to prepare and preserve GTK4 output policy. |
| Live reasoning quality | Demonstrate useful investigation, app selection and recovery with the configured OMP/provider. Fixture-agent success is insufficient. |

## Incremental delivery and verification

1. **Phase 1: this review.** Source/primary-document inspection only; no sandbox,
   live-agent or new runtime test claim.
2. **Phase 2a: inspection broker.** Typed schema, bounded list/read/search/facts,
   common path policy, private action state, stale-result checks and adapter
   continuations. No new executable tool capability.
3. **Phase 2b: diagnostic recovery.** Model-facing failures, failure-before-copy
   handling, persisted budgets, narrow deterministic retry and composer/restart
   handling. Preserve source settings and previous work.
4. **Phase 3: isolation proof, then fixed commands.** Do not enable command
   execution before filesystem/credential/network/process/resource tests pass.
5. **Phase 4: preparation/repairs.** Add writable copies, export checks, scoped
   approvals and dependency/build policy after the isolation milestone.
6. **Phase 5: integration.** Retain native import/collaboration/validation/update
   checks and demonstrate real-agent behaviour across varied sources.

Automated coverage should include GTK4, web, multiple app roots, missing
dependencies, multiple/invalid refs, unfamiliar local manifests, incomplete
configuration and hostile build scripts. Phase 2 must inspect hostile scripts as
data and prove they never run. Boundary cases include traversal, symlink swaps,
special files, secrets in paths/content/output, output/deadline limits, duplicate
actions, stale completions, restart, original-file hashes and prompt injection.
Command-phase coverage additionally includes process trees, unavailable sandbox,
socket/credential denial, quotas and approval spoofing. Existing core/network/
GTK validation and invalid-output recovery checks remain required.

Run product tests only on ARM64 NixOS under UTM. Keep machine-specific installation
instructions and hands-on acceptance in **Centaur Install**, with live-agent
observations separate from fixture results. Publish runtime changes only after
verification through the existing tested, signed Cachix workflow. This
documentation-only increment requires source/link checks, not an app build.
