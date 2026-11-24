{ config, lib, pkgs, ... }:
let
  cfg = config.services.centaur-figma;
  grants = pkgs.writeText "centaur-figma-project-grants.json" (builtins.toJSON cfg.projects);
in {
  options.services.centaur-figma = {
    enable = lib.mkEnableOption "the private Centaur read-only Figma service";
    user = lib.mkOption { type = lib.types.str; description = "Local account permitted to request project designs"; };
    credentialFile = lib.mkOption { type = lib.types.str; description = "Absolute path to a root-owned file containing the Figma read token, outside the Nix store"; };
    projects = lib.mkOption {
      type = lib.types.attrsOf (lib.types.listOf lib.types.str);
      default = {};
      description = "Map each authorised project UUID to the Figma file and branch keys it may read";
    };
  };
  config = lib.mkIf cfg.enable {
    assertions = [{
      assertion = lib.hasPrefix "/" cfg.credentialFile && !(lib.hasPrefix "/nix/store/" cfg.credentialFile);
      message = "Keep the Centaur Figma credential in a private file outside the Nix store.";
    }];
    systemd.sockets.centaur-figma = {
      wantedBy = [ "sockets.target" ];
      socketConfig = { ListenStream = "/run/centaur-figma.sock"; Accept = true; SocketMode = "0600"; SocketUser = cfg.user; MaxConnections = 4; };
    };
    systemd.services."centaur-figma@" = {
      serviceConfig = {
        ExecStart = "${pkgs.nodejs}/bin/node ${../integrations/figma}/broker.cjs ${grants}";
        StandardInput = "socket"; StandardOutput = "socket"; StandardError = "null";
        LoadCredential = "figma:${cfg.credentialFile}";
        DynamicUser = true; NoNewPrivileges = true; PrivateTmp = true;
        ProtectSystem = "strict"; ProtectHome = true; MemoryMax = "256M";
        RuntimeMaxSec = 60; TasksMax = 16;
      };
    };
  };
}
