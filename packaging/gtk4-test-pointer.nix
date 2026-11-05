{ pkgs }:
pkgs.stdenv.mkDerivation {
  pname = "centaur-wayland-test-pointer";
  version = "0.1.0";
  src = ../gtk4/testing;
  nativeBuildInputs = [ pkgs.pkg-config pkgs.wayland-scanner ];
  buildInputs = [ pkgs.wayland ];
  buildPhase = ''
    protocol=${pkgs.wlr-protocols}/share/wlr-protocols/unstable/wlr-virtual-pointer-unstable-v1.xml
    wayland-scanner client-header "$protocol" virtual-pointer-client-protocol.h
    wayland-scanner private-code "$protocol" virtual-pointer-protocol.c
    $CC pointer.c virtual-pointer-protocol.c $(pkg-config --cflags --libs wayland-client) -o centaur-test-pointer
  '';
  installPhase = ''
    install -Dm755 centaur-test-pointer "$out/bin/centaur-test-pointer"
  '';
  meta.platforms = [ "aarch64-linux" ];
}
