"""Exercise Centaur's launcher in one disposable GNOME Shell session."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import time


DESKTOP_ID = 'org.centaur.Gtk4.desktop'
APP = f'Shell.AppSystem.get_default().lookup_app({json.dumps(DESKTOP_ID)})'


def shell_eval(code):
    reply = subprocess.check_output([
        'gdbus', 'call', '--session', '--dest', 'org.gnome.Shell',
        '--object-path', '/org/gnome/Shell', '--method', 'org.gnome.Shell.Eval', code,
    ], text=True, timeout=5, stderr=subprocess.DEVNULL).strip()
    success, value = ast.literal_eval(reply.replace('(true,', '(True,', 1).replace('(false,', '(False,', 1))
    if not success:
        raise RuntimeError(value or 'GNOME Shell is not ready for evaluation')
    return json.loads(value) if value else None


def wait(check, message, timeout=25):
    deadline = time.monotonic() + timeout
    error = None
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except (OSError, RuntimeError, subprocess.SubprocessError) as caught:
            error = caught
        time.sleep(.15)
    raise AssertionError(message) from error


def main(previous, candidate, version, folder):
    previous, candidate, folder = (Path(p).resolve() for p in (previous, candidate, folder))
    folder.mkdir()
    home = folder/'home with spaces'
    runtime = folder/'runtime'
    runtime.mkdir(mode=0o700)
    data = home/'.local/share'
    profile = home/'.local/state/nix/profiles/centaur-gtk4'
    profile.parent.mkdir(parents=True)
    desktop = data/'applications'/DESKTOP_ID
    desktop.parent.mkdir(parents=True)
    feed = folder/'no-update.json'
    feed.write_text('{}')
    env = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(data), XDG_RUNTIME_DIR=str(runtime),
               XDG_CONFIG_HOME=str(home/'.config'), XDG_CACHE_HOME=str(home/'.cache'),
               XDG_STATE_HOME=str(home/'.local/state'), XDG_CURRENT_DESKTOP='GNOME', XDG_SESSION_TYPE='wayland',
               GSETTINGS_BACKEND='memory', GTK_A11Y='none', GSK_RENDERER='cairo', LIBGL_ALWAYS_SOFTWARE='1',
               CENTAUR_UPDATER_FIXTURE_FEED=feed.as_uri())
    for name in ('WAYLAND_DISPLAY', 'DISPLAY'):
        env.pop(name, None)

    def activate(package):
        subprocess.run(['nix', '--extra-experimental-features', 'nix-command', 'build', '--offline', '--no-link',
                        '--max-jobs', '0', '--builders', '', '--profile', str(profile), str(package)],
                       env=env, check=True, timeout=40)
        assert profile.resolve() == package

    def windows():
        return shell_eval(f'{APP}?.get_windows().map(window => window.get_pid())') or []

    def expect_version(pid, expected):
        settings = Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
        assert f'CENTAUR_GTK4_BUILD_ID={expected}'.encode() in settings, f'GNOME launched the wrong build (PID {pid})'

    def close_window(pid):
        shell_eval(f'{APP}.get_windows().find(window => window.get_pid() === {pid}).delete(global.get_current_time())')
        wait(lambda: pid not in windows(), 'Centaur did not close')

    def launch_from_gnome(expected):
        shell_eval(f'{APP}.activate()')
        pid = wait(lambda: next(iter(windows()), None), 'GNOME did not launch Centaur')
        expect_version(pid, expected)
        return pid

    activate(previous)
    legacy = profile/'share/applications'/DESKTOP_ID
    desktop.symlink_to(legacy)
    # Eval is enabled only in this dedicated compositor on a private D-Bus session.
    with (folder/'gnome-shell.log').open('w') as log:
        shell = subprocess.Popen(['gnome-shell', '--headless', '--wayland', '--no-x11', '--unsafe-mode',
                                  '--wayland-display=centaur-gnome', '--virtual-monitor=1280x900'],
                                 env=env, stdout=log, stderr=subprocess.STDOUT)
        first_candidate = None
        try:
            command = lambda: shell_eval(f'{APP}?.get_app_info().get_commandline()') or ''
            wait(lambda: str(previous/'bin/centaur-gtk4') in command(), 'GNOME did not cache the legacy command')
            old_pid = launch_from_gnome('0000000')
            close_window(old_pid)
            # The old-version fixture contains current registration code.
            # Reinstate the historical link and ensure GNOME actually caches it.
            desktop.unlink()
            desktop.symlink_to(legacy)
            wait(lambda: str(previous/'bin/centaur-gtk4') in command(), 'GNOME did not reload the legacy command')
            activate(candidate)
            # The signed-updater check covers the real handoff to this startup.
            first_candidate = subprocess.Popen([str(candidate/'bin/centaur-gtk4'), '--desktop-launch'],
                                               env=dict(env, WAYLAND_DISPLAY='centaur-gnome'), stdout=log,
                                               stderr=subprocess.STDOUT)
            wait(lambda: first_candidate.pid in windows(), 'Updated Centaur did not start in the same GNOME session')
            expect_version(first_candidate.pid, version)
            assert desktop.is_file() and not desktop.is_symlink()
            wait(lambda: str(profile/'bin/centaur-gtk4') in command(), 'GNOME kept the store-specific launch command')
            close_window(first_candidate.pid)
            assert first_candidate.wait(timeout=10) == 0
            relaunched = launch_from_gnome(version)
            close_window(relaunched)

            # A subsequent switch resolves the stable command even when the
            # desktop directory itself receives no update event.
            desktop_stat = desktop.stat()
            activate(previous)
            assert desktop.stat().st_ino == desktop_stat.st_ino
            assert desktop.stat().st_mtime_ns == desktop_stat.st_mtime_ns
            rolled_back = launch_from_gnome('0000000')
            close_window(rolled_back)
            (folder/'result.json').write_text(json.dumps({
                'passed': True, 'desktopId': DESKTOP_ID, 'gnomeShellPid': shell.pid,
                'previousPid': old_pid, 'migratedPid': first_candidate.pid,
                'relaunchedPid': relaunched, 'relaunchedBuild': version, 'rollbackPid': rolled_back,
            }, indent=2)+'\n')
            print(f'PASS: GNOME relaunched {version} after migration, then followed a second profile switch')
        finally:
            if first_candidate and first_candidate.poll() is None:
                first_candidate.terminate()
                first_candidate.wait(timeout=10)
            shell.terminate()
            shell.wait(timeout=10)


if __name__ == '__main__':
    main(*sys.argv[1:])
