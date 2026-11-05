"""GTK viewport; native embedding/lifecycle remains in the backend."""
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gsk', '4.0')
gi.require_version('Graphene', '1.0')
from gi.repository import Gdk, Graphene, Gsk, Gtk
from viewport_model import ViewportModel


class PreviewViewport(Gtk.Widget):
    __gtype_name__ = 'CentaurPreviewViewport'

    def __init__(self, child, width, height):
        super().__init__(hexpand=True, vexpand=True)
        self.child = child
        self.model = ViewportModel(width, height)
        self.set_overflow(Gtk.Overflow.HIDDEN)
        child.set_parent(self)
        drag = Gtk.GestureDrag(button=2, propagation_phase=Gtk.PropagationPhase.CAPTURE)
        drag.connect('drag-begin', self.drag_begin)
        drag.connect('drag-update', self.drag_update)
        self.add_controller(drag)
        self.drag_origin = (0, 0)
        self.drag_count = self.drag_updates = 0

    def do_contains(self, x, y):
        # Transparent canvas space is still a target for panning gestures.
        return 0 <= x < self.get_width() and 0 <= y < self.get_height()

    def do_measure(self, orientation, for_size):
        return (100, 560 if orientation == Gtk.Orientation.HORIZONTAL else 640, -1, -1)

    def do_size_allocate(self, width, height, baseline):
        if self.child is None:
            return
        geometry = self.model.geometry(width, height)
        point = Graphene.Point().init(geometry['stage_x'], geometry['stage_y'])
        transform = Gsk.Transform.new().translate(point).scale(geometry['scale'], geometry['scale'])
        # GTK uses this same transform for snapshotting and input picking. The
        # compositor's allocation/output stays constant when only zoom changes.
        self.child.allocate(geometry['stage_width'], geometry['stage_height'], -1, transform)

    def do_snapshot(self, snapshot):
        if self.child is not None:
            shadow = Gsk.Shadow()
            shadow.color = Gdk.RGBA(red=0, green=0, blue=0, alpha=0.12)
            shadow.dx, shadow.dy, shadow.radius = 0, 2, 6
            snapshot.push_shadow([shadow])
            self.snapshot_child(self.child, snapshot)
            snapshot.pop()

    def set_zoom(self, mode):
        self.model.select(mode, self.get_width(), self.get_height())
        self.queue_allocate()

    def centre(self):
        self.model.pan_x = self.model.pan_y = 0
        self.queue_allocate()

    def drag_begin(self, gesture, x, y):
        self.drag_count += 1
        geometry = self.describe()
        if (self.model.app_width*geometry['scale'] <= self.get_width()-32+1e-6 and
                self.model.app_height*geometry['scale'] <= self.get_height()-32+1e-6):
            gesture.set_state(Gtk.EventSequenceState.DENIED)
            return
        self.drag_origin = (geometry['pan_x'], geometry['pan_y'])
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    def drag_update(self, gesture, dx, dy):
        self.drag_updates += 1
        self.model.pan_x = self.drag_origin[0] + dx
        self.model.pan_y = self.drag_origin[1] + dy
        self.queue_allocate()

    def describe(self):
        data = self.model.geometry(self.get_width(), self.get_height())
        data.update(drag_count=self.drag_count, drag_updates=self.drag_updates)
        return data

    def release(self):
        if self.child is not None:
            self.child.unparent()
            self.child = None
