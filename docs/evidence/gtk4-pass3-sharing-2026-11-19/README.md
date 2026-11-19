# GTK4 Pass 3 sharing verification

The disposable ARM64 NixOS VM run used three native GTK4 instances with separate profiles. It covered project switching, participant rosters on both sides, departure and rejoining, host cancellation and confirmation, an online guest retaining a copy, and an offline guest declining after reconnecting and restarting. The original host app and a second active share survived. The retained app ran locally from a new Git repository with no remotes, and a message sent there stayed on the guest's device.

| Flow | Evidence |
| --- | --- |
| Hover rosters and sidebar roles | [Host](01-host-roster.png), [guest](02-guest-roster.png) |
| End sharing from Projects | [Project menu](03-host-project-menu.png), [confirmation](04-host-confirmation.png), [recording](host-stop-sharing.mp4) |
| Keep an independent copy | [Guest decision](05-guest-decision.png), [retained project](06-independent-project.png), [recording](guest-keep-copy.mp4) |
| Decline after reconnecting | [Guest decision](07-offline-guest-decision.png), [Projects after declining](08-offline-guest-declined.png), [recording](offline-guest-declines.mp4) |

The host confirmation uses the layout and original artwork from [Figma's confirmation](https://www.figma.com/design/9RnuP79pD007wjhTdXZ5WW/Centaur?node-id=104-3520). Stop sharing sits before Delete in the existing project menu, as shown in the [Figma menu](https://www.figma.com/design/9RnuP79pD007wjhTdXZ5WW/Centaur?node-id=63-1680). The guest decides whether to keep a copy.

Retained projects start with the last authenticated app snapshot and its cached conversation, annotations, and decisions. Each copy has its own project ID, local agent defaults, and a fresh Git history. The original host's repository, imported source checkout, credentials, and pending work stay separate. An offline guest receives the end notice when it can reach the original host again. The Iroh regression covers host restart and reuse of the same project ID in a later share.

The [native integration summary](summary.json) lists all 45 checks. The [embedding summary](embedding-summary.json) covers the separate GTK client and embedding harness. Source [`d9ea71e`](https://github.com/mattatgit/Centaur/commit/d9ea71eeb42c72ecfa0dfbdd71e2b30f8a6bf5f8) matches the VM candidate. The [signed release workflow](https://github.com/mattatgit/Centaur/actions/runs/44462337557) ran against that commit.

Preview `0.4.0-preview+d9ea71e` is available through the [public update feed](https://github.com/mattatgit/Centaur/releases/tag/gtk4-preview). The [release receipt](release-verification.json) records the signed artifact, the matching advertised manifest, and the preserved owner profiles. The [updater report](updater-summary.json) passed in CI and in the VM's disposable update profile.
