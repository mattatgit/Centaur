# Public distribution cache. Import this file from the machine's NixOS
# configuration; no Cachix write token belongs on a downloading machine.
{ ... }: {
  nix.settings = {
    experimental-features = [ "nix-command" "flakes" ];
    extra-substituters = [ "https://mattatgit-centaur.cachix.org?priority=30" ];
    extra-trusted-public-keys = [
      "mattatgit-centaur.cachix.org-1:ouvsfGud6lFrvNNxpE1S5yGkNFm9J2WKtnIm38OSQ58="
    ];
  };
}
