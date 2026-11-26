"""Inspect a generated window as seen inside Centaur's white preview canvas."""
import json
import os
from pathlib import Path
import time

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gdk, Gio, GLib, Gtk
from PIL import Image

from backend import AppSpec, CasildaBackend
from bundle import load_bundle
from check import read, until
from viewport import PreviewViewport


def capture(driver, application, folder, source):
    folder.mkdir()
    bundle = load_bundle(source)
    w, h = bundle['width'], bundle['height']
    window = Gtk.ApplicationWindow(application=application, decorated=False, default_width=w+80, default_height=h+80)
    provider = Gtk.CssProvider()
    provider.load_from_path(str(Path(__file__).with_name('shell.css')))
    display = Gdk.Display.get_default()
    Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    backend = CasildaBackend()
    viewport = PreviewViewport(backend.widget, w, h)
    viewport.add_css_class('canvas-panel')
    window.set_child(viewport)
    report = folder/'client.json'

    def pump():
        while GLib.MainContext.default().iteration(False):
            pass

    def allocated():
        pump()
        return backend.widget.get_width() == w+192 and backend.widget.get_height() == h+192

    try:
        window.present()
        until(allocated, 'Preview stage did not allocate')
        backend.start(AppSpec((os.environ['CENTAUR_GTK_RUNNER'], str(source)), w, h), folder, report)

        def ready():
            pump()
            client = read(report)
            return (client.get('width'), client.get('height')) == (w, h)

        until(ready, 'Separate app failed to map at its saved dimensions')
        handle = driver.find_window(application.get_application_id(), os.getpid())
        assert viewport.get_width() >= w+32 and viewport.get_height() >= h+32, 'Canvas cannot show all four corners'
        results = {}
        for mode in ('100%', '75%'):
            viewport.set_zoom(mode)
            # Wait for the host to present the new transform before reading compositor pixels.
            deadline = time.monotonic()+.3
            while time.monotonic() < deadline:
                pump()
                time.sleep(.01)
            view = viewport.describe()
            scale = view['scale']
            x, y = round(view['app_x']), round(view['app_y'])
            last_x = round(view['app_x']+w*scale)-1
            last_y = round(view['app_y']+h*scale)-1
            screenshot = folder/('canvas-'+mode[:-1]+'.png')
            driver.screenshot(handle, screenshot)
            with Image.open(screenshot) as image:
                pixels = image.convert('RGB')
            # An opaque white window on white exposes its silhouette only through its shadow.
            # Probe inside the nominal rectangle, outside the 12px arc, in all four corners.
            # Stay one pixel inside to exclude the rectangular edge's antialiasing.
            reach = max(2, round(5*scale))
            values = [min(pixels.getpixel((cx+dx*i, cy+dy*j))[0]
                          for i in range(1, reach) for j in range(1, reach))
                      for cx, dx in ((x, 1), (last_x, -1))
                      for cy, dy in ((y, 1), (last_y, -1))]
            results[mode] = dict(corners=values, interior=pixels.getpixel((x+20,y+20))[0],
                                 leftShadow=pixels.getpixel((x-2,(y+last_y)//2))[0],
                                 canvas=pixels.getpixel((x-16,(y+last_y)//2))[0])
        (folder/'pixels.json').write_text(json.dumps(results, indent=2))
        return results
    finally:
        backend.stop()
        viewport.release()
        window.destroy()
        Gtk.StyleContext.remove_provider_for_display(display, provider)


def check_corners(driver, folder):
    Gtk.init()
    application = Gtk.Application(application_id='org.centaur.Gtk4EmbeddingTest', flags=Gio.ApplicationFlags.NON_UNIQUE)
    application.register()
    folder.mkdir()
    source = folder/'App.gtk.json'
    ui = """<interface><object class="GtkWindow" id="window">
      <property name="overflow">hidden</property><style><class name="editor-window"/></style>
      <child><object class="GtkScrolledWindow"><child><object class="GtkTextView"/>
      </child></object></child></object></interface>"""
    for radius in (0, 12):
        source.write_text(json.dumps({
            'format': 'gtk4-v1', 'designSystem': 'centaur-basic-v1', 'width': 600, 'height': 842,
            'files': {'app.py': "def create_window(builder): return builder.get_object('window')", 'app.ui': ui,
                      'style.css': f'window.editor-window {{background: white; border-radius: {radius}px;}}'
                                   'scrolledwindow, textview, textview text {background: white;}'}}))
        result = capture(driver, application, folder/f'radius-{radius}', source)
        for mode, pixels in result.items():
            assert pixels['interior'] >= 252 and pixels['canvas'] >= 252, (radius, mode, pixels)
            assert pixels['leftShadow'] <= 250, ('Missing window shadow', radius, mode, pixels)
            if radius:
                assert max(pixels['corners']) <= 251, ('Window looks square on white', mode, pixels)
            else:
                assert min(pixels['corners']) >= 252, ('Square window looks rounded', mode, pixels)
