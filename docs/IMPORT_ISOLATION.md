# Import isolation proof

Phase 3 engineering verification, 16 November 2026. This follows the
[diagnostic-agent review](IMPORT_DIAGNOSTICS.md#phase-3-isolation-recommendation)
and Phase 2 read-only broker. The owner's current request is to verify the
boundary on ARM64 NixOS under UTM before enabling diagnostic commands.

## Scope

The [separate proof package](../packaging/import-isolation-probe.nix) and
[adversarial driver](../scripts/import-isolation/check.py) exercise a candidate
policy using disposable source fixtures. They are engineering tools; Centaur
does not install, invoke or advertise them to OMP. The application retains the
Phase 2 tool allowlist. Fixed Python, Git and GCC version probes in this package
demonstrate compatibility inside the boundary, without registering command
execution in the application.

The policy combines pinned non-setuid Bubblewrap, a native ARM64 seccomp
allowlist generated with libseccomp 2.6.1 or later, and transient services in the
existing systemd user manager. No root helper, persistent service, NixOS rebuild,
credential change or installed-profile change is needed. The test driver refuses
other architectures and operating systems. Installation and hands-on acceptance
remain in **Centaur Install**.

## Candidate boundary

The trusted supervisor opens the selected fixture directory one component at a
time without following symlinks, then gives Bubblewrap that descriptor for a
read-only mount. Only individual pinned runtime closure paths enter the new
root; the complete host Nix store, home, Centaur/OMP data, user/system buses,
SSH agent and Nix daemon sockets are absent. The root and private proc filesystem
are read-only. Minimal null/zero/random devices replace the host device tree.

User, PID, mount, IPC, network, UTS and cgroup namespaces are mandatory. Nested
user namespaces are disabled, capabilities are dropped, a new session separates
the terminal, and the environment contains only HOME, TMPDIR, LANG, a fixed
non-executable PATH and Bubblewrap's sandbox-local PWD. Input is `/dev/null`;
output is a bounded pipe. The native seccomp policy defaults to EPERM, kills
other syscall architectures, permits ordinary process creation without namespace
flags, and rejects clone3 with
ENOSYS so libc can use the constrained clone fallback. Socket creation, mounting,
namespace changes, tracing, keyrings, BPF, io_uring and device creation receive
no allowance. The sole ioctl allowance is FIOCLEX, used by the measured ARM64
Python/glibc runtime to mark a descriptor close-on-exec; terminal ioctls remain
denied.

| Resource | Candidate ceiling |
| --- | --- |
| Memory | 128 MiB per transient cgroup, swap disabled |
| Processes/threads | 32 tasks for the whole service |
| CPU | 25% of one CPU |
| Runtime | 8 seconds enforced independently by systemd |
| Cancellation | Whole cgroup; SIGKILL after a 500 ms grace period |
| Scratch | One 8 MiB tmpfs shared by temporary files and empty home |
| Regular file | 1 MiB hard limit |
| Descriptors | 64 hard limit; inherited descriptors excluded |
| Core dumps | Disabled |
| Retained output | 32 KiB, then whole-service termination |

The stage checks effective cgroup files and hard process limits before executing
the sandbox. Missing or ineffective boundaries cause refusal. The driver tests
missing manager/Bubblewrap, invalid seccomp data and an injected missing effective
limit. There is no unsandboxed execution fallback.

## Verification and enablement gate

The final candidate passed **18 checks** on the actual ARM64 NixOS GNOME VM under UTM, as UID
1000, with kernel 6.18.57, Bubblewrap 0.13.1 and libseccomp 2.6.1. The existing
systemd user manager identified itself as 260.5 during preflight. The immutable
proof package is
`/nix/store/kkcjxzan650qpgsk8ighckay8512n9q8-centaur-import-isolation-proof-1`.
[Raw evidence and tested source hashes](evidence/import-isolation-phase3/)
bind this result to the actual archive and installed Python bytes.

The daemon-readiness pipe handshake ensures the parent announces readiness only
after its double-forked, detached child has installed SIGTERM ignore. All three
lifecycle cases verified this handshake before checking cleanup. Status records
are published atomically so the monitor cannot consume partially written JSON.

The boundary check verified all seven namespaces differed from the host, zero
effective/bounding capabilities, no-new-privileges and active seccomp, exactly
three inherited standard descriptors, only sandbox-local environment values,
and exactly 51 permitted runtime store paths. Host files and escape symlinks
were unreadable, source/root writes were refused, and IPv4, IPv6, Unix and
Netlink socket creation was denied. The driver deliberately held an inheritable
synthetic secret descriptor and working host sockets outside the sandbox.

Enforcement measurements reached 8,388,608 aggregate scratch bytes across
multiple files in both temporary/home paths, a 1,048,576-byte individual file
limit, and 29 forked children before the shared 32-task ceiling. The memory
exhaustion unit ended with `Result=oom-kill`; GNOME produced its generic
"Application Stopped" notification for that intentional test. The five-second
CPU loop consumed 1,299,543 microseconds of aggregate CPU and recorded 51
throttled periods. Output stopped at 32,768 retained bytes. Daemonised descendants
were gone after cancellation (0.284 seconds), runtime expiry (8.223 seconds),
and request-client death followed by the independent deadline (8.167 seconds).
Original fixture hashes stayed unchanged. Missing executable/manager, invalid
filter and injected ineffective-limit cases refused execution.

Initial runs found supervisor compatibility and measurement issues: use
`OOMPolicy=kill` and verify `memory.oom.group`, request user namespaces explicitly,
handle cgroup teardown reads, permit only FIOCLEX for script opening, and measure
inherited descriptors before libffi opens its own read-only library descriptor.
Final review added the explicit daemon handshake; the subsequent run also exposed
and fixed a partial-status-file race by publishing the record atomically.
The completed run used no syscall tracer. Its test scratch was disposed of,
test units were stopped/reset and the temporary transfer server was stopped.
The installed app and profiles were not changed.

Production integration must expose fixed typed operations with host-chosen
executables/arguments and managed snapshots, preserve attempt/operation identity,
bound and filter model-facing output, and bind cancellation/restart to the
service lifecycle. Mount the Phase 2 policy-filtered snapshot, retaining its
secret exclusions; supplied source bytes are readable inside the sandbox.
Recheck capabilities and effective limits on the machine executing each job.
The proof's internal fixture/fault interface is not a product
command API. Scratch inode exhaustion, arbitrary tool compatibility, preparation
exports and an application-integrated lifecycle are not established by this
proof. Existing **Run preview** continues to use the account's permissions;
this milestone does not change that execution path. Preparation, repairs,
dependency downloads, network grants and general builds remain later work.

Policy references: [Bubblewrap options](https://github.com/containers/bubblewrap/blob/main/bwrap.xml),
[systemd resource controls](https://www.freedesktop.org/software/systemd/man/260/systemd.resource-control.html),
[OOM policy](https://www.freedesktop.org/software/systemd/man/260/systemd.service.html#OOMPolicy=)
and [libseccomp advisory/fix](https://github.com/seccomp/libseccomp/security/advisories/GHSA-4q85-33p6-j5g6).
The VM measurements establish this candidate's result.
