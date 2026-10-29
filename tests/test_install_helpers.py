"""Failure-path tests with fake services/packages; never edit the real OS.

The cache helper's absolute system paths and root check are redirected in a
temporary copy. Its service operations are simulated. Real Nix profile switching
is checked separately by scripts/check-centaur-profile.sh in CI.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]


class Helpers(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="centaur-helper-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.home = self.root / "home"
        self.bin = self.root / "bin"
        self.proc = self.root / "proc"
        for folder in (self.home, self.bin, self.proc):
            folder.mkdir()
        self.profile = self.home / ".local/state/nix/profiles/centaur"
        self.profile.parent.mkdir(parents=True)
        self.config = self.root / "etc/nix/centaur-cache.conf"
        self.dropin = self.root / "etc/systemd/system/nix-daemon.service.d/90-centaur-cache.conf"
        self.config.parent.mkdir(parents=True)
        (self.root / "etc/NIXOS").touch()
        (self.root / "run/systemd/system").mkdir(parents=True)
        self.state = {"environment": "", "fail_download": False, "fail_switch": False}
        self.state_file = self.root / "state.json"
        self.log = self.root / "calls.jsonl"
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        DISPLAY=":test", XDG_CONFIG_HOME=str(self.home / ".config"),
                        XDG_DATA_HOME=str(self.home / ".local/share"), FAKE_ROOT=str(self.root))
        self.env.pop("CENTAUR_AGENT", None)
        self.env.pop("SUDO_USER", None)
        # Keep absolute paths/ownership isolated even when CI runs as root.
        self.updater = self.copy_script("centaur-update.sh", root_guard="1000")
        self.cache_setup = self.copy_script("centaur-cache-setup.sh", root_guard="0")
        self.program("uname", "print('Linux')")
        self.program("flock", "pass")
        self.program("sleep", "pass")
        self.program("nix", """
args = sys.argv[1:]
log(['nix'] + args)
if '--version' in args:
    print('nix (Nix) 2.28.4'); sys.exit(0)
if '--out-link' in args:
    if state.get('fail_download'): sys.exit(1)
    link = pathlib.Path(args[args.index('--out-link') + 1])
    link.symlink_to(root / 'candidate')
    if state.get('window_during_download'):
        folder = root / 'proc/777'; folder.mkdir()
        (folder / 'cmdline').write_bytes(b'centaur\\x00--demo\\x00')
elif '--profile' in args:
    if state.get('fail_switch'): sys.exit(1)
    link = pathlib.Path(args[args.index('--profile') + 1])
    temporary = link.with_name('new-profile')
    temporary.symlink_to(root / 'candidate')
    os.replace(str(temporary), str(link))
else:
    raise RuntimeError('Unexpected nix command: ' + repr(args))
""")
        self.program("systemctl", """
args = sys.argv[1:]; log(['systemctl'] + args)
dropin = root / 'etc/systemd/system/nix-daemon.service.d/90-centaur-cache.conf'
config = str(root / 'etc/nix/centaur-cache.conf')
if args[0] == 'show':
    key = args[args.index('-p') + 1]
    values = {'LoadState': 'loaded', 'User': '', 'Environment': state.get('environment', ''),
              'EnvironmentFiles': state.get('environment_files', ''),
              'ExecStart': state.get('exec_start', '/nix/store/test/bin/nix-daemon --daemon'),
              'MainPID': '55'}
    if dropin.exists() and not values['Environment']:
        values['Environment'] = '\\"NIX_CONFIG=include ' + config + '\\"'
    print(values.get(key, ''))
elif args[0] == 'restart':
    if state.get('fail_restart_once'):
        state['fail_restart_once'] = False
        (root / 'state.json').write_text(json.dumps(state)); sys.exit(1)
    folder = root / 'proc/55'; folder.mkdir(exist_ok=True)
    (folder / 'environ').write_bytes(('NIX_CONFIG=include ' + config + '\\x00').encode())
elif args[0] not in ('daemon-reload', 'is-active'):
    raise RuntimeError('Unexpected systemctl command')
""")
        self.package("old")
        self.package("candidate")
        self.profile.symlink_to(self.root / "old")
        # A sentinel for every class of data the updater must never edit.
        self.data = self.home / ".local/share/Centaur/Centaur"
        self.data.mkdir(parents=True)
        for name in ("project.qml", "conversation.jsonl", "member.identity", "credentials"):
            (self.data / name).write_text("keep exactly " + name)
        self.before = {p.name: p.read_bytes() for p in self.data.iterdir()}

    def copy_script(self, name, root_guard):
        source = (REPO / "scripts" / name).read_text()
        source = source.replace("/etc/", str(self.root / "etc") + "/")
        source = source.replace("/run/systemd/system", str(self.root / "run/systemd/system"))
        source = source.replace("/proc/", str(self.proc) + "/")
        source = source.replace("$EUID", root_guard)
        target = self.root / name
        target.write_text(source)
        return target

    def program(self, name, body, destination=None):
        path = destination or self.bin / name
        path.parent.mkdir(parents=True, exist_ok=True)
        prefix = """import json, os, pathlib, shutil, sys
root = pathlib.Path(os.environ['FAKE_ROOT'])
state = json.loads((root / 'state.json').read_text())
def log(value):
    with (root / 'calls.jsonl').open('a') as stream:
        stream.write(json.dumps(value) + '\\n')
"""
        path.write_text("#!" + sys.executable + "\n" + prefix + body + "\n")
        path.chmod(0o755)

    def package(self, name):
        folder = self.root / name / "bin"
        self.program("centaur", """
if '--version' in sys.argv:
    print('Centaur 0.3.1+fixture')
