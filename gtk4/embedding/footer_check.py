"""Native updater artwork, real input, confirmation and lifecycle presentation."""
import json,os,time,threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import gi
gi.require_version('Gtk','4.0');gi.require_version('Gdk','4.0')
from gi.repository import Gdk,Gio,GLib,Gtk
from PIL import Image
from ui import box,margins,Modal
from update_ui import UpdateControls
from updater import write_json


def check_footer(driver,folder):
    folder.mkdir();Gtk.init()
    app=Gtk.Application(application_id='org.centaur.Gtk4',flags=Gio.ApplicationFlags.NON_UNIQUE);app.register()
    window=Gtk.ApplicationWindow(application=app,title='Centaur updater presentation check',default_width=560,default_height=480,decorated=False)
    provider=Gtk.CssProvider();provider.load_from_path(str(Path(__file__).with_name('shell.css')))
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    overlay=Gtk.Overlay();root=margins(box(True,24),24);overlay.set_child(root);window.set_child(overlay)
    entry=Gtk.Entry();root.append(entry);section=box(True,16);root.append(section);footer=box(spacing=8);footer.set_size_request(-1,48);root.append(footer)
    owner=SimpleNamespace(update_session=None,version=lambda:'0.4.0-preview+4451f19',targets={},update_footer=footer,
        closing=False,window=window,root_overlay=overlay,top=Gtk.Box(),active_form=None)
    def dismiss(dialog):
        dialog.destroy()
        if owner.active_form is dialog:owner.active_form=None
    def dialog(title,width):
        value=Modal(owner,title,width);owner.active_form=value
        content=box(True,0,'dialog-card');value.set_child(content);owner.targets['dialog-card']=content
        return value,content
    def clear(widget):
        while widget.get_first_child():widget.remove(widget.get_first_child())
    owner.dialog=dialog;owner.dismiss_dialog=dismiss;owner.clear=clear
    controls=UpdateControls(owner,section);assert 0<controls.next_check-time.monotonic()<=2
    controls.next_check=float('inf');context=GLib.MainContext.default();window.present()
    evidence={'checks':[]};handle=None;gate=threading.Event();started=[]
    def pump():
        while context.pending():context.iteration(False)
        controls.refresh_footer()
    def settle(seconds=.2):
        end=time.monotonic()+seconds
        while time.monotonic()<end:pump();time.sleep(.01)
    def wait(test,message,seconds=8):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            pump()
            if test():return
            time.sleep(.02)
        raise AssertionError(message)
    def bounds(widget):
        ok,r=widget.compute_bounds(window);assert ok
        return list(map(round,(r.get_x(),r.get_y(),r.get_width(),r.get_height())))
    def click(widget):
        x,y,w,h=bounds(widget);driver.click(handle,x+w//2,y+h//2);settle()
    def photo(name):driver.screenshot(handle,folder/(name+'.png'))
    try:
        wait(window.get_mapped,'Updater fixture did not map');handle=driver.find_window('org.centaur.Gtk4',os.getpid());settle()
        stable=[bounds(controls.footer_button),bounds(controls.footer_version)]
        assert bounds(controls.icon)[2:]==[16,16] and not controls.footer_button.get_sensitive()
        assert controls.icon.state=='disabled' and controls.footer_version.get_text()=='V0.4 4451f19'
        assert controls.version.get_text()=='Centaur V0.4 4451f19'
        photo('disabled');click(controls.footer_button);assert owner.active_form is None and not controls.work
        evidence['checks'].append('original-disabled-16px-download-art-and-static-right-version-chip')
        # A late background discovery result must not move the user's focus.
        entry.grab_focus();settle();focus=window.get_focus()
        manifest={'version':'Centaur GTK4 0.4.0-preview+abcdef0','sourceRevision':'a'*40}
        def discovery(*args):gate.wait(8);return manifest
        with patch('update_ui.check_update',side_effect=discovery):
            controls.check();wait(lambda:controls.checking,'Discovery did not start')
            assert 898<controls.next_check-time.monotonic()<=900;gate.set()
            wait(lambda:not controls.checking,'Discovery did not finish')
        assert window.get_focus()==focus and controls.icon.state=='available' and owner.active_form is None
        assert [bounds(controls.footer_button),bounds(controls.footer_version)]==stable
        photo('available');evidence['checks'].append('real-background-check-schedule-no-focus-theft-stable-geometry')
        with patch.object(controls,'start_update',side_effect=lambda m:started.append(m)):
            for endpoint in (controls.button,controls.footer_button):
                click(endpoint);assert controls.confirmation and controls.confirmation.get_visible()
                assert not started and controls.work is None,'Update started before confirmation'
                photo('settings-warning' if endpoint==controls.button else 'footer-warning')
                click(owner.targets['update-cancel']);assert owner.active_form is None and not started
            # Reach the available footer with physical keyboard traversal.
            entry.grab_focus();settle()
            for _ in range(6):
                driver.key('Tab');settle(.08)
                if controls.footer_focused:break
            assert controls.footer_focused,'Keyboard cannot reach the update icon'
            driver.key('Return');wait(lambda:bool(controls.confirmation),'Keyboard did not open restart warning')
            click(owner.targets['update-confirm']);assert len(started)==1 and started[0]==manifest
            click(controls.button);assert len(started)==1
            click(owner.targets['update-confirm']);assert len(started)==2 and started[1]==manifest
        evidence['checks'].append('both-entry-points-cancel-and-confirm-keyboard-no-download-before-consent')
        work=folder/'transaction';work.mkdir();controls.work=work
        for downloaded in (0,2_100_000,8_400_000):
            write_json(work/'status.json',{'phase':'downloading','message':'Downloaded 0.0 of 16.5 MB',
                                          'downloadBytes':downloaded,'totalBytes':16_500_000})
            controls.tick();settle(.06)
            expected=f'Downloaded {downloaded/1_000_000:.1f} of 16.5 MB'
            assert controls.status.get_text()==controls.footer_status.get_text()==expected
        evidence['checks'].append('footer-and-settings-use-advancing-byte-count-even-with-stale-status-text')
        for phase in ('starting','downloading','verifying','ready'):
            write_json(work/'status.json',{'phase':phase,'message':'Downloaded 2.1 of 16.5 MB'})
            controls.tick();settle(.06)
            assert controls.icon.state=='updating' and not controls.footer_button.get_sensitive()
        frames=[];centres=[]
        for i in range(5):
            settle(.11);photo('progress-'+str(i));x,y,w,h=bounds(controls.icon)
            with Image.open(folder/('progress-'+str(i)+'.png')) as im:
                crop=im.convert('RGB').crop((x,y,x+w,y+h));frames.append(crop.tobytes());centres.append(crop.crop((6,5,10,11)).tobytes())
        assert controls.icon.tick is not None and len(set(frames))>2,'Circular progress stroke did not move'
        assert len(set(centres))==1,'The arrow rotated with the circular stroke'
        settings=controls.icon.settings;prop=controls.icon.motion_property;previous=settings.get_property(prop)
        try:
            settings.set_property(prop,Gtk.ReducedMotion.REDUCE if prop=='gtk-interface-reduced-motion' else False);settle()
            assert controls.icon.tick is None and controls.icon.state=='updating';photo('progress-reduced-motion')
        finally:settings.set_property(prop,previous)
        evidence['checks'].append('original-named-stroke-rotates-arrow-stays-still-reduced-motion')
        # Failed and intermediate helper phases cannot manufacture completion.
        write_json(work/'status.json',{'phase':'failed','message':'Disposable failure'});controls.tick();settle()
        assert controls.icon.state!='complete' and not controls.completion_waiting and not controls.completion_until
        photo('failure')
        controls.origin_page='workspace'
        controls.work=work;write_json(work/'status.json',{'phase':'complete','message':'Centaur updated.'});controls.tick();settle()
        assert controls.icon.state=='complete' and not controls.footer_button.get_sensitive();photo('complete')
        assert [bounds(controls.footer_button),bounds(controls.footer_version)]==stable
        evidence['checks'].append('complete-checkmark-only-after-real-helper-complete-phase')
        with patch('update_ui.time.monotonic',return_value=controls.completion_until):
            controls.refresh_footer()
        assert controls.icon.state=='disabled' and controls.icon.filename.endswith('/418fd.svg')
        controls.origin_page='settings'
        controls.work=work
        owner.page='settings'
        # Keep the simulated receipt in the past when returning to the runner's
        # real clock, including on a freshly booted machine.
        first_edit=time.monotonic()-10
        with patch('update_ui.time.monotonic',return_value=max(0,first_edit-30)):
            controls.tick()
        assert controls.completion_waiting and controls.icon.state=='disabled'
        owner.page='workspace'
        with patch('update_ui.time.monotonic',return_value=first_edit):
            controls.refresh_footer()
        assert controls.completion_until==first_edit+5 and controls.icon.state=='complete'
        owner.page='projects'
        with patch('update_ui.time.monotonic',return_value=first_edit+1):
            controls.refresh_footer()
        owner.page='workspace'
        with patch('update_ui.time.monotonic',return_value=first_edit+4):
            controls.refresh_footer()
        assert controls.completion_until==first_edit+5 and not controls.completion_waiting
        with patch('update_ui.time.monotonic',return_value=first_edit+5):
            controls.refresh_footer()
        assert controls.icon.state=='disabled'
        evidence['checks'].append('settings-receipt-awaits-first-edit-and-keeps-original-deadline-across-navigation')
        with patch('update_ui.check_update',return_value=None):
            click(controls.button)
            wait(lambda:controls.footer_status.get_text()=='Up to date','No-update notice did not appear')
        assert controls.icon.state=='disabled' and controls.work is None and owner.active_form is None
        photo('up-to-date')
        with patch('update_ui.time.monotonic',return_value=controls.footer_notice_until):
            controls.refresh_footer()
        assert controls.footer_status.get_text()=='' and controls.footer_version.get_text()=='V0.4 4451f19'
        evidence['checks'].append('no-update-notice-expires-without-changing-version-or-starting-download')
        evidence.update(passed=True,icon=bounds(controls.icon),button=stable[0],versionChip=stable[1],confirmationCount=len(started))
    finally:
        if owner.active_form:dismiss(owner.active_form)
        gate.set();(folder/'geometry.json').write_text(json.dumps(evidence,indent=2)+'\n')
        window.destroy();pump()
