{
  description = "Centaur — a native, collaborative app workshop";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "aarch64-darwin" ];
      eachSystem = nixpkgs.lib.genAttrs systems;
      qtPackages = pkgs: with pkgs.qt6; [ qtbase qtdeclarative qtsvg ]
        ++ pkgs.lib.optional pkgs.stdenv.hostPlatform.isLinux qtwayland;
      qmlPath = pkgs: pkgs.lib.makeSearchPath "lib/qt-6/qml" (qtPackages pkgs);
      pluginPath = pkgs: pkgs.lib.makeSearchPath "lib/qt-6/plugins" (qtPackages pkgs);
      package = pkgs: pkgs.stdenv.mkDerivation {
        pname = "centaur";
        version = "0.1.1";
        src = self;
        nativeBuildInputs = with pkgs; [ cmake ninja qt6.wrapQtAppsHook ];
        buildInputs = qtPackages pkgs;
        cmakeFlags = [ "-DBUILD_TESTING=ON"
          "-DCENTAUR_BUILD_ID=${self.shortRev or self.dirtyShortRev or "dev"}" ];
        nativeCheckInputs = [ pkgs.git ] ++ pkgs.lib.optional pkgs.stdenv.hostPlatform.isLinux pkgs.gdb;
        doCheck = true;
        preCheck = ''
          export QT_QPA_PLATFORM=offscreen
          export QT_QUICK_BACKEND=software
          export QT_FORCE_STDERR_LOGGING=1
          export QML_IMPORT_PATH="${qmlPath pkgs}"
          export QT_PLUGIN_PATH="${pluginPath pkgs}"
          export XDG_CACHE_HOME="$TMPDIR/centaur-cache"
          mkdir -p "$XDG_CACHE_HOME"
          export XDG_RUNTIME_DIR="$TMPDIR/centaur-runtime"
          mkdir -p "$XDG_RUNTIME_DIR"
          chmod 700 "$XDG_RUNTIME_DIR"
          ${pkgs.lib.optionalString pkgs.stdenv.hostPlatform.isLinux ''
            export LC_ALL=C.UTF-8
            export FONTCONFIG_FILE="${pkgs.makeFontsConf { fontDirectories = [ pkgs.dejavu_fonts ]; }}"
          ''}
        '';
        checkPhase = ''
          runHook preCheck
          if ctest --output-on-failure; then
            runHook postCheck
          else
            ${pkgs.lib.optionalString pkgs.stdenv.hostPlatform.isLinux ''
              gdb --batch -ex 'set pagination off' -ex 'set debuginfod enabled off' \
                -ex run -ex 'thread apply all bt' --args ./centaur --embedding-smoke-test || true
            ''}
            exit 1
          fi
        '';
        # Application projects are real local Git repositories.
        qtWrapperArgs = [ "--prefix" "PATH" ":" (pkgs.lib.makeBinPath [ pkgs.git ])
          "--prefix" "QML_IMPORT_PATH" ":" (qmlPath pkgs) ];
        meta = {
          description = "Native canvas and shared conversation for building native apps";
          mainProgram = "centaur";
          platforms = systems;
        };
      };
    in {
      packages = eachSystem (system: { default = package nixpkgs.legacyPackages.${system}; });
      devShells = eachSystem (system:
        let pkgs = nixpkgs.legacyPackages.${system}; in {
          default = pkgs.mkShell {
            inputsFrom = [ self.packages.${system}.default ];
            packages = [ pkgs.git ];
            shellHook = ''
              export QML_IMPORT_PATH="${qmlPath pkgs}"
              export QT_PLUGIN_PATH="${pluginPath pkgs}"
            '';
          };
        });
      checks = eachSystem (system: { prototype = self.packages.${system}.default; });
    };
}