else:
    log(['launch', os.environ.get('CENTAUR_AGENT', ''), sys.argv[1:]])
""", folder / "centaur")
        self.program("centaur-host", """
log(['stop', sys.argv[1:]])
if not state.get('host_wont_stop'):
    shutil.rmtree(str(root / 'proc/123'), ignore_errors=True)
""", folder / "centaur-host")
        for executable in ("centaur-preview", "centaur-network", "centaur-update"):
            self.program(executable, "pass", folder / executable)

    def run_helper(self, script=None, *args):
        self.state_file.write_text(json.dumps(self.state))
        result = subprocess.run(["bash", str(script or self.updater)] + list(args),
                                env=self.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True)
        self.assertEqual(self.before, {p.name: p.read_bytes() for p in self.data.iterdir()})
        return result

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_update_downloads_then_stops_switches_launches_and_remembers_omp(self):
        omp = self.home / ".local/bin/omp"
        self.program("omp", "pass", omp)
        result = self.run_helper(None, "--omp", str(omp))
        self.assertEqual(result.returncode, 0, result.stdout)
        calls = self.calls()
        self.assertEqual([item[0] for item in calls], ["nix", "stop", "nix", "launch"])
        for args in (calls[0], calls[2]):
            self.assertIn("--max-jobs", args)
            self.assertEqual(args[args.index("--max-jobs") + 1], "0")
            self.assertEqual(args[args.index("--builders") + 1], "")
            self.assertIn("require-sigs", args)
            self.assertIn("fallback", args)
            self.assertNotIn("trusted-public-keys", args)
        self.assertIn("--offline", calls[2])
        self.assertEqual(calls[2][-1], str(self.root / "candidate"))
        download_link = Path(calls[0][calls[0].index("--out-link") + 1])
        self.assertFalse(download_link.parent.exists(), 'The temporary download GC root must be removed before launch')
        self.assertEqual(calls[3][1], str(omp))
        self.assertEqual(self.profile.resolve(), self.root / "candidate")
        self.assertEqual((self.home / ".config/centaur-launcher/omp-path").read_text().strip(), str(omp))
        self.log.unlink()
        result = self.run_helper(None, "start")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.calls()[0][1], str(omp))

    def test_missing_binary_never_stops_host_or_changes_profile(self):
        self.state["fail_download"] = True
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([x[0] for x in self.calls()], ["nix"])
        self.assertEqual(self.profile.resolve(), self.root / "old")

    def test_profile_failure_preserves_previous_installation(self):
        self.state["fail_switch"] = True
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.profile.resolve(), self.root / "old")
        self.assertNotIn("launch", [x[0] for x in self.calls()])

    def test_open_window_blocks_update(self):
        folder = self.proc / "777"; folder.mkdir()
        (folder / "cmdline").write_bytes(b".centaur-wrapped\0--demo\0")
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_window_opened_during_download_blocks_switch(self):
        self.state["window_during_download"] = True
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([x[0] for x in self.calls()], ["nix"])

    def test_host_that_does_not_stop_blocks_profile_switch(self):
        folder = self.proc / "123"; folder.mkdir()
        (folder / "cmdline").write_bytes(b"centaur-host\0--data-dir\0" + str(self.data).encode() + b"\0")
        self.state["host_wont_stop"] = True
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.profile.resolve(), self.root / "old")
        self.assertEqual([x[0] for x in self.calls()], ["nix", "stop"])

    def test_unrelated_program_in_profile_is_preserved(self):
        self.program("unrelated", "pass", self.root / "old/bin/unrelated")
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_missing_omp_fails_before_stopping_host(self):
        result = self.run_helper(None, "--omp", "/missing/omp")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_new_install_uses_same_profile(self):
        self.profile.unlink()
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.profile.resolve(), self.root / "candidate")

    def test_readonly_service_check_writes_no_configuration(self):
        result = self.run_helper(self.cache_setup, "check")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(self.config.exists())
        self.assertFalse(self.dropin.exists())

    def test_cache_setup_is_repeatable_and_reversible(self):
        for _ in range(2):
            result = self.run_helper(self.cache_setup, "enable")
            self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("require-sigs = true", self.config.read_text())
        self.assertNotIn("trusted-users", self.config.read_text())
        self.assertIn("NIX_CONFIG=include", self.dropin.read_text())
        result = self.run_helper(self.cache_setup, "disable")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(self.config.exists())
        self.assertFalse(self.dropin.exists())

    def test_cache_setup_refuses_existing_environment(self):
        self.state["environment"] = '"NIX_CONFIG=keep-outputs = true"'
        result = self.run_helper(self.cache_setup, "enable")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.config.exists())

    def test_cache_setup_refuses_environment_files_and_custom_flags(self):
        for key, value in (("environment_files", "/custom/settings"),
                           ("exec_start", "/nix/store/test/nix-daemon --option require-sigs false")):
            with self.subTest(key=key):
                self.state[key] = value
                result = self.run_helper(self.cache_setup, "enable")
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.config.exists())
                self.state.pop(key)

    def test_cache_setup_refuses_unrelated_file(self):
        self.config.write_text("keep this custom configuration\n")
        result = self.run_helper(self.cache_setup, "enable")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.config.read_text(), "keep this custom configuration\n")

    def test_cache_setup_rolls_back_when_daemon_restart_fails(self):
        self.state["fail_restart_once"] = True
        result = self.run_helper(self.cache_setup, "enable")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.config.exists())
        self.assertFalse(self.dropin.exists())
        self.assertIn("restored", result.stdout)


if __name__ == "__main__":
    unittest.main()
