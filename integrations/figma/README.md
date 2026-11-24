# Centaur Figma reader

The optional NixOS module `nixosModules.figma-reader` runs Dialogue’s reader in a separate system service. The socket accepts connections from the configured local account. Grant access to a particular file or branch for a particular Centaur project. Everyone in that project can ask the host agent about its authorised designs.

Configure the service on the machine authorised to read the designs. Supply a private, root-owned credential file outside the Nix store containing a Figma token with read-only file content access. Only systemd supplies the token to the service. Project history stores the original link and title. The agent receives a bounded design outline and a rendered PNG of the referenced node.

```nix
services.centaur-figma = {
  enable = true;
  user = "your-local-account";
  credentialFile = "/run/secrets/centaur-figma";
  projects."your-centaur-project-uuid" = [ "authorised-file-or-branch-key" ];
};
```

`dialogue-reader.cjs` is an unmodified copy of Dialogue’s `server/figma.js` at revision `6be674c46c4e2cf499f1bb7b22de8830e8528b64`. Its license is included in `assets/dialogue/LICENSE`. The Centaur adapter adds project grants, branch selection and a bounded PNG export. It never sends the API credential to an asset host.
