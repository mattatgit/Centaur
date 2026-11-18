"""Native components using the original exports from Centaur UI V2.0."""
import cairo
import math
from gi.repository import Gtk, GLib, Rsvg
from ui import ASSETS, box, label, picture, original, button


class WorkingMark(Gtk.DrawingArea):
    def __init__(self):
        super().__init__(content_width=32,content_height=32,halign=Gtk.Align.START,valign=Gtk.Align.CENTER)
        self.filename=str(ASSETS/'v2/centaur_wait_animation.svg')
        self.frames=[]
        for first,second in ((1,0),(0,1)):
            handle=Rsvg.Handle.new_from_file(self.filename)
            handle.set_stylesheet(('#frame-1 { opacity: '+str(first)+' !important; } #frame-2 { opacity: '+str(second)+' !important; }').encode())
            self.frames.append(handle)
        self.tick=None
        self.working=False; self.settings=Gtk.Settings.get_default(); self.settings_handler=None
        # Since GTK 4.22 reduced motion is a separate accessibility preference.
        # GNOME can disable toolkit transitions on virtual/slow displays while
        # leaving that preference at NO_PREFERENCE. Do not mistake that
        # performance policy for a request to suppress this activity indicator.
        self.motion_property=('gtk-interface-reduced-motion' if self.settings.find_property('gtk-interface-reduced-motion') else 'gtk-enable-animations')
        self.add_css_class('working-mark')
        self.set_can_target(False); self.set_draw_func(self.draw); self.phase(0)
        self.connect('map',self.mapped); self.connect('unmap',self.unmapped)

    def phase(self,phase):
        # librsvg draws the unchanged original document. Its static renderer
        # does not run SVG CSS animations, so GTK's frame clock supplies the
        # original one-second opacity tracks on the original named groups.
        second=min(1,phase*2); first=1-second
        self.frame_opacities=(first,second)
        self.queue_draw()

    def draw(self,area,cr,width,height):
        rect=Rsvg.Rectangle(); rect.x=rect.y=0; rect.width=width; rect.height=height
        # Mix complete original frames in an isolated group. Fading two SVG
        # groups over one another with OVER reduces common ink to 75% at the
        # midpoint, producing the unwanted flash. ADD preserves their weighted
        # coverage without changing the supplied artwork or opacity tracks.
        cr.save(); cr.push_group()
        for handle,weight in zip(self.frames,self.frame_opacities):
            if not weight: continue
            cr.set_operator(cairo.OPERATOR_OVER); cr.push_group()
            handle.render_document(cr,rect); frame=cr.pop_group()
            cr.set_operator(cairo.OPERATOR_ADD); cr.set_source(frame); cr.paint_with_alpha(weight)
        blended=cr.pop_group(); cr.set_operator(cairo.OPERATOR_OVER); cr.set_source(blended); cr.paint(); cr.restore()

    def set_working(self,working):
        self.working=bool(working); self.sync_animation()

    def mapped(self,*unused):
        self.settings_handler=self.settings.connect('notify::'+self.motion_property,lambda *_:self.sync_animation())
        self.sync_animation()

    def unmapped(self,*unused):
        if self.settings_handler is not None:
            self.settings.disconnect(self.settings_handler); self.settings_handler=None
        self.sync_animation()

    def sync_animation(self):
        preference=self.settings.get_property(self.motion_property)
        reduced=(preference==Gtk.ReducedMotion.REDUCE if self.motion_property=='gtk-interface-reduced-motion' else not preference)
        animated=self.working and self.get_mapped() and not reduced
        if animated and self.tick is None:
            self.epoch=GLib.get_monotonic_time(); self.tick=self.add_tick_callback(self.animate)
        elif not animated:
            if self.tick is not None: self.remove_tick_callback(self.tick); self.tick=None
            if self.frame_opacities!=(1,0): self.phase(0)

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
        self.clay=clay
        clay.set_halign(Gtk.Align.CENTER); clay.set_valign(Gtk.Align.START); clay.set_margin_top(35); stage.add_overlay(clay); self.append(stage)
        captions=box(True,0); captions.set_valign(Gtk.Align.CENTER)
        caption_slot=Gtk.CenterBox(orientation=Gtk.Orientation.VERTICAL); caption_slot.set_size_request(-1,88)
        caption_slot.set_center_widget(captions); self.append(caption_slot)
        self.title=label('Centaur is importing your project','waiting-title',True)
        self.title.set_xalign(.5); captions.append(self.title)
        self.status=label('Please wait a moment','waiting-support muted',True)
        self.status.set_xalign(.5); captions.append(self.status)
        self.set_can_target(False)

    def update(self, phase, operation='import'):
        self.operation=operation
        self.title.set_text('Centaur is creating your project' if operation=='create' else 'Centaur is importing your project')
        self.status.set_text('Please wait a moment')


