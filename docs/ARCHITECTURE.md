# Architecture

## Product and runtime

Centaur is a native workshop for families to build native apps collaboratively. One project represents one app and one Git repository. Linux/NixOS and macOS are the intended native client platforms; NixOS and modest hardware are the initial delivery and testing focus.

The current shell uses C++17 and Qt Quick. On Linux, a nested Wayland compositor embeds a separate native Qt Quick app process in the canvas and forwards input to it. Chat, drawing and comment overlays belong to Centaur; the generated app runs in its own process. Multiple Centaur windows share an authoritative local session over QLocalSocket. Collaboration uses authenticated, certificate-pinned TLS connections to a background host, carried either directly over the LAN or over native Iroh peer-to-peer streams. Cloud accounts and automatic host migration are not implemented.

App changes update the existing project. Git checkpoints preserve source history without presenting each change as a new project or announcing numbered revisions. Making a request approves an ordinary compatible change; only conflicting requirements need agreement by the affected authors.

See [Current state](CURRENT.md) for implemented behaviour, deliberate boundaries and validation evidence.

## Platform and visual design direction

Agreed in the owner's design-system handover: retain C++17 and Qt Quick. Qt's styling flexibility and the existing Linux embedding implementation favour continuing this architecture over a GTK rewrite. Centaur's own interface and the design systems used by generated apps are separate concerns; neither depends on Qt's default control appearance. The current Dialogue-derived shell is a prototype reference, and Centaur's final visual identity remains open.

Linux uses Qt Wayland Compositor. macOS currently builds the native shell and coordination tools, with an explicit unavailable-preview view. Equivalent native embedding on macOS remains unresolved. Window integration, focus, popups, scaling and lifecycle behaviour need platform-specific evaluation.

## Runtime responsibilities

| Boundary | Responsibility and source |
| --- | --- |
| Native shell | QML views and `src/controller.*` expose projects, chat, drawings and preview lifecycle. |
| Background host | `src/session.*` owns the authoritative writer per data directory, queued requests, agreement, validation and persistence. One agent/checking pipeline is serialised across that host. |
| Agent adapter | `src/agent.*` invokes OMP without tools, rules, skills or discovered extensions. It supplies conversation, decisions, current source, revision-bound marks/image context and bounded history; it parses questions, source proposals or restore requests. |
| App storage | `src/workspace.*` owns app source and additive Git checkpoints; JSON/JSONL collaboration records live under `.centaur/` outside the generated app's Git history. Backups must include both. |
| Network | `src/collaboration.*`, `src/irohbridge.*` and `networking/` carry project-scoped state and commands to the same host. |
| Preview and check | `centaur-preview` checks candidate QML in a separate process and runs accepted apps. Linux renders app surfaces through `qml/WaylandPreview.qml`; overlays belong to Centaur. |

An explicit request enters the host queue. The agent returns a question, a complete source proposal, or a reference to an exact saved checkpoint. The coordinator rejects stale/invalid results, waits for affected authors only when requirements conflict, checks candidate QML, then saves a checkpoint and distributes accepted source. Clients restart their own previews. A failed check leaves the working app in place. This validation is not a sandbox for native QML.

## Generated app design systems

Agreed direction: separate application logic from visual implementation and allow multiple independent systems, each containing tokens, reusable components and layout/pattern rules. Projects should record their selected system/version and eventually support switching systems without losing functionality or content. Agents should generate with those components/rules, with rendered appearance validation added over time.

This is a target architecture. Today the source, agent response, checker, history and collaboration contracts operate on one `App.qml`. A modular app/system contract and safe migration require changes across those boundaries. The token schema, QML module layout, composition rules, version/upgrade policy and state-transfer mechanism remain open.

The proposed next design experiment compares two or three systems on one small app before building an editor. Shared data/action/component contracts and token-driven visual implementations are hypotheses to test. See [Design systems](DESIGN_SYSTEMS.md) and [Decisions](DECISIONS.md).

## Collaboration between people

### Current support

A background `centaur-host` owns each local data directory, runs OMP, validates source and saves Git history. Native windows connect over the existing OS-user-only local socket. Closing the owner's window no longer ends sharing. The host computer must remain awake; a service installation and automatic failover are outside this prototype.

