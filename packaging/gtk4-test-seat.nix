{ pkgs }:
pkgs.stdenv.mkDerivation {
  pname = "centaur-wayland-test-seat";
  version = "0.1.0";
  src = ../gtk4/testing;
  nativeBuildInputs = [ pkgs.pkg-config pkgs.wayland-scanner ];
  buildInputs = [ pkgs.wayland pkgs.libxkbcommon ];
  buildPhase = ''
    protocols=${pkgs.wlroots_0_20.src}/protocol
    wayland-scanner client-header "$protocols/wlr-virtual-pointer-unstable-v1.xml" virtual-pointer-client-protocol.h
    wayland-scanner private-code "$protocols/wlr-virtual-pointer-unstable-v1.xml" virtual-pointer-protocol.c
    wayland-scanner client-header "$protocols/virtual-keyboard-unstable-v1.xml" virtual-keyboard-client-protocol.h
    wayland-scanner private-code "$protocols/virtual-keyboard-unstable-v1.xml" virtual-keyboard-protocol.c
    $CC seat.c virtual-pointer-protocol.c virtual-keyboard-protocol.c $(pkg-config --cflags --libs wayland-client xkbcommon) -o centaur-test-seat
  '';
  installPhase = ''
    install -Dm755 centaur-test-seat "$out/bin/centaur-test-seat"
  '';
  meta.platforms = [ "aarch64-linux" ];
}
