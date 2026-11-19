# Centaur GTK4 V2 follow-up

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
