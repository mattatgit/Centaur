# Centaur requirements

These requirements describe product outcomes. Implementation status refers to source snapshot `f2f7257`; acceptance criteria for planned work are draft evaluation criteria, not claims that the feature exists.

## Core workshop

| ID | Required outcome | Status and acceptance |
| --- | --- | --- |
| R01 | One project retains one app and repository identity across edits. | Implemented. Reopening, renaming, editing and rewinding retain the same project and recoverable source history. |
| R02 | People discuss, sketch and try an app in one workspace. | Implemented on Linux: canvas, shared chat, Draw, Comment, Undo and Interact/Build modes. Chat remains usable in either mode. |
| R03 | Multiple authors share conversation, annotations, decisions and accepted source. | Implemented through a background host, local sockets, LAN TLS and Iroh. Each preview has independent runtime interaction state. |
| R04 | Only the host needs an authenticated OMP installation. | Implemented. A guest can request a change through the host without receiving provider credentials. |
| R05 | Compatible explicit agent requests proceed automatically; genuine conflicts require only affected authors' agreement. | Implemented coordination. Unknown or malformed conflict classifications leave the app unchanged. Real mediation quality needs evaluation with people. |
| R06 | Failed or stale candidates do not replace the working app. | Implemented separate QML check and stale-work rejection/retry. Rewinds retrieve exact saved source and append a new checkpoint. |
| R07 | Native clients support Linux/NixOS and macOS. | Linux embedding is implemented. macOS supports shell and coordination development; equivalent embedded previews remain open. |
| R08 | Entry-level machines can obtain and use the app without routine local compilation. | Cachix distribution exists for x86_64-linux and aarch64-linux. Resource measurements and a minimum hardware specification remain open. |

## Design systems

These are agreed direction from the handover and remain planned.

| ID | Required outcome | Draft acceptance criteria |
| --- | --- | --- |
| R09 | Multiple systems coexist, each covering tokens, reusable components, and layouts/patterns. | The same small app expresses meaningfully different hierarchy, density and composition under at least two systems. Changing a palette alone is insufficient evidence. |
| R10 | Select a system at creation and change it later without losing functionality or content. | Add content, change systems and verify the original actions, records and behaviour remain available. State retention and restart behaviour must be explicitly defined by the experiment. |
| R11 | Record the selected system and version per project. | Reopening a project resolves its recorded version. Updating a library must not silently change projects pinned to an earlier version. Format and upgrade policy remain open. |
| R12 | Agents generate interfaces using the selected system's components and composition rules. | Inspect generated source and rendered screens for component use, spacing, hierarchy, states and layout consistency. Enforcement and tooling remain proposed. |
| R13 | Application behaviour and design-system implementation remain independently maintainable. | A system switch does not require the agent to recreate application logic. Component contracts and migration from single-file apps remain open. |

Rendered appearance validation is an agreed longer-term direction. The initial review method and any automated visual checks are still to be established.

## Standalone deployment

The existing architecture records these agreed, unimplemented stages.

| ID | Required outcome | Draft acceptance criteria |
| --- | --- | --- |
| R14 | Install an app on the current NixOS computer. | A release from a saved checkpoint has stable identity, name, icon and launcher; opens without Centaur/OMP; preserves app data separately from its package; and remains stable during further workshop edits. |
| R15 | Share an installation link with family. | Recipients install without Centaur/OMP. Distribution access, dependencies and private sharing need a design before this stage ships. |
| R16 | Explicitly publish updates to installed copies. | Releases can be traced to source checkpoints; updates preserve data according to an agreed migration contract. Workshop changes do not publish automatically. |

Centaur's own cached authoring package is not evidence that generated-app deployment exists. Shared application data, authentication and backend services need separate requirements.

## Existing limits

Generated QML is trusted native code with no sandbox. Invitations and project credentials control authoring access; they do not make arbitrary generated code safe. Offline sending/drawing, automatic host migration, individual member removal, arbitrary assets/compiled app distribution and synchronised runtime app data are outside the current implementation.

Detailed current behaviour and historical test results live in [Current state](CURRENT.md). Operational acceptance procedures live in [Target machine testing](TESTING_ON_NIXOS.md) and [Collaboration](LAN_COLLABORATION.md). Open choices and proposals are tracked in [Decisions](DECISIONS.md).
