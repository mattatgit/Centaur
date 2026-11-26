"""Separate-process GTK4 application runner and bounded coordinator checker."""
import argparse
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, Gtk
from bundle import load_bundle, construct, StyleError, BuilderError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('source', type=Path)
    parser.add_argument('--width', type=int)
    parser.add_argument('--height', type=int)
    args = parser.parse_args()
    if args.check:
        # The coordinator receives fixed categories without raw exceptions or source text.
        try:
            bundle = load_bundle(args.source)
        except PermissionError:
            return 26
        except SyntaxError:
            return 21
        except ET.ParseError:
            return 22
        except ValueError:
            return 23
        Gtk.init()
        try:
            window = construct(bundle)
        except PermissionError:
            return 26
        except StyleError:
            return 24
        except BuilderError:
            return 25
        window.destroy()
        return 0
    bundle = load_bundle(args.source)
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
