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

The native decoration queues `_centaurSquareFrame` updates onto its window’s GUI thread, since frame painting may occur on a render thread. A small
application observer uses this to turn off the client corner alpha while tiled
or maximized, preserving opaque square edges and normal native snapping.


The optional GTK4 Casilda derivation also applies `casilda-pointer-grab.patch` on the migration branch. It preserves the implicit pointer grab and surface-relative motion while a button is held, including when the pointer leaves and returns to the original surface. Native regressions exercise this at 100% and 150%. This is the third local Casilda patch (`1.6.0-centaur3`), alongside initial-keymap and ordered-event-state fixes; it is experimental, not upstream approval.
