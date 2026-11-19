# Centaur GTK4 V2 follow-up

The signed preview is **`0.4.0-preview+ff58f74`**, built from
`ff58f74d19e5e4c2c7751a46c1d5abc658506826`. The public feed matches the
verified manifest and its 613 signed closure paths.
[Preview](https://github.com/mattatgit/Centaur/releases/tag/gtk4-preview) ·
[Product and updater CI](https://github.com/mattatgit/Centaur/actions/runs/44446129302) ·
[Embedding CI](https://github.com/mattatgit/Centaur/actions/runs/44446129466)

The four refinements build on the accepted `0.4.0-preview+4144bb8`. The
[prototype](https://www.figma.com/proto/9RnuP79pD007wjhTdXZ5WW/Centaur?node-id=68-2121),
[Main switch](https://www.figma.com/design/9RnuP79pD007wjhTdXZ5WW/Centaur?node-id=68-2297),
[shared tile](https://www.figma.com/design/9RnuP79pD007wjhTdXZ5WW/Centaur?node-id=68-2477)
and [default footer](https://www.figma.com/design/9RnuP79pD007wjhTdXZ5WW/Centaur?node-id=44-1925)
guided the implementation.

- A verified update shows **Complete** for ten seconds when started in Edit.
  The Settings path holds its receipt until the first Edit visit after the
  updater restarts Centaur, then shows it for five seconds. Both paths return
  to the original grey download arrow and installed version chip. Older
  updater requests use the restored page to identify where the update started.
- Projects and Edit exchange places over 320 ms. Chat travels from the
  left and the canvas from the right. The panes retain their allocations
  during the animation. Reopening the selected project keeps the same native
  preview process, chat position and viewport. Below 720px the panes stack
  vertically so the window can keep its existing size.
- Interact and Build share one rounded track and a single sliding indicator.
  The 180 ms animation can reverse from its current position. The native
  toggle buttons apply the selected mode immediately and expose their active
  state to keyboard and accessibility navigation. Both animations respect
  GTK reduced-motion settings.
- Shared project tiles reveal their roster on pointer hover. The 24px
  circles overlap by 8px with a 16px top and right inset. Centaur uses the
  current user's saved picture when available and initials for people whose
  pictures are unavailable. Larger rosters show a count for the remaining
  participants and expose the full roster in the accessible description.
  Membership names come from the existing authenticated project connection.

The signed updater, agent execution and sharing actions retain their existing
behavior. Pass 3 owns the remaining sharing workflows.

The ARM64 NixOS run in UTM passed all 40 native product checks, 19 embedding
checks, 94 Python tests with zero skips, and three service suites. The two
native profiles joined a shared project and kept their respective app
processes through navigation. The native tests also covered rapid mode
changes, keyboard activation, reduced motion, an unshared tile and a
560px-wide Edit view. All 67 original Figma exports and the supplied
animation match their recorded hashes.

[Product results](evidence/gtk4-v2-followup-2026-11-19/vm/native/summary.json) ·
[Opening](evidence/gtk4-v2-followup-2026-11-19/vm/native/polish-projects-to-workspace.png) ·
[Returning to Projects](evidence/gtk4-v2-followup-2026-11-19/vm/native/polish-workspace-to-projects.png) ·
[Mode selection in motion](evidence/gtk4-v2-followup-2026-11-19/vm/native/polish-mode-slide-right.png) ·
[Shared tile](evidence/gtk4-v2-followup-2026-11-19/vm/native/polish-shared-host.png) ·
[Narrow Edit view](evidence/gtk4-v2-followup-2026-11-19/vm/native/polish-narrow-workspace.png)

The exact signed artifact passed 13 updater checks in CI and in disposable
ARM64 NixOS profiles. Both signed transactions switched profiles and
restarted Centaur. Edit showed the receipt for ten seconds, Settings held it
until the first Edit visit and showed it for five seconds, and both returned
to the original grey icon. A later Edit visit after expiry showed the idle
icon. The VM run reused a disposable copy of public package metadata and
verified the signed package and original artwork. The installed owner
profile remained on the accepted baseline.
[Release receipt](evidence/gtk4-v2-followup-2026-11-19/release-verification.json) ·
[Edit after completion](evidence/gtk4-v2-followup-2026-11-19/ci/updated-app.png) ·
[Edit after expiry](evidence/gtk4-v2-followup-2026-11-19/ci/edit-completion-expired.png) ·
[First Edit visit after Settings update](evidence/gtk4-v2-followup-2026-11-19/ci/settings-completion-in-edit.png)

Installation and hands-on GNOME acceptance remain in Centaur Install.
