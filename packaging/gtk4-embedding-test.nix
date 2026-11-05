{ pkgs, buildId, services ? null }:
let
  python = pkgs.python3.withPackages (p: [ p.pygobject3 p.pycairo p.pillow ]);
  fonts = pkgs.runCommandNoCC "centaur-inter-fonts" { } ''
    mkdir -p "$out/share/fonts"
    cp -r ${../assets/fonts/inter} ${../assets/fonts/inter-tight} "$out/share/fonts/"
  '';
  casilda = pkgs.casilda.overrideAttrs (old: {
    version = "1.6.0-centaur3";
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
      (builtins.toFile "casilda-pointer-grab.patch"
        (builtins.readFile ./patches/casilda-pointer-grab.patch))
    ];
  });
in pkgs.stdenvNoCC.mkDerivation {
  pname = if services == null then "centaur-gtk4-embedding-test" else "centaur-gtk4-preview";
  version = if services == null then "0.1.0" else "0.4.0-preview";
  src = ../gtk4/embedding;
  nativeBuildInputs = [ pkgs.wrapGAppsHook4 pkgs.gobject-introspection ];
  buildInputs = [ pkgs.gtk4 pkgs.librsvg casilda ];
  dontBuild = true;
  installPhase = ''
    runHook preInstall
    mkdir -p "$out/bin" "$out/share/centaur-gtk4-test"
    cp *.py *.css "$out/share/centaur-gtk4-test/"
    mkdir -p "$out/share/centaur-gtk4-test/assets"
    cp ${../assets/dialogue}/*.svg ${../assets/dialogue}/*.png "$out/share/centaur-gtk4-test/assets/"
    cp ${../assets/dialogue/LICENSE} "$out/share/centaur-gtk4-test/Dialogue-LICENSE"
    cp ${../packaging/centaur.svg} "$out/share/centaur-gtk4-test/assets/centaur.svg"
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
    ${pkgs.lib.optionalString (services != null) ''
      for entry in centaur-gtk4 centaur-gtk4-preview centaur-gtk4-integration-check; do
        case "$entry" in
          centaur-gtk4) module=shell ;;
          centaur-gtk4-preview) module=runner ;;
          centaur-gtk4-integration-check) module=integration_check ;;
        esac
        cat > "$out/bin/$entry" <<EOF
      #!${python}/bin/python3
      import sys
      sys.path.insert(0, "$out/share/centaur-gtk4-test")
      from $module import main
      raise SystemExit(main())
      EOF
        chmod +x "$out/bin/$entry"
      done
      ln -s ${services}/bin/centaur-host "$out/bin/centaur-host"
      ln -s ${services}/bin/centaur-gtk4-bridge "$out/bin/centaur-gtk4-bridge"
      ln -s ${services}/bin/centaur-network "$out/bin/centaur-network"
    ''}
    runHook postInstall
  '';
  preFixup = ''
    gappsWrapperArgs+=(--set FONTCONFIG_FILE ${pkgs.makeFontsConf { fontDirectories = [ fonts ]; }})
    ${pkgs.lib.optionalString (services != null) ''
      gappsWrapperArgs+=(--set CENTAUR_GTK_BRIDGE ${services}/bin/centaur-gtk4-bridge)
      gappsWrapperArgs+=(--set CENTAUR_HOST ${services}/bin/centaur-host)
      gappsWrapperArgs+=(--set CENTAUR_GTK_HOST ${services}/bin/centaur-host)
      gappsWrapperArgs+=(--set CENTAUR_GTK_RUNNER "$out/bin/centaur-gtk4-preview")
    ''}
    gappsWrapperArgs+=(--set CENTAUR_GTK4_BUILD_ID ${pkgs.lib.escapeShellArg buildId})
    gappsWrapperArgs+=(--set CENTAUR_GTK4_CASILDA_VERSION ${casilda.version})
  '';
  passthru = {
    inherit python services;
    dbusConfig = "${pkgs.dbus}/share/dbus-1/session.conf";
    dbusForTests = pkgs.dbus;
    waylandTestSeat = import ./gtk4-test-seat.nix { inherit pkgs; };
    runtimeVersions = { gtk = pkgs.gtk4.version; casilda = casilda.version; glib = pkgs.glib.version; };
  };
  meta = {
    description = "Isolated experimental GTK4 host and separate native GTK4 app via Casilda";
    platforms = [ "aarch64-linux" ];
    mainProgram = if services == null then "centaur-gtk4-test" else "centaur-gtk4";
  };
}
