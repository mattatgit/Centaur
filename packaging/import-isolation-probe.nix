{ pkgs }:
assert pkgs.stdenv.hostPlatform.system == "aarch64-linux";
assert pkgs.lib.versionAtLeast pkgs.libseccomp.version "2.6.1";
let
  # A separate engineering proof package: not installed by, or wired into, Centaur.
  inherit (import ./import-isolation-policy.nix { inherit pkgs; }) config;
in pkgs.stdenvNoCC.mkDerivation {
  pname = "centaur-import-isolation-proof";
  version = "1";
  src = ../scripts/import-isolation;
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/share/centaur-isolation"
    cp *.py "$out/share/centaur-isolation/"
    cp ${config} "$out/share/centaur-isolation/config.json"
    cat > "$out/bin/centaur-import-isolation-proof" <<EOF
    #!${pkgs.python3}/bin/python3
    import runpy, sys
    sys.path.insert(0, "$out/share/centaur-isolation")
    runpy.run_path("$out/share/centaur-isolation/check.py", run_name="__main__")
    EOF
    chmod +x "$out/bin/centaur-import-isolation-proof"
  '';
  meta.platforms = [ "aarch64-linux" ];
}
