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
and mono previews visually inspected, 35 GTK/Python tests passed. Native ARM64
icon lookup, desktop/profile update checks and publication are pending.
