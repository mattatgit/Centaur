# Centaur GTK4 V2 corrections

Signed preview **`0.4.0-preview+c337908`** was built from
`c33790850fae820091c742419bacd4d4e18f79a5`. The public update manifest matches
the verified Cachix artifact and its 613 signed closure paths. The VM also
verified the packaged frontend against the tested source and checked the
original Figma and animation assets. [Signed preview](https://github.com/mattatgit/Centaur/releases/tag/gtk4-preview) · [Product and updater CI](https://github.com/mattatgit/Centaur/actions/runs/44451576105) · [Embedding CI](https://github.com/mattatgit/Centaur/actions/runs/44451576075) · [Release verification](evidence/gtk4-v2-corrections-2026-11-19/release-verification.json)

## Visual review

The Projects tile and breadcrumb were exercised in Figma Presentation in both directions. The prototype clears Projects content before the white canvas moves its left edge from x216 to x448. Its right edge stays at x1432, and Chat comes in from the left. Returning to Projects fades the editor content, moves the canvas edge back, and reveals the cards. The native recordings show the same 232 px travel in a 1200 px window and a stationary right edge. GTK4 keeps the same embedded process, conversation, scroll position, zoom and pan through the transition. The stacked view below 720 px changes pages immediately. [Interactive Figma prototype](https://www.figma.com/proto/9RnuP79pD007wjhTdXZ5WW/Centaur?node-id=68-2121)

The 136 × 24 px mode control paints one rounded track and a single moving selection. Its Interact and Build positions use the Figma widths and fills. The 220 ms GTK animation makes intermediate positions visible at normal playback speed. Keyboard selection and GTK reduced motion are covered by the native checks. [Figma Main switch](https://www.figma.com/design/9RnuP79pD007wjhTdXZ5WW/Centaur?node-id=68-2297)

- [Projects to Edit](evidence/gtk4-v2-corrections-2026-11-19/projects-to-edit.mp4)
- [Edit to Projects](evidence/gtk4-v2-corrections-2026-11-19/edit-to-projects.mp4)
- [Interact to Build and back](evidence/gtk4-v2-corrections-2026-11-19/mode-switch.mp4)
- [Frame measurements](evidence/gtk4-v2-corrections-2026-11-19/recorded-motion.json)

## Sharing and regression checks

Creating an invitation enables the host listener before the project has any invited members. The tile now requires an actual participant roster with someone other than the current user. Two disposable profiles exercised a never-shared tile, the host tile with an outstanding invitation, and the same host tile after an authenticated guest joined. The host and guest saw both participants on hover, and each saw their own avatar first. [Unshared](evidence/gtk4-v2-corrections-2026-11-19/polish-unshared-hover.png) · [Outstanding invitation](evidence/gtk4-v2-corrections-2026-11-19/polish-unused-invitation-hover.png) · [Shared host view](evidence/gtk4-v2-corrections-2026-11-19/polish-shared-host.png) · [Shared guest view](evidence/gtk4-v2-corrections-2026-11-19/polish-shared-guest.png)

The ARM64 NixOS run under UTM passed 41 product checks, 19 native embedding checks, 94 Python tests and all three service suites. The final product run passed the host and guest drawing checks after fixing click readiness during the return transition. [Product results](evidence/gtk4-v2-corrections-2026-11-19/summary.json) · [Embedding results](evidence/gtk4-v2-corrections-2026-11-19/embedding-summary.json)

The accepted updater behaviour passed all 13 checks in CI and again with the
signed artifact in disposable VM profiles. The Edit path showed the completion
receipt for ten seconds. The Settings path showed it for five seconds on the
first Edit visit. Both paths returned to the original idle artwork after the
receipt expired. [Updater checks](evidence/gtk4-v2-corrections-2026-11-19/updater-summary.json)

Installation and owner acceptance are managed in Centaur Install.
