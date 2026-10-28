# Centaur development conventions

Preserve the working native app while making small, reviewable changes. The boundaries below describe existing implementation practice; the documentation workflow is proposed for adoption with this documentation set.

## Start from the project record

Read [Vision](VISION.md), [Requirements](REQUIREMENTS.md), [Decisions](DECISIONS.md), [Architecture](ARCHITECTURE.md) and the relevant [Current state](CURRENT.md) section before implementation. Inspect the current source and branch revision. Treat Proposed items as experiments rather than accepted specifications.

When code and prose disagree, establish current behaviour from source and checks, then record whether the discrepancy is a bug, stale documentation or a decision requiring review. Do not silently turn existing implementation details or a conversational suggestion into a permanent requirement.

## Existing boundaries to preserve

- Keep authoritative mutations, agreement enforcement, validation and checkpoints in the coordinator. The agent proposes source; it does not directly write the project.
- Keep the working source on failed checks and reject stale work. New explicit directions/sketches affect pending work; ordinary conversation must remain usable while the agent runs.
- Keep generated-app preview execution separate from Centaur's overlays. Preserve surface/input behaviour and shutdown ordering when changing Linux preview code.
- Keep exact-source rewinds additive to Git history. Do not reset away later checkpoints or recreate an old app through model output.
- Keep provider credentials on the host, project access scoped to credentials, and remote authorship assigned by the host. Do not include private authoring state in generated-app releases.
- Retain asset provenance and notices. Bundle fonts in every rendering process/package that needs them; preserve explicit font choices and fallback support.
- Keep resource use bounded and event driven. Measure on intended hardware before claiming a performance improvement or minimum specification.

These boundaries are reflected in the current source and guides. When a change intentionally revises one, record the resulting product or architecture decision and its validation.

## Build and verification

The shell uses C++17 and Qt 6.8 or later with CMake/Ninja. The native Iroh helper uses Rust, with locked dependencies. Nix outputs cover x86_64-linux, aarch64-linux and aarch64-darwin; the existing public binary workflow publishes the two Linux architectures. Use the [README build instructions](../README.md#build-and-test) and keep dependency locks stable unless intentionally updating them.

| Change | Relevant checks |
| --- | --- |
| Persistence, agent or agreement logic | Core tests for checkpoints, exact rewinds, malformed conflicts, stale work and restart recovery. Use explicit agent doubles for automated coordination tests. |
| Invitations, permissions or transport | Network and Iroh suites; include reconnect, replay/pin rejection, revocation and mixed transports as applicable. |
| Native UI or preview | UI smoke checks and visual/input inspection; Linux native-embedding and network-native-embedding suites for real buffers/input/lifecycle. macOS shell checks do not prove Linux embedding. |
| Rust helper | Locked Cargo build/tests and relevant formatting/Clippy checks; retain integration with the Qt tests. |
| Distribution | Existing workflow/script checks, both Linux architectures and verified signed closure downloads. A successful build alone does not establish publication. |
| Documentation only | Check source claims, statuses and links; review changed procedures against current behaviour. |

Use the existing [target machine](TESTING_ON_NIXOS.md) and [cross-network](LAN_COLLABORATION.md#internet-acceptance-test) procedures for physical acceptance. Report automated checks, historical evidence and live-model/manual tests separately. Tests with an agent double establish coordination, not mediation quality.

## Proposed documentation workflow

Keep one home for each subject: requirements for outcomes, decisions for rationale/status, architecture for boundaries, CURRENT for dated implementation/evidence, and operational guides for commands. Update the relevant documents in the same change when behaviour or an accepted decision changes.

Describe a change in terms of the concrete problem, resulting behaviour, validation and remaining limitations. Include exact source revisions and tested environments for meaningful validation claims. Record unresolved choices in the decision register without promoting them to commitments.

This guide does not introduce a branch naming scheme, commit format, release cadence or general publication approval policy. Those conventions have not been established by the reviewed material.
