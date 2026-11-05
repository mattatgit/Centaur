{ pkgs, buildId }:
let
  python = pkgs.python3.withPackages (p: [ p.pygobject3 p.pillow ]);
  casilda = pkgs.casilda.overrideAttrs (old: {
    version = "1.6.0-centaur2";
    src = pkgs.fetchzip {
      url = "https://gitlab.gnome.org/jpu/casilda/-/archive/1.6.0/casilda-1.6.0.tar.gz";
      hash = "sha256-1Iq0RKte56gg69MRlEhfu5aWc+Vl7HgopS7RGIrf59w=";
    };
    buildInputs = old.buildInputs ++ [ pkgs.libdrm pkgs.pixman pkgs.libx11 pkgs.libxcb ];
    patches = (old.patches or [ ]) ++ [
      (builtins.toFile "casilda-initial-keymap.patch"
        (builtins.readFile ./patches/casilda-initial-keymap.patch))
      (builtins.toFile "casilda-key-event-state.patch"
        (builtins.readFile ./patches/casilda-key-event-state.patch))
    ];
  });
in pkgs.stdenvNoCC.mkDerivation {
  pname = "centaur-gtk4-embedding-test";
  version = "0.1.0";
  src = ../gtk4/embedding;
  nativeBuildInputs = [ pkgs.wrapGAppsHook4 pkgs.gobject-introspection ];
  buildInputs = [ pkgs.gtk4 casilda ];
  dontBuild = true;
  installPhase = ''
    runHook preInstall
    mkdir -p "$out/bin" "$out/share/centaur-gtk4-test"
    cp *.py "$out/share/centaur-gtk4-test/"
    cp ${casilda.src}/COPYING "$out/share/centaur-gtk4-test/Casilda-COPYING"
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
    gappsWrapperArgs+=(--set CENTAUR_GTK4_CASILDA_VERSION ${casilda.version})
  '';
  passthru = {
    inherit python;
    dbusConfig = "${pkgs.dbus}/share/dbus-1/session.conf";
    dbusForTests = pkgs.dbus;
    waylandTestSeat = import ./gtk4-test-seat.nix { inherit pkgs; };
    runtimeVersions = { gtk = pkgs.gtk4.version; casilda = casilda.version; glib = pkgs.glib.version; };
  };
  meta = {
    description = "Isolated experimental GTK4 host and separate native GTK4 app via Casilda";
    platforms = [ "aarch64-linux" ];
    mainProgram = "centaur-gtk4-test";
  };
}
