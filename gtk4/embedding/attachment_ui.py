"""GTK input and rendering for image and Figma conversation references."""
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from gi.repository import Gdk, Gio, GLib, Gtk, Pango
from attachment_model import (MAX_IMAGE, MAX_INPUT, MAX_ITEMS, MAX_MESSAGE, figma_reference,
                              image_filename, mention_suffix, prepare_image, stored_image)
from ui import OriginalSvg, accessible, box, label, picture


def artwork(name, size, rect=None):
    mark = OriginalSvg('composer/' + name, size)
    if rect:
        mark.art_rect = rect
    return mark


def icon_button(title, child, callback, style):
    button = Gtk.Button(css_classes=[style])
    accessible(button, title)
    button.set_child(child)
    button.connect('clicked', lambda _: callback())
    return button


def chip(ref, activate, remove=None):
    row = box(spacing=6, css='figma-chip')
    row.append(artwork('538c8.svg',16))
    title = label(ref.get('name') or 'Figma design','chip-title')
    title.set_ellipsize(Pango.EllipsizeMode.END)
    title.set_max_width_chars(18)
    if activate:
        link = Gtk.Button(child=title,css_classes=['chip-action'])
        link.connect('clicked', lambda _: Gio.AppInfo.launch_default_for_uri(ref['url'],None))
        row.append(link)
    else:
        row.append(title)
    row.set_tooltip_text(ref['url'])
    if remove:
        row.append(icon_button('Remove Figma link', artwork('20fa9.svg',16,(5,5,6,6)),remove,'chip-action'))
    row.set_halign(Gtk.Align.START)
    row.set_valign(Gtk.Align.CENTER)
    return row


def thumbnail(path, remove):
    tile = Gtk.Overlay()
    tile.set_size_request(72,72)
    tile.set_halign(Gtk.Align.START)
    frame = Gtk.Box(css_classes=['image-thumbnail'], overflow=Gtk.Overflow.HIDDEN)
    frame.set_margin_top(8)
    frame.set_margin_end(8)
    pic = picture(path,64,cover=True)
    pic.set_hexpand(True)
    frame.append(pic)
    tile.set_child(frame)
    close = icon_button('Remove image',artwork('f0a73.svg',16,(4,4,8,8)),remove,'image-remove')
    close.set_halign(Gtk.Align.END); close.set_valign(Gtk.Align.START)
    tile.add_overlay(close)
    return tile


