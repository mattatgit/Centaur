"""Compare native chat avatars with the original artwork in a disposable GNOME session."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import time

import cairo
from PIL import Image, ImageChops
from shell import Centaur, Gdk, GLib, Gtk
from ui import ASSETS, Rsvg, box


def check(folder):
    Gtk.init()
    display=Gdk.Display.get_default()
    css=Gtk.CssProvider()
    css.load_from_path(str(Path(__file__).with_name('shell.css')))
    Gtk.StyleContext.add_provider_for_display(display,css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    window=Gtk.Window(title='Centaur chat rendering check',default_width=390)
    content=box(True,8)
    window.set_child(content)
    avatars=[]
    for kind,art,text in [('agent','144b3.svg','Updated the app.'),('system','2fe69.svg','Sharing ended.')]:
        card,widgets,_,_=Centaur.message_row(SimpleNamespace(project={}),
            {'kind':kind,'author':'centaur','text':text}, {},None,None)
        content.append(card)
        avatars.append((widgets[0],art))
    window.present()
    try:
        context=GLib.MainContext.default()
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            while context.pending(): context.iteration(False)
            if content.get_width() and content.get_height() and content.get_mapped():
                snapshot=Gtk.Snapshot.new()
                Gtk.WidgetPaintable.new(content).snapshot(snapshot,content.get_width(),content.get_height())
                node=snapshot.to_node()
                if node: break
            time.sleep(.03)
        else: raise AssertionError('GNOME did not render the chat rows')
        assert window.get_scale_factor()==1
        texture=window.get_renderer().render_texture(node,None)
        output=folder/'chat-avatars-gnome-100.png'
        assert texture.save_to_png(str(output))
        with Image.open(output) as image:
            for widget,art in avatars:
                ok,rect=widget.compute_bounds(content)
                assert ok and (rect.get_width(),rect.get_height())==(32,32)
                x,y=round(rect.get_x()),round(rect.get_y())
                actual=image.convert('RGB').crop((x,y,x+32,y+32))
                surface=cairo.ImageSurface(cairo.FORMAT_ARGB32,32,32)
                cr=cairo.Context(surface); cr.set_source_rgb(*([250/255]*3)); cr.paint()
                size=Rsvg.Rectangle(); size.width=size.height=32
                Rsvg.Handle.new_from_file(str(ASSETS/'v2'/art)).render_document(cr,size)
                png=BytesIO(); surface.write_to_png(png); png.seek(0)
                expected=Image.open(png).convert('RGB')
                diff=ImageChops.difference(actual,expected)
                for left in (0,24):
                    for top in (0,24):
                        assert max(v for _,v in diff.crop((left,top,left+8,top+8)).getextrema())<=3, (art,left,top)
                assert len(actual.getcolors(1024))>3
        print('PASS: both 32px chat avatar corner radii match the original artwork at GNOME scale 1',flush=True)
    finally:
        window.destroy()
