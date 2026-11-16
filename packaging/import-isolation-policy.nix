{ pkgs }:
assert pkgs.stdenv.hostPlatform.system == "aarch64-linux";
assert pkgs.lib.versionAtLeast pkgs.libseccomp.version "2.6.1";
let
  policy = pkgs.stdenv.mkDerivation {
    pname = "centaur-import-seccomp-proof";
    version = "1";
    src = ../scripts/import-isolation;
    buildInputs = [ pkgs.libseccomp ];
    buildPhase = ''
      $CC -D_GNU_SOURCE -Wall -Wextra -Werror -O2 filter.c -lseccomp -o filter
      ./filter policy.bpf
    '';
    installPhase = ''
      mkdir -p "$out"
      cp policy.bpf "$out/"
    '';
  };
  closure = pkgs.closureInfo { rootPaths = [ pkgs.python3 pkgs.gitMinimal pkgs.gcc-unwrapped ]; };
  config = pkgs.writeText "centaur-isolation-proof-config.json" (builtins.toJSON {
    bwrap = "${pkgs.bubblewrap}/bin/bwrap";
    python = "${pkgs.python3}/bin/python3";
    git = "${pkgs.gitMinimal}/bin/git";
    gcc = "${pkgs.gcc-unwrapped}/bin/gcc";
    systemdRun = "${pkgs.systemd}/bin/systemd-run";
    systemctl = "${pkgs.systemd}/bin/systemctl";
    filter = "${policy}/policy.bpf";
    closure = "${closure}/store-paths";
    versions = { bubblewrap = pkgs.bubblewrap.version; seccomp = pkgs.libseccomp.version; };
  });
in { inherit policy closure config; }
