"""Versioned GTK app contract, independent of embedding and project storage."""
import ast
import json
from pathlib import Path
import xml.etree.ElementTree as ET

FORMAT = 'gtk4-v1'
FILES = {'app.py', 'app.ui', 'style.css'}


def load_bundle(path):
    raw = Path(path).read_bytes()
    if len(raw) > 256000:
        raise ValueError('The app exceeds the 256 KB prototype limit')
    bundle = json.loads(raw)
    if bundle.get('format') != FORMAT:
        raise ValueError('This app needs a different native runtime')
    for dimension in ('width', 'height'):
        if type(bundle.get(dimension)) is not int or not 120 <= bundle[dimension] <= 4096:
            raise ValueError('App dimensions must be whole logical pixels from 120 to 4096')
    files = bundle.get('files')
    if not isinstance(files, dict) or set(files) != FILES or not all(isinstance(v, str) for v in files.values()):
        raise ValueError('An app needs exactly app.py, app.ui and style.css')
    tree = ast.parse(files['app.py'], filename='app.py')
    if not any(isinstance(node, ast.FunctionDef) and node.name == 'create_window' for node in tree.body):
        raise ValueError('app.py must define create_window(builder)')
    xml = ET.fromstring(files['app.ui'])
    if xml.tag != 'interface' or not any(node.get('id') == 'window' and node.get('class') == 'GtkWindow' for node in xml.iter('object')):
        raise ValueError('app.ui must define a GtkWindow named window')
    if not isinstance(bundle.get('designSystem'), str) or len(bundle['designSystem']) > 100:
        raise ValueError('An app needs a versioned design-system identifier')
    return bundle


def construct(bundle):
    # Generated apps are trusted native code, with normal user permissions.
    # This contract/validation boundary is not an execution sandbox.
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Gdk', '4.0')
    from gi.repository import Gtk, Gdk
    provider = Gtk.CssProvider()
    errors = []
    provider.connect('parsing-error', lambda p, section, error: errors.append(str(error)))
    provider.load_from_data(bundle['files']['style.css'].encode())
    if errors:
        raise ValueError('Invalid GTK CSS: ' + '; '.join(errors))
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    builder = Gtk.Builder.new_from_string(bundle['files']['app.ui'], -1)
    namespace = {'__name__': 'centaur_generated_app', '__file__': 'app.py'}
    exec(compile(bundle['files']['app.py'], 'app.py', 'exec'), namespace)
    window = namespace['create_window'](builder)
    if not isinstance(window, Gtk.Window):
        raise ValueError('create_window must return a Gtk.Window')
    if window.get_visible():
        window.destroy()
        raise ValueError('create_window must return an unpresented window')
    window.set_decorated(False)
    window.set_default_size(bundle['width'], bundle['height'])
    return window
