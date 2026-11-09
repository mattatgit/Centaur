"""Small Settings surface; the detached updater owns installation and recovery."""
import os
from pathlib import Path
import subprocess
import threading
import uuid
from gi.repository import GLib, Gtk
from ui import box,button,button_text,label
from updater import (check_update,process_identity,profile_path,read_json,state_path,write_json)


class UpdateControls:
    def __init__(self,owner,section):
        self.owner=owner; self.manifest=None; self.checking=False; self.checked=False
        self.work=None; self.process=None; self.handed_off=False; self.ready_written=False; self.restored=False
        self.install_after_check=False
        self.starting=bool(os.environ.get('CENTAUR_UPDATE_STARTING'))
        self.resume=read_json(owner.update_session/'resume.json') if owner.update_session else {}
        self.version=label('Centaur v'+owner.version(),'small muted'); section.append(self.version)
        row=box(spacing=16)
        self.button=button('Update app',self.clicked); self.button.set_halign(Gtk.Align.START)
        row.append(self.button); self.status=label('','small muted',True); self.status.set_hexpand(True); row.append(self.status)
        section.append(row); self.button.set_sensitive(False)
        owner.targets['update-app']=self.button
        if owner.update_session:
            self.work=owner.update_session
            self.status.set_text(read_json(self.work/'status.json').get('message','Starting the updated app…'))

    def check(self,install=False):
        if self.checking or self.process or self.starting: return
        self.checked=True; self.checking=True; self.status.set_text('Checking for updates…'); self.button.set_sensitive(False)
        self.install_after_check=install
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
        self.status.set_text(error or ('Update available · '+manifest['version'].removeprefix('Centaur GTK4 ') if manifest else 'You’re up to date.'))
        self.button.set_tooltip_text('Update available' if manifest else 'Check for updates')
        self.button.set_sensitive(True)
        install=self.install_after_check; self.install_after_check=False
        if install and manifest: self.clicked()
        return False

    def clicked(self):
        if not self.manifest: self.check(install=True); return
        if self.blocked(): self.status.set_text('Finish the current work before updating.'); return
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
            self.button.set_sensitive(False)
        except Exception as error:
            self.process=None; self.status.set_text('Could not start the updater. '+str(error)); self.button.set_sensitive(True)

    def blocked(self):
        owner=self.owner
        buffer=owner.editor.get_buffer()
        return bool(owner.data.get('updateBlocked') or owner.data.get('busy') or owner.data.get('joining') or
                    owner.data.get('inviting') or owner.pending_message or owner.points or owner.active_form or
                    not owner.data.get('connected') or owner.project.get('queueCount'))

    def restore(self):
        owner=self.owner
        if not owner.update_session or self.restored or not owner.data.get('connected') or not owner.data.get('snapshotReady'): return
        resume=self.resume
        owner.drafts=resume.get('drafts',{})
        project=resume.get('projectId')
        if project and not any(p['id']==project for p in owner.data.get('projects',[])): return
        self.restored=True
        if project: owner.open_project(project)
        owner.navigate('settings')

    def tick(self):
        owner=self.owner
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
        if value.get('message'): self.status.set_text(value['message'])
        if self.process and phase=='ready' and not self.handed_off:
            if self.blocked(): self.status.set_text('Update downloaded. Waiting for the current work to finish…'); return
            self.handed_off=True
            buffer=owner.editor.get_buffer(); drafts=dict(owner.drafts)
            if owner.project: drafts[owner.project['id']]=buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),False)
            write_json(self.work/'approve.json',{'approved':True,'resume':{'projectId':owner.project.get('id'),'drafts':drafts}})
            owner.quit()
        elif self.process and self.process.poll() is not None:
            if phase not in ('failed','recovered','complete'): self.status.set_text('The update stopped. Your installed version is preserved.')
            self.process=None; self.button.set_sensitive(True); self.work=None
        elif not self.process and phase in ('complete','recovered','failed','recovery-required'):
            self.button.set_sensitive(True); self.work=None

