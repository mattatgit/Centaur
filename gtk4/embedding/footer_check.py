"""Native footer state, input and painted-geometry regressions; isolated CI UI."""
import json
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch
import gi

gi.require_version('Gtk','4.0')
gi.require_version('Gdk','4.0')
from gi.repository import Gdk,Gio,GLib,Gtk
from PIL import Image
from ui import box,margins
from update_ui import UpdateControls


def check_footer(driver,folder):
    folder.mkdir()
    Gtk.init()
    app=Gtk.Application(application_id='org.centaur.Gtk4',flags=Gio.ApplicationFlags.NON_UNIQUE); app.register()
    window=Gtk.ApplicationWindow(application=app,title='Centaur footer check',default_width=560,default_height=240,decorated=False)
    provider=Gtk.CssProvider(); provider.load_from_path(str(Path(__file__).with_name('shell.css')))
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    root=margins(box(True,24),24); entry=Gtk.Entry(); root.append(entry)
    section=box(True,16); root.append(section); footer=box(spacing=8); root.append(footer); window.set_child(root)
    owner=SimpleNamespace(update_session=None,version=lambda:'0.4.0-preview+4451f19',targets={},
                          update_footer=footer,closing=False,window=window)
    controls=UpdateControls(owner,section)
    assert 0<controls.next_check-time.monotonic()<=2,'Startup discovery schedule changed'
    controls.next_check=float('inf')
    context=GLib.MainContext.default(); window.present()
    def pump():
        while context.pending(): context.iteration(False)
    def wait(predicate,message,timeout=8):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            pump(); controls.refresh_footer()
            if predicate(): return
            time.sleep(.02)
        raise AssertionError(message)
    def settle():
        # Wait through the next frame allocation, not just the state change.
        for _ in range(12): pump(); time.sleep(.02)
    def bounds(widget):
        ok,r=widget.compute_bounds(window); assert ok
        return [round(r.get_x()),round(r.get_y()),round(r.get_width()),round(r.get_height())]
    caption=lambda:controls.footer_labels.get_visible_child()
    text=lambda:caption().get_text()
    gate=threading.Event(); evidence={}
    try:
        wait(window.get_mapped,'Footer fixture did not map')
        handle=next(n['id'] for n in driver.nodes() if n.get('app_id')=='org.centaur.Gtk4' and n.get('pid')==os.getpid())
        def hover(widget):
            x,y,w,h=bounds(widget); rect=driver.rect(handle)
            driver.ipc(f"seat seat0 cursor set {round(rect['x']+x+w/2)} {round(rect['y']+y+h/2)}")
            driver.seat_command('motion 0 0'); settle()
        def click(widget):
            x,y,w,h=bounds(widget); driver.click(handle,x+w//2,y+h//2); settle()
        entry.grab_focus(); hover(entry)
        wait(lambda:text().startswith('v0.4.'),'Idle footer did not show installed version')
        settle(); stable=[bounds(controls.footer_button),bounds(controls.footer_status)]
        evidence['idle']={'button':stable[0],'progress':stable[1],'caption':bounds(caption())}
        driver.screenshot(handle,folder/'idle.png')
        hover(controls.footer_button)
        wait(lambda:text()=='Update app','Pointer hover did not show action')
        settle(); painted=bounds(caption()); evidence['hover']={'caption':painted,'button':bounds(controls.footer_button)}
        assert [bounds(controls.footer_button),bounds(controls.footer_status)]==stable,'Hover shifted footer layout'
        assert painted[2]<stable[0][2]-24,'Action highlight still uses version width'
        assert abs(painted[2]-(caption().get_layout().get_pixel_size()[0]+16))<=1,'Action does not have 8px horizontal padding'
        driver.screenshot(handle,folder/'hover.png')
        with Image.open(folder/'hover.png') as source:
            pixels=source.convert('RGB'); x,y,w,h=painted
            assert pixels.getpixel((x+4,y+h//2))==(235,235,235),'Hover grey fill missing'
            assert pixels.getpixel((x,y))!=(235,235,235),'Hover corners are square'
            assert pixels.getpixel((x+w+4,y+h//2))!=(235,235,235),'Grey highlight extends into reserved version space'
        # Real click, real asynchronous checked_result; only discovery is doubled.
        def no_update(*args): gate.wait(10); return None
        with patch('update_ui.check_update',side_effect=no_update):
            click(controls.footer_button)
            wait(lambda:controls.checking,'Footer click did not check')
            assert 898<controls.next_check-time.monotonic()<=900,'Periodic discovery schedule changed'
            gate.set()
            wait(lambda:not controls.checking and controls.footer_status.get_text()=='Up to date','No-update feedback missing')
        settle()
        assert controls.footer_hovered and text()=='v'+owner.version(),'Stationary pointer hid checked version'
        driver.screenshot(handle,folder/'checked-no-update.png')
        wait(lambda:controls.footer_status.get_text()=='','No-update notice did not expire',timeout=5)
        assert text()=='v'+owner.version(),'Expired notice rearmed a stationary pointer'
        assert [bounds(controls.footer_button),bounds(controls.footer_status)]==stable,'No-update result shifted layout'
        hover(entry); hover(controls.footer_button)
        wait(lambda:text()=='Update app','Pointer re-entry did not rearm action')
        # Independent keyboard traversal, activation, retained focus and re-entry.
        hover(entry); click(entry)
        for _ in range(4):
            driver.key('Tab'); settle()
            if controls.footer_focused: break
        assert controls.footer_focused and text()=='Update app','Keyboard cannot reach footer action'
        driver.screenshot(handle,folder/'keyboard-focus.png')
        with patch('update_ui.check_update',return_value=None):
            driver.key('Return')
            wait(lambda:controls.footer_status.get_text()=='Up to date','Keyboard activation did not check')
        assert controls.footer_focused and text()=='v'+owner.version(),'Retained focus hid checked version'
        driver.key('Tab'); settle(); driver.key('Shift+Tab'); settle()
        assert controls.footer_focused and text()=='Update app','Focus re-entry did not rearm action'
        hover(entry); click(entry)
        controls.checked_result({'version':'Centaur GTK4 0.4.0-preview+abcdef0'},None); settle()
        assert text()=='Update available' and controls.badge.get_visible(),'Background discovery did not show availability'
        assert bounds(controls.badge)[2:]==[8,8],'Availability badge is not 8px'
        assert [bounds(controls.footer_button),bounds(controls.footer_status)]==stable,'Availability shifted footer layout'
        driver.screenshot(handle,folder/'available.png')
        controls.work=folder; controls.set_sensitive(False); controls.status.set_text('Downloaded 2.1 of 16.5 MB'); controls.refresh_footer(); settle()
        assert text()=='Updating…' and controls.footer_status.get_text()=='Downloaded 2.1 of 16.5 MB'
        assert not controls.badge.get_visible() and not controls.footer_button.get_sensitive()
        driver.screenshot(handle,folder/'updating.png')
        controls.work=None; controls.manifest=None; controls.footer_feedback=False; controls.set_sensitive(True); controls.refresh_footer(); settle()
        assert text()=='v'+owner.version() and not controls.badge.get_visible(),'Completed transaction retained stale availability'
        evidence['passed']=True
        (folder/'geometry.json').write_text(json.dumps(evidence,indent=2))
    finally:
        gate.set(); window.destroy(); pump()
