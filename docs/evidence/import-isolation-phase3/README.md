# Phase 3 ARM64 UTM isolation evidence

16 November 2026. The final standalone engineering proof passed all **18 checks** on
the existing ARM64 NixOS GNOME VM under UTM as UID 1000. It used only disposable
fixtures and transient user services; it did not install a new Centaur version,
change the user profiles/NixOS configuration, or access existing project,
conversation, identity, OMP credential/configuration or separate Qt data.
Centaur Install separately confirmed the installed `e8d627c` and provisionally
accepted Landline's GTK4 UI adaptation before this work.

These files capture the final candidate with the daemon-readiness pipe handshake
and atomic status publication. All three lifecycle cases verified the detached,
double-forked child had installed SIGTERM ignore before checking termination.

- `vm-report.json`: exact successful measurements, effective cgroup limits,
  namespace/capability/descriptor checks, negative cases and cleanup results.
- `vm-verification.txt`: successful VM Nix build and complete test output,
  including the transferred archive SHA-256.
- `tested-source-sha256.json`: archive and per-file hashes checked against the
  checkout; the three installed Python files also matched the measured package.
  The unchanged repository lock file supplied the pinned Nix inputs.

Measured package:
`/nix/store/kkcjxzan650qpgsk8ighckay8512n9q8-centaur-import-isolation-proof-1`.
Policy SHA-256:
`f2a02eb484336a464c6716555757868bf3395f4088d7e874a764d67aae8a43eb`.

The memory check intentionally exhausted its 128 MiB service cgroup. Its recorded
result was `oom-kill`; GNOME's generic "Application Stopped" notification appeared
during that test. This is expected engineering evidence. No VM memory or security
setting needs changing. The sampler missed the very short-lived kernel OOM
counter; the retained service result records the termination.

The owner started intermediate staged runs because UTM was turning automated
keystrokes into desktop shortcuts. The final corrected run was started through
the existing Console after verifying its literal command. The successful
candidate was downloaded, built and executed by the existing NixOS account.
No macOS substitute test ran. The temporary transfer server was stopped after
the final results were received and matched against the checkout.

This proves the measured candidate for these fixtures and fixed version probes.
No command tool was registered with Centaur or OMP, and the existing published
app/update feed remains `0.4.0-preview+e8d627c`. See
[the policy and remaining integration gate](../../IMPORT_ISOLATION.md).
Installation instructions and hands-on acceptance remain in **Centaur Install**.
