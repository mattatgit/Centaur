# GTK4 multiplayer follow-up verification

The release workflow exercised two native GTK4 instances with disposable host and guest profiles on each GitHub Linux runner. Each architecture passed 50 native integration checks and 13 signed updater checks. The native suite verified chat, agent builds, project navigation and previews, plus the new avatar, ink, pointer and approval scenarios.

| Behaviour | ARM64 Linux | x86-64 Linux |
| --- | --- | --- |
| Remote images on chat and the hover roster | [Chat](aarch64-linux/avatars-chat-host.png), [roster](aarch64-linux/avatars-roster-guest.png) | [Chat](x86_64-linux/avatars-chat-host.png), [roster](x86_64-linux/avatars-roster-guest.png) |
| Blue host stroke with its acknowledgement withheld, then received | [Before](aarch64-linux/host-blue-before-sync.png), [after](aarch64-linux/host-blue-after-sync.png) | [Before](x86_64-linux/host-blue-before-sync.png), [after](x86_64-linux/host-blue-after-sync.png) |
| Red guest stroke with its acknowledgement withheld, then received | [Before](aarch64-linux/guest-red-before-sync.png), [after](aarch64-linux/guest-red-after-sync.png) | [Before](x86_64-linux/guest-red-before-sync.png), [after](x86_64-linux/guest-red-after-sync.png) |
| Human pointer attached to its message | [Guest canvas](aarch64-linux/pointer-guest.png) | [Guest canvas](x86_64-linux/pointer-guest.png) |
| The app waits at one vote and applies the agreed choice once | [Waiting](aarch64-linux/conflict-one-vote.png), [agreed](aarch64-linux/conflict-agreed.png) | [Waiting](x86_64-linux/conflict-one-vote.png), [agreed](x86_64-linux/conflict-agreed.png) |
| Guest end-of-sharing dialog with original Centaur artwork | [Guest dialog](aarch64-linux/sharing-ended.png) | [Guest dialog](x86_64-linux/sharing-ended.png) |

The native host file chooser accepted a 1,181,089-byte PNG. The original bytes stayed in the disposable profile and the sharing copy was a 256 × 256 JPEG. The guest exercised startup conversion of an alpha PNG, live replacement through the same preparation and bridge used by Settings, reconnect and a fresh invitation. Each broker verified the avatar hash before caching the optimized image.

The native drawing test paused the disposable coordinator and compared rendered pixels before and after acknowledgement on both sides. For approval, queued work stayed blocked after one vote, after the guest reconnected and while the two participants selected different options. A unanimous vote applied the chosen original request exactly once. The suite separately verified unanimous approval of a compromise and declining a proposal.

The signed source is [`2507957`](https://github.com/mattatgit/Centaur/commit/250795702e946e0426a3b314a5fc5abc1f140b95). The [release workflow](https://github.com/mattatgit/Centaur/actions/runs/45100031289) gates both update feeds on both architecture jobs. The [verification receipt](release-verification.json) records the matched feeds and signed artifacts. The ARM64 [native](aarch64-linux/integration-summary.json) and [updater](aarch64-linux/updater-summary.json) reports and x86-64 [native](x86_64-linux/integration-summary.json) and [updater](x86_64-linux/updater-summary.json) reports list the checks.
