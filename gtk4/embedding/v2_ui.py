"""Native components using the original exports from Centaur UI V2.0."""
from gi.repository import Gtk, GLib, Rsvg
from ui import ASSETS, box, label, picture, original, button


class WorkingMark(Gtk.DrawingArea):
    def __init__(self):
        super().__init__(content_width=32,content_height=32,halign=Gtk.Align.START,valign=Gtk.Align.CENTER)
        self.filename=str(ASSETS/'v2/centaur_wait_animation.svg')
        self.handle=Rsvg.Handle.new_from_file(self.filename); self.tick=None
        self.add_css_class('working-mark')
        self.set_can_target(False); self.set_draw_func(self.draw); self.phase(0)

    def phase(self,phase):
        # librsvg draws the unchanged original document. Its static renderer
        # does not run SVG CSS animations, so GTK's frame clock supplies the
        # original one-second opacity tracks on the original named groups.
        second=min(1,phase*2); first=1-second
        self.frame_opacities=(first,second)
        self.handle.set_stylesheet(('#frame-1 { opacity: '+str(first)+' !important; } #frame-2 { opacity: '+str(second)+' !important; }').encode())
        self.queue_draw()

    def draw(self,area,cr,width,height):
        rect=Rsvg.Rectangle(); rect.x=rect.y=0; rect.width=width; rect.height=height
        self.handle.render_document(cr,rect)

    def set_working(self,working):
        animated=working and Gtk.Settings.get_default().get_property('gtk-enable-animations')
        if animated and self.tick is None:
            self.epoch=GLib.get_monotonic_time(); self.tick=self.add_tick_callback(self.animate)
        elif not animated and self.tick is not None:
            self.remove_tick_callback(self.tick); self.tick=None; self.phase(0)

    def animate(self,widget,clock):
        self.phase(((clock.get_frame_time()-self.epoch)%1000000)/1000000)
        return True


class ImportWaiting(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=0,
                         halign=Gtk.Align.CENTER,valign=Gtk.Align.CENTER)
        self.add_css_class('import-waiting'); self.set_size_request(304,256)
        stage=Gtk.Overlay(); stage.set_size_request(304,168); stage.set_child(box())
        shadow=original('f83cd.svg',129); shadow.set_content_height(49)
        shadow.set_halign(Gtk.Align.CENTER); shadow.set_valign(Gtk.Align.END); shadow.set_margin_end(9); stage.add_overlay(shadow)
        clay=picture(ASSETS/'v2/dc3c7.png',128)
        clay.set_halign(Gtk.Align.CENTER); clay.set_valign(Gtk.Align.START); clay.set_margin_top(35); stage.add_overlay(clay); self.append(stage)
        captions=box(True,0); captions.set_valign(Gtk.Align.CENTER)
        caption_slot=Gtk.CenterBox(orientation=Gtk.Orientation.VERTICAL); caption_slot.set_size_request(-1,88)
        caption_slot.set_center_widget(captions); self.append(caption_slot)
        self.title=label('Centaur is importing your project','waiting-title',True)
        self.title.set_xalign(.5); captions.append(self.title)
        self.status=label('Reviewing the source files…','small muted',True)
        self.status.set_xalign(.5); captions.append(self.status)
        self.set_can_target(False)

    def update(self, phase):
        self.title.set_text('Centaur is importing your project' if phase in ('fetching','inspecting','investigating') else 'Your project is saved')
        self.status.set_text({'fetching':'Copying the source files…','inspecting':'Reviewing the source files…',
            'investigating':'Checking how to run your project…','awaitingAnswer':'Reply in chat to continue.',
            'readyToRun':'Ready to try your project.','failed':'See the conversation to continue.',
            'interrupted':'Ask in chat when you’re ready to continue.'}.get(phase,'See the conversation to continue.'))


def rule(filename,height=1):
    image=original(filename,1); image.set_content_width(0); image.set_hexpand(True)
    image.set_content_height(1); image.art_height=height; image.set_halign(Gtk.Align.FILL)
    return image


def form_card(owner, title):
    dialog,card=owner.dialog(title,408)
    owner.clear(card); card.add_css_class('v2-form'); card.set_spacing(0)
    heading=label(title,'dialog-title'); heading.set_size_request(-1,64)
    heading.set_margin_start(24); heading.set_margin_end(24); card.append(heading)
    line=rule('293c2.svg',.5); line.set_margin_start(24); line.set_margin_end(32); card.append(line)
    fields=box(True,22); fields.set_margin_top(13); fields.set_margin_bottom(24)
    fields.set_margin_start(24); fields.set_margin_end(24); card.append(fields)
    card.append(rule('9688b.svg'))
    footer=box(spacing=8,css='modal-footer'); footer.set_halign(Gtk.Align.END)
    footer.set_margin_top(15); footer.set_margin_bottom(16); footer.set_margin_end(16); card.append(footer)
    return dialog,fields,footer


def field(content,caption,widget):
    group=box(True,6); group.append(label(caption,'import-caption')); group.append(widget); content.append(group)
    return group


def prompt_field(placeholder):
    view=Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR,accepts_tab=False,css_classes=['import-prompt'])
    overlay=Gtk.Overlay(css_classes=['import-prompt-box']); overlay.set_size_request(-1,88)
    scroll=Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER); scroll.set_child(view); overlay.set_child(scroll)
    hint=label(placeholder,'import-placeholder',True); hint.set_can_target(False)
    hint.set_halign(Gtk.Align.START); hint.set_valign(Gtk.Align.START)
    hint.set_margin_start(16); hint.set_margin_top(12); hint.set_margin_end(16); overlay.add_overlay(hint)
    view.get_buffer().connect('changed',lambda b:hint.set_visible(not b.get_char_count()))
    return view,overlay


def cancel_button(owner,dialog,footer,callback=None):
    item=button('Cancel',lambda:(callback() if callback else None,owner.dismiss_dialog(dialog)),tone='plain',width=69)
    footer.append(item); return item
