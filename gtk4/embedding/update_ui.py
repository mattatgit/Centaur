"""Small Settings surface; the detached updater owns installation and recovery."""
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid
from gi.repository import GLib, Gtk
from ui import box,button,button_text,label
from updater import (check_update,process_identity,profile_path,read_json,state_path,write_json)
from download_progress import progress_message


class UpdateControls:
    def __init__(self,owner,section):
        self.owner=owner; self.manifest=None; self.checking=False; self.checked=False
        self.work=None; self.process=None; self.handed_off=False; self.ready_written=False; self.restored=False
        self.install_after_check=False
        self.footer_feedback=False; self.footer_hovered=False; self.footer_focused=False
        self.footer_hover_suppressed=False; self.footer_focus_suppressed=False
        self.footer_notice_until=0
        self.next_check=time.monotonic()+2
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
        self.footer_button=Gtk.Button(css_classes=['update-version'],height_request=24,valign=Gtk.Align.CENTER)
        self.footer_button.set_cursor_from_name('pointer')
        self.footer_button.set_tooltip_text('Update app · v'+owner.version())
        row=box(spacing=8)
        # Reserve the largest caption's space, but paint only the natural-width
        # START-aligned label. The hit target and right-hand status never move.
        self.footer_labels=Gtk.Stack(hhomogeneous=True,vhomogeneous=True)
        for name,text in [('version','v'+owner.version()),('action','Update app'),
                          ('available','Update available'),('updating','Updating…')]:
            caption=label(text,'version update-caption'); caption.set_halign(Gtk.Align.START)
            self.footer_labels.add_named(caption,name)
        self.footer_labels.set_visible_child_name('version'); row.append(self.footer_labels)
        badge_slot=Gtk.Box(width_request=8,valign=Gtk.Align.CENTER)
        self.badge=Gtk.Box(css_classes=['update-badge'],width_request=8,height_request=8,valign=Gtk.Align.CENTER)
        self.badge.set_visible(False); badge_slot.append(self.badge); row.append(badge_slot)
        self.footer_button.set_child(row)
        self.footer_button.connect('clicked',lambda b:self.clicked())
        motion=Gtk.EventControllerMotion()
        motion.connect('enter',lambda c,x,y:self.footer_state(hovered=True))
        motion.connect('leave',lambda c:self.footer_state(hovered=False)); self.footer_button.add_controller(motion)
        focus=Gtk.EventControllerFocus()
        focus.connect('enter',lambda c:self.footer_state(focused=True))
        focus.connect('leave',lambda c:self.footer_state(focused=False)); self.footer_button.add_controller(focus)
        self.footer_status=label('','version muted',True); self.footer_status.set_hexpand(True); self.footer_status.set_xalign(1)
        owner.update_footer.append(self.footer_button); owner.update_footer.append(self.footer_status)
        owner.targets.update({'update-footer':owner.update_footer,'update-version':self.footer_button,
                              'update-badge':self.badge,'update-progress':self.footer_status})

    def footer_state(self,hovered=None,focused=None):
        if hovered is not None:
            self.footer_hovered=hovered
            if not hovered: self.footer_hover_suppressed=False
        if focused is not None:
            self.footer_focused=focused
            if not focused: self.footer_focus_suppressed=False
        self.refresh_footer()

    def set_sensitive(self,value):
        self.button.set_sensitive(value); self.footer_button.set_sensitive(value)

    def refresh_footer(self):
        busy=bool(self.work or self.process or self.starting)
        action=not (busy or self.checking) and (
            (self.footer_hovered and not self.footer_hover_suppressed) or
            (self.footer_focused and not self.footer_focus_suppressed))
        name='updating' if busy else 'action' if action else 'available' if self.manifest else 'version'
        self.footer_labels.set_visible_child_name(name)
        self.owner.targets['update-caption']=self.footer_labels.get_visible_child()
        (self.footer_button.add_css_class if action else self.footer_button.remove_css_class)('action')
        self.badge.set_visible(bool(self.manifest) and not busy)
        message=self.status.get_text() if self.checking or busy or self.footer_feedback else ''
        if not message and time.monotonic()<self.footer_notice_until: message='Up to date'
        self.footer_status.set_text(message); self.footer_status.set_tooltip_text(message or None)
        self.footer_button.set_tooltip_text(('Update available · ' if self.manifest else 'Update app · ')+ 'v'+self.owner.version())

    def check(self,install=False):
        if self.checking or self.process or self.starting: return
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
        self.button.set_tooltip_text('Update available' if manifest else 'Check for updates')
        self.set_sensitive(True)
        if install and not manifest and not error:
            # Keep the result visible under a stationary pointer/retained focus.
            # Each input source rearms independently after leaving the control.
            self.footer_hover_suppressed=self.footer_hovered
            self.footer_focus_suppressed=self.footer_focused
            self.footer_notice_until=time.monotonic()+3
        self.refresh_footer()
        if install and manifest: self.clicked()
        return False

    def clicked(self):
        if self.checking or self.process or self.starting: return
        self.footer_feedback=True
        self.footer_notice_until=0
        if not self.manifest: self.check(install=True); return
        if self.blocked(): self.status.set_text('Finish the current work before updating.'); self.refresh_footer(); return
        owner=self.owner
        try:
            base=state_path(); base.mkdir(parents=True,exist_ok=True,mode=0o700)
            self.work=base/('run-'+uuid.uuid4().hex); self.work.mkdir(mode=0o700)
            package=os.environ['CENTAUR_GTK_PACKAGE']
            write_json(self.work/'manifest.json',self.manifest)
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
            self.process=None; self.set_sensitive(True); self.work=None
        elif not self.process and phase in ('complete','recovered','failed','recovery-required'):
            self.set_sensitive(True); self.work=None

