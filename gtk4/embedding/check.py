"""Bounded Linux/Xvfb acceptance probe; never drives the user's desktop."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from PIL import Image


def command(*args):
    return subprocess.check_output(list(args), text=True).strip()


def read(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def until(predicate, message, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError(message)


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: centaur-gtk4-check NEW_REPORT_DIRECTORY (run under Xvfb)')
    folder = Path(sys.argv[1]).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    launcher = Path(sys.argv[0]).resolve().parent / 'centaur-gtk4-test'
    process = subprocess.Popen([str(launcher), '--report-dir', str(folder)])
    summary = {'casilda_approved': False, 'checks': []}
    child_pid = None
    try:
        host = lambda: read(folder / 'host.json')
        client = lambda: read(folder / 'client.json')
        until(lambda: client().get('width', 0) > 120 and host().get('canvas'), 'Client did not map')
        child_pid = client()['pid']
        assert child_pid != host()['pid'], 'Probe is not a separate process'
        assert client()['backend'] == 'wayland' and client()['private_socket'] and client()['desktop_display_removed']
        window = command('xdotool', 'search', '--onlyvisible', '--name', '^Centaur GTK4 embedding test$').splitlines()[0]
        standalone = subprocess.run(['xdotool', 'search', '--name', '^Centaur separate GTK4 probe$'], stdout=subprocess.DEVNULL)
        assert standalone.returncode == 1, 'Client escaped into a desktop X11 window'
        initial_size = (client()['width'], client()['height'])

        def click_box(box):
            x, y, w, h = box
            command('xdotool', 'mousemove', '--window', window, str(round(x + w / 2)), str(round(y + h / 2)), 'click', '1')

        def click_client(name):
            box = until(lambda: client().get('targets', {}).get(name), 'Missing target ' + name)
            cx, cy, cw, ch = host()['canvas']
            x, y, w, h = box
            click_box([cx + (cw - client()['width']) / 2 + x,
                       cy + (ch - client()['height']) / 2 + y, w, h])

        screenshot = folder / 'embedded.png'
        def rendered():
            command('magick', 'import', '-window', window, str(screenshot))
            with Image.open(screenshot) as source:
                image = source.convert('RGB')
            return sum(1 for r, g, b in image.getdata() if abs(r-23) < 4 and abs(g-187) < 4 and abs(b-133) < 4) > 500
        until(rendered, 'Client marker was not rendered in the host screenshot')
        summary['checks'].append('separate-process-private-wayland-render')
        click_client('button')
        until(lambda: 'click' in client().get('events', []), 'Pointer did not reach embedded button')
        click_client('entry')
        command('xdotool', 'type', '--clearmodifiers', 'Embedded input')
        until(lambda: client().get('text') == 'Embedded input', 'Keyboard/text input did not reach client')
        summary['checks'].append('pointer-keyboard-text')
        click_client('scroll')
        command('xdotool', 'click', '--repeat', '5', '--delay', '40', '5')
        until(lambda: client().get('scroll', 0) > 0, 'Scrolling did not reach client')
        summary['checks'].append('scroll')
        click_client('menu')
        click_client('popup_action')
        until(lambda: 'popup' in client().get('events', []), 'Popup action did not receive input')
        summary['checks'].append('popup')
        click_client('dialog')
        until(lambda: 'dialog-opened' in client().get('events', []), 'Dialog did not open')
        command('xdotool', 'key', '--clearmodifiers', 'Escape')
        until(lambda: 'dialog-closed' in client().get('events', []), 'Modal dialog focus/close failed')
        summary['checks'].append('modal-dialog')
        click_box(host()['entry'])
        command('xdotool', 'type', '--clearmodifiers', 'Host focus')
        until(lambda: host().get('host_text') == 'Host focus', 'Focus did not return to host')
        click_client('entry')
        command('xdotool', 'key', '--clearmodifiers', 'ctrl+a', 'ctrl+c')
        time.sleep(0.2)
        click_box(host()['entry'])
        command('xdotool', 'key', '--clearmodifiers', 'ctrl+a', 'ctrl+v')
        time.sleep(0.3)
        summary['clipboard_client_to_host'] = host().get('host_text') == 'Embedded input'
        command('xdotool', 'key', '--clearmodifiers', 'ctrl+a')
        command('xdotool', 'type', '--clearmodifiers', 'From host')
        command('xdotool', 'key', '--clearmodifiers', 'ctrl+a', 'ctrl+c')
        time.sleep(0.2)
        click_client('entry')
        command('xdotool', 'key', '--clearmodifiers', 'ctrl+a', 'ctrl+v')
        time.sleep(0.3)
        summary['clipboard_host_to_client'] = client().get('text') == 'From host'
        summary['checks'].append('host-client-focus')
        command('xdotool', 'windowsize', window, '1000', '760')
        time.sleep(0.5)
        assert (client()['width'], client()['height']) == initial_size, 'Host resize changed app dimensions'
        click_client('button')
        summary['checks'].append('host-resize-preserves-app-dimensions')
        old_pid = child_pid
        click_box(host()['restart'])
        child_pid = until(lambda: client().get('pid') if client().get('pid') != old_pid else None, 'Restart did not create a new app')
        until(lambda: client().get('width', 0) > 120, 'Restarted client did not map')
        try:
            os.kill(old_pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise AssertionError('Old child remains after restart')
        summary['checks'].append('restart')
        summary['automated_core_passed'] = True
    finally:
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=5)
        if child_pid:
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                summary['child_stopped_on_close'] = True
            else:
                summary['child_stopped_on_close'] = False
        (folder / 'summary.json').write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2), flush=True)
    assert summary.get('child_stopped_on_close'), 'Child remains after host shutdown'


if __name__ == '__main__':
    main()
