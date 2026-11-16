# Phase 4 diagnostic broker integration

Verified on the owner's **ARM64 NixOS UTM** VM, as UID 1000, kernel 6.18.57.
No macOS application tests were substituted. The installed GTK/Qt profiles,
projects, conversations, identities and OMP configuration/credentials were not
changed. Tests use disposable data and transient services. Product installation
and hands-on acceptance stay in **Centaur Install**.

- [VM report](vm-report.json): exact product/sandbox/proof paths, all 18 isolation
  checks, installed source hashes and identical production/proof engine bytes.
- [Build verification](vm-build-verification.txt): final transferred archive,
  all 88 Python checks, boundary checks and product build. [Core/network/Iroh
  checks](vm-service-verification.txt) also passed in the preceding build; unchanged service inputs were reused.
- [Supervisor death](vm-supervisor-death.json): actual SIGTERM/SIGKILL sent after
  the daemon's double-fork/session/SIGTERM-ignore handshake, with no descendants.
  Cleanup took 0.064 seconds and 7.991 seconds respectively.
- [Live OMP](vm-live-agent.json): actual packaged worker and retained coordinator;
  runtime_version, validate_manifest and read operations diagnosed two unfamiliar
  apps, a missing runtime and malformed JSON, then asked which app to work on.
  No hostile project code executed; original hashes stayed unchanged. General
  OMP tools/extensions remained disabled.
- [Tested source hashes](tested-source-sha256.json): bytes from the actual VM
  archive, matching checkout runtime/packaging/test files. Documentation may
  subsequently record verification and release status.

The strengthened supervisor test initially caught a real cancellation bug:
selectors swallowed InterruptedError raised by the signal handler. The final
RuntimeError handler reaches the engine's whole-cgroup cleanup. Other initial
harness-only issues were missing Python/Git on the Console PATH, an incorrect
expectation that Python 3.14 rejects deeply nested valid JSON, and reuse of a
prior live-test output directory. The final recorded checks use pinned tools,
a bounded parser result and a fresh live data directory.

Scope: two host-chosen fixed diagnostics only. Manifest values/parser messages,
raw compiler/systemd/Bubblewrap output and host locators are not forwarded to
the model. There are no repair writes, builds, dependency/network grants,
general terminal tools or changes to existing Run preview permissions.
Publication through the existing signed updater is recorded separately after
its required checks pass. Automated verification is not owner acceptance.
