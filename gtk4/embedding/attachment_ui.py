"""GTK input and rendering for image and Figma conversation references."""
import json
import re
import socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import gi
gi.require_version('Gtk','4.0')
gi.require_version('Gdk','4.0')
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, GObject, Gtk, Pango
from attachment_model import (MAX_IMAGE, MAX_INPUT, MAX_ITEMS, MAX_MESSAGE, figma_reference,
                              image_filename, mention_suffix, prepare_image, stored_image)
from ui import OriginalSvg, accessible, allocate, box, label


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
    row = box(spacing=8, css='figma-chip')
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
        row.append(icon_button('Remove Figma link', artwork('20fa9.svg',16,(5.38,5.38,5.24,5.24)),remove,'chip-action'))
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
    preview = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path),64,64,True)
    pic = Gtk.Picture.new_for_paintable(Gdk.Texture.new_for_pixbuf(preview))
    pic.set_content_fit(Gtk.ContentFit.COVER)
    pic.set_can_shrink(True)
    pic.set_hexpand(True)
    frame.append(pic)
    tile.set_child(frame)
    close = icon_button('Remove image',artwork('f0a73.svg',16,(3.71,3.71,8.57,8.57)),remove,'image-remove')
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
        self.clipboard_reads=set()
        self.titles_inflight = 0
        self.metadata_pool = ThreadPoolExecutor(max_workers=2,thread_name_prefix='figma-title')
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
        target.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
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
        formats = Gtk.FileFilter(); formats.set_name('PNG, JPEG and WebP images')
        for mime in ('image/png','image/jpeg','image/webp'): formats.add_mime_type(mime)
        filters=Gio.ListStore.new(Gtk.FileFilter); filters.append(formats)
        project = self.project
        def selected(chooser, result):
            try:
                files=chooser.open_multiple_finish(result)
            except GLib.Error as error:
                if not error.matches(Gtk.DialogError.quark(),Gtk.DialogError.DISMISSED):
                    self.owner.show_error('The image chooser could not open the selection.')
                return
            if self.project==project and files:
                self.files(files.get_item(index) for index in range(files.get_n_items()))
        Gtk.FileDialog(title='Attach images',filters=filters,modal=True).open_multiple(self.owner.window,None,selected)

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
        image_types=[mime for mime in ('image/png','image/jpeg','image/webp') if formats.contain_mime_type(mime)]
        if image_types:
            # Read the encoded selection under the same limits as the picker.
            # Asking GTK for a texture first would decode it before validation.
            editor.stop_emission_by_name('paste-clipboard')
            def stream_ready(source,result):
                try:
                    stream,_mime=source.read_finish(result)
                    if stream is None: return
                    if project!=self.project:
                        stream.close(None)
                        return
                    cancel=Gio.Cancellable()
                    self.clipboard_reads.add(cancel)
                    timer=GLib.timeout_source_new_seconds(10)
                    timer.set_callback(lambda *_:cancel.cancel() or False)
                    timer.attach(None)
                    def close_stream():
                        timer.destroy()
                        self.clipboard_reads.discard(cancel)
                        return False
                    def read():
                        raw=bytearray()
                        try:
                            while len(raw)<=MAX_INPUT:
                                chunk=stream.read_bytes(min(65536,MAX_INPUT+1-len(raw)),cancel).get_data()
                                if not chunk: break
                                raw.extend(chunk)
                            return bytes(raw)
                        except GLib.Error as error:
                            raise ValueError('The clipboard image could not be read.') from error
                        finally:
                            GLib.idle_add(close_stream)
                            stream.close(None)
                    if not self.ingest(read):
                        close_stream(); stream.close(None)
                except GLib.Error:
                    self.owner.show_error('The clipboard image could not be read.')
            clipboard.read_async(image_types,GLib.PRIORITY_DEFAULT,None,stream_ready)
        elif formats.contain_gtype(Gdk.Texture.__gtype__):
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
        elif formats.contain_gtype(GObject.TYPE_STRING) or any(m.startswith('text/plain') for m in formats.get_mime_types()):
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
        return project and len(self.drafts.get(project,[])) < MAX_ITEMS

    def ingest(self, read):
        project = self.project
        if not self.has_room(project) or sum(self.pending.values()) >= MAX_ITEMS:
            self.owner.show_error('Attach up to eight references at a time.')
            return False
        placeholder={'type':'loading'}
        self.drafts.setdefault(project,[]).append(placeholder)
        self.pending[project] = self.pending.get(project,0)+1
        self.refresh()
        future = self.pool.submit(lambda:prepare_image(read()))
        def finish():
            if self.owner.closing: return False
            self.pending[project] -= 1
            draft=self.drafts.get(project,[])
            slot=next((i for i,item in enumerate(draft) if item is placeholder),None)
            if slot is None: return False
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
                draft[slot]=ref
            except (ValueError,OSError) as error:
                draft.pop(slot)
                self.owner.show_error(str(error))
            if project==self.project: self.refresh()
            return False
        future.add_done_callback(lambda _:GLib.idle_add(finish))
        return True

    def refine_title(self, project, ref):
        # A denied or unavailable reader leaves the URL-derived title usable.
        def fetch():
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
                client.settimeout(5)
                client.connect('/run/centaur-figma.sock')
                query={'project':project,'operation':'title','urls':[ref['url']]}
                client.sendall(json.dumps(query).encode()+b'\n')
                with client.makefile('rb') as stream: data=stream.readline(1025)
            if len(data)>1024: return None
            result=json.loads(data).get('results',[])
            return result[0].get('name') if result else None
        def finish(future):
            self.titles_inflight -= 1
            if self.owner.closing: return False
            try: name=future.result()
            except (OSError,ValueError,IndexError): return False
            # Never mutate metadata after sending, or replace another chip.
            if name and not self.owner.pending_message and any(r is ref for r in self.drafts.get(project,[])):
                ref['name']=name[:120]
                if self.project==project: self.refresh()
            return False
        if self.titles_inflight < 2 and Path('/run/centaur-figma.sock').is_socket():
            self.titles_inflight += 1
            self.metadata_pool.submit(fetch).add_done_callback(lambda future:GLib.idle_add(finish,future))

    def add(self, project, ref):
        if not self.has_room(project):
            self.owner.show_error('Attach up to eight references per message.')
            return
        self.drafts.setdefault(project,[]).append(ref)
        if ref['type']=='figma': self.refine_title(project,ref)
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
        for key in list(self.owner.targets):
            if key.startswith('remove-reference-'): del self.owner.targets[key]
        for i,r in enumerate(self.refs):
            remove = lambda i=i:self.remove(i)
            if r['type']=='loading':
                child=Gtk.Button(label='Preparing image…')
                child.connect('clicked',lambda _,remove=remove:remove())
            elif r['type']=='figma':
                child=chip(r,False,remove)
            else:
                child=thumbnail(self.directory/image_filename(r),remove)
            self.flow.insert(child,-1)
            self.owner.targets['remove-reference-'+str(i)]=child.get_last_child()
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
        for cancel in self.clipboard_reads: cancel.cancel()
        self.metadata_pool.shutdown(wait=False,cancel_futures=True)
        self.pool.shutdown(wait=False,cancel_futures=True)