class ComposerInput:
    def __init__(self, owner):
        self.owner = owner
        self.editor = owner.editor
        self.directory = Path(owner.runtime.name)
        self.drafts = {}
        self.pending = {}
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='composer-image')
        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=False,
                                min_children_per_line=1, max_children_per_line=8,
                                row_spacing=8,column_spacing=8,halign=Gtk.Align.FILL)
        self.ghost = label('', 'composer-placeholder', False)
        self.ghost.set_can_target(False); self.ghost.set_halign(Gtk.Align.START); self.ghost.set_valign(Gtk.Align.START)
        owner.composer.area.add_overlay(self.ghost)
        owner.composer.set_attachments(self.flow)
        self.buffer = self.editor.get_buffer()
        self.bold = self.buffer.create_tag('agent-address',weight=Pango.Weight.BOLD)
        self.suffix = ''; self.dismissed = None
        self.buffer.connect('changed', self.text_changed)
        self.buffer.connect('notify::cursor-position', lambda *_: self.refresh_suggestion())
        owner.composer.scroll.get_vadjustment().connect('value-changed', lambda *_: self.refresh_suggestion())
        self.editor.connect('paste-clipboard', self.paste)
        target = Gtk.DropTarget.new(Gdk.FileList,Gdk.DragAction.COPY)
        target.connect('drop', self.drop)
        owner.composer.add_controller(target)
        self.refresh()

    @property
    def project(self):
        return self.owner.project.get('id')

    @property
    def refs(self):
        return self.drafts.get(self.project, [])

    def name(self):
        value = self.owner.project.get('agentName') or 'Centaur'
        return 'Centaur' if value == 'centaur' else value

    def text_changed(self, buf):
        self.dismissed = None
        start, end = buf.get_bounds()
        text = buf.get_text(start,end,False)
        buf.remove_tag(self.bold,start,end)
        for m in re.finditer(r'(?<![\w@])@' + re.escape(self.name()) + r'(?![\w-])',text,re.I):
            buf.apply_tag(self.bold,buf.get_iter_at_offset(m.start()),buf.get_iter_at_offset(m.end()))
        self.refresh_suggestion()

    def refresh_suggestion(self):
        buf = self.buffer
        cursor = buf.get_iter_at_mark(buf.get_insert())
        text = buf.get_text(*buf.get_bounds(),False)
        context = (cursor.get_offset(),text)
        self.suffix = '' if buf.get_has_selection() or context == self.dismissed else mention_suffix(text,context[0],[self.name()])
        self.ghost.set_visible(bool(self.suffix))
        if self.suffix:
            rect = self.editor.get_iter_location(cursor)
            x,y = self.editor.buffer_to_window_coords(Gtk.TextWindowType.WIDGET,rect.x,rect.y)
            self.ghost.set_text(self.suffix)
            self.ghost.set_margin_start(max(0,x)); self.ghost.set_margin_top(max(0,y))
        return False

    def key(self, key, state):
        if self.suffix and key == Gdk.KEY_Tab and not state & (Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK):
            self.buffer.insert_at_cursor(self.suffix + ' ')
            return True
        if self.suffix and key == Gdk.KEY_Escape:
            self.dismissed = (self.buffer.props.cursor_position,self.buffer.get_text(*self.buffer.get_bounds(),False))
            self.refresh_suggestion()
            return True
        return False

    def pick(self):
        dialog = Gtk.FileChooserNative.new('Attach images',self.owner.window,Gtk.FileChooserAction.OPEN,'Attach','Cancel')
        dialog.set_select_multiple(True)
        formats = Gtk.FileFilter(); formats.set_name('PNG, JPEG and WebP images')
        for mime in ('image/png','image/jpeg','image/webp'): formats.add_mime_type(mime)
        dialog.add_filter(formats)
        project = self.project
        def selected(chooser, response):
            if response == Gtk.ResponseType.ACCEPT and self.project == project:
                self.files(chooser.get_files())
            chooser.destroy()
        dialog.connect('response',selected)
        dialog.show()

    def drop(self, target, value, x, y):
        self.files(value.get_files())
        return True

    def files(self, files):
        for file in files:
            path = file.get_path()
            if not path:
                self.owner.show_error('Choose an image stored on this device.')
                continue
            def read(path=Path(path)):
                if not path.is_file() or path.stat().st_size > MAX_INPUT:
                    raise ValueError('Choose a regular image file smaller than 16 MB.')
                with path.open('rb') as stream:
                    return stream.read(MAX_INPUT+1)
            if not self.ingest(read): break

    def paste(self, editor):
        clipboard = editor.get_clipboard()
        formats = clipboard.get_formats()
        project = self.project
        if formats.contain_gtype(Gdk.Texture.__gtype__):
            editor.stop_emission_by_name('paste-clipboard')
            def texture_ready(source, result):
                try:
                    texture = source.read_texture_finish(result)
                    if not texture or project != self.project: return
                    if texture.get_width()*texture.get_height()>16000000:
                        raise ValueError('Choose an image of up to 16 megapixels.')
                    raw = texture.save_to_png_bytes().get_data()
                    self.ingest(lambda: raw)
                except (GLib.Error,ValueError) as error: self.owner.show_error(str(error))
            clipboard.read_texture_async(None, texture_ready)
        elif any(m.startswith('text/plain') for m in formats.get_mime_types()):
            editor.stop_emission_by_name('paste-clipboard')
            mark = self.buffer.create_mark(None,self.buffer.get_iter_at_mark(self.buffer.get_insert()),False)
            def text_ready(source, result):
                try:
                    text = source.read_text_finish(result)
                    if not text or project != self.project: return
                    ref = figma_reference(text.strip())
                    if ref: self.add(project,ref)
                    elif self.buffer.get_iter_at_mark(mark).equal(self.buffer.get_iter_at_mark(self.buffer.get_insert())):
                        self.buffer.begin_user_action()
                        self.buffer.delete_selection(True,True)
                        self.buffer.insert_at_cursor(text)
                        self.buffer.end_user_action()
                    else: self.buffer.insert(self.buffer.get_iter_at_mark(mark),text)
                except GLib.Error as error: self.owner.show_error(str(error))
                finally: self.buffer.delete_mark(mark)
            clipboard.read_text_async(None,text_ready)

    def has_room(self, project):
        return project and len(self.drafts.get(project,[])) + self.pending.get(project,0) < MAX_ITEMS

    def ingest(self, read):
        project = self.project
        if not self.has_room(project) or sum(self.pending.values()) >= MAX_ITEMS:
            self.owner.show_error('Attach up to eight references at a time.')
            return False
        self.pending[project] = self.pending.get(project,0)+1
        self.owner.update_send()
        future = self.pool.submit(lambda:prepare_image(read()))
        def finish():
            if self.owner.closing: return False
            self.pending[project] -= 1
            try:
                ref, raw = future.result()
                draft = self.drafts.get(project,[])
                if sum((self.directory/image_filename(r)).stat().st_size for r in draft if r['type']=='image') + len(raw) > MAX_MESSAGE:
                    raise ValueError('These images exceed the 3 MB message limit. Send them in separate messages.')
                path = self.directory/image_filename(ref)
                if not path.exists():
                    if sum(p.stat().st_size for p in self.directory.glob('*.*') if p.is_file()) + len(raw) > 32*MAX_IMAGE:
                        raise ValueError('Send or remove images from other drafts to make room.')
                    path.write_bytes(raw)
                self.add(project,ref)
            except (ValueError,OSError) as error: self.owner.show_error(str(error))
            self.owner.update_send()
            return False
        future.add_done_callback(lambda _:GLib.idle_add(finish))
        return True

    def add(self, project, ref):
        if not self.has_room(project):
            self.owner.show_error('Attach up to eight references per message.')
            return
        self.drafts.setdefault(project,[]).append(ref)
        if project == self.project: self.refresh()

    def remove(self, index):
        self.refs.pop(index)
        self.refresh(); self.clean_files()

    def clean_files(self):
        used = {image_filename(r) for draft in self.drafts.values() for r in draft if r['type']=='image'}
        for suffix in ('png','jpeg'):
            for path in self.directory.glob('*.'+suffix):
                if re.fullmatch(r'[0-9a-f]{64}\.(png|jpeg)',path.name) and path.name not in used:
                    path.unlink(missing_ok=True)

    def refresh(self):
        while self.flow.get_first_child():
            self.flow.remove(self.flow.get_first_child())
        for i,r in enumerate(self.refs):
            remove = lambda i=i:self.remove(i)
            child = chip(r,False,remove) if r['type']=='figma' else thumbnail(self.directory/image_filename(r),remove)
            self.flow.insert(child,-1)
        self.owner.composer.tray.set_visible(bool(self.refs))
        self.owner.composer.queue_resize()
        self.owner.update_send()
        self.refresh_suggestion()

    def confirmed(self, sent):
        draft = self.refs
        if draft[:len(sent)] == sent:
            del draft[:len(sent)]
            self.refresh(); self.clean_files()

    def close(self):
        self.pool.shutdown(wait=False,cancel_futures=True)


