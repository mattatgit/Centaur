# V2 four-fix polish investigation

Scope: the owner's ARM64 NixOS GNOME review of `0.4.0-preview+9680f97`.
Implementation and publication remain on `main`; owner acceptance stays in
Installer (Centaur Install). All runtime checks use ARM64 NixOS under UTM.

## Causes recorded before changes

- **Open source** is a frontend import action, not an agent-supplied control. It
  opens the saved import's `source` directory (or its adaptation output) in the
  desktop file manager. `shell.py` adds it permanently below the working card
  and shows it whenever import metadata contains a framework. This remains true
  after successful import and while ordinary agent work is active. Move this
  inspection action to the existing project options menu, keeping Run preview
  and Retry import/Change source in their existing import flow.
- **Provider actions** explicitly give disconnected actions a `#171717` fill
  and white text as soon as the row is hovered. The original Figma component
  variants at `46:683` and `46:702` instead specify transparent row-hover
  actions, `#EBEBEB` direct-hover fill for disconnected providers and `#E0F2EE`
  for connected providers. Rows remain 504×48 with 12px corners; actions are
  32px high with 8px corners, 10px horizontal padding, Inter Tight Medium 12px.
  Connect uses its original 67px slot; Disconnect retains its 80px slot. Normal
  action text is `#323232`; direct-hover text is `#171717`.
  Native keyboard checks also found that making the entire disconnected button
  transparent excluded it from GTK's focus traversal. Hide only its label at
  rest; the transparent button retains its focus target and accessible name.
  Row hover or keyboard focus reveals the label without changing geometry.
- **Tooltips** originate both from explicit assignments and the common `button`
  helper, which sets a tooltip for every button. Replace that semantic information
  with GTK accessibility properties on Centaur controls, without changing global
  GTK/GNOME preferences or embedded app settings.
- **Working animation**: the source SVG contains both original frames and one
  second opacity tracks. Existing tests manually rendered each frame and checked
  tick state; they did not compare visibly clock-driven frames during an active
  request. GNOME's animation preference is enabled on the owner's VM. Native
  reproduction found GTK's `gtk-enable-animations=false` and portal
  `org.gnome.desktop.interface/enable-animations=false`, despite the stored GNOME
  preference being true. The portal's separate reduced-motion value was 0
  (no preference). No ticks ran, and only one native draw occurred in 2.3 seconds.
  GTK 4.22+ exposes the actual accessibility preference through
  [`gtk-interface-reduced-motion`](https://docs.gtk.org/gtk4/property.Settings.gtk-interface-reduced-motion.html).
  Use that property, with the legacy toolkit flag only on older GTK. Observe
  preference changes immediately, run only while mapped and working, and reset
  to the original first frame at idle/unmap/reduced motion. No global setting
  is changed.

## Verification and release

The ARM64 NixOS UTM product run passed all 27 checks, including changing native
pixels during actual agent work, reduced motion, idle/unmap transitions, exact
provider colours/geometry, keyboard focus, no configured/shown Centaur tooltips,
and the native project-menu action opening the exact managed source directory.
All 92 Python tests (zero skips), the packaged Phase 4 sandbox, all three service
suites and the standalone 19-check embedding gate also passed in the VM.

The existing chat-avatar and pan-pixel checks now wait for actual allocation and
current transforms. The new keyboard check observes each native focus change
before sending another Tab, retaining its exact geometry/pixel assertions.

[Curated evidence](evidence/gtk4-polish-2026-11-17/vm-verification.json) records the
source hashes and boundaries. The VM's normal DNS failure was again typed and
bounded correctly. Successful real-GitHub/Landline verification used a disposable
Git DNS fixture with normal certificate verification; no product or owner Git/DNS
override was installed. The verified branch is `linux-nix`, commit
`205fc1185335dc1c85b359af7673f6e5d7653222`, with both Linux entry points in agent
context. Owner provider authentication was not exercised or changed.

All 64 original asset hashes still match. Signed publication and final owner
acceptance remain separate gates; publication details will be recorded here.
