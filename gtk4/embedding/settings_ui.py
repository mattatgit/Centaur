"""Autosaved native Settings; the bridge and OMP acknowledge actual changes."""
import os
from pathlib import Path
import tempfile
import uuid
import time
from urllib.parse import urlparse
from gi.repository import Gdk, Gio, GLib, Gtk, Pango
from ui import accessible, ASSETS, WidthLimit, box, label, button, button_text, original, picture, margins
from update_ui import UpdateControls
from omp_settings import OmpSettings
from v2_ui import field

PROVIDERS=(('ChatGPT','6ae43.svg',('openai-codex',)),
           ('Claude','e625a.svg',('anthropic',)),
           ('OpenRouter','ce828.svg',('openrouter',)),
           ('Copilot','d77f2.svg',('github-copilot',)),
           ('Gemini','995cf.svg',('google-gemini-cli','google-antigravity','google')))


class NumericEntry(Gtk.Entry):
    def __init__(self,value,minimum,maximum,callback,suffix='',dirty=None):
        super().__init__(width_chars=4,max_width_chars=4,xalign=.5)
        self.minimum,self.maximum,self.callback,self.suffix=minimum,maximum,callback,suffix
        self.value=value; self.source=None; self.syncing=False; self.dirty=dirty or (lambda active:None)
        self.set_text(str(value)+suffix); self.set_size_request(56,24)
        self.connect('changed',self.edited)
        self.connect('activate',lambda e:self.commit())
        focus=Gtk.EventControllerFocus(); focus.connect('leave',lambda c:self.commit()); self.add_controller(focus)

    def commit(self):
        if self.source: GLib.source_remove(self.source); self.source=None
        try: value=max(self.minimum,min(self.maximum,int(self.get_text().removesuffix(self.suffix).strip())))
        except ValueError: value=self.value
        changed=value!=self.value; self.value=value
        self.syncing=True; self.set_text(str(value)+self.suffix); self.syncing=False
        if changed: self.callback(value)
        self.dirty(False); return False

    def edited(self,*unused):
        if self.syncing: return
        if self.source: GLib.source_remove(self.source)
        self.dirty(True); self.source=GLib.timeout_add(500,self.commit)

    def set_value(self,value):
        self.value=value
        if self.source is None and not self.get_state_flags() & Gtk.StateFlags.FOCUS_WITHIN:
            self.syncing=True; self.set_text(str(value)+self.suffix); self.syncing=False


