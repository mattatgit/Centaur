# Dialogue UI assets

Copied from Matt's Dialogue repository, `mattatgit/dialogue`, checkout `7e67a66c0cf338220e730ef7a972dbdb9d5a1e55` (`codex/accounts-shared-workspace`). The original repository licence is preserved in `LICENSE` and installed alongside Centaur's third-party notices.

- Sidebar, Interact/Comment state and message-send SVGs are unchanged copies of `assets/` files.
- `review-icons.svg` is the original symbol sheet. Individual `grid`, `arrow`, `reload` and `share` files wrap the corresponding original symbol geometry in a standalone SVG without redrawing it.
- `breadcrumb-arrow.svg` is the original inline SVG from `project.html`, with the SVG namespace added for standalone loading.
- `design-system-empty-suitcase.png` is the original Design Systems empty-state illustration. Reusing the PNG was explicitly approved because Dialogue has no SVG version.
- Build temporarily reuses Dialogue's Comment state SVGs. Draw and Undo temporarily retain Centaur's existing text glyphs, as approved while replacement SVGs are pending.

`css/review-shared.css`, `css/dialogue.css`, `css/prototype-review.css`, `workspace.html`, `design-systems.html`, `settings.html` and `js/review-model.mjs` supply the reference styles, states and grid defaults. These are implemented with native Qt components; no web renderer is introduced. Centaur continues using bundled Inter rather than Dialogue's Inter Tight.
