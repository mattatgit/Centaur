# Centaur product vision

Centaur helps families and small groups create useful native applications together. People discuss an app, point to its interface and sketch changes; a shared coding agent helps clarify the direction, mediate incompatible requirements and implement the resulting app.

## Agreed product direction

One project represents one app and one Git repository. The shared canvas and conversation are the main workspace. People can try the native app, draw rough ideas or attach Comment arrows, and address the agent in the same chat they use with one another.

The working application and its history should survive experimentation. Ordinary compatible requests authorise implementation; actual conflicts require agreement from the affected authors. Git provides quiet checkpoints and recoverable history while the conversation remains understandable without repository terminology.

Linux/NixOS and macOS are intended native client platforms. NixOS and modest hardware are the initial delivery and testing focus. Preserve the working native embedding and collaboration capabilities as the architecture develops.

## Design quality

Applications built primarily through natural-language prompts should be coherent, well designed and consistent. Designers should be able to encode reusable expertise in design tokens, components, layouts and usage rules that guide the agent from the start of generation.

Support multiple independent, versioned design systems. A user should eventually be able to select a system when creating an app and change systems later while preserving the app's functionality and content. Themes are variations within a system.

Centaur's own visual identity is a separate concern. Retain Qt Quick while allowing a distinctive interface independent of Qt's default appearance. The current Dialogue-derived interface is a prototype reference; Centaur's final design remains open.

## From workshop to everyday app

The repository records an agreed deployment direction: finished apps should open independently of Centaur and OMP, except when an app intentionally includes its own agent feature. Begin with installation on the current NixOS computer, then consider family installation links and explicit release updates. Workshop edits should not immediately replace an installed release.

An app's persistent and shared data needs its own design. Authoring collaboration does not automatically synchronise the data people enter into installed apps.

## Scope and success

The current prototype generates one Qt Quick `App.qml`, coordinates a shared conversation and runs independent local previews. Arbitrary native frameworks, offline collaborative authoring, host migration, standalone app deployment and the design-system library are future capabilities.

Success means people can shape a working app together, recover from unsuccessful changes and obtain a recognisable, coherent interface from their selected design system. Minimum hardware specifications, mediation quality and the design-system approach still need practical evaluation.

See [Requirements](REQUIREMENTS.md), [Design systems](DESIGN_SYSTEMS.md) and [Decisions](DECISIONS.md) for scope and unresolved choices.
