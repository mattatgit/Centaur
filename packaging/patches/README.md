# Qt Adwaita bottom corners

`qt-adwaita-bottom-corners.patch` changes only the frame path in the pinned
Qt Wayland Adwaita decoration. Qt's existing 12 px radius is applied to all
four corners instead of the top two. Maximized/tiled frame geometry, shadows, native
window buttons, title bar, pointer cursors and system resize behaviour are retained.

The Nix flake applies this patch to its private Qt Wayland package, explicitly enables the Adwaita feature with its SVG dependency and verifies that the plugin was installed. Centaur selects that native plugin in GNOME sessions unless a user has explicitly overridden the decoration. No global
GNOME settings or system packages are modified. Transparent bottom client corners
in Main.qml keep Centaur's own background from covering the frame curve.

Upstream source (Qt's licence/copyright headers are retained in the source):
https://code.qt.io/cgit/qt/qtwayland.git/tree/src/plugins/decorations/adwaita/qwaylandadwaitadecoration.cpp

Qt release/source hashes remain pinned by flake.lock and the selected nixpkgs
package. Rebuilds fail if the patch no longer applies to an upgraded Qt version.

The native decoration reports `_centaurSquareFrame` on its window. A small
application observer uses this to turn off the client corner alpha while tiled
or maximized, preserving opaque square edges and normal native snapping.
