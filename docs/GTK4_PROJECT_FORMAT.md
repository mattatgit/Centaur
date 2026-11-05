# GTK4 development project format

The GTK4 migration branch uses an experimental `gtk4-v1` application bundle. This is a native GTK4/PyGObject frontend and generated-app path, not a web renderer. The package is `gtk4-preview`, launcher `centaur-gtk4`; it is separate from the preserved Qt package and the earlier `gtk4-embedding-test` probe.

## Storage and compatibility

A project stores **`App.gtk.json`** alongside the existing `.centaur/state.json`, conversation log and Git history. `state.appFormat` is `gtk4-v1`. Legacy projects without that field still use **`App.qml`** and their existing checker/history paths. There is no automatic conversion of a Qt project or copying of production data.

The complete generated app is one atomically written, versioned JSON bundle. That avoids partially updating layout and behaviour independently. The bundle contains:

```json
{
  "format": "gtk4-v1",
  "width": 520,
  "height": 640,
  "designSystem": "centaur-basic-v1",
  "files": {
    "app.py": "Python behaviour defining create_window(builder)",
    "app.ui": "GtkBuilder XML containing a GtkWindow named window",
    "style.css": "GTK CSS"
  }
}
```

The prototype bounds the bundle to 256 KB and dimensions to 120–4096 whole logical pixels. Exactly those three file names are accepted; no archive extraction or arbitrary output paths are supported. The runner loads the files from the bundle in memory. This initial format deliberately does not implement asset imports, external packages or a comprehensive design-system library.

`create_window(builder)` connects behaviour and returns an unpresented `Gtk.Window`. The runner supplies the `Gtk.Application`, dimensions, presentation, private Wayland connection and lifecycle. App code must not launch another application/main loop or present its window during construction. The starter separates Python actions, GtkBuilder layout and CSS so a later design system can replace presentation without rewriting project coordination.

The design-system identifier is versioned metadata for now, not an implemented registry or compatibility guarantee. A future format can add components/tokens/templates and controlled dependencies. Inter and Inter Tight are bundled; GTK CSS uses Inter through 16 logical CSS pixels (12 pt at 96 DPI) and Inter Tight above that.

## Agent changes and history

OMP still runs only on the authoritative host, using its existing executable and login. A GTK proposal returns `kind`, `message`, explicit `conflict` and a complete `gtk` bundle. Qt proposals retain their `qml` field. The coordinator rejects a proposal in the wrong project format.

Before changing live source, a separate checker loads the bundle, compiles Python, parses GtkBuilder and CSS, constructs the window and checks the window contract. It does not present the window. The coordinator bounds validation to ten seconds. A failure leaves the existing source, history and previews intact. This is a construction check, not a proof that every later interaction works.

Passing source is committed through the existing Git/checkpoint path, with rollback if committing fails. Restores retrieve the exact bundle from an ancestor checkpoint and validate it again. Ordinary requests remain their author's approval; only a genuine conflict between affected authors waits for their agreement. Existing queued/stale-request, cancellation and conflict policies remain in the coordinator.

**Generated Python is trusted native code with the user's permissions. Validation and a private display are not an execution sandbox.** The preview gives the app temporary config/data/cache directories, as the earlier experiment did; durable generated-app data and deployable packaging need their own contract.

## Collaboration and interface boundary

The GTK frontend talks over bounded newline JSON to `centaur-gtk4-bridge`. That non-visual C++ adapter reuses the existing Controller/Session/SharedProject implementation for local project management, TLS authentication/pinning, persistent memberships, Iroh transport, reconnect/outbox, OMP and negotiation. Qt libraries remain temporary service dependencies; the visible frontend, canvas and generated apps use GTK4. This is not a completed removal of every Qt dependency.

The GTK service build excludes the Qt frontend and Qt Wayland compositor. Core, network and Iroh regressions still run. The default Qt build and preserved branch retain their original frontend and embedding checks.

Shared GTK projects carry the whole bundle through the existing authenticated source/hash channel. Guests save `App.gtk.json`, and each machine launches its own separate native preview. A `gtk4-v1` capability is required before consuming an invitation to a GTK project; older Qt-only clients receive an incompatibility message. Project IDs, authorship, revisions and decisions stay host-owned. Generated-app runtime data is not synchronised by this source protocol.

The viewport owns logical dimensions, zoom, centring, clipping and panning; the Casilda adapter owns native surfaces and process lifecycle. Drawing/grid coordinates share the viewport transform. GTK annotations use normalised app coordinates with a full-app frame, independent of zoom. Agent canvas captures contain the canvas and marks, excluding chat. Compatible source changes restart previews; chat alone does not.

## Development isolation and acceptance

The GTK launcher defaults to **`~/.local/share/Centaur/GTK4`**, preserving normal Centaur data and profiles. It finds the VM's existing `~/.local/bin/omp` through PATH without copying or changing credentials. The ordinary updater/desktop shortcut is not redirected. Background hosting survives a frontend close; `centaur-gtk4 --stop-host` stops the host for the selected GTK data directory.

Use the separate ARM64 VM test profile and Centaur Install for machine instructions. Installation/publication is gated on native checks and full signed-closure verification. This development preview is not approval to replace production Qt Centaur. Native macOS embedding, physical remote-client acceptance, IME/alternative layouts, Num Lock, fractional desktop scaling and default/GPU rendering remain separate acceptance work.
