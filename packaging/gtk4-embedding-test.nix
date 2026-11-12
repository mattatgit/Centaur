{ pkgs, buildId, services ? null, sourceTimestamp ? 0, updaterFixture ? false }:
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
  nativeBuildInputs = [ pkgs.wrapGAppsHook4 pkgs.gobject-introspection pkgs.librsvg pkgs.desktop-file-utils ];
  buildInputs = [ pkgs.gtk4 pkgs.librsvg casilda ];
  dontBuild = true;
  installPhase = ''
    runHook preInstall
    mkdir -p "$out/bin" "$out/share/centaur-gtk4-test"
    cp *.py *.css "$out/share/centaur-gtk4-test/"
    mkdir -p "$out/share/centaur-gtk4-test/assets"
    cp ${../assets/dialogue}/*.svg ${../assets/dialogue}/*.png "$out/share/centaur-gtk4-test/assets/"
    cp ${../assets/figma}/*.svg "$out/share/centaur-gtk4-test/assets/"
    cp ${../assets/dialogue/LICENSE} "$out/share/centaur-gtk4-test/Dialogue-LICENSE"
    cp ${../assets/branding/Centaur_mono.svg} "$out/share/centaur-gtk4-test/assets/centaur.svg"
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
      mkdir -p "$out/share/applications" "$out/share/icons/hicolor/scalable/apps"
      cp ${pkgs.hicolor-icon-theme}/share/icons/hicolor/index.theme "$out/share/icons/hicolor/"
      cp ${../packaging/centaur-app.svg} "$out/share/icons/hicolor/scalable/apps/org.centaur.Gtk4.svg"
      cp ${../assets/branding/Centaur_mono.svg} "$out/share/icons/hicolor/scalable/apps/org.centaur.Gtk4-symbolic.svg"
      for size in 16 24 32 48 64 128 256 512; do
        mkdir -p "$out/share/icons/hicolor/''${size}x''${size}/apps"
        rsvg-convert --width "$size" --height "$size" ${../packaging/centaur-app.svg} \
          --output "$out/share/icons/hicolor/''${size}x''${size}/apps/org.centaur.Gtk4.png"
      done
      substitute ${./gtk4-centaur.desktop} "$out/share/applications/org.centaur.Gtk4.desktop" --subst-var out
      desktop-file-validate "$out/share/applications/org.centaur.Gtk4.desktop"
      for entry in centaur-gtk4 centaur-gtk4-preview centaur-gtk4-integration-check centaur-gtk4-update centaur-gtk4-updater-check centaur-gtk4-import; do
        case "$entry" in
          centaur-gtk4) module=shell ;;
          centaur-gtk4-preview) module=runner ;;
          centaur-gtk4-integration-check) module=integration_check ;;
          centaur-gtk4-update) module=updater ;;
          centaur-gtk4-updater-check) module=updater_check ;;
          centaur-gtk4-import) module=source_import ;;
        esac
        cat > "$out/bin/$entry" <<EOF
      #!${python}/bin/python3
      import sys
      sys.path.insert(0, "$out/share/centaur-gtk4-test")
      ${pkgs.lib.optionalString updaterFixture ''
      import os, updater
      updater.FEED = os.environ["CENTAUR_UPDATER_FIXTURE_FEED"]
      ''}
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
      gappsWrapperArgs+=(--set CENTAUR_GTK_IMPORT_TOOL "$out/bin/centaur-gtk4-import")
      gappsWrapperArgs+=(--prefix PATH : ${pkgs.lib.makeBinPath [ pkgs.git ]})
      gappsWrapperArgs+=(--set CENTAUR_GTK_PACKAGE "$out")
      gappsWrapperArgs+=(--set CENTAUR_GTK4_SOURCE_TIME ${toString sourceTimestamp})
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
    updaterPrevious = if updaterFixture || services == null then null else import ./gtk4-embedding-test.nix {
      inherit pkgs services;
      buildId = "0000000";
      sourceTimestamp = 1;
      updaterFixture = true;
    };
  };
  meta = {
    description = "Isolated experimental GTK4 host and separate native GTK4 app via Casilda";
    platforms = [ "aarch64-linux" ];
    mainProgram = if services == null then "centaur-gtk4-test" else "centaur-gtk4";
  };
}