def available_images(owner, message):
    source = owner.data.get('sourcePath')
    folder = Path(source).parent/'.centaur'/'attachments' if source else None
    return tuple(bool(folder and stored_image(folder,r)) for r in message.get('attachments',[]) if r.get('type')=='image')


def conversation_references(owner, message, author, card):
    from gi.repository import GdkPixbuf
    wrapper = box(True,8)
    folder = Path(owner.data['sourcePath']).parent/'.centaur'/'attachments'
    for ref in message.get('attachments',[]):
        if ref.get('type') == 'figma' and figma_reference(ref.get('url')):
            wrapper.append(chip(ref,True))
        elif ref.get('type') == 'image':
            path = stored_image(folder,ref)
            if path:
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path),232,232,True)
                    visual = Gtk.Picture.new_for_paintable(Gdk.Texture.new_for_pixbuf(pixbuf))
                    visual.set_can_shrink(True)
                    def inspect(path=path):
                        dialog, column = owner.dialog('Uploaded image',760)
                        large = Gtk.Picture.new_for_filename(str(path))
                        large.set_can_shrink(True)
                        large.set_size_request(-1,max(128,min(520, owner.window.get_height()-230)))
                        column.append(large)
                        close = Gtk.Button(label='Close')
                        close.connect('clicked',lambda _:owner.dismiss_dialog(dialog))
                        column.append(close); dialog.present(close)
                    view = icon_button('Inspect image uploaded by '+author,visual,inspect,'uploaded-image')
                    view.set_halign(Gtk.Align.START)
                    wrapper.append(view)
                except GLib.Error:
                    wrapper.append(label('This image could not be read.','muted',True))
            else:
                wrapper.append(label('Image unavailable on this device. Reconnect to retrieve it.','muted',True))
            wrapper.append(label(author+' uploaded this image','upload-attribution',True))
    if message.get('text'):
        wrapper.append(card)
        wrapper.pointer_anchor = card
    return wrapper
