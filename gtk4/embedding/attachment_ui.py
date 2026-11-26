"""GTK input and rendering for image and Figma conversation references."""
import json
import math
import re
import socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import gi
gi.require_version('Gtk','4.0')
gi.require_version('Gdk','4.0')
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, GObject, Gtk, Pango
from attachment_model import (MAX_IMAGE, MAX_INPUT, MAX_ITEMS, MAX_MESSAGE, check_image_dimensions,
                              check_input_size, figma_reference, image_filename, mention_suffix,
                              prepare_image, stored_image)
from ui import OriginalSvg, Raster, WidthLimit, accessible, allocate, box, label
from workspace_motion import reduced_motion


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


class LoadingRing(OriginalSvg):
    def __init__(self):
        super().__init__('composer/5488c.svg',26)
        self.angle = 0
        self.tick = None
        self.connect('map', self.start)
        self.connect('unmap', self.stop)

    def start(self, *_):
        prop = 'gtk-interface-reduced-motion' if self.get_settings().find_property('gtk-interface-reduced-motion') else 'gtk-enable-animations'
        self.preference = self.get_settings().connect('notify::'+prop, self.sync)
        self.sync()

    def stop(self, *_):
        self.get_settings().disconnect(self.preference)
        if self.tick is not None:
            self.remove_tick_callback(self.tick)
            self.tick = None

    def sync(self, *_):
        if reduced_motion(self):
            if self.tick is not None:
                self.remove_tick_callback(self.tick)
                self.tick = None
            self.angle = 0
            self.queue_draw()
        elif self.tick is None:
            self.tick = self.add_tick_callback(self.advance)

    def advance(self, widget, clock):
        self.angle = math.tau * (clock.get_frame_time() % 1_000_000) / 1_000_000
        self.queue_draw()
        return True

    def draw(self, area, cr, width, height):
        cr.translate(width/2, height/2)
        cr.rotate(self.angle)
        cr.translate(-width/2, -height/2)
        super().draw(area, cr, width, height)


def thumbnail(texture, remove):
    tile = Gtk.Overlay()
    tile.add_css_class('draft-thumbnail')
    tile.set_size_request(72,72)
    tile.set_halign(Gtk.Align.START)
    tile.set_valign(Gtk.Align.START)
    frame = Gtk.Box(css_classes=['image-thumbnail'], overflow=Gtk.Overflow.HIDDEN)
    frame.set_margin_top(8)
    frame.set_margin_end(8)
    if texture is None:
        frame.add_css_class('image-loading')
        accessible(frame,'Preparing image')
        frame.set_halign(Gtk.Align.FILL)
        frame.set_homogeneous(True)
        frame.append(LoadingRing())
    else:
        frame.append(Raster('',64,cover=True,texture=texture))
    tile.set_child(frame)
    close = icon_button('Cancel image preparation' if texture is None else 'Remove image',
                        artwork('f0a73.svg',16,(3.71,3.71,8.57,8.57)),remove,'image-remove')
    close.set_halign(Gtk.Align.END); close.set_valign(Gtk.Align.START)
    tile.add_overlay(close)
    return tile


class ImageNotice(WidthLimit):
    def __init__(self, dismiss):
        row = Gtk.Box(spacing=16, accessible_role=Gtk.AccessibleRole.ALERT, css_classes=['image-notice'])
        row.append(artwork('d4461.svg',16))
        self.caption = label('', 'image-notice-caption', True)
        self.caption.set_hexpand(True)
        self.caption.set_margin_end(12)
        row.append(self.caption)
        self.dismiss = icon_button('Dismiss image notification', artwork('cd44b.svg',16,(5.14,5.14,5.714,5.714)),
                                   dismiss, 'image-notice-dismiss')
        self.dismiss.set_valign(Gtk.Align.CENTER)
        row.append(self.dismiss)
        super().__init__(row,392)
        self.set_halign(Gtk.Align.END)
        self.set_valign(Gtk.Align.END)
        for side in ('start','end','bottom'):
            getattr(self,'set_margin_'+side)(24)
        self.set_visible(False)

    def do_measure(self, orientation, for_size):
        minimum, natural, a, b = super().do_measure(orientation, for_size)
        return minimum, self.maximum if orientation == Gtk.Orientation.HORIZONTAL else natural, a, b


class ImageLoad:
    def __init__(self, project):
        self.project = project
        self.slot = {'type':'loading'}
        self.cancel = Gio.Cancellable()
        self.future = None
        self.timer = None

    def stop_timer(self):
        if self.timer is not None:
            self.timer.destroy()
            self.timer = None