class UpdateIcon(Gtk.DrawingArea):
    """Original 16px Figma artwork; only its named progress stroke rotates."""
    FILES={'disabled':'418fd.svg','available':'pass2/d0b9d.svg',
           'updating':'pass2/d627f.svg','complete':'pass2/0b220.svg'}

    def __init__(self):
        super().__init__(content_width=16,content_height=16,halign=Gtk.Align.CENTER,valign=Gtk.Align.CENTER)
        self.set_can_target(False); self.state='disabled'; self.phase=0; self.tick=None
        self.filename=str(ASSETS/'v2'/self.FILES['disabled'])
        self.handles={state:Rsvg.Handle.new_from_file(str(ASSETS/'v2'/name)) for state,name in self.FILES.items()}
        self.base=Rsvg.Handle.new_from_file(str(ASSETS/'v2'/self.FILES['updating']))
        self.base.set_stylesheet(b'#stroke { opacity: 0 !important; }')
        self.settings=Gtk.Settings.get_default(); self.settings_handler=None
        self.motion_property=('gtk-interface-reduced-motion' if self.settings.find_property('gtk-interface-reduced-motion') else 'gtk-enable-animations')
        self.set_draw_func(self.draw); self.connect('map',self.mapped); self.connect('unmap',self.unmapped)

    def set_state(self,state):
        if self.state!=state:
            self.state=state; self.filename=str(ASSETS/'v2'/self.FILES[state]); self.queue_draw()
        self.sync_animation()

    def mapped(self,*unused):
        self.settings_handler=self.settings.connect('notify::'+self.motion_property,lambda *_:self.sync_animation())
        self.sync_animation()

    def unmapped(self,*unused):
        if self.settings_handler is not None:
            self.settings.disconnect(self.settings_handler); self.settings_handler=None
        self.sync_animation()

    def sync_animation(self):
        preference=self.settings.get_property(self.motion_property)
        reduced=(preference==Gtk.ReducedMotion.REDUCE if self.motion_property=='gtk-interface-reduced-motion' else not preference)
        active=self.state=='updating' and self.get_mapped() and not reduced
        if active and self.tick is None:
            self.epoch=GLib.get_monotonic_time(); self.tick=self.add_tick_callback(self.animate)
        elif not active:
            if self.tick is not None: self.remove_tick_callback(self.tick); self.tick=None
            self.phase=0; self.queue_draw()

    def animate(self,widget,clock):
        self.phase=((clock.get_frame_time()-self.epoch)%1000000)/1000000; self.queue_draw(); return True

    def draw(self,area,cr,width,height):
        rect=Rsvg.Rectangle(); rect.x=rect.y=0; rect.width=width; rect.height=height
        if self.state!='updating' or self.tick is None:
            self.handles[self.state].render_document(cr,rect); return
        self.base.render_document(cr,rect)
        cr.save(); cr.translate(width/2,height/2); cr.rotate(self.phase*2*math.pi); cr.translate(-width/2,-height/2)
        self.handles['updating'].render_layer(cr,'#stroke',rect); cr.restore()


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
