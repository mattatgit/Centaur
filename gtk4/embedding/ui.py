"""Qt reference metrics, rounded to the owner's 8px component grid.

Typography keeps the reference point/pixel sizes. SVGs use their original
geometry and the same alpha-mask tinting as src/svgicon.cpp.
"""
from pathlib import Path
import math
import os
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Rsvg', '2.0')
gi.require_version('Graphene', '1.0')
gi.require_version('Gsk', '4.0')
gi.require_foreign('cairo')
from gi.repository import Gdk, Graphene, Gsk, Gtk, Pango, Rsvg

ASSETS = Path(os.environ.get('CENTAUR_GTK_ASSETS', Path(__file__).parent / 'assets'))
SIDEBAR, COMPACT_SIDEBAR, HEADER = 216, 72, 80
CHAT_WIDTH, CHAT_MIN, CHAT_MAX = 432, 368, 624
TILE_HEIGHT, TILE_GAP, TILE_MIN = 256, 32, 264


def grid(value):
    return int(math.floor(value / 8 + .5) * 8)


def columns(width):
    return max(1, min(5, int((width + TILE_GAP) // (TILE_MIN + TILE_GAP))))


def label(text='', css=None, wrap=False):
    widget = Gtk.Label(label=text, xalign=0, wrap=wrap, wrap_mode=Pango.WrapMode.WORD_CHAR)
    if css:
        for name in css.split(): widget.add_css_class(name)
    return widget


def box(vertical=False, spacing=8, css=None):
    widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL, spacing=spacing)
    if css:
        for name in css.split(): widget.add_css_class(name)
    return widget


def margins(widget, value):
    for edge in ('top', 'bottom', 'start', 'end'):
        getattr(widget, 'set_margin_' + edge)(value)
    return widget


class Svg(Gtk.DrawingArea):
    handles = {}

    def __init__(self, filename, size=16):
        super().__init__(content_width=size, content_height=size, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.set_can_target(False)
        self.add_css_class('svg')
        self.art_height=None
        self.set_from_file(str(ASSETS / filename))
        self.set_draw_func(self.draw)

    def set_pixel_size(self, size):
        self.set_content_width(size); self.set_content_height(size)

    def set_from_file(self, filename):
        self.filename = filename
        if filename not in self.handles:
            self.handles[filename] = Rsvg.Handle.new_from_file(filename)
        self.queue_draw()

    def draw(self, area, cr, width, height):
        rect = Rsvg.Rectangle(); rect.x = rect.y = 0; rect.width = width; rect.height = height if self.art_height is None else self.art_height
        cr.push_group()
        self.handles[self.filename].render_document(cr, rect)
        mask = cr.pop_group()
        color = self.get_style_context().get_color()
        cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)
        cr.mask(mask)


def selected(widget, value):
    (widget.add_css_class if value else widget.remove_css_class)('selected')
    if isinstance(widget, Gtk.ToggleButton): widget.set_active(value)
    if hasattr(widget, 'centaur_image'): widget.centaur_image.queue_draw()


def button(text, callback, icon=None, css=None, *, tone='soft', width=None, height=32, icon_size=16, toggle=False):
    widget = Gtk.ToggleButton() if toggle else Gtk.Button()
    widget.add_css_class('flat-button'); widget.add_css_class('tone-' + tone)
    if css:
        for name in css.split(): widget.add_css_class(name)
    row = box(spacing=8); row.set_halign(Gtk.Align.CENTER); row.set_valign(Gtk.Align.CENTER)
    widget.centaur_label = label(text, 'button-label')
    if icon:
        image = Svg(icon, icon_size)
        row.append(image); widget.centaur_image = image; widget.centaur_icon = icon
        widget.connect('state-flags-changed', lambda b, previous: image.queue_draw())
    if text: row.append(widget.centaur_label)
    else: widget.add_css_class('icon-only')
    widget.set_child(row)
    widget.set_size_request(width if width is not None else -1, height)
    widget.set_tooltip_text(text or 'Project options')
    widget.connect('clicked', lambda b: callback())
    return widget


def button_text(widget, text):
    widget.centaur_label.set_text(text)


def allocate(widget, width, height, x=0, y=0):
    widget.measure(Gtk.Orientation.HORIZONTAL, -1)
    widget.measure(Gtk.Orientation.VERTICAL, max(0, int(width)))
    point = Graphene.Point().init(x, y)
    widget.allocate(max(0, int(width)), max(0, int(height)), -1, Gsk.Transform.new().translate(point))


class ProjectGrid(Gtk.Widget):
    __gtype_name__ = 'CentaurProjectGrid'

    def __init__(self):
        super().__init__(hexpand=True, valign=Gtk.Align.START)
        self.cards = []

    def append(self, card):
        card.set_parent(self); self.cards.append(card); self.queue_resize()

    def clear(self):
        for card in self.cards: card.unparent()
        self.cards.clear(); self.queue_resize()

    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_measure(self, orientation, for_size):
        if orientation == Gtk.Orientation.HORIZONTAL: return (0, 1120, -1, -1)
        count = columns(for_size if for_size >= 0 else self.get_width())
        rows = math.ceil(len(self.cards) / count)
        height = rows * TILE_HEIGHT + max(0, rows - 1) * TILE_GAP
        return (height, height, -1, -1)

    def do_size_allocate(self, width, height, baseline):
        count = columns(width)
        card_width = max(8, math.floor((width - (count - 1) * TILE_GAP) / count / 8) * 8)
        for index, card in enumerate(self.cards):
            allocate(card, card_width, TILE_HEIGHT, (index % count) * (card_width + TILE_GAP), (index // count) * (TILE_HEIGHT + TILE_GAP))

    def do_snapshot(self, snapshot):
        for card in self.cards: self.snapshot_child(card, snapshot)


class Composer(Gtk.Widget):
    __gtype_name__ = 'CentaurComposer'

    def __init__(self, editor, row):
        super().__init__(hexpand=True)
        self.add_css_class('composer')
        self.editor = editor; self.row = row
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(editor)
        self.area = Gtk.Overlay(); self.area.set_child(scroll)
        self.placeholder = label('', 'composer-placeholder', True)
        self.placeholder.set_halign(Gtk.Align.START); self.placeholder.set_valign(Gtk.Align.START)
        self.placeholder.set_can_target(False)
        self.area.add_overlay(self.placeholder)
        self.area.set_parent(self); row.set_parent(self)
        editor.get_buffer().connect('changed', self.changed)
        focus = Gtk.EventControllerFocus()
        focus.connect('enter', lambda c: self.add_css_class('focus'))
        focus.connect('leave', lambda c: self.remove_css_class('focus'))
        editor.add_controller(focus)

    def changed(self, buffer):
        self.placeholder.set_visible(not buffer.get_char_count()); self.queue_resize()

    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_measure(self, orientation, for_size):
        if orientation == Gtk.Orientation.HORIZONTAL: return (CHAT_MIN - 48, 384, -1, -1)
        buffer = self.editor.get_buffer()
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
        layout = self.editor.create_pango_layout(text or ' ')
        layout.set_width(max(1, (for_size if for_size >= 0 else 384) - 32) * Pango.SCALE)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        height = min(184, max(104, math.ceil((layout.get_pixel_size()[1] + 64) / 8) * 8))
        # The editor scrolls, so its minimum remains 104 even when the natural
        # text height grows. Claiming both as the minimum violates GTK's
        # height-for-width contract during typing/resizing.
        return (104, height, -1, -1)

    def do_size_allocate(self, width, height, baseline):
        allocate(self.area, width - 32, height - 56, 16, 16)
        allocate(self.row, width - 16, 32, 8, height - 40)

    def do_snapshot(self, snapshot):
        snapshot.render_background(self.get_style_context(), 0, 0, self.get_width(), self.get_height())
        self.snapshot_child(self.area, snapshot); self.snapshot_child(self.row, snapshot)

    def release(self):
        self.area.unparent(); self.row.unparent()


class WidthLimit(Gtk.Widget):
    """A left-aligned maximum width without imposing a minimum on small windows."""
    def __init__(self, child, maximum=640, centred=False):
        super().__init__(hexpand=True, valign=Gtk.Align.START)
        self.child, self.maximum, self.centred = child, maximum, centred
        child.set_parent(self)

    def do_get_request_mode(self): return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_measure(self, orientation, for_size):
        if orientation == Gtk.Orientation.HORIZONTAL:
            minimum,natural,_,_=self.child.measure(orientation,-1)
            minimum=min(minimum,self.maximum)
            return (minimum,max(minimum,min(natural,self.maximum)),-1,-1)
        return self.child.measure(orientation, min(self.maximum, for_size if for_size >= 0 else self.maximum))

    def do_size_allocate(self, width, height, baseline):
        child_width=min(self.maximum,width)
        allocate(self.child,child_width,height,(width-child_width)/2 if self.centred else 0)

    def do_snapshot(self, snapshot): self.snapshot_child(self.child, snapshot)

    def release(self): self.child.unparent()


class Modal:
    """App-owned modal placement, independent of desktop window-placement policy.

    The content is native GTK. The overlay blocks the main UI, confines Tab
    traversal, and restores the previous keyboard focus on dismissal.
    """
    def __init__(self, owner, title, width):
        self.owner, self.title, self.width = owner, title, width
        self.previous_focus=owner.window.get_focus(); self.closed=False
        self.root=Gtk.Overlay(hexpand=True,vexpand=True)
        self.root.set_child(box(css='modal-shade'))
        self.root.set_visible(False); owner.root_overlay.add_overlay(self.root)
        key=Gtk.EventControllerKey(); key.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key.connect('key-pressed',self.key); self.root.add_controller(key)

    def set_child(self, child):
        self.content=child
        self.limit=WidthLimit(child,self.width,centred=True); self.limit.set_valign(Gtk.Align.CENTER)
        self.limit.set_margin_start(16); self.limit.set_margin_end(16)
        self.root.add_overlay(self.limit)

    def key(self, controller, keyval, keycode, state):
        if keyval not in (Gdk.KEY_Tab,Gdk.KEY_ISO_Left_Tab): return False
        def walk(widget):
            if not widget.get_mapped() or not widget.is_sensitive(): return
            descendants=[]
            child=widget.get_first_child()
            while child:
                descendants.extend(walk(child)); child=child.get_next_sibling()
            # Entry and scrolled-window delegates must be one Tab stop, not a
            # container stop followed by the actual editable widget.
            if descendants: yield from descendants
            elif widget.get_focusable(): yield widget
        items=list(walk(self.content))
        if items:
            current=self.owner.window.get_focus(); backwards=bool(state&Gdk.ModifierType.SHIFT_MASK) or keyval==Gdk.KEY_ISO_Left_Tab
            index=items.index(current) if current in items else (0 if backwards else -1)
            items[(index+(-1 if backwards else 1))%len(items)].grab_focus()
        return True

    def present(self):
        self.owner.root_overlay.get_child().set_can_target(False)
        self.root.set_visible(True); self.content.child_focus(Gtk.DirectionType.TAB_FORWARD)

    def destroy(self):
        if self.closed: return
        self.closed=True; self.root.set_visible(False); self.limit.release()
        self.owner.root_overlay.remove_overlay(self.root)
        self.owner.root_overlay.get_child().set_can_target(True)
        if self.previous_focus and self.previous_focus.get_mapped(): self.previous_focus.grab_focus()

    def get_visible(self): return self.root.get_visible() and not self.closed
    def get_title(self): return self.title
    def add_controller(self, controller): self.root.add_controller(controller)


class Stepper(Gtk.Box):
    def __init__(self, value, minimum, maximum, callback):
        super().__init__(spacing=0, halign=Gtk.Align.END)
        self.add_css_class('stepper')
        self.minimum, self.maximum, self.callback = minimum, maximum, callback
        self.entry = Gtk.Entry(text=str(value), xalign=.5, width_chars=3, max_width_chars=3)
        self.entry.set_size_request(64, 40)
        self.entry.connect('activate', lambda e: self.set_value(e.get_text()))
        self.append(button('−', lambda: self.set_value(self.value - 1), css='stepper-arrow', width=40, height=40))
        self.append(self.entry)
        self.append(button('+', lambda: self.set_value(self.value + 1), css='stepper-arrow', width=40, height=40))
        self.value = value
        focus = Gtk.EventControllerFocus(); focus.connect('leave', lambda c: self.set_value(self.entry.get_text()))
        self.entry.add_controller(focus)

    def set_value(self, value):
        try: value = max(self.minimum, min(self.maximum, int(value)))
        except ValueError: value = self.value
        changed = value != self.value; self.value = value; self.entry.set_text(str(value))
        if changed: self.callback(value)


class Switch(Gtk.ToggleButton):
    def __init__(self, active, callback):
        super().__init__(active=active, halign=Gtk.Align.END)
        self.add_css_class('switch'); self.set_size_request(56, 32)
        self.art = Gtk.DrawingArea(content_width=56, content_height=32)
        self.art.set_draw_func(self.draw); self.set_child(self.art)
        self.connect('toggled', lambda b: (self.art.queue_draw(), callback(b.get_active())))

    def draw(self, area, cr, width, height):
        cr.set_line_width(16); cr.set_line_cap(1)
        cr.set_source_rgb(*((.2,.2,.2) if self.get_active() else (.85,.85,.85)))
        cr.move_to(12,16); cr.line_to(44,16); cr.stroke()
        cr.arc(40 if self.get_active() else 16, 16, 15, 0, 2*math.pi)
        cr.set_source_rgb(1,1,1); cr.fill_preserve(); cr.set_line_width(1); cr.set_source_rgb(.75,.75,.75); cr.stroke()
