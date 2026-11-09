"""Native Wayland or X11 automation, used only in disposable CI displays."""
import json
import os
import subprocess
import socket
import time


def command(*args):
    return subprocess.check_output(list(args), text=True).strip()


class Driver:
    def __init__(self):
        self.wayland = os.environ.get('CENTAUR_GTK4_TEST_BACKEND') == 'wayland'

    def nodes(self):
        def walk(node):
            yield node
            for child in node.get('nodes', []) + node.get('floating_nodes', []):
                yield from walk(child)
        return list(walk(json.loads(command('swaymsg', '-t', 'get_tree', '-r'))))

    def find_window(self, app_id='org.centaur.Gtk4EmbeddingTest', pid=None):
        if self.wayland:
            return next(n['id'] for n in self.nodes() if n.get('app_id') == app_id and (pid is None or n.get('pid') == pid))
        return command('xdotool', 'search', '--onlyvisible', '--name', '^Centaur GTK4 embedding test$').splitlines()[0]

    def standalone_exists(self):
        if self.wayland:
            return any(n.get('app_id') == 'org.centaur.EmbeddingProbe' for n in self.nodes())
        return subprocess.run(['xdotool', 'search', '--name', '^Centaur separate GTK4 probe$'], stdout=subprocess.DEVNULL).returncode != 1

    def ipc(self, text):
        result = json.loads(command('swaymsg', '-r', text))
        assert all(r.get('success') for r in result), result

    def rect(self, window):
        return next(n['rect'] for n in self.nodes() if n['id'] == window)

    def click(self, window, x, y):
        if self.wayland:
            self.ipc(f'[con_id={window}] focus')
            r = self.rect(window)
            self.ipc(f"seat seat0 cursor set {r['x'] + x} {r['y'] + y}")
            self.ipc('seat seat0 cursor press button1')
            self.ipc('seat seat0 cursor release button1')
        else:
            command('xdotool', 'mousemove', '--window', window, str(x), str(y), 'click', '1')

    def type(self, text):
        if self.wayland:
            self.seat_command('text ' + text)
        else:
            command('xdotool', 'type', '--clearmodifiers', text)

    def key(self, *keys):
        if self.wayland:
            for key in keys:
                self.seat_command('key ' + key)
        else:
            command('xdotool', 'key', '--clearmodifiers', *keys)

    def seat_command(self, request):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(10)
            connection.connect(os.environ['CENTAUR_GTK4_TEST_SEAT'])
            connection.sendall(request.encode('ascii'))
            connection.shutdown(socket.SHUT_WR)
            assert connection.recv(16) == b'ok', 'The disposable test seat rejected a request'

    def scroll(self, up=False):
        button, repeat = ('button4',20) if up else ('button5',5)
        if self.wayland:
            for _ in range(repeat):
                self.seat_command('scroll up' if up else 'scroll down')
                time.sleep(0.025)
            # Let GTK finish the wheel batch before reversing direction.
            time.sleep(0.2)
        else:
            command('xdotool', 'click', '--repeat', str(repeat), '--delay', '40', '4' if up else '5')

    def drag(self, window, x, y, dx, dy, button=2):
        self.drag_path(window,x,y,[(dx,dy)],button)

    def drag_path(self, window, x, y, moves, button=1):
        if self.wayland:
            self.ipc(f'[con_id={window}] focus')
            r = self.rect(window)
            self.ipc(f"seat seat0 cursor set {r['x'] + x} {r['y'] + y}")
            name = 'left' if button == 1 else 'middle'
            self.seat_command(name + ' press')
            previous_x = previous_y = 0
            for dx,dy in moves:
                for step in range(5):
                    self.seat_command(f'motion {(dx-previous_x)/5} {(dy-previous_y)/5}')
                    time.sleep(0.02)
                previous_x,previous_y = dx,dy
            self.seat_command(name + ' release')
        else:
            command('xdotool','mousemove','--window',window,str(x),str(y),'mousedown',str(button))
            for dx,dy in moves:
                command('xdotool','mousemove','--window',window,str(round(x+dx)),str(round(y+dy)))
            command('xdotool','mouseup',str(button))

    def screenshot(self, window, path, focus=True):
        if self.wayland:
            # Focusing the parent can hide a separate transient dialog under
            # Sway. Modal screenshots must preserve the current native focus.
            if focus: self.ipc(f'[con_id={window}] focus')
            r = self.rect(window)
            command('grim', '-g', f"{r['x']},{r['y']} {r['width']}x{r['height']}", str(path))
        else:
            command('magick', 'import', '-window', window, str(path))

    def resize(self, window, width, height):
        if self.wayland:
            self.ipc(f'[con_id={window}] resize set width {width} px height {height} px')
        else:
            command('xdotool', 'windowsize', window, str(width), str(height))