class AttachmentLayout(Gtk.LayoutManager):
    """Wrap each attachment at its own width; a long chip occupies only its row."""
    gap = 8  # A 72px tile reserves another 8px beside its 64px image for the X.

    def do_get_request_mode(self, widget):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def place(self, widget, width, allocate_children=False, row_limit=None):
        x = y = row_height = 0
        row = 1
        for child in widget:
            natural = child.measure(Gtk.Orientation.HORIZONTAL, -1)[1]
            w = min(natural, width) if width >= 0 else natural
            if x and width >= 0 and x + w > width:
                if row == row_limit: break
                row += 1
                y += row_height + self.gap
                x = row_height = 0
            h = child.measure(Gtk.Orientation.VERTICAL, w)[1]
            if allocate_children:
                allocate(child, w, h, x, y)
            x += w + self.gap
            row_height = max(row_height, h)
        return y + row_height

    def do_measure(self, widget, orientation, for_size):
        if orientation == Gtk.Orientation.HORIZONTAL:
            widths = [child.measure(orientation, -1) for child in widget]
            minimum = max((w[0] for w in widths), default=0)
            natural = sum(w[1] for w in widths) + self.gap * max(0, len(widths)-1)
            return minimum, natural, -1, -1
        height = self.place(widget, for_size)
        return height, height, -1, -1

    def do_allocate(self, widget, width, height, baseline):
        self.place(widget, width, allocate_children=True)


