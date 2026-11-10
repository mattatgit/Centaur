# GTK4 interface reference

The preserved Qt frontend is the visual and interaction reference for the GTK4
development preview. Reference source is `codex/native-prototype` at
`3d24d11e959c1c6ec8c16df5b1c3e4bd7183e450`, particularly `qml/Theme.qml`,
`FlatButton.qml`, `Main.qml`, `SideNavigation.qml`, `ProjectsView.qml`,
`WorkspaceView.qml`, `ChatPanel.qml` and `SettingsView.qml`.

The owner requested that component dimensions and padding also follow an 8px
grid. Fixed geometry is rounded to an 8px step; typography and thin borders keep
their reference sizes. Responsive project-card widths round down to an 8px step
while retaining 32px gutters and a maximum of five columns. Flexible window and
canvas extents can follow the desktop's allocation.

## Layout and controls

| Element | GTK4 reference metric |
| --- | --- |
| Header | 80px high |
| Native GTK titlebar | Centaur-only #F8F8F8 fill in active/backdrop states; default controls, text, borders, shadows and window-state handling retained |
| Centaur UI mark | 24×24px viewport, centred in a 32×32px button; preserves the supplied 30:32 aspect ratio |
| Sidebar | 216px; 72px compact below a 760px window width; hidden in a project |
| Sidebar navigation | 40px high; original 32px SVGs; 8px inset/radius |
| Profile avatar | 40px square, 8px radius |
| Page panel | White, 16px radius |
| Project/settings page padding | 40px, reducing to 24px on small pages |
| Project cards | 256px high; 24px padding; 32px gutters; one to five columns |
| Project badge | 56px square, 16px radius |
| Card options | 32px button; rounded hover/pressed background; Rename/Delete menu |
| Workspace margins | 16px inside the existing 8px page edge |
| Canvas/chat splitter | 8px; chat preferred 432px, minimum 368px, maximum 624px |
| Interact/Build switch | 240 × 48px, centred in the window; two 112 × 32px buttons |
| Standard buttons | 32px high; 8px radius; reference plain/soft/dark/lime/selected tones |
| Build toolbar | 296 × 48px, 16px above the canvas bottom; Draw/Comment/Undo |
| Chat inset/spacing | 24px inset; 16px sections; 24px between messages |
| Chat avatars | 24px square, 8px radius; human and agent reference colours |
| Composer | 104–184px high; 16px radius; mention control and 32px icon send button |
| Chat footer | Left-aligned 24px-high version/update button, 8px availability badge; status/progress right aligned, 8px gap |

Chat remains available in both modes. The sidebar, project actions and settings
retain the Qt structure. Deployment and design-system import remain placeholders.
Deleting a project still requires explicit confirmation; cancelling is the safe
initial action. Local names, agent naming, grid preferences, invitations and
sharing use the retained controller rather than a second set of UI-only state.

## Typography and assets

Inter is used through 12pt (16px); Inter Tight is used above 12pt. Fonts are the
bundled originals, independent of the desktop's installed fonts.

| Chat element | Family | Size | Weight |
| --- | --- | --- | --- |
| Chat heading | Inter Tight | 14pt | 600 |
| Body and composer | Inter Tight | 12.5pt | 400 |
| User/agent names | Inter | 10.5pt | 600 |
| Status/model line | Inter | 10.5pt | 400 |
| Avatar letters | Inter | 9pt | 600 |
| Timestamps | Inter | 9pt | 400 |
| Version/update button and footer progress | Inter | 8.5pt | 400 |

The former author/keyboard-hint footer is removed. The version button changes
to **Update app** on hover or keyboard focus, retaining its width. Its 8px
circular availability badge matches the `#ccff00` agent avatar. The footer and
Settings share the same updater; details and acceptance are recorded in
[GTK4_UPDATER.md](GTK4_UPDATER.md).

The main window's `centaur-window` CSS class scopes the native default titlebar
fill override. It sets only background colour/image, keeping the native titlebar,
controls, active/backdrop foreground treatment, border/shadow and maximized,
tiled and fullscreen behaviour. This does not install a custom titlebar or
change GNOME's global theme. Other applications and generated-app processes
retain their own styling. GNOME's actual decorated appearance requires VM review;
the regular headless integration suite deliberately disables decorations.

