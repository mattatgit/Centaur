# Phase 2 VM evidence — 16 November 2026

Tests ran only on the ARM64 NixOS GNOME VM under UTM. They used disposable
source fixtures and separate host data directories under `/tmp`, without
installing the candidate or changing existing projects, conversations, OMP
configuration/credentials, identities or the separate Qt installation.

- `vm-verification.txt`: 84 Python checks, successful retained service Nix build
  (core/network/Iroh checks enabled), and both live-agent results. The candidate
  archive SHA-256 is recorded in this log.
- `tested-source-sha256.json`: 75 runtime/test files checked byte-for-byte against
  that VM archive and the checkout before committing the verified fix.
- `live-agent.json`: actual OMP/provider responses and assertions for unfamiliar
  project inspection and controlled recovery. The recovery scenario injects a
  DNS failure and a synthetic acquisition; it verifies reasoning and host retry
  enforcement without pretending to reproduce a new real network incident.

The five-minute first live harness run stopped after successful listing and
searching, before reasoning finished. The final harness allows fifteen minutes
across multiple calls; Centaur's per-call timeout is unchanged. A new cancellation
regression initially found the UI retaining a stale busy gate after a discarded
late result. The final service build passed after fixing publication of that gate.

Product/native UI, updater and signed distribution evidence will be added after
the existing release workflow completes. Hands-on acceptance belongs in
**Centaur Install** and is not established by these tests.
