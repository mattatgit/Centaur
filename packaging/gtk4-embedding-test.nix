{ pkgs, buildId }:
let python = pkgs.python3.withPackages (p: [ p.pygobject3 p.pillow ]);
in pkgs.stdenvNoCC.mkDerivation {
  pname = "centaur-gtk4-embedding-test";
  version = "0.1.0";
  src = ../gtk4/embedding;
  nativeBuildInputs = [ pkgs.wrapGAppsHook4 pkgs.gobject-introspection ];
  buildInputs = [ pkgs.gtk4 pkgs.casilda ];
  dontBuild = true;
  installPhase = ''
    runHook preInstall
    mkdir -p "$out/bin" "$out/share/centaur-gtk4-test"
    cp *.py "$out/share/centaur-gtk4-test/"
    for entry in test check; do
      module=host
      if [ "$entry" = check ]; then module=check; fi
      cat > "$out/bin/centaur-gtk4-$entry" <<EOF
    #!${python}/bin/python3
    import sys
    sys.path.insert(0, "$out/share/centaur-gtk4-test")
    from $module import main
    raise SystemExit(main())
    EOF
      chmod +x "$out/bin/centaur-gtk4-$entry"
    done
    runHook postInstall
  '';
  preFixup = ''
    gappsWrapperArgs+=(--set CENTAUR_GTK4_BUILD_ID ${pkgs.lib.escapeShellArg buildId})
  '';
  passthru = { inherit python; };
  meta = {
    description = "Isolated experimental GTK4 host and separate native GTK4 app via Casilda";
    platforms = [ "aarch64-linux" ];
    mainProgram = "centaur-gtk4-test";
  };
}
