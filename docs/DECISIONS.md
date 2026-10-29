# Centaur decisions and open questions

This register separates established direction from implementation choices and experiments. **Handover** identifies direction explicitly supplied by the owner. **Repository record** identifies a choice already described as agreed in existing documentation. **Proposal** identifies an idea still to evaluate, including recommendations in the pasted earlier discussion.

## Agreed decisions

| ID | Decision and rationale | Source and consequence |
| --- | --- | --- |
| D01 | Retain C++17 and Qt Quick. Styling flexibility and the working Linux compositor favour continuing the existing implementation over a GTK rewrite. | Handover. Preserve native collaboration and embedding while evolving the architecture. |
| D02 | Target native Linux/NixOS and macOS clients. | Handover. macOS preview parity is unresolved; shell compilation is not embedding support. |
| D03 | Keep Centaur's identity independent of generated-app systems and Qt's default appearance. | Handover and pasted discussion. Current Dialogue-derived chrome does not settle the final identity. |
| D04 | Support multiple independent systems containing tokens, components and layouts/patterns; themes live within systems. | Handover. A palette alone does not define a system. |
| D05 | Separate app behaviour from visual implementation, record system/version and support later system changes preserving functionality/content. | Handover. This is a target architecture; the current single-file contract needs to evolve. |
| D06 | Have agents use the selected system's components and rules, and eventually validate rendered results. | Handover. Enforcement and visual evaluation methods remain open. |
| D07 | One project represents one app and repository; the canvas and shared conversation are the workspace. | Repository record: README and CURRENT. Editing and rewinding preserve project identity. |
| D08 | A compatible explicit request authorises a change; only genuine conflicts require agreement from affected authors. | Repository record: CURRENT and ARCHITECTURE. Preserve this distinction through future generation/deployment work. |
| D09 | Finished apps should run independently of Centaur/OMP, beginning with local NixOS installation and later family sharing and explicit release updates. | Repository record: ARCHITECTURE, agreed 27 October 2026. Installed releases/data have separate lifecycles from workshop edits. |
| D10 | Prioritise modest hardware and precompiled NixOS delivery. | Repository record and handover. Keep the public Cachix path; measure before setting a hardware floor. |
| D11 | Use Inter at 12 pt or smaller and Inter Tight above 12 pt for Centaur’s default typography, retaining current sizes/weights pending review. | Owner request, 29 October 2026. Bundle both families and licences in the native runtimes; this default does not prescribe fonts for every future design system. |

## Current implementation choices

These describe the inspected prototype, not irreversible commitments: a background host is authoritative for each local data directory; one agent/checking pipeline is serialised across that host; guests use project credentials and pinned TLS over LAN or Iroh; each participant renders an independent native preview; accepted source is one `App.qml`; collaboration records are JSON/JSONL outside the generated app's Git history. See [Architecture](ARCHITECTURE.md).

## Proposals to evaluate

| ID | Proposal | Evidence needed before adoption |
| --- | --- | --- |
| P01 | Compare two or three different systems on the same small app before building an editor. | Consistent generation, rendered quality and successful switching after content exists. |
| P02 | Use shared data/action/component contracts and a modular app/system structure. | Demonstrate independent logic and presentation without breaking checking, history or collaboration. Folder names and JSON schemas are not settled. |
| P03 | Explore Editorial, Utility and Playful as contrasting systems. | Designer review and experiment results; these are illustrative directions. |
| P04 | Build a visual system library/editor and allow designers to publish reusable systems. | Establish the model, validation, distribution and authoring needs first. |

The repository also records local app installation as the next deployment milestone and cross-network Iroh testing as the next networking acceptance step. No ordering between those workstreams and the design-system experiment has been agreed here.

## Open questions

| ID | Question | Next useful evidence |
| --- | --- | --- |
| Q01 | How can native apps be embedded on macOS with input, focus, popups, scaling and reliable lifecycle handling? | A bounded prototype that evaluates options and limitations. |
| Q02 | What schema, component contract and version/upgrade model should systems use? | P01/P02 results, including incompatible components, assets and layout rules. |
| Q03 | What state must survive a system change, and how do existing single-file projects migrate? | Content/behaviour checks plus an explicit transient-state and restart policy. |
| Q04 | What should Centaur itself look like? | Design exploration separate from generated-app systems. |
| Q05 | What application/distribution licensing approach should be used with Qt and bundled assets? | An explicit licensing decision; existing third-party notices remain required. |
| Q06 | How should untrusted generated native QML be isolated, and how should membership management evolve? | A sandbox and permissions design, including individual member removal. Current QML remains trusted code. |
| Q07 | How reliable and useful is the agent's conflict mediation with real groups? | Real conversations, misunderstandings and correction/reopening scenarios. |
| Q08 | Does Iroh work reliably across the intended physical networks and relay fallback paths on modest devices? | Air/VM acceptance over different networks, recovery and resource measurements. Automated relay evidence is already recorded. |
| Q09 | What are the minimum hardware requirements? | CPU, memory, latency and graphics measurements on target machines. |
| Q10 | How are installed app identity, persistence, migration, updates and optional shared data implemented? | The first standalone-installation prototype and a separate data/synchronisation design. |
| Q11 | What rendered checks establish design quality, including readability and interaction states? | A repeatable review rubric and observed failures from P01. |

## Recording later decisions

For a new material choice, record its status, date, context, decision, rationale, consequences and source. Link the affected requirements and implementation change. Preserve superseded decisions with a pointer to their replacement. Split substantial decisions into individual records only when the register becomes difficult to use.

Sources: the owner's Development and Design-System Handover and pasted Qt/design-system discussion supplied on 28 October 2026; existing [README](../README.md), [Architecture](ARCHITECTURE.md) and [Current state](CURRENT.md), inspected at `f2f7257`. The pasted discussion supplies recommendations; it does not establish additional approvals beyond the handover.
