"""Phase 1 only: GTK4 host and separately running GTK4 interaction probe."""
import argparse
import json
import os
from pathlib import Path
import sys
import signal
import tempfile
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gio, GLib, Gtk
from backend import AppSpec, CasildaBackend


class Host(Gtk.Application):
    def __init__(self, report_dir):
        super().__init__(application_id='org.centaur.Gtk4EmbeddingTest', flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.runtime = tempfile.TemporaryDirectory(prefix='centaur-gtk4-preview-')
        self.report_dir = report_dir or Path(self.runtime.name) / 'reports'
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.backend = None
        self.failure = False

    def do_activate(self):
        self.backend = CasildaBackend()
        self.window = Gtk.ApplicationWindow(application=self, title='Centaur GTK4 embedding test',
                                            default_width=1100, default_height=800,
                                            decorated=not bool(os.environ.get('CENTAUR_GTK4_TEST_UNDECORATED')))
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        toolbar = Gtk.Box(spacing=12, margin_top=12, margin_start=16, margin_end=16)
        toolbar.append(Gtk.Label(label='GTK4 embedding experiment', hexpand=True, xalign=0))
        restart = Gtk.Button(label='Restart app')
        restart.connect('clicked', lambda b: self.restart())
        self.restart_button = restart
        toolbar.append(restart)
        root.append(toolbar)
        self.canvas = self.backend.widget
        self.canvas.set_hexpand(True)
        self.canvas.set_vexpand(True)
        root.append(self.canvas)
        self.host_entry = Gtk.Entry(placeholder_text='Host text field — test focus and clipboard across the app boundary',
                                    margin_start=16, margin_end=16)
        self.host_entry.connect('changed', lambda e: self.write_status())
        root.append(self.host_entry)
        self.status = Gtk.Label(label='Starting separate app…', xalign=0, margin_start=16, margin_bottom=12)
        root.append(self.status)
        self.window.set_child(root)
        self.window.connect('close-request', self.close)
        self.canvas.connect('realize', lambda w: GLib.idle_add(self.start))
        self.window.present()
        GLib.timeout_add(200, self.poll)

    def start(self):
        try:
            spec = AppSpec((sys.executable, str(Path(__file__).with_name('probe.py'))))
            self.backend.start(spec, Path(self.runtime.name), self.report_dir / 'client.json')
            self.failure = False
            self.status.set_text('App launched · interaction checks required · Casilda remains experimental')
        except Exception as error:
            self.failure = True
            self.status.set_text('Could not launch test app: ' + str(error))
            print(self.status.get_text(), file=sys.stderr, flush=True)
        return GLib.SOURCE_REMOVE

    def restart(self):
        self.backend.stop()
        (self.report_dir / 'client.json').unlink(missing_ok=True)
        self.start()

    def write_status(self):
        ok, rect = self.canvas.compute_bounds(self.window)
        entry_ok, entry = self.host_entry.compute_bounds(self.window)
        restart_ok, restart = self.restart_button.compute_bounds(self.window)
        data = {'pid': os.getpid(), 'child_pid': self.backend.process.pid if self.backend.process else None,
                'runtime': {'gtk': '.'.join(str(part) for part in (Gtk.get_major_version(), Gtk.get_minor_version(), Gtk.get_micro_version())),
                            'casilda': os.environ.get('CENTAUR_GTK4_CASILDA_VERSION', 'unknown')},
                'host_text': self.host_entry.get_text(), 'failure': self.failure,
                'canvas': [rect.get_x(), rect.get_y(), rect.get_width(), rect.get_height()] if ok else None,
                'entry': [entry.get_x(), entry.get_y(), entry.get_width(), entry.get_height()] if entry_ok else None}
        data['restart'] = [restart.get_x(), restart.get_y(), restart.get_width(), restart.get_height()] if restart_ok else None
        temporary = self.report_dir / 'host.tmp'
        temporary.write_text(json.dumps(data, indent=2))
        temporary.replace(self.report_dir / 'host.json')

    def poll(self):
        if self.backend and self.backend.process and self.backend.process.poll() is not None:
            self.failure = True
            self.status.set_text('Test app exited · use Restart app to retry')
        self.write_status()
        return GLib.SOURCE_CONTINUE

    def close(self, window):
        self.backend.stop()
        return False

    def do_shutdown(self):
        if self.backend:
            self.backend.stop()
        self.runtime.cleanup()
        Gtk.Application.do_shutdown(self)


def main():
    parser = argparse.ArgumentParser(description='Isolated GTK4/Casilda Phase 1 test; no Centaur project data is opened.')
    parser.add_argument('--report-dir', type=Path, help='Write new diagnostic JSON files to this directory')
    parser.add_argument('--version', action='version', version='Centaur GTK4 experiment +' + os.environ.get('CENTAUR_GTK4_BUILD_ID', 'dev'))
    args = parser.parse_args()
    app = Host(args.report_dir)
    for signum in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, lambda: (app.quit(), GLib.SOURCE_REMOVE)[1])
    return app.run([])


if __name__ == '__main__':
    raise SystemExit(main())
