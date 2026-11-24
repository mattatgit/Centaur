"""External clipboard and file drag source for the disposable Wayland test."""
from pathlib import Path
import sys
import gi
gi.require_version('Gtk','4.0')
gi.require_version('Gdk','4.0')
from gi.repository import Gdk,GLib,Gtk


def activate(app):
    window=Gtk.ApplicationWindow(application=app,title='Composer reference source',decorated=False)
    mode,*inputs=sys.argv[1:]
    if mode=='drop':
        widget=Gtk.Label(label='Drag images')
        uris=''.join(Path(name).resolve().as_uri()+'\r\n' for name in inputs)
        provider=Gdk.ContentProvider.new_for_bytes('text/uri-list',GLib.Bytes.new(uris.encode()))
        drag=Gtk.DragSource(actions=Gdk.DragAction.COPY)
        drag.set_content(provider)
        widget.add_controller(drag)
    else:
        widget=Gtk.Button(label='Copy reference')
        if mode=='image':
            mime,content='image/png',Path(inputs[0]).read_bytes()
        elif mode=='text':
            mime,content='text/plain;charset=utf-8',inputs[0].encode()
        else: raise ValueError('Unsupported fixture')
        provider=Gdk.ContentProvider.new_for_bytes(mime,GLib.Bytes.new(content))
        widget.connect('clicked', lambda _:widget.get_clipboard().set_content(provider))
    window.set_child(widget)
    window.present()


if __name__=='__main__':
    app=Gtk.Application(application_id='org.centaur.ComposerFixture')
    app.connect('activate',activate)
    app.run([])
