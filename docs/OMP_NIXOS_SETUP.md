# Set up the Centaur agent on NixOS

Centaur uses [oh-my-pi (OMP)](https://github.com/can1357/oh-my-pi) as its AI runtime. Install OMP on the computer that hosts agent requests. Guests using a host's agent can join and make requests without installing OMP on their own computers.

## Install OMP on the host

Use the same NixOS user account that runs Centaur. If `omp --version` already works for that user, keep the existing OMP installation.

For Nix 2.30 or newer, install OMP with:

```sh
nix --extra-experimental-features 'nix-command flakes' \
  profile add github:can1357/oh-my-pi
```

For older Nix versions, use `profile install` in place of `profile add`. See the [OMP installation instructions](https://github.com/can1357/oh-my-pi#install) for other installation methods.

Check that the executable is available.

```sh
omp --version
```

Then [open Centaur GTK4](NIXOS_INSTALL.md#3-set-up-the-host-and-open-centaur).

## Connect a provider and choose a model

1. On the host computer, open **Settings → LLM and Model** in Centaur.
2. Click **Connect** next to your provider and follow the sign-in prompts. If your provider is already connected through OMP, use **Refresh** to load the connection.
3. Choose a model from that provider's menu. Centaur saves the selection in its settings and uses it for subsequent agent requests.

Routine configuration happens in Centaur and, when prompted, on your provider's sign-in page. OMP manages provider credentials.

To try the connection, open a project on the host and send a short question such as `@centaur What does this app do?`. Use the agent's configured name if you've renamed it.

## Troubleshooting

- **OMP is unavailable.** Run `omp --version` as the same user who launches Centaur. If the command is missing, open a new terminal and check that OMP was installed in a folder on your command path (`PATH`). If Centaur was already running when you installed OMP, reopen it.
- **Sign-in fails or no models appear.** Retry **Connect**, complete the provider's prompts and click **Refresh**. If Centaur says the connection is configured outside its sign-in flow, check the credentials in OMP's configured source, then refresh in Centaur.
- **An agent request fails.** On the host, check the provider connection and selected model, then retry with a short question. If it still fails, record the error shown in chat, the provider/model and the output of `omp --version`. For a guest request, also check that the host is online.