def available_images(owner, message):
    source = owner.data.get('sourcePath')
    folder = Path(source).parent/'.centaur'/'attachments' if source else None
    return tuple(bool(folder and stored_image(folder,r)) for r in message.get('attachments',[]) if r.get('type')=='image')


class ConversationImageLayout(Gtk.LayoutManager):
    """Keep uploaded artwork at its intended size even in a tall, nearly empty chat."""
    def __init__(self,pixbuf):
        super().__init__()
        self.width,self.height=pixbuf.get_width(),pixbuf.get_height()

    def do_get_request_mode(self,widget):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def scaled_height(self,width):
        return max(1,round(width*self.height/self.width))

    def do_measure(self,widget,orientation,for_size):
        if orientation==Gtk.Orientation.HORIZONTAL: return 1,self.width,-1,-1
        width=self.width if for_size<0 else min(self.width,for_size)
        height=self.scaled_height(width)
        return height,height,-1,-1

    def do_allocate(self,widget,width,height,baseline):
        width=min(width,self.width)
        allocate(widget.get_first_child(),width,min(height,self.scaled_height(width)))


def conversation_references(owner, message, author, card):
    wrapper = box(True,8)
    wrapper.image_buttons=[]
    folder = Path(owner.data['sourcePath']).parent/'.centaur'/'attachments'
    for ref in message.get('attachments',[]):
        if ref.get('type') == 'figma' and figma_reference(ref.get('url')):
            wrapper.append(chip(ref,True))
        elif ref.get('type') == 'image':
            path = stored_image(folder,ref)
            if path:
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path),232,232,True)
                    def inspect(path=path):
                        dialog, column = owner.dialog('Uploaded image',760)
                        large = Gtk.Picture.new_for_filename(str(path))
                        large.set_can_shrink(True)
                        large.set_size_request(-1,max(128,min(520, owner.window.get_height()-230)))
                        column.append(large)
                        close = Gtk.Button(label='Close')
                        close.connect('clicked',lambda _:owner.dismiss_dialog(dialog))
                        column.append(close); dialog.present(close)
                    picture=Gtk.Picture.new_for_paintable(Gdk.Texture.new_for_pixbuf(pixbuf))
                    picture.set_can_shrink(True)
                    view=icon_button('Inspect image uploaded by '+author,picture,inspect,'uploaded-image')
                    view.set_overflow(Gtk.Overflow.HIDDEN)
                    frame=Gtk.Box(valign=Gtk.Align.START)
                    frame.set_layout_manager(ConversationImageLayout(pixbuf))
                    frame.append(view)
                    wrapper.append(frame); wrapper.image_buttons.append(view)
                except GLib.Error:
                    wrapper.append(label('This image could not be read.','muted',True))
            else:
                notice = ('Image unavailable on this device. Reconnect to retrieve it.' if owner.data.get('remote')
                          else 'Image unavailable in this copy. Attach it again to share it.')
                wrapper.append(label(notice,'muted',True))
            wrapper.append(label(author+' uploaded this image','upload-attribution',True))
    if message.get('text'):
        if any(ref.get('type')=='image' for ref in message.get('attachments',[])):
            card.set_margin_top(16)
        wrapper.append(card)
        wrapper.pointer_anchor = card
    return wrapper
