"""Native CSD regression in the disposable ARM64 Wayland display.

Uses GTK's supported WindowHandle and WindowControls with original V2 artwork.
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
from ui import box, close_art
from v2_ui import WorkingMark


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
    content = box(True,8)
    animation=WorkingMark(); animation.set_halign(Gtk.Align.CENTER); animation.set_margin_top(48)
    content.append(animation); content.append(Gtk.Label(label='Native Centaur window controls'))
    content.add_css_class('sidebar')
    clip=Gtk.Overlay(css_classes=['centaur-content']); clip.set_overflow(Gtk.Overflow.HIDDEN); clip.set_child(content)
    window.set_child(clip)
    header=Gtk.CenterBox(css_classes=['topbar']); header.set_size_request(-1,80)
    native=Gtk.WindowControls(side=Gtk.PackType.END,decoration_layout=':close')
    native.set_valign(Gtk.Align.CENTER); native.set_margin_end(24); header.set_end_widget(native)
    window.set_titlebar(Gtk.WindowHandle(child=header))
    child=native.get_first_child()
    while child:
        if isinstance(child,Gtk.Button) and child.has_css_class('close'): child.set_child(close_art())
        child=child.get_next_sibling()
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
        header = window.get_titlebar()
        button = controls()['close']
        return {'header': bounds(header), 'content': bounds(content), 'button': bounds(button),
                'image': bounds(button.get_child()), 'artwork':bounds(button.get_child().centaur_image),
                'icon': Path(button.get_child().centaur_image.filename).name,
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
        assert current['image'][2:] == [32, 32], current
        hx, hy, hw, hh = current['header']
        ix, iy, iw, ih = current['image']
        assert hh==80 and iy-hy == 24 and hx+hw-ix-iw == 24, current
        assert current['icon'] == '78a93.svg' and current['action'] == 'window.close', current
        assert baseline['canFocus'] == current['canFocus'], 'Native focus policy changed'
        report['checks'].append('original-v2-32px-artwork-integrated-80px-header-native-close-action')

        # Calibrate root-widget versus compositor client coordinates: GTK CSD
        # shadows are outside the visible header and vary with compositor state.
        r = driver.rect(handle)
        driver.ipc(f"seat seat0 cursor set {r['x']+200} {r['y']+150}")
        driver.seat_command('motion 0 0')
        settle()
        assert pointer, 'No native pointer motion in decorated window'
        offset = (200-pointer[-1][0], 150-pointer[-1][1])
        report['pointerOffset'] = offset

        animation.phase(0); settle(); driver.screenshot(handle,folder/'working-frame-one.png',focus=False)
        animation.phase(.5); settle(); driver.screenshot(handle,folder/'working-frame-two.png',focus=False)
        ax,ay,aw,ah=bounds(animation); assert (aw,ah)==(32,32)
        crops=[]
        for name in ('working-frame-one','working-frame-two'):
            with Image.open(folder/(name+'.png')) as source:
                crop=source.convert('RGB').crop((round(ax+offset[0]),round(ay+offset[1]),round(ax+offset[0]+32),round(ay+offset[1]+32)))
                assert sum(pixel==(23,178,57) for pixel in crop.getdata())>10,'Original animation frame did not render'
                crops.append(crop.tobytes())
        assert crops[0]!=crops[1],'Original animation frames are indistinguishable'
        animation.phase(.25); settle(); driver.screenshot(handle,folder/'working-midpoint.png',focus=False)
        with Image.open(folder/'working-midpoint.png') as source:
            midpoint=source.convert('RGB').crop((round(ax+offset[0]),round(ay+offset[1]),round(ax+offset[0]+32),round(ay+offset[1]+32)))
        ends=[list(Image.frombytes('RGB',(32,32),raw).get_flattened_data()) for raw in crops]
        common=[i for i,(a,b) in enumerate(zip(*ends)) if a==b==(23,178,57)]
        middle=list(midpoint.get_flattened_data());assert len(common)>5,'No common original ink for the transition check'
        drift=max(abs(channel-expected) for i in common for channel,expected in zip(middle[i],(23,178,57)))
        assert drift<=2,('Shared animation ink flashed during the crossfade',drift)
        report['crossfade']={'commonInkPixels':len(common),'maximumChannelDrift':drift,'originalSvgUnchanged':True}
        midpoint.save(folder/'working-midpoint-crop.png')
        enabled=settings.get_property('gtk-enable-animations')
        motion=settings.get_property(animation.motion_property)
        try:
            # Reproduce GNOME's virtual-display policy: toolkit transitions
            # disabled, but no accessibility request for reduced motion.
            settings.set_property('gtk-enable-animations',False)
            settings.set_property(animation.motion_property,Gtk.ReducedMotion.NO_PREFERENCE)
            animation.set_working(True)
            samples=[]; rendered=[]; start=time.monotonic()
            for index in range(15):
                settle(.10)
                path=folder/f'working-clock-{index:02}.png'
                driver.screenshot(handle,path,focus=False)
                with Image.open(path) as source:
                    crop=source.convert('RGB').crop((round(ax+offset[0]),round(ay+offset[1]),round(ax+offset[0]+32),round(ay+offset[1]+32)))
                    rendered.append(crop.copy())
                path.unlink(); crop.save(path)
                samples.append({'seconds':round(time.monotonic()-start,3),'opacities':animation.frame_opacities})
            assert animation.tick is not None and len({c.tobytes() for c in rendered})>=3,'Frame clock did not produce visible native movement'
            assert any(s['opacities'][1]>.99 for s in samples) and any(s['opacities'][1]<.5 for s in samples),samples
            assert sum(samples[i]['opacities'][1]<samples[i-1]['opacities'][1] for i in range(1,len(samples)))>=1,'One-second animation never repeated'
            rendered[0].save(folder/'working-playback.gif',save_all=True,append_images=rendered[1:],duration=round(samples[-1]['seconds']*1000/len(rendered)),loop=0)
            report['clockPlayback']=samples
            settings.set_property(animation.motion_property,Gtk.ReducedMotion.REDUCE)
            assert animation.tick is None and animation.frame_opacities==(1,0)
            settle(.15); assert animation.frame_opacities==(1,0)
            settings.set_property(animation.motion_property,Gtk.ReducedMotion.NO_PREFERENCE)
            settle(.15); assert animation.tick is not None
            animation.set_visible(False); settle(); assert animation.tick is None
            animation.set_visible(True); settle(.15); assert animation.tick is not None
            animation.set_working(False); assert animation.tick is None and animation.frame_opacities==(1,0)
        finally:
            animation.set_working(False); settings.set_property(animation.motion_property,motion)
            settings.set_property('gtk-enable-animations',enabled)
        report['checks'].append('original-svg-visible-clock-driven-frames-one-second-loop-reduced-motion-and-map-idle-transitions')

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
        with Image.open(folder/'normal.png') as source:
            pixels=source.convert('RGB'); width,height=pixels.size
            assert pixels.getpixel((2,height-3))!=(248,248,248), 'Bottom left corner is square'
            assert pixels.getpixel((width-3,height-3))!=(248,248,248), 'Bottom right corner is square'
            assert pixels.getpixel((width//2,height-3))==(248,248,248), 'Bottom content was clipped away'
        report['checks'].append('native-rounded-bottom-corners-and-clipped-content')
        move(ix+12, iy+12)
        assert controls()['close'].get_state_flags() & Gtk.StateFlags.PRELIGHT
        capture('hover')
        with Image.open(folder/'normal.png') as normal,Image.open(folder/'hover.png') as hover:
            point=(round(ix+offset[0]+4),round(iy+offset[1]+16))
            assert normal.convert('RGB').getpixel(point)==(255,255,255),'Original default close fill differs'
            assert hover.convert('RGB').getpixel(point)==(235,235,235),'Figma close hover fill missing'
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
        assert not hasattr(other_close.get_child(),'centaur_image'), 'Centaur artwork leaked into an unscoped window'
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
