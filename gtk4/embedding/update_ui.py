"""Small Settings surface; the detached updater owns installation and recovery."""
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid
from gi.repository import GLib, Gtk, Pango
from ui import ASSETS,box,button,button_text,label,accessible,picture
from v2_ui import UpdateIcon
from updater import (check_update,process_identity,profile_path,read_json,state_path,write_json)
from download_progress import progress_message


class UpdateControls:
    def __init__(self,owner,section):
        self.owner=owner; self.manifest=None; self.checking=False; self.checked=False
        self.work=None; self.process=None; self.handed_off=False; self.ready_written=False; self.restored=False
        self.install_after_check=False
        self.check_focus=None
        self.footer_feedback=False; self.footer_hovered=False; self.footer_focused=False
        self.footer_hover_suppressed=False; self.footer_focus_suppressed=False
        self.footer_notice_until=0
        self.next_check=time.monotonic()+2
        self.completed=False; self.confirmation=None
        self.starting=bool(os.environ.get('CENTAUR_UPDATE_STARTING'))
        self.resume=read_json(owner.update_session/'resume.json') if owner.update_session else {}
        self.restore_page_pending=bool(owner.update_session)
        self.version=label('Centaur v'+owner.version(),'small muted'); section.append(self.version)
        row=box(spacing=16)
        self.button=button('Update app',self.clicked); self.button.set_halign(Gtk.Align.START)
        row.append(self.button); self.status=label('','small muted',True); self.status.set_hexpand(True); row.append(self.status)
        section.append(row)
        owner.targets['update-app']=self.button
        self.build_footer()
        self.set_sensitive(not self.starting)
        if owner.update_session:
            self.work=owner.update_session
            self.status.set_text(read_json(self.work/'status.json').get('message','Starting the updated app…'))

    def build_footer(self):
        owner=self.owner
        self.footer_button=Gtk.Button(css_classes=['update-icon'],width_request=16,height_request=24,valign=Gtk.Align.CENTER)
        self.footer_button.set_cursor_from_name('pointer')
        accessible(self.footer_button,'Update app · v'+owner.version())
        self.icon=UpdateIcon(); self.footer_button.set_child(self.icon)
        left=box(spacing=8); left.set_hexpand(True); left.append(self.footer_button)
        captions=box(True,0); captions.set_hexpand(True); captions.set_valign(Gtk.Align.CENTER)
        self.footer_labels=Gtk.Stack(hhomogeneous=False,vhomogeneous=True)
        for name,text in [('disabled',''),('available','Update available'),('updating','Updating…'),('complete','Complete')]:
            caption=label(text,'update-caption',True); caption.set_halign(Gtk.Align.START)
            self.footer_labels.add_named(caption,name)
        self.footer_labels.set_visible_child_name('disabled'); captions.append(self.footer_labels)
        self.footer_button.connect('clicked',lambda b:self.clicked())
        motion=Gtk.EventControllerMotion()
        motion.connect('enter',lambda c,x,y:self.footer_state(hovered=True))
        motion.connect('leave',lambda c:self.footer_state(hovered=False)); self.footer_button.add_controller(motion)
        # Observe the window's final focus location. Controller crossing signals
        # can arrive before GtkWindow has finished transferring focus.
        owner.window.connect('notify::focus-widget',lambda w,p:GLib.idle_add(self.sync_footer_focus))
        self.footer_status=label('','version muted',True); self.footer_status.set_hexpand(True)
        self.footer_status.set_lines(2); self.footer_status.set_ellipsize(Pango.EllipsizeMode.END)
        self.footer_status.set_width_chars(1); captions.append(self.footer_status); left.append(captions)
        self.footer_version=label('v'+owner.version(),'version-chip'); self.footer_version.set_valign(Gtk.Align.CENTER)
        owner.update_footer.append(left); owner.update_footer.append(self.footer_version)
        owner.targets.update({'update-footer':owner.update_footer,'update-version':self.footer_button,
                              'update-icon':self.footer_button,'update-art':self.icon,
                              'version-chip':self.footer_version,'update-progress':self.footer_status})

    def footer_state(self,hovered=None,focused=None):
        if hovered is not None:
            self.footer_hovered=hovered
            if not hovered: self.footer_hover_suppressed=False
        if focused is not None:
            self.footer_focused=focused
            if not focused: self.footer_focus_suppressed=False
        self.refresh_footer()

    def sync_footer_focus(self):
        focus=self.owner.window.get_focus()
        self.footer_state(focused=bool(focus and (focus==self.footer_button or focus.is_ancestor(self.footer_button))))
        return False

    def set_sensitive(self,value):
        self.button.set_sensitive(value); self.footer_button.set_sensitive(bool(value and self.manifest))

    def reset_footer_action(self):
        focus=self.owner.window.get_focus()
        self.footer_focused=bool(focus and (focus==self.footer_button or focus.is_ancestor(self.footer_button)))
        self.footer_hover_suppressed=self.footer_hovered
        self.footer_focus_suppressed=self.footer_focused

    def refresh_footer(self):
        busy=bool(self.work or self.process or self.starting)
        name='updating' if busy else 'available' if self.manifest else 'complete' if self.completed else 'disabled'
        self.icon.set_state(name)
        self.footer_labels.set_visible_child_name(name)
        self.owner.targets['update-caption']=self.footer_labels.get_visible_child()
        message=self.status.get_text() if self.checking or busy or self.footer_feedback else ''
        if not message and time.monotonic()<self.footer_notice_until: message='Up to date'
        self.footer_status.set_text(message); self.footer_status.set_visible(bool(message))
        accessible(self.footer_status,'Update status',message or '')
        accessible(self.footer_button,{'available':'Update available','updating':'Updating Centaur','complete':'Update complete','disabled':'No update available'}[name],
                   'Installed version '+self.owner.version())
        self.footer_button.set_sensitive(bool(self.manifest and not busy and not self.checking))
        accessible(self.button,'Update app' if self.manifest else 'Check for updates')
        button_text(self.button,'Update app' if self.manifest else 'Check for updates')

    def check(self,install=False):
        if self.checking or self.process or self.starting or self.work: return
        focus=self.owner.window.get_focus()
        self.check_focus=focus if focus in (self.button,self.footer_button) else None
        self.checked=True; self.checking=True; self.status.set_text('Checking for updates…'); self.set_sensitive(False)
        self.next_check=time.monotonic()+900
        self.install_after_check=install
        self.footer_notice_until=0
        self.refresh_footer()
        def worker():
            try:
                if os.uname().sysname!='Linux' or os.uname().machine not in ('aarch64','arm64'):
                    raise RuntimeError('Updates are available on ARM64 NixOS.')
                manifest=check_update(os.environ.get('CENTAUR_GTK4_BUILD_ID','dev'),int(os.environ.get('CENTAUR_GTK4_SOURCE_TIME','0')))
                GLib.idle_add(self.checked_result,manifest,None)
            except Exception as error: GLib.idle_add(self.checked_result,None,str(error))
        threading.Thread(target=worker,daemon=True).start()

    def checked_result(self,manifest,error):
        if self.owner.closing: return False
        self.checking=False; self.manifest=manifest
        install=self.install_after_check; self.install_after_check=False
        self.footer_notice_until=0
        self.footer_feedback=bool(error)
        self.status.set_text(error or ('Update available · '+manifest['version'].removeprefix('Centaur GTK4 ') if manifest else 'You’re up to date.'))
        accessible(self.button,'Update available' if manifest else 'Check for updates')
        self.set_sensitive(True)
        # Disabling GtkButton clears keyboard focus. Restore the initiating
        # entry point only if the user has not focused another control meanwhile.
        if self.check_focus and self.owner.window.get_focus() is None: self.check_focus.grab_focus()
        self.check_focus=None
        if install and not manifest and not error:
            # Keep the result visible under a stationary pointer/retained focus.
            # Each input source rearms independently after leaving the control.
            self.reset_footer_action()
            self.footer_notice_until=time.monotonic()+3
        self.refresh_footer()
        if install and manifest: self.clicked()
        return False

    def clicked(self):
        if self.checking or self.process or self.starting or self.work: return
        self.footer_notice_until=0
        if not self.manifest: self.check(install=True); return
        if self.confirmation and self.confirmation.get_visible(): return
        owner=self.owner; manifest=dict(self.manifest)
        dialog,card=owner.dialog('Restart Centaur to update?',288); self.confirmation=dialog
        owner.clear(card); card.add_css_class('restart-dialog'); card.set_spacing(0); card.set_overflow(Gtk.Overflow.HIDDEN)
        hero=Gtk.Overlay(css_classes=['restart-hero']); hero.set_size_request(-1,128); hero.set_child(box())
        clay=picture(ASSETS/'v2/dc3c7.png',72); clay.set_halign(Gtk.Align.CENTER); clay.set_valign(Gtk.Align.CENTER)
        hero.add_overlay(clay); card.append(hero)
        title=label('Restart Centaur to update?','dialog-title',True); title.set_xalign(.5)
        title.set_size_request(-1,21); title.set_margin_top(25); card.append(title)
        text=label('Centaur will restart after downloading,\nare you ready to update?','restart-description',True)
        text.set_xalign(.5); text.set_justify(Gtk.Justification.CENTER); text.set_size_request(-1,44); text.set_margin_top(4); card.append(text)
        row=box(spacing=16); row.set_margin_top(10); row.set_margin_bottom(24); row.set_margin_start(24); row.set_margin_end(24); card.append(row)
        cancel=button('Not now',lambda:owner.dismiss_dialog(dialog),tone='soft',width=112); row.append(cancel)
        def confirmed():
            owner.dismiss_dialog(dialog)
            self.start_update(manifest)
        confirm=button('Yes, update',confirmed,tone='dark',width=112); row.append(confirm)
        dialog.on_close=lambda:setattr(self,'confirmation',None)
        owner.targets.update({'update-cancel':cancel,'update-confirm':confirm,'update-confirmation-clay':clay})
        dialog.present(); cancel.grab_focus()

    def start_update(self,manifest):
        if self.checking or self.process or self.starting or self.work: return
        self.footer_feedback=True; self.completed=False
        if self.blocked(): self.status.set_text('Finish the current work before updating.'); self.refresh_footer(); return
        owner=self.owner
        try:
            base=state_path(); base.mkdir(parents=True,exist_ok=True,mode=0o700)
            self.work=base/('run-'+uuid.uuid4().hex); self.work.mkdir(mode=0o700)
            package=os.environ['CENTAUR_GTK_PACKAGE']
            write_json(self.work/'manifest.json',manifest)
            write_json(self.work/'request.json',{'dataDir':str(owner.root),'package':package,
                       'parentPid':os.getpid(),'parentIdentity':process_identity(os.getpid()),
                       'reportDir':str(owner.reports) if owner.reports else None,
                       'omp':os.environ.get('CENTAUR_AGENT') or owner.data.get('agentExecutable','')})
            write_json(self.work/'status.json',{'phase':'starting','message':'Preparing the update…'})
            with (self.work/'helper.log').open('a') as log:
                self.process=subprocess.Popen([package+'/bin/centaur-gtk4-update','--transaction',str(self.work)],
                                              stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                                              start_new_session=True,close_fds=True)
            self.status.set_text('Preparing the update…'); self.set_sensitive(False); self.refresh_footer()
        except Exception as error:
            self.process=None; self.work=None; self.status.set_text('Could not start the updater. '+str(error)); self.set_sensitive(True); self.refresh_footer()

    def blocked(self):
        owner=self.owner
        buffer=owner.editor.get_buffer()
        return bool(owner.data.get('updateBlocked') or owner.data.get('busy') or owner.data.get('joining') or
                    owner.data.get('inviting') or owner.pending_message or owner.points or owner.active_form or
                    getattr(getattr(owner,'comment',None),'phase','idle')!='idle' or
                    not owner.data.get('connected') or owner.project.get('queueCount'))

    def restore(self):
        owner=self.owner
        if not owner.update_session or not owner.data.get('connected') or not owner.data.get('snapshotReady'): return
        if self.restored:
            if self.restore_page_pending and (not self.resume.get('projectId') or owner.project.get('id')==self.resume['projectId']):
                self.restore_page_pending=False; owner.navigate(self.resume.get('page','settings'))
            return
        resume=self.resume
        owner.drafts=resume.get('drafts',{})
        project=resume.get('projectId')
        if project and not any(p['id']==project for p in owner.data.get('projects',[])): return
        self.restored=True
        if project: owner.open_project(project)
        owner.navigate(resume.get('page','settings'))
        if not project: self.restore_page_pending=False

    def tick(self):
        self._tick()
        self.refresh_footer()

    def _tick(self):
        owner=self.owner
        if time.monotonic()>=self.next_check and not (self.checking or self.process or self.starting): self.check()
        expected=self.resume.get('projectId')
        if (owner.update_session and not self.ready_written and self.restored and owner.window.get_mapped()
            and owner.data.get('connected') and owner.data.get('snapshotReady')
            and (not expected or owner.project.get('id')==expected)):
            self.ready_written=True
            write_json(owner.update_session/'ready.json',{'pid':os.getpid(),'buildId':os.environ.get('CENTAUR_GTK4_BUILD_ID','dev'),'connected':True})
        if not self.work: return
        value=read_json(self.work/'status.json'); phase=value.get('phase')
        if self.starting:
            owner.root_overlay.get_child().set_sensitive(False)
            if self.ready_written and not owner.data.get('updateHeld'):
                self.starting=False; owner.root_overlay.get_child().set_sensitive(True)
                if phase=='restarting': self.status.set_text('Centaur updated.')
        if value.get('message'):
            message=value['message']
            if phase=='verifying' and value.get('downloadBytes',0)>0:
                message=progress_message(value['downloadBytes'],value.get('totalBytes'))+' · Verifying…'
            self.status.set_text(message)
        if self.process and phase=='ready' and not self.handed_off:
            if self.blocked(): self.status.set_text('Update downloaded. Waiting for the current work to finish…'); return
            self.handed_off=True
            buffer=owner.editor.get_buffer(); drafts=dict(owner.drafts)
            if owner.project: drafts[owner.project['id']]=buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),False)
            write_json(self.work/'approve.json',{'approved':True,'resume':{'projectId':owner.project.get('id'),'drafts':drafts,'page':owner.page}})
            owner.quit()
        elif self.process and self.process.poll() is not None:
            if phase not in ('failed','recovered','complete'): self.status.set_text('The update stopped. Your installed version is preserved.')
            if phase=='complete': self.completed=True; self.manifest=None; self.footer_feedback=False
            self.process=None; self.set_sensitive(True); self.work=None
        elif not self.process and phase in ('complete','recovered','failed','recovery-required'):
            self.completed=phase=='complete'
            if self.completed: self.manifest=None; self.footer_feedback=False
            self.work=None; self.set_sensitive(True); self.reset_footer_action()

