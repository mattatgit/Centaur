{ pkgs }:
let
  inherit (import ./import-isolation-policy.nix { inherit pkgs; }) config;
in pkgs.stdenvNoCC.mkDerivation {
  pname = "centaur-import-sandbox";
  version = "1";
  dontUnpack = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/share/centaur-isolation"
    cp ${../scripts/import-isolation/boundary.py} "$out/share/centaur-isolation/boundary.py"
    cp ${../scripts/import-isolation/entry.py} "$out/share/centaur-isolation/entry.py"
    cp ${../scripts/import-isolation/diagnostic.py} "$out/share/centaur-isolation/diagnostic.py"
    cp ${config} "$out/share/centaur-isolation/config.json"
    cat > "$out/bin/centaur-import-sandbox" <<EOF
    #!${pkgs.python3}/bin/python3 -I
    import runpy, sys
    sys.path.insert(0, "$out/share/centaur-isolation")
    runpy.run_path("$out/share/centaur-isolation/entry.py", run_name="__main__")
    EOF
    chmod +x "$out/bin/centaur-import-sandbox"
  '';
  meta.platforms = [ "aarch64-linux" ];
}
