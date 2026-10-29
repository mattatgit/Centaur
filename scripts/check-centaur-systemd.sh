#!/usr/bin/env bash
# CI-only integration check against a disposable REAL systemd service. Never
# restart/reconfigure the runner's Nix daemon. Run on an ephemeral Linux runner.
set -euo pipefail
[[ $EUID == 0 && -d /run/systemd/system ]] || { echo 'This CI check needs root on a systemd Linux runner.' >&2; exit 2; }
work_directory=$(mktemp -d /tmp/centaur-systemd-check.XXXXXX)
unit="centaur-cache-fixture-$$.service"
base_unit="/run/systemd/system/$unit"
override="/etc/systemd/system.control/$unit.d/90-centaur-cache.conf"
cleanup() {
    systemctl stop "$unit" || true
    rm -f "$override" "$base_unit"
    rmdir "$(dirname "$override")" 2>/dev/null || true
    systemctl daemon-reload || true
    rm -rf "$work_directory"
}
trap cleanup EXIT
# The only substitutions are fixture identity and private test paths. Execute
# the production helper's service lookup, preflight, staging and recovery code.
python3 - "$work_directory" "$unit" <<'PY'
import pathlib, sys
root, unit = pathlib.Path(sys.argv[1]), sys.argv[2]
(root / 'NIXOS').touch()
source = pathlib.Path('scripts/centaur-cache-setup.sh').read_text()
source = source.replace('/etc/NIXOS', str(root / 'NIXOS'))
source = source.replace('/etc/nix', str(root / 'nix'))
source = source.replace('nix-daemon.service', unit)
(root / 'setup.sh').write_text(source)
PY
cat > "$base_unit" <<'UNIT'
[Service]
Type=simple
Environment=CENTAUR_FIXTURE_KEEP=present
ExecStart=/usr/bin/sleep infinity
UNIT
cp "$base_unit" "$work_directory/original-unit"
systemctl daemon-reload
systemctl start "$unit"
bash "$work_directory/setup.sh" check
bash "$work_directory/setup.sh" enable
cmp "$base_unit" "$work_directory/original-unit"
systemctl show "$unit" -p Environment --value | grep -F 'CENTAUR_FIXTURE_KEEP=present' >/dev/null
[[ -f $override && -f $work_directory/nix/centaur-cache.conf ]]
bash "$work_directory/setup.sh" enable
bash "$work_directory/setup.sh" disable
[[ ! -e $override && ! -e $work_directory/nix/centaur-cache.conf ]]
systemctl is-active --quiet "$unit"
[[ $(systemctl show "$unit" -p Environment --value) == CENTAUR_FIXTURE_KEEP=present ]]
echo 'Real systemd loaded the persistent control override, passed environment verification and removed it cleanly; base unit unchanged.'
