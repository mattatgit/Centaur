# Architecture

## Product and runtime

Centaur is a native workshop for families to build native apps collaboratively. One project represents one app and one Git repository. NixOS and modest hardware are the initial targets.

The current shell uses C++17 and Qt Quick. On Linux, a nested Wayland compositor embeds a separate native Qt Quick app process in the canvas and forwards input to it. Chat, drawing and comment overlays belong to Centaur; the generated app runs in its own process. Multiple Centaur windows share an authoritative local session over QLocalSocket. Accounts and collaboration between computers are not implemented yet.

App changes update the existing project. Git checkpoints preserve source history without presenting each change as a new project or announcing numbered revisions. Making a request approves an ordinary compatible change; only conflicting requirements need agreement by the affected authors.

See [Current state](CURRENT.md) for implemented behaviour, deliberate boundaries and validation evidence.

## Deployment direction

Agreed on 27 October 2026: a finished app should become an ordinary native application that people can open independently of Centaur. Centaur remains the workshop where its authors return to improve it. An installed app should not require the Centaur authoring environment or OMP, unless an app deliberately includes an agent feature with its own runtime requirements.

Deployment has three stages:

1. **Install this app:** package a chosen working version with its name, icon and application launcher on the current computer.
2. **Share with family:** provide an installation link for other people to install the native app without installing Centaur or OMP. Private distribution and access control need a separate design before this stage ships.
3. **Publish an update:** explicitly release a finished change to installed copies. Workshop edits do not immediately replace the version people are using. This release step does not introduce an approval requirement for every authoring change.

### First milestone: install on this computer

The next deployment milestone is **Install this app on this computer**, targeting NixOS. It needs:

- A standalone native application package and desktop launcher, with an app name and icon.
- A stable application identity across edits and installations, distinct from the chosen display name.
- A release built from a saved source checkpoint, including its required assets and pinned runtime dependencies. The installed app must keep working as the workshop project is edited further.
- Persistent app data stored separately from the installed package and Centaur's authoring state. App updates must preserve that data.
- A way to associate an installed release with its source project and checkpoint so authors can return to the workshop and prepare a later release.

The initial packaging approach is Nix. Builds can run on a faster machine or CI and be distributed through a binary cache, reducing compilation on entry-level devices. ARM64 Linux and x86-64 Linux require appropriate builds; the UTM VM and older Air must not be assumed to use the same executable. The build service, cache hosting and update delivery are not implemented or selected yet. See [Nix binary distribution](https://nix.dev/manual/nix/stable/package-management/binary-cache-substituter.html).

### App data and synchronisation

Installing the same app on two devices does not automatically share its data. A family planner, for example, needs an explicit storage and synchronisation design to show the same tasks on both devices.

Local persistence is part of the first installation milestone. Shared family data, authentication, synchronisation and any backend service are separate work. The storage format and migration strategy remain to be chosen. Package rollback alone must not be treated as rollback of user data.

Centaur's conversation, drawings, agent configuration and other authoring records are not automatically part of a deployed app. Package the app source, runtime and selected assets without copying the workshop's private state or provider credentials.

### Current implementation boundary

Today, generated apps are Qt Quick `Item` or `Rectangle` roots in `App.qml`. They can run outside Centaur with `centaur-preview /path/to/App.qml`, but this uses Centaur's preview runner. It is not yet an independently installable release with its own application identity, launcher or persistence contract. The starter app's in-memory task model does not yet provide persistent storage.

Export, independent app packaging, family installation links and release updates are planned features, not existing capabilities.

## Fonts and packaged assets

Open-source fonts can be used in Centaur and in generated native apps when their individual licences permit redistribution. Inter is an available option under the SIL Open Font License 1.1; adopting it as the default typography is a separate UI decision.

For an Inter-based implementation:

- Bundle a pinned, unmodified upstream font release with its copyright notice and licence text in Centaur and every generated app package that includes the font. The font remains under its own licence; bundling it does not require the app itself to use the OFL.
- Load the font locally using Qt's application-font facilities. Register it in each process that renders text: loading it in Centaur does not make it available automatically in the separate app process. Standalone releases must carry the same required font assets.
- Use the same font files and family settings in the embedded preview and installed app. Do not depend on users installing the font or on a web font service being reachable.
- Include only the font styles needed and retain fallback fonts for scripts and symbols outside the chosen font's coverage. Check readability at the intended text sizes on the target hardware.
- If modifying font files, check the exact release's modification and reserved-name conditions before redistribution. Check other fonts' licences individually rather than assuming all open-source fonts have identical terms.

Sources: [Inter licence](https://github.com/rsms/inter/blob/master/LICENSE.txt), [OFL bundling FAQ](https://openfontlicense.org/ofl-faq/), [Qt application fonts](https://doc.qt.io/qt-6/qfontdatabase.html#addApplicationFont).

No font files have been added or font defaults changed as part of this architecture record. Font licensing is separate from the unresolved application and Qt distribution licensing decisions noted in the README.
