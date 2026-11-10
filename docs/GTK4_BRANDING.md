# Centaur GTK4 application identity

The owner's 10 November 2026 artwork is retained verbatim in
`assets/branding/Centaur.svg` (120×128, orange `#FF9601` and green `#177967`)
and `Centaur_mono.svg` (30×32, `#171717`). Do not redraw these paths.

`packaging/centaur-app.svg` wraps the colour mark in a transparent 128×128
canvas. Uniform 0.875 scaling gives a 105×112 silhouette, centred with an 8px
top/bottom margin and 11.5px sides. It adds no background tile, shadow or altered
colours. The SVG is the scalable app icon; Nix renders transparent PNGs at
16, 24, 32, 48, 64, 128, 256 and 512 pixels using librsvg.

The GTK UI loads the supplied monochrome SVG as its existing `centaur.svg`
asset. Its aspect ratio is preserved in the existing 32px UI icon slot and the
existing alpha-mask tinting retains hover states. The Qt branch/assets are
preserved. A copy of the mono SVG is also installed as the symbolic desktop icon.

Desktop filename, GTK application ID, window icon, icon name and
`StartupWMClass` all use **org.centaur.Gtk4**. The packaged menu entry is named
**Centaur GTK4**, keeping the preserved Qt installation distinct. Nix validates
the desktop file while packaging; GTK adds the bundled icon theme search path.

The separate GTK profile does not normally contribute to the desktop's global
data search paths. On normal startup from the dedicated installed profile,
`desktop.py` registers per-user desktop/icon symlinks under `$XDG_DATA_HOME`
(default `~/.local/share`). They point through the stable GTK profile, so icons
and the launcher follow future updates. Development runs outside that profile
do not register themselves; existing user-created entries are left intact.

The packaged menu action uses `--desktop-launch`. Its small private settings file
is `$XDG_CONFIG_HOME/centaur-gtk4/desktop.json` (default `~/.config`), recording the
current GTK data path and only `GSK_RENDERER`, `GDK_BACKEND`,
`LIBGL_ALWAYS_SOFTWARE` and `CENTAUR_AGENT` when present. This retains the VM's
Cairo configuration and existing OMP executable without copying credentials.
No system settings, Qt desktop entry or Qt projects are changed. An older pinned
manual shortcut may need to be replaced in favourites with the registered
Centaur GTK4 entry; installation guidance belongs in Centaur Install.

Local checks: original SVGs compared against the supplied files, 512px colour
and mono previews visually inspected, 35 GTK/Python tests passed.

## Verified ARM64 build — 10 November 2026

Published source `a842d71ca0c2faffca0cffdf7e1dd90d3a3b174f`, version
`Centaur GTK4 0.4.0-preview+a842d71`.
Store path:
`/nix/store/27nfwpfyh1wp3vkmcgfg986ipg6w5d9c-centaur-gtk4-preview-0.4.0-preview`.
[Product/update CI 42745110211](https://github.com/mattatgit/Centaur/actions/runs/42745110211)
and [standalone embedding CI 42745110058](https://github.com/mattatgit/Centaur/actions/runs/42745110058)
passed. The public `gtk4-preview` feed was read back and advertises this exact
source/path after acceptance.

The native GTK report confirms the window icon ID and resolves both full-colour
and symbolic icons. The real updater test validates the registered per-user
desktop symlink, icon/StartupWMClass keys, saved data folder and Cairo setting,
all eight RGBA PNG sizes, and the symlink following the profile into the new
package after update. The updated UI mark was inspected in the restart image.
All 35 Python checks and existing native embedding, canvas, collaboration and
footer-update tests passed. Updater evidence: `13731232825`; native product
evidence: `13731412230`. Signed distribution artifact `13731462091` confirms
the complete 531-path runtime closure downloaded into an empty store with
builders disabled. Qt profile/data sentinels remained intact.

GNOME app-grid/dock appearance and launching via the menu on the actual UTM VM
remain hands-on acceptance. CI verifies the desktop descriptor/links and config
restoration, rather than operating GNOME Shell itself. The GUI update candidate
is already realised in CI; the publisher separately supplies the fresh-download
verification. Continue machine-specific guidance in Centaur Install.
