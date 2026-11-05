"""Separate native GTK4 process used to exercise the compositor boundary."""
import argparse
import json
import os
from pathlib import Path
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gio, GLib, Gtk


class Probe(Gtk.Application):
    def __init__(self, width, height):
        super().__init__(application_id='org.centaur.EmbeddingProbe', flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.width, self.height = width, height
        self.report = Path(os.environ['CENTAUR_GTK4_PROBE_REPORT'])
        self.state = {'pid': os.getpid(), 'events': [], 'text': '', 'scroll': 0,
                      'wheel_events': 0,
                      'backend': os.environ.get('GDK_BACKEND'),
                      'private_socket': bool(os.environ.get('WAYLAND_SOCKET')),
                      'desktop_display_removed': 'WAYLAND_DISPLAY' not in os.environ and 'DISPLAY' not in os.environ}
        self.targets = {}

    def write(self):
        self.state['width'], self.state['height'] = self.window.get_width(), self.window.get_height()
        self.state['targets'] = {}
        for name, widget in self.targets.items():
            if widget.get_mapped():
                ok, rect = widget.compute_bounds(self.window)
                if ok:
                    self.state['targets'][name] = [rect.get_x(), rect.get_y(), rect.get_width(), rect.get_height()]
        temporary = self.report.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.state, indent=2))
        temporary.replace(self.report)

    def event(self, name):
        self.state['events'].append(name)
        self.write()

    def do_activate(self):
        self.window = Gtk.ApplicationWindow(application=self, title='Centaur separate GTK4 probe',
                                            default_width=self.width, default_height=self.height, decorated=False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for edge in ('top', 'bottom', 'start', 'end'):
            getattr(box, 'set_margin_' + edge)(24)
        self.window.set_child(box)
        wheel = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.BOTH_AXES)
        wheel.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        wheel.connect('scroll', self.wheel_event)
        self.window.add_controller(wheel)
        marker = Gtk.Box(height_request=16)
        marker.set_name('probe-marker')
        box.append(marker)
        box.append(Gtk.Label(label='A separate GTK4 app', xalign=0))
        entry = Gtk.Entry(placeholder_text='Type here to test focus and text input')
        entry.connect('changed', lambda e: self.on_text(e))
        box.append(entry)
        self.targets['entry'] = entry
        button = Gtk.Button(label='Click to test input')
        button.connect('clicked', lambda b: self.event('click'))
        box.append(button)
        self.targets['button'] = button
        menu = Gtk.MenuButton(label='Open popup')
        popover = Gtk.Popover()
        pop_button = Gtk.Button(label='Choose popup action')
        pop_button.connect('clicked', lambda b: (self.event('popup'), popover.popdown()))
        popover.set_child(pop_button)
        menu.set_popover(popover)
        box.append(menu)
        self.targets['menu'] = menu
        self.targets['popup_action'] = pop_button
        dialog_button = Gtk.Button(label='Open dialog')
        dialog_button.connect('clicked', self.open_dialog)
        box.append(dialog_button)
        self.targets['dialog'] = dialog_button
        scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=100)
        rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for number in range(1, 31):
            rows.append(Gtk.Label(label=f'Scrollable row {number}', xalign=0))
        scroll.set_child(rows)
        scroll.get_vadjustment().connect('value-changed', self.on_scroll)
        box.append(scroll)
        self.targets['scroll'] = scroll
        self.window.present()
        GLib.timeout_add(150, self.update)

    def update(self):
        self.write()
        return GLib.SOURCE_CONTINUE

    def on_text(self, entry):
        self.state['text'] = entry.get_text()
        self.write()

    def on_scroll(self, adjustment):
        self.state['scroll'] = adjustment.get_value()
        self.write()

    def wheel_event(self, controller, dx, dy):
        self.state['wheel_events'] += 1
        self.state['last_wheel_delta'] = [dx,dy]
        self.write()
        return False

    def open_dialog(self, button):
        dialog = Gtk.Window(title='Embedded GTK4 dialog', transient_for=self.window,
                            modal=True, default_width=280, default_height=140)
        close = Gtk.Button(label='Close dialog')
        close.connect('clicked', lambda b: (self.event('dialog-closed'), dialog.destroy()))
        dialog.set_child(close)
        key = Gtk.EventControllerKey()
        key.connect('key-pressed', lambda c, value, code, state: self.dismiss_dialog(dialog, value))
        dialog.add_controller(key)
        dialog.connect('map', lambda w: self.event('dialog-opened'))
        dialog.present()

    def dismiss_dialog(self, dialog, value):
        if value == Gdk.KEY_Escape:
            self.event('dialog-closed')
            dialog.destroy()
            return True
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--height', type=int, required=True)
    args = parser.parse_args()
    app = Probe(args.width, args.height)
    app.connect('startup', lambda a: install_css())
    return app.run([])


def install_css():
    provider = Gtk.CssProvider()
    provider.load_from_data(b'window { background: #ffffff; } #probe-marker { background: rgb(23,187,133); border-radius: 4px; }')
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


if __name__ == '__main__':
    raise SystemExit(main())