Owners create project-scoped, single-use invitations from Invite. A guest joins from Projects and receives a stable member credential, a host-assigned display name, the invited conversation/drawings and accepted app source. Duplicate display names receive a suffix. The host authenticates every connection, assigns authorship from the credential and restricts remote commands to contribution/approval/stop actions. Guests cannot manage invitations, rename/delete/archive projects or read other projects. Stop sharing revokes all credentials for that project; guests can leave independently.

Transport uses Qt Network TLS sockets with the host certificate fingerprint embedded in the invitation. Credentials are sent only after checking the pin. Acknowledged command sequences are stored with accepted mutations to prevent duplicate effects after reconnects; stale drawings and votes cannot apply to a different app revision. Guests keep private cached source/state and automatically reconnect with the same identity. One guest window per device owns the outgoing queue; additional views are read-only and can take over when that window closes. Offline contribution is disabled, drafts remain editable, and the last synced native preview remains available.

Each participant runs a local native preview with independent interaction state. Synchronising data inside a generated/deployed app remains separate from authoring collaboration. The first network contract distributes the existing single-file Qt Quick app, not arbitrary assets or compiled frameworks.

Agent requests are queued and persisted. Ordinary chat does not invalidate in-flight agent work; new explicit agent directions and sketches do. Stale work is retried against current conversation/source. Compatible changes still apply directly, and only actual conflicts require agreement from the affected authors. Pending conflict discussion can invalidate its agreements. Requests interrupted by a host restart return to the queue.

See [LAN collaboration](LAN_COLLABORATION.md) for the complete host/join flow, NixOS firewall/VM prerequisites, background-host maintenance and acceptance tests. Native QML remains trusted code and invitations should be shared privately. Internet connections use Iroh with relay fallback; there is no cloud account system, per-member removal UI or host migration.

### Iroh transport (v0.3)

`centaur-network` is a native Rust helper using pinned Iroh 1.4.1. One helper and persistent endpoint key serve each data directory, shared by the background host and local UI windows. A private, owner-only Unix socket controls it. Exclusive locking prevents duplicate endpoints; the helper exits after all local clients leave and an idle grace period. It uses two worker threads, bounded control frames, a maximum of 24 tunnels and streaming socket backpressure.

The helper maps a dedicated Centaur ALPN and bidirectional QUIC stream to a loopback TLS connection. The existing certificate pin and project-scoped credential checks remain end to end, including on the local loopback hops. The QUIC initiator sends a short protocol preface before announcing its local tunnel, avoiding a stream-opening deadlock. Stream FIN and acknowledgement handling preserve final rejection and revocation messages. No project state or provider credentials are decoded by the helper.

Version 2 (`centaur2:`) invitations contain the project, single-use expiring credential, pinned TLS certificate and host Iroh endpoint identity/address hints. Iroh authenticates that endpoint; Qt checks the certificate before sending project credentials. The default n0 preset supplies relay and endpoint lookup services, with automatic direct paths where available. Relays carry encrypted traffic; availability still depends on network access and service reachability. No public TCP listener is needed for Iroh sharing. Version 1 LAN invitations and memberships continue to work, including alongside Iroh in the same project. Saved legacy sharing is retained when adding Iroh.

The host remains authoritative for membership, source, agent requests and conflict decisions. Each participant renders their own native preview. Peer-to-peer transport does not introduce a replicated database, offline authoring, automatic host election or synchronisation of generated-app runtime data.

### Next stages

The owner confirmed the LAN flow on the Intel NixOS Air and ARM64 NixOS VM on 28 October 2026: invitation/join, shared chat and live agent requests work. The next physical acceptance test uses different internet connections and relay fallback, followed by member management and sandboxing. Provider credentials remain on the host throughout.

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

The initial packaging approach is Nix. Builds can run on a faster machine or CI and be distributed through a binary cache, reducing compilation on entry-level devices. ARM64 Linux and x86-64 Linux require appropriate builds; the UTM VM and older Air must not be assumed to use the same executable. Centaur itself now has a [GitHub Actions/Cachix distribution workflow](BINARY_DISTRIBUTION.md) for both Linux architectures; the initial complete signed publications were verified on 27 October 2026. This distributes the authoring package, not standalone generated-app releases. Generated-app build/update delivery remains future work.

### App data and synchronisation

Installing the same app on two devices does not automatically share its data. A family planner, for example, needs an explicit storage and synchronisation design to show the same tasks on both devices.

Local persistence is part of the first installation milestone. Shared family data, authentication, synchronisation and any backend service are separate work. The storage format and migration strategy remain to be chosen. Package rollback alone must not be treated as rollback of user data.

