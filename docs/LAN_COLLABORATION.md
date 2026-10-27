# Collaborate across computers

Centaur 0.2 adds a first local-network collaboration flow. Both computers need Centaur; only the project host needs OMP installed and signed in. Start with two NixOS computers, such as the ARM64 UTM VM and the NixOS Air. This is a trusted-family prototype, not an internet hosting service.

## Update and launch

Close older Centaur windows. On each computer, run:

```sh
CENTAUR_AGENT="$HOME/.local/bin/omp" \
  nix --refresh run 'github:mattatgit/Centaur?ref=codex/native-prototype' -- --demo
```

The guest can omit `CENTAUR_AGENT`. An existing shortcut that refreshes the same branch also works. Look for **v0.2.0** with a source identifier in the chat footer or Settings.

The app starts `centaur-host` automatically as a background process for its data directory. It coordinates local windows, stores projects and runs OMP. The network listener starts only when an owner creates an invitation; saved sharing resumes when the host is restarted. Closing a Centaur window stops that window's preview but leaves the background host running. The computer must remain awake and reachable. No system service installation is required for this prototype.

## Host a project

1. Open a project and choose **Invite**, beside Deploy.
2. Check the displayed address. It must be an IPv4 address that the other computer can reach.
3. Choose **Create invitation**, then **Copy invitation**. Send the complete code privately to one participant.
4. Create another invitation for each additional person. Each code is single-use and expires after 20 minutes.

The host uses TCP port **43177** by default. On NixOS, allow that port in the host's existing firewall configuration, preserving any other allowed ports:

```nix
networking.firewall.allowedTCPPorts = [ 43177 ];
```

Apply the configuration using your normal NixOS rebuild procedure, for example `sudo nixos-rebuild switch`. Only the host needs an incoming port; guests initiate outgoing connections. Keep access within the trusted local network for this milestone.

A VM's address is not necessarily reachable from another physical computer. If the Air cannot reach the VM address, arrange a reachable VM network or forward the host port to the VM. Opening the guest firewall alone cannot change the VM's network reachability. Enter the address reachable by the Air in Invite; if forwarding a port, keep the external port at 43177. This task does not change UTM or capture its mouse.

## Join a project

1. In Projects, choose **Join project**.
2. Enter your name and paste the complete invitation code.
3. Read the trust notice and choose **Join project**. Shared native QML executes on your device, so join only a host you trust.
4. The project opens with its conversation, drawings and current app. It also appears as a shared card in Projects and reconnects on later launches.

Names are assigned to stable participant credentials. If a name is already used in the project, the host adds a suffix rather than merging two identities. Reconnecting reuses the assigned name and identity. Changing this device's local display name does not change an existing shared identity. There are no cloud accounts yet.

## Work together

Both Interact and Build retain chat. Messages, sketches, Comment arrows, conflict proposals and accepted app source synchronise. Each computer renders a separate native preview; ticking a checkbox or typing inside one preview does not synchronise that app's runtime data.

Only the host invokes OMP, checks proposed QML and saves source history. Compatible requests apply automatically. Agent mentions are queued; ordinary chat can continue while the agent works. New explicit agent directions and changed sketches invalidate stale work, which is retried against the latest conversation. Only the affected authors approve an actual conflict. Stop clears the selected project's pending requests.

The guest receives accepted `App.qml`, recent conversation/decisions and annotation state for the invited project. It does not receive other projects, Git directories, host filesystem paths, provider credentials or the host's private data directory. The current generated-app contract remains one QML file using built-in Qt modules and bundled fonts; arbitrary assets or compiled projects are not distributed by this milestone.

## Disconnection, leaving and access

When the host becomes unreachable, the guest shows a connection status and reconnects automatically. Cached app source remains usable locally. Sending and drawing are disabled while disconnected; an unsent chat draft remains in the composer. Actions already saved for transmission are retried with sequence numbers, so an acknowledgement lost during a disconnect does not duplicate the accepted action. A stale drawing or conflict vote is rejected if the app changed before it arrived.

For this prototype, each project has one editable guest window per device. Additional windows show the same project read-only; closing the editing window lets another take over automatically. This protects the device’s pending-action queue from competing writers. Different devices can all contribute at once.

A guest's project-card menu offers **Leave project**, with confirmation. This removes that device's saved membership without deleting the owner's project. Rename, archive, deletion and invitations are owner actions. To return after leaving, request a new invitation.

The owner can choose **Stop sharing** in Invite. This revokes all invitations and participant credentials for that project and disconnects its guests. Existing copies of app source on a guest cannot be remotely erased. Owners can start sharing again with fresh invitations. Individual-member removal is not implemented yet.

## Background host maintenance

The host keeps the OMP executable/model environment from when it was launched. After changing that environment or updating Centaur, close local windows and restart the background host before reopening the app. From a local repository checkout, with the same data directory used by Centaur:

```sh
nix build
./result/bin/centaur-host --stop --data-dir "$HOME/.local/share/Centaur/Centaur"
```

If you used `--data-dir`, substitute that directory. On the next launch, Centaur starts the updated host with the launcher's environment. Do not stop a host while collaborators are actively working. No automatic transfer to a different host is provided.

## Storage and transport

- Original projects and history stay under `projects/<id>` on the host.
- TLS certificate, private key and hashed invitation/member credentials live in the host's owner-only `network/` directory.
- Guests store their credential, pending actions, cached state and `App.qml` under an owner-only `shared/<id>/` directory. Leaving removes the credential; cached source remains for recovery.
- The invitation contains the host certificate's SHA-256 fingerprint. The client checks that fingerprint before sending any invitation or member credential. A changed certificate stops reconnection and requires a fresh invitation.
- The transport is bounded newline-delimited JSON over TLS 1.2 or later, with protocol version 1. The host authorises each project/action and assigns author identity from the credential. Sequence acknowledgements are persisted with accepted project mutations.

TLS uses Qt Network's socket API; see [Qt SSL sockets](https://doc.qt.io/qt-6/qsslsocket.html). This first version has no relay, internet discovery, mobile client, automatic host failover or sandbox for untrusted native QML.

## Two-machine acceptance test

1. Update both machines. Start the host with its working OMP environment.
2. Invite the second machine. Verify the project card and assigned name on the guest.
3. Exchange chat and drawings in both directions, including while Interact is selected.
4. Make an agent request from the guest. Check that the host's OMP handles it and both native previews receive the accepted change.
5. Send ordinary chat during a request, then queue a second agent request. Both should be retained and completed.
6. Give incompatible directions and check that only the affected authors must agree.
7. Close the owner's UI window. The guest should still be able to chat and request an app change.
8. Disconnect/reconnect the guest's network. Check status, retained draft, eventual source catch-up and absence of duplicated messages.
9. Test Leave and Stop sharing. Unrelated host projects must never appear on the guest.
