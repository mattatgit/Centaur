"""Bounded disposable Linux display probe; never drives the user's desktop."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from PIL import Image
from test_driver import Driver


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
        raise SystemExit('Usage: centaur-gtk4-check NEW_REPORT_DIRECTORY (disposable CI display only)')
    folder = Path(sys.argv[1]).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    launcher = Path(sys.argv[0]).resolve().parent / 'centaur-gtk4-test'
    process = subprocess.Popen([str(launcher), '--report-dir', str(folder)])
    driver = Driver()
    summary = {'casilda_approved': False, 'checks': [], 'host_backend': 'wayland' if driver.wayland else 'x11'}
    child_pid = None
    try:
        host = lambda: read(folder / 'host.json')
        client = lambda: read(folder / 'client.json')
        until(lambda: client().get('width', 0) > 120 and host().get('canvas'), 'Client did not map')
        child_pid = client()['pid']
        summary['runtime'] = host()['runtime']
        assert child_pid != host()['pid'], 'Probe is not a separate process'
        assert client()['backend'] == 'wayland' and client()['private_socket'] and client()['desktop_display_removed']
        window = driver.find_window()
        assert not driver.standalone_exists(), 'Client escaped into a desktop window'
        initial_size = (client()['width'], client()['height'])

        def click_box(box):
            x, y, w, h = box
            driver.click(window, round(x + w / 2), round(y + h / 2))

        def click_client(name):
            box = until(lambda: client().get('targets', {}).get(name), 'Missing target ' + name)
            cx, cy, cw, ch = host()['canvas']
            view = host()['viewport']
            x, y, w, h = box
            x, y = cx+view['app_x']+x*view['scale'], cy+view['app_y']+y*view['scale']
            right, bottom = min(cx+cw, x+w*view['scale']), min(cy+ch, y+h*view['scale'])
            x, y = max(cx,x), max(cy,y)
            assert right > x and bottom > y, 'Target is outside the visible preview: ' + name
            click_box([x,y,right-x,bottom-y])

        screenshot = folder / 'embedded.png'
        last_marker = {}
        def rendered():
            driver.screenshot(window, screenshot)
            with Image.open(screenshot) as source:
                image = source.convert('RGB')
            points = [(i % image.width, i // image.width) for i,(r,g,b) in enumerate(image.getdata())
                      if abs(r-23) < 4 and abs(g-187) < 4 and abs(b-133) < 4]
            if len(points) <= 500:
                return False
            last_marker['x'] = min(x for x,y in points)
            last_marker['y'] = min(y for x,y in points)
            return True

        def positioned():
            if not rendered():
                return False
            cx,cy,cw,ch = host()['canvas']
            view = host()['viewport']
            # Check actual composition, rather than trusting the model/report:
            # the sample's green marker starts at app-local (24,24).
            return (abs(last_marker['x'] - (cx+view['app_x']+24*view['scale'])) < 3 and
                    abs(last_marker['y'] - (cy+view['app_y']+24*view['scale'])) < 3)
        until(rendered, 'Client marker was not rendered in the host screenshot')
        assert host()['viewport']['mode'] == '100%' and host()['viewport']['scale'] == 1
        until(positioned, 'The initial app presentation was not centred at 100%')
        summary['checks'].append('separate-process-private-wayland-render')
        click_client('button')
        until(lambda: 'click' in client().get('events', []), 'Pointer did not reach embedded button')
        click_client('entry')
        driver.type('Embedded input')
        until(lambda: client().get('text') == 'Embedded input', 'Keyboard/text input did not reach client')
        summary['checks'].append('pointer-keyboard-text')
        click_client('scroll')
        driver.scroll()
        until(lambda: client().get('scroll', 0) > 0, 'Scrolling did not reach client')
        summary['checks'].append('scroll')
        click_client('menu')
        click_client('popup_action')
        until(lambda: 'popup' in client().get('events', []), 'Popup action did not receive input')
        summary['checks'].append('popup')
        click_client('dialog')
        until(lambda: 'dialog-opened' in client().get('events', []), 'Dialog did not open')
        driver.key('Escape')
        until(lambda: 'dialog-closed' in client().get('events', []), 'Modal dialog focus/close failed')
        summary['checks'].append('modal-dialog')
        click_box(host()['entry'])
        driver.type('Host focus')
        until(lambda: host().get('host_text') == 'Host focus', 'Focus did not return to host')
        click_client('entry')
        driver.key('ctrl+a', 'ctrl+c')
        time.sleep(0.2)
        click_box(host()['entry'])
        driver.key('ctrl+a', 'ctrl+v')
        try:
            until(lambda: host().get('host_text') == 'Embedded input', 'Client to host clipboard failed', timeout=3)
            summary['clipboard_client_to_host'] = True
        except AssertionError:
            summary['clipboard_client_to_host'] = False
        driver.key('ctrl+a')
        driver.type('From host')
        driver.key('ctrl+a', 'ctrl+c')
        time.sleep(0.2)
        click_client('entry')
        driver.key('ctrl+a', 'ctrl+v')
        try:
            until(lambda: client().get('text') == 'From host', 'Host to client clipboard failed', timeout=3)
            summary['clipboard_host_to_client'] = True
        except AssertionError:
            summary['clipboard_host_to_client'] = False
        summary['checks'].append('host-client-focus')
        driver.resize(window, 1000, 760)
        time.sleep(0.5)
        assert (client()['width'], client()['height']) == initial_size, 'Host resize changed app dimensions'
        until(positioned, 'Resizing the host did not recenter the actual app image')
        click_client('button')
        summary['checks'].append('host-resize-recentres-and-preserves-app-dimensions')

        zoom_modes = ('50%', '75%', '100%', '125%', '150%', 'Fit')
        for index, mode in enumerate(zoom_modes):
            click_box(host()['zoom'])
            driver.key('Home', *(['Down']*index), 'Return')
            until(lambda: host()['viewport']['mode'] == mode, 'Zoom control did not select ' + mode)
            click_box(host()['centre'])
            until(lambda: abs(host()['viewport']['pan_y']) < 1, 'Centre did not reset panning')
            view = host()['viewport']
            cx,cy,cw,ch = host()['canvas']
            pan = max(0, (initial_size[1]*view['scale']-ch)/2+16)
            if pan > 16:
                driver.drag(window, round(cx+view['app_x']+8), round(cy+ch/2), 0, round(pan))
                until(lambda: host()['viewport']['pan_y'] > 10, 'Middle-button panning did not move the preview')
            screenshot = folder / ('zoom-' + mode.replace('%','') + '.png')
            until(positioned, 'Composed app position is incorrect at ' + mode)
            assert (client()['width'],client()['height']) == initial_size, 'Zoom changed app logical dimensions'
            count = client()['events'].count('click')
            click_client('button')
            until(lambda: client()['events'].count('click') > count, 'Scaled pointer missed at ' + mode)
            click_client('entry')
            driver.key('ctrl+a')
            value = 'Zoom ' + str(index)
            driver.type(value)
            until(lambda: client()['text'] == value, 'Scaled keyboard focus failed at ' + mode)
            click_client('scroll')
            driver.scroll(up=True)
            until(lambda: client()['scroll'] == 0, 'Scaled scroll-to-top failed at ' + mode)
            driver.scroll()
            until(lambda: client()['scroll'] > 0, 'Scaled scroll failed at ' + mode)
            popups = client()['events'].count('popup')
            click_client('menu')
            click_client('popup_action')
            until(lambda: client()['events'].count('popup') > popups, 'Scaled popup missed at ' + mode)
            dialogs = client()['events'].count('dialog-closed')
            click_client('dialog')
            until(lambda: client()['events'].count('dialog-opened') > dialogs, 'Scaled dialog did not open')
            driver.key('Escape')
            until(lambda: client()['events'].count('dialog-closed') > dialogs, 'Scaled dialog focus failed')
            summary['checks'].append('zoom-input-popup-dialog-' + mode)
        driver.resize(window, 1100, 800)
        until(positioned, 'Fit did not recenter after host resizing')
        view = host()['viewport']
        assert view['app_x'] >= 15 and view['app_y'] >= 15, 'Fit clipped the app'
        summary['checks'].append('fit-updates-on-resize')
        (folder / 'client-before-restart.json').write_text(json.dumps(client(), indent=2))
        for attempt in range(3):
            old_pid = child_pid
            click_box(host()['restart'])
            child_pid = until(lambda: client().get('pid') if client().get('pid') != old_pid else None, 'Restart did not create a new app')
            until(lambda: client().get('width', 0) > 120, 'Restarted client did not map')
            until(rendered, 'Restarted app did not render')
            click_client('button')
            until(lambda: 'click' in client().get('events', []), 'Restarted app did not receive input')
            try:
                os.kill(old_pid, 0)
            except ProcessLookupError:
                pass
            else:
                raise AssertionError('Old child remains after restart')
            summary['checks'].append(f'restart-{attempt + 1}')
        assert summary['clipboard_client_to_host'] and summary['clipboard_host_to_client'], 'Clipboard must work in both directions'
        summary['automated_core_passed'] = True
    finally:
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=5)
        summary['host_exit_code'] = process.returncode
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
    assert summary['host_exit_code'] == 0, 'Host did not shut down normally'


if __name__ == '__main__':
    main()
