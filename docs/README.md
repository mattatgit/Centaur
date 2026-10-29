# Centaur project documentation

Centaur is a native workshop for building apps together through conversation and a shared canvas. These documents separate product intent, architectural choices and implementation evidence so people and coding agents can work from the same project understanding.

## Reading order

| Document | Purpose |
| --- | --- |
| [Product vision](VISION.md) | People, purpose and product principles. |
| [Requirements](REQUIREMENTS.md) | Required outcomes and their implementation status. |
| [Decisions and open questions](DECISIONS.md) | Agreed direction, recorded choices, proposals and unresolved issues. |
| [Architecture](ARCHITECTURE.md) | Runtime boundaries, collaboration, deployment and assets. |
| [Design systems](DESIGN_SYSTEMS.md) | The three layers, separation from app logic and proposed experiment. |
| [Current state](CURRENT.md) | Implemented behaviour, historical validation and next evidence needed. |
| [Development conventions](DEVELOPMENT.md) | How to make, validate and document changes. |

Before implementing a feature, read its requirements and decisions, then inspect the relevant source and current-state entry. Resolve discrepancies explicitly; an implementation detail does not by itself establish a permanent product decision.

## Status language

- **Agreed** means established direction in the owner's handover or explicitly recorded as agreed in existing project documentation. The decision register distinguishes those sources.
- **Proposed** means an option or experiment for evaluation. It does not establish a required implementation or delivery order.
- **Open** means a decision or technical solution is still needed.
- **Implemented** describes the inspected source. **Planned** describes an agreed outcome that has not shipped. Validation claims must identify their revision and environment.

The source snapshot used for this review is `f2f72577b90edf23c8266b15a1a07905e017c066` on `codex/native-prototype`, declaring v0.3.0. The handover's verified v0.2.0 build, `09c573d4feddca55ca49d7641748fff78ffaa775`, remains an earlier baseline. Current evidence belongs in [Current state](CURRENT.md); it should advance as development proceeds.

## Operational guides

Keep these procedures in their existing locations:

- [Easy NixOS installation and updates](NIXOS_INSTALL.md)
- [Precompiled NixOS distribution](BINARY_DISTRIBUTION.md)
- [Collaboration over LAN and Iroh](LAN_COLLABORATION.md)
- [OMP setup on NixOS](OMP_NIXOS_SETUP.md)
- [Target machine testing](TESTING_ON_NIXOS.md)
- [Dialogue asset provenance](https://github.com/mattatgit/Centaur/blob/f2f72577b90edf23c8266b15a1a07905e017c066/assets/dialogue/README.md)
- [Inter font provenance](https://github.com/mattatgit/Centaur/blob/f2f72577b90edf23c8266b15a1a07905e017c066/assets/fonts/inter/README.md)

## Documentation maintenance

This repository is the persistent project record. Record new decisions with their rationale and consequences; update requirements, architecture and current-state evidence when a change affects them. Keep experimental ideas labelled Proposed until the owner accepts them. Retain useful historical evidence with its date and revision rather than presenting it as a fresh verification.