Centaur's conversation, drawings, agent configuration and other authoring records are not automatically part of a deployed app. Package the app source, runtime and selected assets without copying the workshop's private state or provider credentials.

### Current implementation boundary

Today, generated apps are Qt Quick `Item` or `Rectangle` roots in `App.qml`. They can run outside Centaur with `centaur-preview /path/to/App.qml`, but this uses Centaur's preview runner. It is not yet an independently installable release with its own application identity, launcher or persistence contract. The starter app's in-memory task model does not yet provide persistent storage.

Export, independent app packaging, family installation links and release updates are planned features, not existing capabilities.

## Fonts and packaged assets

Inter is the default small-text typography in Centaur and its native example/preview runtime. Centaur v0.3.1 uses bundled Inter Tight above 12 pt and Inter at 12 pt or smaller, keeping existing sizes and weights. Both licences are bundled and installed. The upright variable Inter Tight file and its upstream commit/checksum are recorded in [font provenance](../assets/fonts/inter-tight/README.md). Pixel-based UI sizes are resolved through Qt font metrics for the same cutoff. Existing saved apps with explicit font choices retain those choices; the starter and future agent changes use the new split. It is bundled under the SIL Open Font License 1.1. Other open-source fonts can be used when their individual licences permit redistribution.

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

Design-system import and Deploy remain explicit placeholders. That UI integration did not itself add network collaboration; the current networking implementation is described above. A design-system store and standalone app deployment remain unimplemented.


## GNOME window frame and chat header (v0.3.1)

The chat header removes its standalone C badge. The secondary line shows a readable provider/model name when available, or **Agent unavailable** even when model metadata was saved earlier. The tooltip retains the exact provider/model identifier. Agent availability here remains the existing OMP/runtime availability signal; the UI does not claim a separate provider connectivity check.

Centaur preserves native desktop window decorations. Its Linux Nix package applies [a small Qt Adwaita patch](../packaging/patches/qt-adwaita-bottom-corners.patch) to use the existing 12 px top radius at the bottom too. Maximized/tiled frames retain Qt's square treatment. The native decoration reports that state through a private window property so the client background also becomes square when tiled; the app observes this without linking Qt's private Wayland API. The client background has transparent 12 px bottom corners so it does not cover the native frame shape; the sidebar follows the same bottom-left curve. No custom title bar or window-control icons are introduced. This patch affects the Qt package shipped with Centaur, not the desktop's global theme.

A 20 px bottom-right hit area displays the desktop's diagonal resize cursor and calls Qt's `startSystemResize(RightEdge | BottomEdge)`. GNOME handles the actual resize, constraints and snapping. The corner handle is disabled when maximized/fullscreen. A physical GNOME/Wayland check is still required for the system decoration and drag behaviour; headless UI checks cover client alpha, fonts, header state and the cursor target.

## NixOS installation and updates

The Linux package includes `centaur-update` and `centaur-cache-setup`. The guided [installation procedure](NIXOS_INSTALL.md) first inspects each machine. Where the original NixOS configuration is unavailable, the cache helper can add a root-owned Nix daemon systemd drop-in in the separately supported persistent `/etc/systemd/system.control` load path and a separate additive cache configuration, loaded through `NIX_CONFIG`. It checks the actual machine's supported unit paths and target mounts/store links, stages both files before either replacement, and verifies systemd loaded the override before restarting. This leaves the store-backed system configuration and `/etc/systemd/system` intact, retains standard caches and signature verification, and does not grant `trusted-users` privileges. Earlier successful installations in the old writable path are retained without duplication. Existing conflicting service settings are refused for review; this fallback is reversible and separate from reconstructing the OS configuration. The declarative cache module remains available when the actual managed system configuration is known.

The user helper downloads with builders disabled into a temporary GC root before stopping the existing host. It checks the package and local windows, asks the previous host binary to shut down, waits for the matching host process to exit, then activates that exact realised store path offline through Nix's atomic `build --profile` operation. The dedicated profile retains its old generations and no longer depends on a mutable or pinned `nix profile` entry. It must contain only Centaur. Launches retain the existing app data location and use the remembered absolute OMP path; helper settings live separately in `~/.config/centaur-launcher`. No OMP credentials, projects or collaboration identities are copied/reset by installation. Package rollback does not rewind user data.

