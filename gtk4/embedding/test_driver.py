"""Native Wayland or X11 automation, used only in disposable CI displays."""
import json
import os
import subprocess


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

    def find_window(self):
        if self.wayland:
            return next(n['id'] for n in self.nodes() if n.get('app_id') == 'org.centaur.Gtk4EmbeddingTest')
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
            r = self.rect(window)
            self.ipc(f"seat seat0 cursor set {r['x'] + x} {r['y'] + y}")
            self.ipc('seat seat0 cursor press button1')
            self.ipc('seat seat0 cursor release button1')
        else:
            command('xdotool', 'mousemove', '--window', window, str(x), str(y), 'click', '1')

    def type(self, text):
        if self.wayland:
            command('wtype', '-d', '12', text)
        else:
            command('xdotool', 'type', '--clearmodifiers', text)

    def key(self, *keys):
        if self.wayland:
            args = ['wtype']
            for key in keys:
                *modifiers, value = key.split('+')
                for modifier in modifiers:
                    args += ['-M', modifier]
                args += ['-k', value]
                for modifier in reversed(modifiers):
                    args += ['-m', modifier]
            command(*args)
        else:
            command('xdotool', 'key', '--clearmodifiers', *keys)

    def scroll(self):
        if self.wayland:
            for _ in range(5):
                self.ipc('seat seat0 cursor press button5')
        else:
            command('xdotool', 'click', '--repeat', '5', '--delay', '40', '5')

    def screenshot(self, window, path):
        if self.wayland:
            r = self.rect(window)
            command('grim', '-g', f"{r['x']},{r['y']} {r['width']}x{r['height']}", str(path))
        else:
            command('magick', 'import', '-window', window, str(path))

    def resize(self, window, width, height):
        if self.wayland:
            self.ipc(f'[con_id={window}] resize set width {width} px height {height} px')
        else:
            command('xdotool', 'windowsize', window, str(width), str(height))
