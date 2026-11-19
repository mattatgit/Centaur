"""GTK frame-clock motion for the Projects/Edit scene and mode selector."""
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


class SlidePane(Gtk.Widget):
    """Translate the painted panel while keeping its native allocation fixed."""
    def __init__(self, child, distance):
        super().__init__(layout_manager=Gtk.BinLayout(), hexpand=True, vexpand=True)
        self.child = child
        self.distance = distance
        self.progress = 1
        child.set_parent(self)

    def show_progress(self, progress):
        self.progress = progress
        self.queue_draw()

    def do_snapshot(self, snapshot):
        snapshot.save()
        snapshot.translate(Graphene.Point().init(self.distance * (1 - self.progress), 0))
        snapshot.push_opacity(self.progress)
        self.snapshot_child(self.child, snapshot)
        snapshot.pop()
        snapshot.restore()

    def release(self):
        self.child.unparent()


class ModeSwitch:
    def __init__(self, on_change, targets):
        self.widget = Gtk.Overlay(valign=Gtk.Align.CENTER, css_classes=['mode-switch'])
        self.widget.set_size_request(136, 24)
        self.track = Gtk.Fixed(can_target=False)
        self.indicator = box(css='mode-indicator')
        self.indicator.set_can_target(False)
        self.track.put(self.indicator, 0, 0)
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
        self.motion = Motion(self.widget, 180, self.render)
        self.widget.connect('unmap', self.on_unmap)
        self.render()

    def select(self, mode):
        for name, segment in self.buttons.items():
            selected(segment, name == mode)
        self.motion.move(int(mode == 'Build'), lambda t: t * t * (3 - 2 * t))

    def render(self):
        position = self.motion.value
        self.track.move(self.indicator, 72 * position, 0)
        self.indicator.set_size_request(round(72 - 8 * position), 24)

    def on_unmap(self, *unused):
        self.motion.stop()
        self.motion.value = self.motion.destination
        self.render()
