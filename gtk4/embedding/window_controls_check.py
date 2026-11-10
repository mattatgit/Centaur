"""Native CSD regression in the disposable ARM64 Wayland display.

Uses GTK's automatically installed titlebar, never a replacement headerbar.
GNOME's compositor states still require the separate VM acceptance pass.
"""
import json
import os
from pathlib import Path
import time
# PyGObject can initialise GTK while importing its overrides.
# GNOME leaves decorations to GTK; emulate that in this CI process only.
os.environ['GDK_WAYLAND_DISABLE'] = 'org_kde_kwin_server_decoration_manager,zxdg_decoration_manager_v1'
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gio, GLib, Gtk
from PIL import Image
from check import until


def check_window_controls(driver, folder):
    folder.mkdir()
    Gtk.init()
    settings = Gtk.Settings.get_default()
    original_layout = settings.get_property('gtk-decoration-layout')
    settings.set_property('gtk-decoration-layout', ':close')
    app = Gtk.Application(application_id='org.centaur.Gtk4', flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.register()
    provider = Gtk.CssProvider()
    provider.load_from_path(str(Path(__file__).with_name('shell.css')))
    display = Gdk.Display.get_default()
    Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    window = Gtk.ApplicationWindow(application=app, title='Centaur', default_width=704, default_height=400, decorated=True)
    content = Gtk.Label(label='Native Centaur window controls')
    window.set_child(content)
    context = GLib.MainContext.default()

    def settle(seconds=.25):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            while context.pending(): context.iteration(False)
            time.sleep(.005)

    def walk(widget):
        yield widget
        child = widget.get_first_child()
        while child:
            yield from walk(child)
            child = child.get_next_sibling()

    def bounds(widget):
        ok, rect = widget.compute_bounds(window)
        assert ok
        return [round(rect.get_x(), 2), round(rect.get_y(), 2), round(rect.get_width(), 2), round(rect.get_height(), 2)]

    def controls():
        return {name: next(w for w in walk(window) if isinstance(w, Gtk.Button) and w.has_css_class(name))
                for name in ('close',)}

    def geometry():
        header = next(w for w in walk(window) if w.get_css_name() == 'headerbar')
        button = controls()['close']
        return {'header': bounds(header), 'content': bounds(content), 'button': bounds(button),
                'image': bounds(button.get_child()), 'icon': button.get_child().get_icon_name(),
                'action': button.get_action_name(), 'canFocus': button.get_can_focus()}

    report = {'compositor': 'disposable Sway; GNOME visual acceptance pending', 'checks': []}
    closed = []
    allow_close = [False]
    window.connect('close-request', lambda *_: closed.append(True) or not allow_close[0])
    pointer = []
    motion = Gtk.EventControllerMotion()
    motion.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
    motion.connect('motion', lambda _controller, x, y: pointer.append((x, y)))
    window.add_controller(motion)
    window.present()
    try:
        settle(.5)
        handle = driver.find_window('org.centaur.Gtk4', os.getpid())
        driver.ipc(f'[con_id={handle}] move position 100 px 100 px')
        settle()
        baseline = geometry()
        driver.screenshot(handle, folder/'baseline.png', focus=False)
        window.add_css_class('centaur-window')
        settle()
        current = geometry()
        driver.screenshot(handle, folder/'styled.png', focus=False)
        report.update(baseline=baseline, styled=current)
        (folder/'metrics.json').write_text(json.dumps(report, indent=2))
        assert baseline['header'] == current['header'], (baseline, current)
        assert baseline['content'] == current['content'], (baseline, current)
        assert current['button'][2:] == [32, 32], current
        assert current['image'][2:] == [24, 24], current
        hx, hy, hw, hh = current['header']
        ix, iy, iw, ih = current['image']
        assert iy-hy == 8 and hx+hw-ix-iw == 8, current
        assert current['icon'] == 'window-close-symbolic' and current['action'] == 'window.close', current
        assert baseline['canFocus'] == current['canFocus'], 'Native focus policy changed'
        report['checks'].append('24px-image-32px-target-8px-insets-unchanged-titlebar-content-native-icon-and-action')

        # Calibrate root-widget versus compositor client coordinates: GTK CSD
        # shadows are outside the visible header and vary with compositor state.
        r = driver.rect(handle)
        driver.ipc(f"seat seat0 cursor set {r['x']+200} {r['y']+150}")
        driver.seat_command('motion 0 0')
        settle()
        assert pointer, 'No native pointer motion in decorated window'
        offset = (200-pointer[-1][0], 150-pointer[-1][1])
        report['pointerOffset'] = offset

        def move(x, y):
            r = driver.rect(handle)
            driver.ipc(f"seat seat0 cursor set {round(r['x']+x+offset[0])} {round(r['y']+y+offset[1])}")
            driver.seat_command('motion 0 0')
            settle()

        def capture(name):
            settle()
            driver.screenshot(handle, folder/(name+'.png'), focus=False)

        move(hx+32, hy+hh+32)
        capture('normal')
        move(ix+12, iy+12)
        assert controls()['close'].get_state_flags() & Gtk.StateFlags.PRELIGHT
        capture('hover')
        with Image.open(folder/'hover.png') as source:
            pixels = source.convert('RGB')
            x, y = round(ix+offset[0]), round(iy+offset[1])
            tile = pixels.crop((x, y, x+24, y+24))
            grey = [(a,b) for b in range(24) for a in range(24) if tile.getpixel((a,b)) == (235,235,235)]
            assert grey and (min(a for a,b in grey), min(b for a,b in grey), max(a for a,b in grey), max(b for a,b in grey)) == (0,0,23,23), 'Hover is not 24px'
            assert tile.getpixel((0,0)) == (248,248,248), 'Hover corners are not rounded'
            assert pixels.getpixel((x-2,y+12)) == (248,248,248), 'Original circle/parent hover remains'
        driver.seat_command('left press'); settle(); capture('pressed')
        assert controls()['close'].get_state_flags() & Gtk.StateFlags.ACTIVE
        driver.seat_command('left release'); settle()
        report['checks'].append('native-pointer-hover-pressed-and-no-underlying-circular-fill')

        # Every edge and corner of the larger target must close via GTK's
        # original window.close action, including outside the visible image.
        bx, by, bw, bh = current['button']
        for x,y in ((1,1),(16,1),(30,1),(1,16),(30,16),(1,30),(16,30),(30,30)):
            before = len(closed)
            move(bx+x, by+y)
            driver.seat_command('left press'); settle(.04)
            driver.seat_command('left release'); settle()
            assert len(closed) == before+1, ('Native close target missed', x, y, report)
        report['checks'].append('eight-outer-target-points-activate-native-close')
        button = controls()['close']
        button.set_sensitive(False); settle(); capture('disabled')
        before = len(closed)
        move(ix+12, iy+12)
        driver.seat_command('left press'); driver.seat_command('left release'); settle()
        assert len(closed) == before
        button.set_sensitive(True)
        move(hx+32, hy+hh+32)
        button.set_state_flags(Gtk.StateFlags.FOCUS_VISIBLE, False); settle(); capture('focus-visible-synthetic')
        button.unset_state_flags(Gtk.StateFlags.FOCUS_VISIBLE)
        report['checks'].append('disabled-does-not-close-native-focus-policy-and-synthetic-focus-visible')

        before = driver.rect(handle)
        move(hx+100, hy+16)
        driver.seat_command('left press'); settle(.05)
        for _ in range(5):
            driver.seat_command('motion 8 6.4'); settle(.03)
        driver.seat_command('left release'); settle()
        after = driver.rect(handle)
        assert (before['x'], before['y']) != (after['x'], after['y']), 'Native titlebar drag failed'
        driver.resize(handle, 800, 480); settle()
        assert geometry()['header'][2] > current['header'][2], 'Native resize failed'
        driver.ipc(f'[con_id={handle}] floating disable'); settle(); capture('tiled')
        report['tiledState'] = int(window.get_surface().get_state())
        driver.ipc(f'[con_id={handle}] floating enable'); settle()
        window.fullscreen(); settle(); capture('fullscreen')
        assert window.is_fullscreen()
        window.unfullscreen(); settle()
        assert controls()['close'].get_mapped(), 'Native controls did not return after fullscreen'
        report['checks'].append('native-titlebar-drag-compositor-resize-tile-fullscreen-and-restore')

        # Compare an unscoped native window: Centaur selectors cannot affect it.
        other = Gtk.ApplicationWindow(application=app, title='Unscoped native window', default_width=400, default_height=240, decorated=True)
        other.present(); settle(); capture('inactive')
        assert not window.is_active(), 'Backdrop state was not exercised'
        other_close = next(w for w in walk(other) if isinstance(w,Gtk.Button) and w.has_css_class('close'))
        assert other_close.get_child().get_width() == baseline['image'][2], 'Unscoped control changed'
        report['checks'].append('inactive-and-unscoped-native-window-unchanged')
        other.destroy(); window.present(); settle()
        allow_close[0] = True
        window.close(); settle()
        assert not window.get_mapped(), 'Native close did not destroy the window'
        report['checks'].append('native-close-destroys-window')
    finally:
        (folder/'metrics.json').write_text(json.dumps(report, indent=2))
        window.destroy(); settle()
        settings.set_property('gtk-decoration-layout', original_layout)
        Gtk.StyleContext.remove_provider_for_display(display, provider)
