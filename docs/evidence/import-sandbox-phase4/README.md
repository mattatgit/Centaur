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
Published `0.4.0-preview+0ddbd19` through the existing signed workflow after its
required checks passed:

- [Release verification](release-verification.json) records both successful
  workflows and downloaded artifact SHA-256 digests. The public feed exactly
  matches the [signed distribution manifest](release-manifest.json); all 613
  closure paths passed empty-store signature verification.
- [Native integration](release-native-integration.json) includes collaboration,
  import, validation/history and Landline's linux-nix branch checks. The downloaded
  agent context contained commit `205fc1185335dc1c85b359af7673f6e5d7653222`,
  branch linux-nix and LandlineNix paths.
- [Updater checks](release-updater.json) include a real disposable profile switch,
  GTK restart and project/chat/preferences/identity/Qt preservation.
- [Published-binary UTM verification](release-vm-verification.json) downloaded the
  exact signed release without builds or an owner profile switch, matched the
  installed broker/shared-engine bytes, and ran both fixed diagnostics.

The owner profile stayed at `e8d627c` during engineering tests. Installation and
hands-on acceptance remain in Centaur Install. Automated verification is not
owner acceptance.
