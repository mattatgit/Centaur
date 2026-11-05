"""Separate-process GTK4 application runner and bounded coordinator checker."""
import argparse
import json
import os
from pathlib import Path
import sys
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, Gtk
from bundle import load_bundle, construct


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('source', type=Path)
    parser.add_argument('--width', type=int)
    parser.add_argument('--height', type=int)
    args = parser.parse_args()
    bundle = load_bundle(args.source)
    if args.check:
        Gtk.init()
        window = construct(bundle)
        window.destroy()
        return 0
    app = Gtk.Application(application_id='org.centaur.GeneratedApp', flags=Gio.ApplicationFlags.NON_UNIQUE)
    def activate(application):
        try:
            window = construct(bundle)
            window.set_application(application)
            window.present()
            def report():
                filename = os.environ.get('CENTAUR_GTK4_PROBE_REPORT')
                if filename:
                    data = {'pid': os.getpid(), 'ready': True, 'width': window.get_width(), 'height': window.get_height(),
                            'title': window.get_title(), 'format': bundle['format']}
                    target = Path(filename)
                    target.with_suffix('.tmp').write_text(json.dumps(data))
                    target.with_suffix('.tmp').replace(target)
                return GLib.SOURCE_CONTINUE
            GLib.timeout_add(200, report)
        except Exception as error:
            print('Native app failed: ' + str(error), file=sys.stderr, flush=True)
            application.quit()
            application.failure = True
    app.connect('activate', activate)
    app.run([])
    return 1 if getattr(app, 'failure', False) else 0


if __name__ == '__main__':
    raise SystemExit(main())
