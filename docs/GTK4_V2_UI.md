# Centaur UI V2

The approved [Centaur UI V2.0 design](https://www.figma.com/design/9RnuP79pD007wjhTdXZ5WW/Centaur?node-id=43-689) supersedes the older Qt visual reference. The native GTK4 frontend still uses the existing coordinator, project storage, collaboration protocol, preview viewport, import broker and signed updater. The recoverable baseline is `checkpoint/pre-v2-ui-2026-11-17` at `cd45de767d0aba11991424555ca57e6c45c462fd`.

## Native presentation

The 80px header is a supported `Gtk.WindowHandle` titlebar containing the breadcrumb/actions and actual `Gtk.WindowControls` close action. There is no separate named titlebar. Native dragging, resizing, maximising, tiling, fullscreen, window switching and close behaviour remain GTK/compositor responsibilities. The styles are scoped to Centaur; the embedded application is a separate process with its own styling and logical dimensions.

The workspace puts the resizable chat pane on the left and the application canvas on the right. At the 1440×1024 reference size the chat is 432px wide, the splitter is 8px and the canvas starts at (448,136). The Interact/Build control is 136×24px; reload, grid and zoom share the 56px toolbar. The six established zoom modes preserve application dimensions and input mapping. Draw/Comment/Undo use the existing 128×48px floating toolbar. Comment targets remain anchored to the app, focus the composer when placed and accompany the next message, including across the application's boundary.

Project cards contain an actual app-only thumbnail, application type and edited time. The thumbnail is an atomic cache entry under the existing project's `.centaur` directory; it is not an extra project or shared source change. The original white-clay fallback is used until an image is available. Rename and confirmed deletion retain existing management behaviour, including recoverable deletion.

The Create split button has a direct main action and a separate arrow menu for Create/Import/Join. The default modal sizes are Create 408×352, Import 408×432, Join 408×272 and Invite 408×248. Conditional repository branch controls expand Import without replacing its existing selection, provenance or source-protection rules. Inputs use caret focus; non-text controls retain understated keyboard focus.

## Original artwork and motion

All V2 artwork is bundled locally in `assets/figma/v2`. `source-map.json` records the original export URL or supplied file and its SHA-256. SVG paths are unchanged and rendered with their original colours/aspect ratios. Grey button plates and layout slots are GTK styling around the original art, rather than altered SVGs. Design example photos, app screenshots and model names are not substituted for actual user/project/runtime data.

The owner's supplied `centaur_wait_animation.svg` is preserved byte-for-byte (SHA-256 `b976ac19686b3c3c59d29291fb9a9a1bf7b43f74464270d6cbb2c3c68234f78c`). The standalone second Figma frame exported transparently, so the supplied complete animation replaces that unusable export. Since librsvg renders a static SVG document, GTK's frame clock applies the original one-second opacity tracks to its original `frame-1` and `frame-2` groups at runtime. There is no path extraction or redrawing. Reduced motion uses a static first frame. The import canvas uses the original clay image and shadow; activity remains in the chat, with a Stop action for the current request.

## Settings persistence and OMP

Names and grid controls save automatically after a short debounce; pressing Enter or leaving a numeric field also commits it. The bridge correlates acknowledgements with requests and checks `QSettings::sync()` status. The Changes saved indicator requires successful persistence. Rapid edits retain the desired full grid state until the corresponding snapshot arrives. A project agent-name edit captures its original project ID before navigation; its acknowledgement is based on that project's saved metadata.

Avatar selection uses GTK's native file chooser or file drop. Validated image bytes are copied atomically to the Centaur data root's `profile-avatar` with mode 0600 and file/directory fsync. The sidebar and the owner's chat rows use that image. No existing conversation/member identity is rewritten. Join uses the configured username; a connected guest's bound collaboration identity remains unchanged.

The provider cards use OMP's supported settings RPC to discover login providers, authenticated state and the current available model catalogue. No design example model catalogue is hardcoded. This helper runs in an empty temporary directory with no sessions, tools, skills, rules, extensions or LSP. It permits only the documented connection/model/authentication RPC operations, correlates replies, bounds requests and reaps its process group on failure or close. Provider login/logout requires its explicit Settings action. Account removal offers the actual OMP account list; secret input is not collected by Centaur.

OMP's `set_model` RPC validates selection but does not persist its global default. Centaur therefore saves its choice in its own `agent/model` preference and passes OMP's supported `--model` option on subsequent requests, including from an already-running host. OMP's credentials and configuration files remain owned by OMP. The actual installed OMP 18.12.6 read-only catalogue probe was performed in the ARM64 NixOS VM; authentication writes are exercised only with a disposable fixture.

General model terminal access remains disabled. The diagnostic broker, verified sandbox/resource limits, source acquisition, branch authority and retry policy are unchanged by this UI work. The signed update feed retains its protocol-1 channel identifier `codex/gtk4-migration`; current source development remains on `main`.

## Verification boundary

Engineering checks run only on ARM64 NixOS under UTM, with private test displays, profiles and source copies. They cover native chrome and pointer states; original animation frames, timing and reduced motion; actual Settings acknowledgements; live fixture model selection; avatar selection; all six zooms and cross-boundary comments/drawings; two-profile collaboration and agent changes; conflicts, restoration, Stop, project navigation/cards and local/GitHub/Landline import regressions. The exact verified source and resulting native evidence are recorded separately.

The disposable compositor uses [GTK’s documented `GDK_DEBUG=no-portals` setting](https://docs.gtk.org/gtk4/running.html) for the native avatar chooser fallback. The product uses the normal platform chooser; the GNOME portal itself remains a hands-on check.

The VM’s normal resolver intermittently failed for `github.com` in both Git and curl outside Centaur. The importer correctly recorded a typed DNS failure and stopped within its retry limit. Functional import verification therefore also uses a disposable Git configuration with a current DNS answer and normal HTTPS hostname/certificate verification. It still acquires the real repositories and verifies their commits; this fixture is not included in the product and does not change the owner’s DNS/Git settings. Normal-network verification remains part of the existing release CI and the VM network issue belongs in the installation/acceptance chat.

Installation and hands-on acceptance remain in **Centaur Install**. Automated results do not imply that human visual/interaction acceptance is complete. The separate Qt installation and all owner projects, conversations, OMP credentials/configuration and collaboration identities are preserved.
