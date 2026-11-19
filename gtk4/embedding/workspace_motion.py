"""GTK frame-clock motion for the Projects/Edit scene and mode selector."""
from math import pi

from gi.repository import Graphene, Gtk
from ui import box, button, selected


def reduced_motion(widget):
    settings = widget.get_settings()
    if settings.find_property('gtk-interface-reduced-motion'):
        return settings.get_property('gtk-interface-reduced-motion') == Gtk.ReducedMotion.REDUCE
    return not settings.get_property('gtk-enable-animations')


class Motion:
    def __init__(self, widget, duration_ms, render, initial=0):
        self.widget = widget
        self.duration = duration_ms * 1000
        self.render = render
        self.value = self.destination = initial
        self.callback = None

    def stop(self):
        if self.callback is not None:
            self.widget.remove_tick_callback(self.callback)
            self.callback = None

    def move(self, destination, easing):
        if self.destination == destination and self.callback is not None:
            return
        self.stop()
        start = self.value
        self.destination = destination
        if start == destination or not self.widget.get_mapped() or reduced_motion(self.widget):
            self.value = destination
            self.render()
            return
        duration = self.duration * abs(destination - start)
        started = self.widget.get_frame_clock().get_frame_time()

        def frame(widget, clock):
            elapsed = max(0, clock.get_frame_time() - started)
            t = 1 if reduced_motion(widget) else min(1, elapsed / duration)
            if t == 1:
                self.callback = None
            self.value = start + (destination - start) * easing(t)
            self.render()
            return t < 1

        self.callback = self.widget.add_tick_callback(frame)


def smoothstep(t):
    t = max(0, min(1, t))
    return t * t * (3 - 2 * t)


def fill_rounded(cr, x, y, width, height, radius, gray):
    radius = min(radius, width / 2, height / 2)
    cr.new_sub_path()
    cr.arc(x + width - radius, y + radius, radius, -pi / 2, 0)
    cr.arc(x + width - radius, y + height - radius, radius, 0, pi / 2)
    cr.arc(x + radius, y + height - radius, radius, pi / 2, pi)
    cr.arc(x + radius, y + radius, radius, pi, 3 * pi / 2)
    cr.close_path()
    cr.set_source_rgb(gray, gray, gray)
    cr.fill()


class MotionLayer(Gtk.Widget):
    """Move only the rendering so the live chat and embedded app stay allocated."""
    def __init__(self, child):
        super().__init__(layout_manager=Gtk.BinLayout(), hexpand=True, vexpand=True)
        self.child = child
        self.offset = 0
        self.opacity = 1
        child.set_parent(self)

    def pose(self, offset, opacity):
        self.offset = offset
        self.opacity = opacity
        self.queue_draw()

    def do_snapshot(self, snapshot):
        if self.opacity == 0:
            return
        snapshot.save()
        snapshot.translate(Graphene.Point().init(self.offset, 0))
        snapshot.push_opacity(self.opacity)
        self.snapshot_child(self.child, snapshot)
        snapshot.pop()
        snapshot.restore()

    def release(self):
        self.child.unparent()


class ModeSwitch:
    def __init__(self, on_change, targets):
        self.widget = Gtk.Overlay(valign=Gtk.Align.CENTER, css_classes=['mode-switch'])
        self.track = Gtk.DrawingArea(content_width=136, content_height=24, can_target=False)
        self.track.set_draw_func(self.draw)
        self.widget.set_child(self.track)
        row = box(spacing=0)
        self.buttons = {}
        for mode, width in (('Interact', 72), ('Build', 64)):
            segment = button(mode, lambda value=mode: on_change(value), css='mode-button',
                             tone='plain', width=width, height=24, toggle=True)
            if self.buttons:
                segment.set_group(self.buttons['Interact'])
            row.append(segment)
            self.buttons[mode] = targets['mode-' + mode] = segment
        self.widget.add_overlay(row)
        self.motion = Motion(self.widget, 220, self.track.queue_draw)
        self.widget.connect('unmap', self.on_unmap)

    def select(self, mode):
        for name, segment in self.buttons.items():
            selected(segment, name == mode)
        self.motion.move(int(mode == 'Build'), smoothstep)

    def draw(self, area, cr, width, height):
        position = self.motion.value
        fill_rounded(cr, 0, 0, width, height, 8, 248 / 255)
        fill_rounded(cr, 72 * position, 0, 72 - 8 * position, height, 8, 235 / 255)

    def on_unmap(self, *unused):
        self.motion.stop()
        self.motion.value = self.motion.destination
        self.track.queue_draw()