Published fill adjustment: `4ad8404619110fe170c0ddf9eaafa0e95ee21670`
(`0.4.0-preview+4ad8404`). All 37 checks and [ARM64 product/update run
42753563095](https://github.com/mattatgit/Centaur/actions/runs/42753563095) passed,
along with [standalone embedding run
42753563071](https://github.com/mattatgit/Centaur/actions/runs/42753563071).
Native evidence `13734249042`, updater `13734651883`, signed distribution
`13734836194`. The complete 531-path closure passed signed empty-store download
verification; the release feed advertises this exact source at
`/nix/store/na7m83da1gc9sw7k8rbflp9b16gzfsc1-centaur-gtk4-preview-0.4.0-preview`.
These checks validate the stylesheet and existing app flows; they do not establish
the decorated GNOME titlebar's active/backdrop appearance. That remains a VM check.

Other reference sizes include 14pt/600 project titles, 11pt descriptions, 10pt
card metadata, 14px navigation text, 16px/600 section titles and 12px/600 button
labels. Text sizes do not round to 8px steps.

SVG geometry comes directly from `assets/dialogue`, with the same alpha-mask
colour treatment used by the Qt SVG renderer. The Centaur mark comes from
`packaging/centaur.svg`; the Design Systems suitcase is the approved original
`design-system-empty-suitcase.png` at 176px. Build continues to reuse the approved
Comment SVG; Draw and Undo retain the previously approved temporary glyphs.

## Preserved preview boundary

This is a restoration of Centaur's interface, not a generated-app redesign. The
tested Casilda backend, separate app process, logical app dimensions, five zoom
levels, Fit, centring, panning, clipping and app shadow remain behind the existing
viewport interface. Canvas controls float over the canvas without adding an app
frame. Agent canvas images contain the app and annotations, excluding Centaur's
floating controls and chat.

The VM acceptance issues in `GTK4_MIGRATION.md` remain separate: drawing beyond
app bounds, the unfinished comment-text workflow, generated-app runtime data
persistence and a visible History interface are not resolved by this UI pass.
Neither production Qt replacement nor native macOS embedding is implied.

## Verification

Native ARM64 CI captures the actual GTK frontend on a disposable Wayland desktop,
including empty projects, Design Systems, settings, project dialogs, Interact,
Build, project menus, cancelled deletion and all five grid column counts. It
checks allocated geometry as well as two-profile collaboration, fixture-agent
changes, genuine-conflict agreement, invalid-change rejection, history restore,
preview reopen and clean shutdown. These are automated checks, distinct from
hands-on UTM testing and real OMP/provider requests.

## Navigation and control tidy-up — 11 November 2026

Projects, Design Systems and Settings use their selected sidebar entries as
their page labels; the duplicate titles in the top bar are removed. The top
bar keeps its existing height, actions and workspace breadcrumb.

Invite is an 88×32px secondary button matching Deploy, with the existing 8px
corner radius and hover scaling. A 1px inset `#d3d7ce` stroke leaves its normal
background clear without changing its layout dimensions. Its hover fill is
`#f3f3f3`. Deploy retains the existing filled style and SVG.

The footer version button keeps its label-to-Update-app interaction, fixed
hover width and availability badge. Its 8px horizontal padding and 8px radius
frame a `#ebebeb` hover/focus background. Progress remains on its right.

The product canvas no longer has a Centre button; zoom, Fit, automatic centring
on resize, panning and Restart remain. The separate embedding experiment's
test controls are unchanged.

Published ARM64 build: **0.4.0-preview+4451f19**, source
`4451f19701cf586e0427ce462bc742626075a45a`, store
`/nix/store/q2yc9qwci2bkwcqywivnzmx5dchcfm37-centaur-gtk4-preview-0.4.0-preview`.
[Product/service/updater CI 42927073797](https://github.com/mattatgit/Centaur/actions/runs/42927073797)
and [standalone embedding CI 42927073579](https://github.com/mattatgit/Centaur/actions/runs/42927073579)
passed, including all 37 Python tests, equal allocated button dimensions, and
rendered-pixel checks for the footer hover fill and rounded corners. Project,
Design Systems, Settings, workspace and footer-hover screenshots were inspected.
Native screenshots: artifact `13814801601`; updater screenshots/recovery reports:
`13814577593`; signed distribution: `13814363163`. The complete 531-path signed
closure passed empty-store verification with builders disabled, and the update
feed was read back to confirm this source/path. Hands-on VM review belongs in
Centaur Install.