class ComposerInput:
    def __init__(self, owner):
        self.owner = owner
        self.editor = owner.editor
        self.directory = Path(owner.runtime.name)
        self.drafts = {}
        self.pending = set()
        self.previews = {}
        self.errors = {}
        self.notice = ImageNotice(self.dismiss_notice)
        owner.root_overlay.add_overlay(self.notice)
        owner.targets['dismiss-image-notice'] = self.notice.dismiss
        owner.targets['image-notice'] = self.notice
        self.titles_inflight = 0
        self.metadata_pool = ThreadPoolExecutor(max_workers=2,thread_name_prefix='figma-title')
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='composer-image')
        self.flow = Gtk.Box()
        self.flow.set_layout_manager(AttachmentLayout())
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
                self.show_notice(self.project,'Choose an image stored on this device.')
                continue
            def read(path=Path(path)):
                if not path.is_file():
                    raise ValueError('Choose a regular image file.')
                check_input_size(path.stat().st_size)
                with path.open('rb') as stream:
                    return stream.read(MAX_INPUT+1)
            if not self.ingest(read): break

    def paste(self, editor):
        clipboard = editor.get_clipboard()
        formats = clipboard.get_formats()
        project = self.project
        image_types=[mime for mime in ('image/png','image/jpeg','image/webp') if formats.contain_mime_type(mime)]
        if image_types or formats.contain_gtype(Gdk.Texture.__gtype__):
            editor.stop_emission_by_name('paste-clipboard')
            job = self.reserve()
            if job is not None:
                self.read_clipboard(job, clipboard, image_types)
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

    def read_clipboard(self, job, clipboard, image_types):
        def timed_out(*_):
            job.cancel.cancel()
            self.finish(job, error='The clipboard image took too long to read. Try copying it again.')
            return False
        job.timer = GLib.timeout_source_new_seconds(10)
        job.timer.set_callback(timed_out)
        job.timer.attach(None)

        def texture_ready(source, result):
            try:
                texture = source.read_texture_finish(result)
                if texture is None: raise ValueError('The clipboard image could not be read.')
                check_image_dimensions(texture.get_width(), texture.get_height())
                self.process(job, lambda:texture.save_to_png_bytes().get_data())
            except (GLib.Error, ValueError) as error:
                self.finish(job,error=str(error))

        def stream_ready(source, result):
            try:
                stream, _mime = source.read_finish(result)
                if stream is None: raise ValueError('The clipboard image could not be read.')
            except (GLib.Error, ValueError):
                self.finish(job,error='The clipboard image could not be read.')
                return
            raw = bytearray()
            def chunk_ready(stream, result):
                try:
                    chunk = stream.read_bytes_finish(result).get_data()
                    if job in self.pending and chunk:
                        raw.extend(chunk)
                        check_input_size(len(raw))
                        next_chunk()
                        return
                    self.process(job, lambda:raw)
                except GLib.Error:
                    self.finish(job,error='The clipboard image could not be read.')
                except ValueError as error:
                    self.finish(job,error=str(error))
                stream.close_async(GLib.PRIORITY_DEFAULT,None,None)

            def next_chunk():
                stream.read_bytes_async(min(65536, MAX_INPUT+1-len(raw)), GLib.PRIORITY_DEFAULT, job.cancel, chunk_ready)
            next_chunk()

        if image_types:
            clipboard.read_async(image_types, GLib.PRIORITY_DEFAULT, job.cancel, stream_ready)
        else:
            clipboard.read_texture_async(job.cancel, texture_ready)

    def has_room(self, project):
        return project and len(self.drafts.get(project,[])) < MAX_ITEMS

    def reserve(self):
        project = self.project
        if not self.has_room(project) or len(self.pending) >= MAX_ITEMS:
            self.show_notice(project,'Attach up to eight references at a time.')
            return None
        job = ImageLoad(project)
        self.pending.add(job)
        self.drafts.setdefault(project,[]).append(job.slot)
        self.refresh()
        return job

    def ingest(self, read):
        job = self.reserve()
        if job is None: return False
        self.process(job, read)
        return True

    def process(self, job, read):
        if job not in self.pending: return
        job.stop_timer()
        def prepare():
            ref, raw = prepare_image(read())
            stream = Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(raw))
            pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(stream,128,128,True,job.cancel)
            return ref, raw, pixbuf
        job.future = self.pool.submit(prepare)
        job.future.add_done_callback(lambda _:GLib.idle_add(self.finish,job))

    def finish(self, job, error=None):
        if job not in self.pending: return False
        self.pending.remove(job)
        job.stop_timer()
        draft = self.drafts.get(job.project,[])
        slot = next((i for i,item in enumerate(draft) if item is job.slot),None)
        if self.owner.closing or slot is None: return False
        try:
            if error is not None: raise ValueError(error)
            ref, raw, pixbuf = job.future.result()
            if sum((self.directory/image_filename(r)).stat().st_size for r in draft if r['type']=='image') + len(raw) > MAX_MESSAGE:
                raise ValueError(f'These images exceed the {MAX_MESSAGE // (1024*1024)} MiB message limit. Send them in separate messages.')
            path = self.directory/image_filename(ref)
            if not path.exists():
                if sum(p.stat().st_size for p in self.directory.glob('*.*') if p.is_file()) + len(raw) > 32*MAX_IMAGE:
                    raise ValueError('Send or remove images from other drafts to make room.')
                staging = path.with_suffix('.part')
                try:
                    staging.write_bytes(raw)
                    staging.replace(path)
                finally:
                    staging.unlink(missing_ok=True)
            self.previews[path.name] = Gdk.Texture.new_for_pixbuf(pixbuf)
            draft[slot] = ref
        except Exception as failure:
            draft.pop(slot)
            message = str(failure) if isinstance(failure,ValueError) else 'This image could not be prepared. Try another image.'
            self.show_notice(job.project, message)
        if job.project == self.project: self.refresh()
        return False

    def show_notice(self, project, message):
        self.errors[project] = message
        self.refresh_notice()

    def refresh_notice(self):
        message = self.errors.get(self.project,'')
        self.notice.caption.set_text(message)
        self.notice.set_visible(bool(message) and self.owner.page == 'workspace')

    def dismiss_notice(self):
        self.errors.pop(self.project,None)
        self.refresh_notice()
        self.editor.grab_focus()

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
        ref = self.refs.pop(index)
        if ref['type'] == 'loading':
            job = next(job for job in self.pending if job.slot is ref)
            job.cancel.cancel()
            job.stop_timer()
            if job.future is None: self.pending.remove(job)
            else: job.future.cancel()
        self.refresh(); self.clean_files()

    def clean_files(self):
        used = {image_filename(r) for draft in self.drafts.values() for r in draft if r['type']=='image'}
        for suffix in ('png','jpeg'):
            for path in self.directory.glob('*.'+suffix):
                if re.fullmatch(r'[0-9a-f]{64}\.(png|jpeg)',path.name) and path.name not in used:
                    path.unlink(missing_ok=True)
                    self.previews.pop(path.name,None)

    def refresh(self):
        while self.flow.get_first_child():
            self.flow.remove(self.flow.get_first_child())
        for key in list(self.owner.targets):
            if key.startswith(('remove-reference-','draft-reference-','draft-image-')): del self.owner.targets[key]
        for i,r in enumerate(self.refs):
            remove = lambda i=i:self.remove(i)
            if r['type']=='figma':
                child=chip(r,False,remove)
            else:
                texture = self.previews[image_filename(r)] if r['type']=='image' else None
                child=thumbnail(texture,remove)
            self.flow.append(child)
            self.owner.targets['remove-reference-'+str(i)]=child.get_last_child()
            if self.owner.reports:
                self.owner.targets['draft-reference-'+str(i)]=child
                if r['type']=='image': self.owner.targets['draft-image-'+str(i)]=child.get_child()
        self.owner.composer.tray.set_visible(bool(self.refs))
        self.owner.composer.queue_resize()
        self.owner.update_send()
        self.refresh_notice()
        self.refresh_suggestion()

    def confirmed(self, sent):
        draft = self.refs
        if draft[:len(sent)] == sent:
            del draft[:len(sent)]
            self.refresh(); self.clean_files()

    def close(self):
        for job in self.pending:
            job.cancel.cancel()
            job.stop_timer()
        self.pending.clear()
        self.notice.release()
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