class SettingsView:
    def __init__(self,owner):
        self.owner=owner; self.pending=set(); self.debounces={}; self.failed=False; self.syncing=False
        self.rpc=None; self.catalog=[]; self.login_providers=[]; self.current_model={}; self.refreshing=False
        self.agent_pending={}; self.agent_edit_context=None
        self.saved_until=0; self.save_acknowledged=False; self.notice_timeout=None; self.fade_tick=None
        page=box(True,0,'panel'); scroll=Gtk.ScrolledWindow(vexpand=True,hscrollbar_policy=Gtk.PolicyType.NEVER)
        owner.settings_inner=margins(box(True,40),72); owner.settings_inner.set_margin_top(48)
        owner.settings_limit=WidthLimit(owner.settings_inner,648); scroll.set_child(owner.settings_limit); page.append(scroll)
        def section(title,gap=16):
            group=box(True,gap); group.append(label(title,'section-title')); owner.settings_inner.append(group); return group
        names=section('Names',14); row=box(spacing=16); names.append(row); fields=box(True,14); fields.set_hexpand(True); row.append(fields)
        owner.name=Gtk.Entry(max_length=50,width_chars=1,placeholder_text='Add a username to be shown in chat',css_classes=['settings-name']); field(fields,'Username',owner.name)
        owner.agent_name_button=Gtk.Entry(max_length=30,width_chars=1,css_classes=['settings-name']); field(fields,'Address Centaur’s agent as',owner.agent_name_button)
        for key,entry in (('name',owner.name),('agent',owner.agent_name_button)):
            entry.connect('changed',lambda e,k=key:self.schedule(k))
            entry.connect('activate',lambda e,k=key:self.flush(k))
            owner.targets['settings-'+key]=entry
        self.avatar_path=owner.root/'profile-avatar'
        self.avatar_wire=owner.root/'profile-avatar-wire'
        try:
            if self.avatar_path.exists() and (not self.avatar_wire.exists() or
                    self.avatar_wire.stat().st_mtime_ns<self.avatar_path.stat().st_mtime_ns):
                from avatars import prepare_avatar
                prepare_avatar(self.avatar_path,self.avatar_wire)
        except (OSError,ValueError): pass
        self.avatar=Gtk.Overlay(css_classes=['avatar-picker']); self.avatar.set_size_request(128,128); self.avatar.set_valign(Gtk.Align.START)
        self.avatar.set_overflow(Gtk.Overflow.HIDDEN)
        avatar_column=box(True,6); avatar_column.append(label('Avatar','import-caption')); row.append(avatar_column)
        pick=Gtk.Button(); pick.set_child(self.avatar); pick.connect('clicked',lambda b:self.choose_avatar()); avatar_column.append(pick)
        self.upload_hint=label('Drag and drop an avatar here or click to upload','avatar-upload',True)
        self.upload_hint.set_justify(Gtk.Justification.CENTER); self.upload_hint.set_visible(False); self.upload_hint.set_can_target(False)
        self.avatar.add_overlay(self.upload_hint)
        motion=Gtk.EventControllerMotion(); motion.connect('enter',lambda c,x,y:self.upload_hint.set_visible(True))
        motion.connect('leave',lambda c:self.upload_hint.set_visible(False)); pick.add_controller(motion)
        focus=Gtk.EventControllerFocus(); focus.connect('enter',lambda c:self.upload_hint.set_visible(True)); focus.connect('leave',lambda c:self.upload_hint.set_visible(False)); pick.add_controller(focus)
        drop=Gtk.DropTarget.new(Gdk.FileList,Gdk.DragAction.COPY)
        drop.connect('drop',lambda target,value,x,y:self.upload(value.get_files()[0]) if value.get_files() else False); pick.add_controller(drop)
        owner.targets['settings-avatar']=pick; self.refresh_avatar()
        models=section('LLM and Model'); self.provider_cards=[]
        for title,icon,ids in PROVIDERS:
            card=box(spacing=8,css='provider-card')
            emblem=Gtk.Overlay(); emblem.set_child(original(icon,32)); card.append(emblem)
            dot=original('37343.svg',8); dot.add_css_class('provider-dot'); dot.set_halign(Gtk.Align.END); dot.set_valign(Gtk.Align.START); dot.set_visible(False); emblem.add_overlay(dot)
            caption=label(title,'provider-label'); caption.set_hexpand(True); card.append(caption)
            chooser=Gtk.MenuButton(css_classes=['provider-model']); chooser.set_visible(False); card.append(chooser)
            model_row=box(spacing=0); model_caption=label('Select model','small')
            model_caption.set_max_width_chars(14); model_caption.set_ellipsize(Pango.EllipsizeMode.END)
            model_row.append(model_caption); arrow=original('0702b.svg',24); arrow.add_css_class('provider-arrow'); model_row.append(arrow); chooser.set_child(model_row)
            action=button('Connect',lambda i=len(self.provider_cards):self.connect_provider(i),css='provider-action',tone='plain',width=67)
            card.append(action); models.append(card)
            self.provider_cards.append({'card':card,'title':title,'ids':ids,'chooser':chooser,'model-caption':model_caption,'action':action,'dot':dot,'models':[]})
            owner.targets['provider-'+ids[0]]=action
            owner.targets['provider-card-'+ids[0]]=card
            owner.targets['provider-models-'+ids[0]]=chooser
        self.provider_feedback=label('','small muted',True); self.provider_feedback.set_visible(False); models.append(self.provider_feedback)
        refresh=button('Refresh',self.refresh,css='settings-refresh',tone='plain',height=24)
        heading=models.get_first_child(); models.remove(heading); title_row=box(spacing=8)
        heading.set_hexpand(True); title_row.append(heading); title_row.append(refresh); models.prepend(title_row)
        owner.targets['provider-refresh']=refresh
        grid=section('Grid'); owner.settings_grid={}
        def gridrow(caption,widget):
            line=box(spacing=8,css='settings-row'); text=label(caption,'small'); text.set_hexpand(True); line.append(text); line.append(widget); grid.append(line)
        colour=button('#BAE6FF',owner.grid_colour,css='colour-button',tone='soft',width=96,height=24)
        colour.centaur_label.set_size_request(64,24); colour.get_child().set_spacing(0)
        gridrow('Grid colour',colour); owner.settings_grid['colour']=colour
        swatch=Gtk.Box(width_request=16,height_request=16,valign=Gtk.Align.CENTER,css_classes=['grid-swatch']); colour.get_child().append(swatch)
        owner.settings_grid['swatch']=swatch
        size=NumericEntry(8,2,64,lambda value:owner.send_grid(size=value),dirty=lambda active:self.numeric_dirty('size',active)); gridrow('Grid point size',size); owner.settings_grid['size']=size
        opacity=NumericEntry(50,0,100,lambda value:owner.send_grid(opacity=value),dirty=lambda active:self.numeric_dirty('opacity',active)); gridrow('Grid opacity %',opacity); owner.settings_grid['opacity']=opacity
        owner.targets.update({'settings-grid-size':size,'settings-grid-opacity':opacity,'settings-grid-colour':colour})
        folder=section('Centaur folder location'); line=box(spacing=16,css='settings-folder-row'); path=label(str(owner.root),'small muted',True); path.set_hexpand(True); line.append(path)
        line.append(button('Open folder',lambda:Gio.AppInfo.launch_default_for_uri(owner.root.as_uri(),None),tone='plain',width=80)); folder.append(line)
        owner.updates=UpdateControls(owner,section('App'))
        owner.stack.add_named(page,'settings')

    def status(self):
        pending=bool(self.pending or self.debounces or getattr(self,'agent_pending',None))
        owner=self.owner
        if pending or self.failed:
            self.clear_notice()
            owner.saved_status.set_opacity(1)
        elif self.save_acknowledged:
            self.clear_notice(); self.save_acknowledged=False
            self.saved_until=time.monotonic()+10; owner.saved_status.set_opacity(1)
            self.notice_timeout=GLib.timeout_add(10000,self.begin_fade)
        text='Could not save changes' if self.failed else 'Saving…' if pending else 'Changes saved' if self.saved_until else ''
        owner.saved_caption.set_text(text); owner.saved_tick.set_visible(bool(self.saved_until) and not pending and not self.failed)
        owner.saved_status.set_visible(owner.page=='settings' and bool(text))
        for css,value in (('pending',pending),('failed',self.failed)):
            (owner.saved_status.add_css_class if value else owner.saved_status.remove_css_class)(css)

    def clear_notice(self):
        if self.notice_timeout is not None: GLib.source_remove(self.notice_timeout); self.notice_timeout=None
        if self.fade_tick is not None: self.owner.saved_status.remove_tick_callback(self.fade_tick); self.fade_tick=None
        self.saved_until=0

    def opened(self):
        self.clear_notice(); self.save_acknowledged=False; self.status()

    def begin_fade(self):
        self.notice_timeout=None
        settings=Gtk.Settings.get_default()
        prop='gtk-interface-reduced-motion' if settings.find_property('gtk-interface-reduced-motion') else 'gtk-enable-animations'
        value=settings.get_property(prop)
        reduced=value==Gtk.ReducedMotion.REDUCE if prop=='gtk-interface-reduced-motion' else not value
        if reduced or self.owner.page!='settings':
            self.saved_until=0; self.owner.saved_status.set_visible(False); return False
        started=GLib.get_monotonic_time()
        def fade(widget,clock):
            fraction=min(1,max(0,(clock.get_frame_time()-started)/400000))
            widget.set_opacity(1-fraction)
            if fraction>=1:
                self.fade_tick=None; self.saved_until=0; widget.set_visible(False); return False
            return True
        self.fade_tick=self.owner.saved_status.add_tick_callback(fade)
        return False

    def numeric_dirty(self,key,active):
        (self.pending.add if active else self.pending.discard)('grid-'+key)
        self.status()

    def schedule(self,key):
        if self.syncing: return
        if key=='agent': self.agent_edit_context=(self.owner.project.get('id'),self.owner.data.get('remote',False))
        if key in self.debounces: GLib.source_remove(self.debounces.pop(key))
        self.debounces[key]=GLib.timeout_add(500,self.flush,key); self.failed=False; self.status()

    def flush(self,key):
        if key in self.debounces: GLib.source_remove(self.debounces.pop(key))
        owner=self.owner
        if not hasattr(owner,'service'): return False
        if key=='name':
            value=owner.name.get_text().strip()
            if value==owner.data.get('author'):
                self.status(); return False
            if value: self.send('author',name=value)
            else: self.failed=True
        else:
            value=owner.agent_name_button.get_text().strip().replace('@','')
            if value and not any(c.isspace() for c in value):
                project_id,remote=self.agent_edit_context or (owner.project.get('id'),owner.data.get('remote',False))
                project=next((p for p in owner.data.get('projects',[]) if p['id']==project_id),{})
                if value==owner.data.get('defaultAgentName') and (not project_id or remote or value==project.get('agentName')):
                    self.status(); return False
                self.send('agentDefaults',agentName=value)
                project_id,remote=self.agent_edit_context or (owner.project.get('id'),owner.data.get('remote',False))
                if project_id and not remote:
                    self.agent_pending[project_id]=value; owner.service.send('agentName',projectId=project_id,name=value)
            else: self.failed=True
        self.status(); return False

    def send(self,kind,**fields):
        ident=uuid.uuid4().hex; self.pending.add(ident); self.failed=False; self.status()
        if not self.owner.service.send(kind,requestId=ident,**fields): self.pending.discard(ident); self.failed=True
        GLib.timeout_add_seconds(10,self.expired,ident); self.status()

    def expired(self,ident):
        if ident in self.pending: self.pending.remove(ident); self.failed=True; self.status()
        return False

    def receive(self,data):
        owner=self.owner
        if data.get('type')=='settingsSaved':
            if data.get('requestId') in self.pending:
                self.pending.remove(data['requestId']); self.failed|=not data.get('success',False)
                if data.get('success'): self.save_acknowledged=True
                self.status()
            return
        if data.get('type')=='error':
            if self.pending or self.agent_pending: self.failed=True; self.agent_pending.clear(); self.status()
            return
        if data.get('type')!='snapshot': return
        if data.get('snapshotReady') and not getattr(self,'announced_avatar',False):
            self.announced_avatar=True
            if self.avatar_wire.is_file(): owner.service.send('refreshAvatar')
        self.syncing=True
        # Existing shared conversations bind the member name at invitation
        # time. Preserve that identity while the guest is connected.
        accessible(owner.name,'Username')
        if 'name' not in self.debounces and not owner.name.get_state_flags() & Gtk.StateFlags.FOCUS_WITHIN: owner.name.set_text(data.get('author',''))
        value=owner.project.get('agentName',data.get('defaultAgentName','centaur')) if not data.get('remote') else data.get('defaultAgentName','centaur')
        if 'agent' not in self.debounces and not owner.agent_name_button.get_state_flags() & Gtk.StateFlags.FOCUS_WITHIN: owner.agent_name_button.set_text(value)
        for project in data.get('projects',[]):
            if project['id'] in self.agent_pending and self.agent_pending[project['id']]==project.get('agentName'):
                self.agent_pending.pop(project['id'],None); self.save_acknowledged=True
        accessible(owner.agent_name_button,'Address Centaur’s agent as','Used for this project and future projects.' if owner.project and not data.get('remote') else 'Used for future projects.')
        self.syncing=False
        selected_model=data.get('selectedModel')
        if selected_model!=getattr(self,'rendered_model',None):
            self.rendered_model=selected_model
            if self.catalog: self.render_providers()
        if data.get('preferencesSaved') is False: self.failed=True
        self.status()

    def refresh_avatar(self):
        owner=self.owner
        uploaded=self.avatar_path.exists()
        try:
            image=picture(self.avatar_path,128,cover=True) if uploaded else None
        except GLib.Error:
            uploaded=False; image=None
        if image is None:
            image=Gtk.Fixed(); image.put(picture(ASSETS/'v2/dc3c7.png',81),26,23)
        self.avatar.set_child(image)
        owner.profile_avatar.set_child(picture(self.avatar_path if uploaded else ASSETS/'v2/dc3c7.png',40,cover=uploaded))

    def upload(self,file):
        if not file.get_path(): return False
        self.pending.add('avatar'); self.status()
        try:
            path=Path(file.get_path())
            if path.stat().st_size>5*1024*1024: raise ValueError('Image too large')
            texture=Gdk.Texture.new_from_file(file)
            if max(texture.get_width(),texture.get_height())>8192: raise ValueError('Image too large')
            data=path.read_bytes(); self.owner.root.mkdir(parents=True,exist_ok=True)
            if self.avatar_path.exists() and self.avatar_path.read_bytes()==data: return True
            with tempfile.NamedTemporaryFile(dir=self.owner.root,prefix='.avatar-',delete=False) as output:
                temporary=Path(output.name); output.write(data); output.flush(); os.fsync(output.fileno())
            try:
                from avatars import prepare_avatar
                prepare_avatar(temporary,self.avatar_wire)
                temporary.replace(self.avatar_path)
            finally:
                temporary.unlink(missing_ok=True)
            fd=os.open(self.owner.root,os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)
            self.refresh_avatar(); self.owner.refresh_messages()
            self.owner.service.send('refreshAvatar')
            self.failed=False; self.save_acknowledged=True
        except (OSError,ValueError,GLib.Error): self.failed=True
        finally:
            self.pending.discard('avatar'); self.status()
        return not self.failed

    def choose_avatar(self):
        def chosen(dialog,result):
            try:
                file=dialog.open_finish(result)
                if file: self.upload(file)
            except GLib.Error: pass
        filters=Gio.ListStore.new(Gtk.FileFilter); image_filter=Gtk.FileFilter(name='Images')
        for mime in ('image/png','image/jpeg','image/webp'): image_filter.add_mime_type(mime)
        filters.append(image_filter); Gtk.FileDialog(title='Choose an avatar',filters=filters).open(self.owner.window,None,chosen)

    def feedback(self,text):
        self.provider_feedback.set_text(text); self.provider_feedback.set_visible(bool(text))

    def ensure_rpc(self):
        if self.rpc: return True
        executable=self.owner.data.get('agentExecutable')
        if not executable: self.feedback('OMP is unavailable on this device.'); return False
        self.rpc=OmpSettings(executable,self.auth_event,lambda cb,*args:GLib.idle_add(cb,*args),
                             later=lambda seconds,callback:GLib.timeout_add_seconds(seconds,callback)); return True

    def refresh(self):
        if self.refreshing or not self.ensure_rpc(): return
        self.refreshing=True; self.feedback('Checking connections…'); replies={}
        def received(kind,response):
            replies[kind]=response
            if len(replies)<3: return
            self.refreshing=False
            if not all(r.get('success') for r in replies.values()): self.feedback('Could not read OMP connections. Refresh to retry.'); return
            self.login_providers=replies['get_login_providers'].get('data',{}).get('providers',[])
            self.catalog=replies['get_available_models'].get('data',{}).get('models',[])
            self.current_model=replies['get_state'].get('data',{}).get('model') or {}
            self.feedback(''); self.render_providers()
        for kind in ('get_login_providers','get_available_models','get_state'):
            self.rpc.request(kind,lambda r,k=kind:received(k,r))

    def render_providers(self):
        for key in list(self.owner.targets):
            if key.startswith('model-option-'): del self.owner.targets[key]
        for index,item in enumerate(self.provider_cards):
            models=[m for m in self.catalog if m.get('provider') in item['ids']]; item['models']=models
            providers=sorted((p for p in self.login_providers if p.get('id') in item['ids']),key=lambda p:item['ids'].index(p['id']))
            item['login']=next((p['id'] for p in providers if p.get('available',True)),None)
            connected=bool(models) or any(p.get('authenticated') for p in providers); item['connected']=connected
            item['dot'].set_visible(connected)
            (item['card'].add_css_class if connected else item['card'].remove_css_class)('connected')
            button_text(item['action'],'Disconnect' if connected else 'Connect')
            item['action'].set_size_request(80 if connected else 67,32)
            accessible(item['action'],('Disconnect ' if connected else 'Connect ')+item['title'])
            accessible(item['chooser'],'Select '+item['title']+' model')
            chooser=item['chooser']; chooser.set_visible(bool(models)); chosen=self.owner.data.get('selectedModel')
            current=next((m for m in models if m.get('provider','')+'/'+m.get('id','')==chosen),None)
            if not current and not chosen: current=next((m for m in models if m.get('id')==self.current_model.get('id') and m.get('provider')==self.current_model.get('provider')),None)
            item['model-caption'].set_text((current or {}).get('name') or (current or {}).get('id') or 'Select model')
            pop=Gtk.Popover(has_arrow=False); entries=box(True,0)
            for model in models:
                def select(m=model,p=pop):
                    p.popdown(); self.select_model(m)
                action=button(model.get('name') or model['id'],select,tone='plain'); action.get_child().set_halign(Gtk.Align.START); entries.append(action)
                self.owner.targets['model-option-'+model['provider']+'/'+model['id']]=action
            scroller=Gtk.ScrolledWindow(max_content_height=320,propagate_natural_height=True,hscrollbar_policy=Gtk.PolicyType.NEVER)
            scroller.set_child(entries); pop.set_child(scroller); chooser.set_popover(pop)

    def select_model(self,model):
        if model['provider']+'/'+model['id']==self.owner.data.get('selectedModel'): return
        if not self.ensure_rpc(): return
        self.feedback('Selecting model…'); self.pending.add('model-selection'); self.status()
        def selected(response):
            self.pending.discard('model-selection')
            if response.get('success'):
                self.send('agentDefaults',model=model['provider']+'/'+model['id']); self.feedback(''); self.current_model=model
            else:
                self.failed=True; self.feedback('Could not select that model. Refresh the available models and retry.')
            self.status()
        self.rpc.request('set_model',selected,provider=model['provider'],modelId=model['id'])

    def connect_provider(self,index):
        item=self.provider_cards[index]
        if not self.ensure_rpc(): return
        if item.get('connected'):
            provider=(item.get('models') or [{}])[0].get('provider') or item.get('login') or item['ids'][0]
            self.rpc.request('get_logout_accounts',lambda r:self.disconnect_accounts(provider,r),providerId=provider)
        elif item.get('login'):
            self.feedback('Finish signing in with your provider…'); self.auth_started=True; self.pending.add('auth'); self.status()
            def finished(response):
                self.auth_started=False; self.pending.discard('auth'); self.failed=not response.get('success',False)
                if response.get('success'): self.save_acknowledged=True
                self.status()
                if response.get('success'): self.refresh()
                else: self.feedback('Sign-in did not finish. Retry, or complete authentication in OMP and refresh.')
            self.rpc.request('login',finished,providerId=item['login'])
        else:
            self.owner.notice('Connect '+item['title'],'This OMP connection uses credentials configured in OMP. After connecting there, use Refresh connections here.')

    def disconnect_accounts(self,provider,response):
        accounts=response.get('data',{}).get('accounts',[]) if response.get('success') else []
        if not accounts:
            self.feedback('This connection is configured outside OMP’s saved accounts. Update that credential source in OMP, then refresh.'); return
        dialog,content=self.owner.dialog('Disconnect account',408)
        content.append(label('Choose the account to disconnect. Other accounts stay connected.','small muted',True))
        for account in accounts:
            def disconnect(a=account):
                self.owner.dismiss_dialog(dialog)
                self.pending.add('auth'); self.status()
                def finished(response):
                    self.pending.discard('auth'); self.failed=not response.get('success',False)
                    if response.get('success'): self.save_acknowledged=True
                    self.status()
                    if response.get('success'): self.refresh()
                    else: self.feedback('Could not disconnect the account.')
                self.rpc.request('logout',finished,providerId=provider,credentialId=a['credentialId'])
            content.append(button(account.get('label') or provider,disconnect,tone='plain'))
        content.append(button('Cancel',lambda:self.owner.dismiss_dialog(dialog),tone='plain')); dialog.present()

    def auth_event(self,event):
        if not getattr(self,'auth_started',False): return False
        method=event.get('method'); ident=event.get('id')
        if method=='open_url':
            url=event.get('launchUrl') or event.get('url',''); parsed=urlparse(url)
            if parsed.scheme=='https' or (parsed.scheme=='http' and parsed.hostname in ('localhost','127.0.0.1','::1')):
                Gio.AppInfo.launch_default_for_uri(url,None)
        elif method=='input' and not event.get('secret'):
            replied=[False]
            def answer(values):
                replied[0]=True; self.rpc.answer(ident,values['code'])
            self.owner.form(event.get('title') or 'Finish sign-in',[('code','Authorization code','')],
                answer,action='Continue',width=408)
            dialog=self.owner.active_form; dialog.on_close=lambda:None if replied[0] else self.rpc.answer(ident,cancelled=True)
        elif method not in ('notify','cancel'): self.rpc.answer(ident,cancelled=True)
        return False

    def close(self):
        self.clear_notice()
        for key in list(self.debounces): self.flush(key)
        for key in ('size','opacity'): self.owner.settings_grid[key].commit()
        if self.rpc: self.rpc.close()
