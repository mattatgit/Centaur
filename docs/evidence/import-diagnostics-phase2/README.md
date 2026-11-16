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

The existing ARM64 release workflow also passed for source
`e8d627cbdd02d5c1bec17cb589a34e8c21b206fd`:

- [Product/service/import/updater workflow](https://github.com/mattatgit/Centaur/actions/runs/43793539315)
  and [standalone embedding workflow](https://github.com/mattatgit/Centaur/actions/runs/43793539331).
- `native-summary.json`: native product regressions, including the actual public
  Landline `linux-nix` import. `import-provenance.json` records the selected branch
  and commit; the check also verifies both `LandlineNix/Cargo.toml` and
  `LandlineNix/src/main.rs` reach the agent context.
- `updater-summary.json`: Settings update, real disposable profile switch/restart,
  project/chat/preferences/identity preservation and separate Qt preservation.
- `manifest.json`: published **0.4.0-preview+e8d627c**, with all 579 closure paths
  downloaded from signed Cachix into an empty store, signature checks enabled,
  fallback caches and builders disabled. The public update feed was read back
  and exactly matched this manifest after the updater check passed.
- `release-verification.json`: workflow conclusions, artifact IDs/digests and
  feed readback. Downloaded ZIP hashes matched GitHub's artifact digests.

The temporary VM test server was stopped after verification. No candidate was
installed in the owner's VM. Hands-on acceptance belongs in **Centaur Install**
and is not established by these tests.
