# Architecture

## Product and runtime

Centaur is a native workshop for families to build native apps collaboratively. One project represents one app and one Git repository. NixOS and modest hardware are the initial targets.

The current shell uses C++17 and Qt Quick. On Linux, a nested Wayland compositor embeds a separate native Qt Quick app process in the canvas and forwards input to it. Chat, drawing and comment overlays belong to Centaur; the generated app runs in its own process. Multiple Centaur windows share an authoritative local session over QLocalSocket. Local-network collaboration uses authenticated, certificate-pinned TLS connections to a background host. Cloud accounts and internet hosting are not implemented.

App changes update the existing project. Git checkpoints preserve source history without presenting each change as a new project or announcing numbered revisions. Making a request approves an ordinary compatible change; only conflicting requirements need agreement by the affected authors.

See [Current state](CURRENT.md) for implemented behaviour, deliberate boundaries and validation evidence.

## Collaboration between people

### Current support

A background `centaur-host` owns each local data directory, runs OMP, validates source and saves Git history. Native windows connect over the existing OS-user-only local socket. Closing the owner's window no longer ends sharing. The host computer must remain awake; a service installation and automatic failover are outside this prototype.

Owners create project-scoped, single-use invitations from Invite. A guest joins from Projects and receives a stable member credential, a host-assigned display name, the invited conversation/drawings and accepted app source. Duplicate display names receive a suffix. The host authenticates every connection, assigns authorship from the credential and restricts remote commands to contribution/approval/stop actions. Guests cannot manage invitations, rename/delete/archive projects or read other projects. Stop sharing revokes all credentials for that project; guests can leave independently.

Transport uses Qt Network TLS sockets with the host certificate fingerprint embedded in the invitation. Credentials are sent only after checking the pin. Acknowledged command sequences are stored with accepted mutations to prevent duplicate effects after reconnects; stale drawings and votes cannot apply to a different app revision. Guests keep private cached source/state and automatically reconnect with the same identity. One guest window per device owns the outgoing queue; additional views are read-only and can take over when that window closes. Offline contribution is disabled, drafts remain editable, and the last synced native preview remains available.

Each participant runs a local native preview with independent interaction state. Synchronising data inside a generated/deployed app remains separate from authoring collaboration. The first network contract distributes the existing single-file Qt Quick app, not arbitrary assets or compiled frameworks.

Agent requests are queued and persisted. Ordinary chat does not invalidate in-flight agent work; new explicit agent directions and sketches do. Stale work is retried against current conversation/source. Compatible changes still apply directly, and only actual conflicts require agreement from the affected authors. Pending conflict discussion can invalidate its agreements. Requests interrupted by a host restart return to the queue.

See [LAN collaboration](LAN_COLLABORATION.md) for the complete host/join flow, NixOS firewall/VM prerequisites, background-host maintenance and acceptance tests. This is a trusted-family LAN milestone: native QML is not sandboxed, invitations should be shared privately, and there is no internet relay, cloud account system, per-member removal UI or host migration.

### Next stages

First complete the physical two-NixOS-device acceptance test, including live OMP, reconnect, independent native previews and resource use on the Air. Then improve member management and sandboxing. Internet access and always-available family hosting require a separate choice of self-hosting, a hosted service or a relay. Provider credentials remain on the host throughout.

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

The initial packaging approach is Nix. Builds can run on a faster machine or CI and be distributed through a binary cache, reducing compilation on entry-level devices. ARM64 Linux and x86-64 Linux require appropriate builds; the UTM VM and older Air must not be assumed to use the same executable. Centaur itself now has a [GitHub Actions/Cachix distribution workflow](BINARY_DISTRIBUTION.md) for both Linux architectures, pending initial cache/account configuration. This distributes the authoring package, not standalone generated-app releases. Generated-app build/update delivery remains future work.

### App data and synchronisation

Installing the same app on two devices does not automatically share its data. A family planner, for example, needs an explicit storage and synchronisation design to show the same tasks on both devices.

Local persistence is part of the first installation milestone. Shared family data, authentication, synchronisation and any backend service are separate work. The storage format and migration strategy remain to be chosen. Package rollback alone must not be treated as rollback of user data.

Centaur's conversation, drawings, agent configuration and other authoring records are not automatically part of a deployed app. Package the app source, runtime and selected assets without copying the workshop's private state or provider credentials.

### Current implementation boundary

Today, generated apps are Qt Quick `Item` or `Rectangle` roots in `App.qml`. They can run outside Centaur with `centaur-preview /path/to/App.qml`, but this uses Centaur's preview runner. It is not yet an independently installable release with its own application identity, launcher or persistence contract. The starter app's in-memory task model does not yet provide persistent storage.

Export, independent app packaging, family installation links and release updates are planned features, not existing capabilities.

## Fonts and packaged assets

Inter is the default typography in Centaur and its native example/preview runtime. It is bundled under the SIL Open Font License 1.1. Other open-source fonts can be used when their individual licences permit redistribution.

For an Inter-based implementation:

- Bundle a pinned, unmodified upstream font release with its copyright notice and licence text in Centaur and every generated app package that includes the font. The font remains under its own licence; bundling it does not require the app itself to use the OFL.
- Load the font locally using Qt's application-font facilities. Register it in each process that renders text: loading it in Centaur does not make it available automatically in the separate app process. Standalone releases must carry the same required font assets.
- Use the same font files and family settings in the embedded preview and installed app. Do not depend on users installing the font or on a web font service being reachable.
- Include only the font styles needed and retain fallback fonts for scripts and symbols outside the chosen font's coverage. Check readability at the intended text sizes on the target hardware.
- If modifying font files, check the exact release's modification and reserved-name conditions before redistribution. Check other fonts' licences individually rather than assuming all open-source fonts have identical terms.

Sources: [Inter licence](https://github.com/rsms/inter/blob/master/LICENSE.txt), [OFL bundling FAQ](https://openfontlicense.org/ofl-faq/), [Qt application fonts](https://doc.qt.io/qt-6/qfontdatabase.html#addApplicationFont).

The implementation embeds unmodified Inter 4.1 Regular, SemiBold and Bold in both native executables and registers them before creating QML engines. New example apps and existing apps using the runtime's default font receive Inter; explicitly chosen font families in saved app source are respected. OMP is told to preserve Inter unless an author requests another font. Source provenance and hashes are recorded in [the font asset directory](../assets/fonts/inter/README.md). The licence is embedded and installed as a readable file with the package. Future standalone app exports must preserve those assets and notices too.

Font licensing is separate from the unresolved application and Qt distribution licensing decisions noted in the README.

## Native UI and Dialogue assets

Centaur ports Dialogue's navigation, button states and grid controls into Qt Quick; it does not embed Dialogue's HTML or introduce a browser runtime. Original SVG files and extracted symbol geometry are bundled as resources and rendered as colour masks with Qt SVG, matching Dialogue's CSS mask approach on both hardware and software rendering paths. The original empty-state PNG is bundled unchanged. See [asset provenance](../assets/dialogue/README.md).

Interact/Build is a per-window input mode, not a different collaboration session or an approval requirement. Chat stays available in both modes. The grid is a painted, non-interactive overlay; its size is measured in the native app's logical design units and its origin follows the app frame. Device preferences live in preferences.ini outside app source/history. Settings can temporarily hide a live workspace while retaining its compositor and preview; closing a project still stops the client before releasing compositor views.

Design-system import and Deploy remain explicit placeholders. This UI update does not implement network collaboration, a design-system store or standalone app deployment.
