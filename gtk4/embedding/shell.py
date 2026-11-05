"""Native GTK4 Centaur frontend; service owns projects, identity and coordination."""
import argparse
import uuid
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from datetime import datetime
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_foreign('cairo')
gi.require_version('Graphene','1.0')
from gi.repository import Gdk, Gio, GLib, Graphene, Gtk, Pango
from backend import AppSpec, CasildaBackend
from bundle import load_bundle
from service import Service
from viewport import PreviewViewport
from viewport_model import ZOOM_MODES

ASSETS = Path(os.environ.get('CENTAUR_GTK_ASSETS', Path(__file__).parent / 'assets'))


def label(text='', css=None, wrap=False):
    widget = Gtk.Label(label=text, xalign=0, wrap=wrap, wrap_mode=Pango.WrapMode.WORD_CHAR)
    if css:
        for name in css.split(): widget.add_css_class(name)
    return widget


def box(vertical=False, spacing=8, css=None):
    widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL, spacing=spacing)
    if css:
        widget.add_css_class(css)
    return widget


def margins(widget, value):
    for edge in ('top','bottom','start','end'):
        getattr(widget,'set_margin_'+edge)(value)
    return widget


def button(text, callback, icon=None, css=None):
    widget = Gtk.Button()
    row = box(spacing=8)
    if icon:
        image=Gtk.Image.new_from_file(str(ASSETS / icon)); image.set_pixel_size(20)
        row.append(image); widget.centaur_image=image; widget.centaur_icon=icon
    if text:
        row.append(label(text))
    widget.set_child(row)
    widget.set_tooltip_text(text or 'Project options')
    if css:
        widget.add_css_class(css)
    if icon in ('interact-grey.svg','comment-grey.svg'):
        motion=Gtk.EventControllerMotion()
        def icon_state(hover=False):
            state='white' if widget.has_css_class('selected') else 'hover' if hover else 'grey'
            widget.centaur_image.set_from_file(str(ASSETS / icon.replace('grey',state)))
        motion.connect('enter',lambda c,x,y:icon_state(True)); motion.connect('leave',lambda c:icon_state(False))
        widget.add_controller(motion); widget.centaur_icon_state=icon_state
    widget.connect('clicked', lambda b: callback())
    return widget


class Centaur(Gtk.Application):
    def __init__(self, root, report_dir=None):
        super().__init__(application_id='org.centaur.Gtk4', flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.root = root
        self.reports = report_dir
        self.runtime = tempfile.TemporaryDirectory(prefix='centaur-gtk4-')
        self.data = {}
        self.project = {}
        self.backend = self.viewport = None
        self.preview_key = None
        self.preview_status = 'Open a project to begin'
        self.mode = 'Interact'
        self.tool = 'draw'
        self.points = []
        self.message_key = self.project_key = None
        self.page = 'projects'
        self.last_invite = ''
        self.closing = False
        self.pending_message = None
        self.drafts = {}
        self.active_form = None
        self.targets = {}

    def do_activate(self):
        provider = Gtk.CssProvider()
        provider.load_from_path(str(Path(__file__).with_name('shell.css')))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.window = Gtk.ApplicationWindow(application=self, title='Centaur', default_width=1400, default_height=940,
                                            decorated=not bool(os.environ.get('CENTAUR_GTK4_TEST_UNDECORATED')))
        self.window.set_size_request(520, 440)
        root = box(spacing=0)
        sidebar = margins(box(True, 8, 'sidebar'), 8)
        sidebar.set_size_request(180, -1)
        brand = button('', lambda:self.navigate('projects'), 'centaur.svg', 'brand')
        brand.set_tooltip_text('Projects'); brand.centaur_image.set_pixel_size(40)
        sidebar.append(brand)
        self.nav = {}
        for key, title, icon in [('projects','Projects','project-icon-default.svg'),('systems','Design Systems','ds-icon-default.svg'),('settings','Settings','settings-icon-default.svg')]:
            item = button(title, lambda k=key:self.navigate(k), icon, 'navigation')
            self.nav[key] = item
            sidebar.append(item)
        spacer = box(); spacer.set_vexpand(True); sidebar.append(spacer)
        self.identity = button('Your settings', lambda:self.navigate('settings'), css='navigation')
        sidebar.append(self.identity)
        root.append(sidebar)
        content = box(True, 0); content.set_hexpand(True)
        top = margins(box(spacing=12, css='topbar'), 16)
        top.append(button('Projects', lambda:self.navigate('projects')))
        self.breadcrumb_arrow = Gtk.Image.new_from_file(str(ASSETS / 'breadcrumb-arrow.svg'))
        top.append(self.breadcrumb_arrow)
        self.breadcrumb = label(''); top.append(self.breadcrumb)
        flexible = box(); flexible.set_hexpand(True); top.append(flexible)
        self.modes = box(spacing=2, css='mode-switch')
        self.mode_buttons = {}
        for title, icon in [('Interact','interact-grey.svg'),('Build','comment-grey.svg')]:
            item = button(title, lambda t=title:self.set_mode(t), icon)
            self.mode_buttons[title] = item; self.modes.append(item); self.targets['mode-'+title]=item
        top.append(self.modes)
        self.invite_button = button('Invite', self.invite, 'share.svg')
        top.append(self.invite_button)
        top.append(button('Deploy', lambda:self.notice('Deploy', 'Deployment is planned for a later version.'), css='primary'))
        content.append(top)
        self.stack = Gtk.Stack(hexpand=True,vexpand=True,hhomogeneous=False,vhomogeneous=False)
        content.append(self.stack)
        self.error_label = label('', 'error', True)
        margins(self.error_label, 12); self.error_label.set_visible(False)
        content.append(self.error_label)
        root.append(content); self.window.set_child(root)
        self.build_projects()
        self.build_workspace()
        self.build_systems()
        self.build_settings()
        self.navigate('projects')
        self.set_mode('Interact')
        self.window.connect('close-request', lambda w:self.close())
        self.window.present()
        self.service = Service(self.root, self.receive)
        GLib.timeout_add(200, self.poll)

    def build_projects(self):
        page = margins(box(True,20,'panel'),24)
        title = box(); title.append(label('Projects','heading'))
        title.get_first_child().set_hexpand(True)
        join = button('Join project',self.join)
        create = button('New project',self.new_project,css='primary')
        title.append(join); title.append(create); self.targets['create'] = create; self.targets['join'] = join
        page.append(title)
        scroll = Gtk.ScrolledWindow(vexpand=True,hexpand=True,hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.cards = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, min_children_per_line=1,max_children_per_line=5,
                                 row_spacing=16,column_spacing=16,homogeneous=True,valign=Gtk.Align.START)
        scroll.set_child(self.cards); page.append(scroll)
        self.empty_projects = label('Create a project, or join one with an invitation.','muted',True)
        page.append(self.empty_projects)
        self.join_progress=label('','muted',True); page.append(self.join_progress)
        self.cancel_join=button('Cancel join',lambda:self.service.send('cancelJoin')); page.append(self.cancel_join); self.cancel_join.set_visible(False)
        self.stack.add_named(page,'projects')

    def build_systems(self):
        page = box(True,16,'panel'); page.set_halign(Gtk.Align.CENTER); page.set_valign(Gtk.Align.CENTER)
        image = Gtk.Image.new_from_file(str(ASSETS/'design-system-empty-suitcase.png')); image.set_pixel_size(176)
        page.append(image); page.append(label('No design systems added yet','muted'))
        page.append(label('Design-system import is not available yet.','small muted'))
        self.stack.add_named(page,'systems')

    def build_settings(self):
        page = margins(box(True,20,'panel'),24)
        page.append(label('Settings','heading'))
        page.append(label('Your name','name'))
        self.name = Gtk.Entry(max_length=50); page.append(self.name)
        page.append(button('Save name',lambda:self.service.send('author',name=self.name.get_text())))
        page.append(label('Agent','name'))
        self.agent_detail = label('', 'muted', True); page.append(self.agent_detail)
        self.agent_name_button=button('Agent name',lambda:self.form('Agent name',[('name','Name used after @',self.project.get('agentName','centaur'))],lambda v:self.service.send('agentName',name=v['name'])))
        page.append(self.agent_name_button)
        self.stop_sharing_button=button('Stop sharing this project',lambda:self.notice('Stop sharing?','Disconnect guests from this project?',lambda:self.service.send('stopSharing'),'Stop sharing'))
        page.append(self.stop_sharing_button)
        page.append(label('The host runs OMP. Guests use the host’s agent and do not need their own credentials.','muted',True))
        page.append(label('Project storage','name')); page.append(label(str(self.root),'muted',True))
        page.append(button('Open project folder',lambda:Gio.AppInfo.launch_default_for_uri(self.root.as_uri(),None)))
        self.stack.add_named(page,'settings')

    def build_workspace(self):
        self.panes = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL,wide_handle=True)
        self.panes.set_position(760)
        canvas_panel = margins(box(True,8,'canvas-panel'),12)
        tools = box(spacing=8)
        spacer=box(); spacer.set_hexpand(True); tools.append(spacer)
        grid_button=button('',self.grid_settings,'grid.svg'); grid_button.set_tooltip_text('Canvas grid'); tools.append(grid_button)
        self.zoom = Gtk.DropDown.new_from_strings(ZOOM_MODES); self.zoom.set_selected(2)
        self.zoom.connect('notify::selected',lambda c,p:self.zoom_changed())
        tools.append(self.zoom); self.targets['zoom']=self.zoom
        tools.append(button('Centre',lambda:self.viewport.centre() if self.viewport else None))
        tools.append(button('Restart app',lambda:self.start_preview(force=True),'reload.svg'))
        canvas_panel.append(tools)
        self.overlay = Gtk.Overlay(hexpand=True,vexpand=True)
        self.preview_holder=box(True,0); self.preview_holder.set_hexpand(True); self.preview_holder.set_vexpand(True)
        self.overlay.set_child(self.preview_holder); self.targets['canvas']=self.overlay
        self.ink = Gtk.DrawingArea(hexpand=True,vexpand=True)
        self.ink.set_draw_func(self.draw_ink)
        self.overlay.add_overlay(self.ink)
        draw = Gtk.GestureDrag(button=1)
        draw.connect('drag-begin',self.ink_begin); draw.connect('drag-update',self.ink_update); draw.connect('drag-end',self.ink_end)
        self.ink.add_controller(draw)
        pan=Gtk.GestureDrag(button=2)
        pan.connect('drag-begin',lambda gesture,x,y:self.viewport.drag_begin(gesture,x,y) if self.viewport else None)
        pan.connect('drag-update',lambda gesture,dx,dy:self.viewport.drag_update(gesture,dx,dy) if self.viewport else None)
        self.ink.add_controller(pan)
        canvas_panel.append(self.overlay)
        self.preview_label=label('','muted'); self.preview_label.set_halign(Gtk.Align.CENTER); canvas_panel.append(self.preview_label)
        self.build_tools=box(spacing=8,css='tools'); self.build_tools.set_halign(Gtk.Align.CENTER)
        self.tool_buttons={}
        for tool,title,icon in [('draw','Draw',None),('comment','Comment','comment-grey.svg')]:
            item=button(title,lambda t=tool:self.set_tool(t),icon); self.tool_buttons[tool]=item; self.build_tools.append(item)
        undo=button('Undo',lambda:self.service.send('undo')); self.build_tools.append(undo); self.targets['undo']=undo
        canvas_panel.append(self.build_tools)
        self.panes.set_start_child(canvas_panel); self.panes.set_resize_start_child(True)
        chat=margins(box(True,12,'chat'),20); chat.set_size_request(340,-1)
        chat.append(label('Chat','heading'))
        self.chat_status=label('Connecting…','muted'); self.chat_status.set_ellipsize(Pango.EllipsizeMode.END); chat.append(self.chat_status)
        chat.append(Gtk.Separator())
        self.chat_scroll=Gtk.ScrolledWindow(vexpand=True,hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.messages=box(True,20); self.chat_scroll.set_child(self.messages); chat.append(self.chat_scroll)
        self.proposal=box(True,8,'proposal'); chat.append(self.proposal)
        composer=box(True,8,'composer')
        self.editor=Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR,accepts_tab=False)
        self.editor.set_size_request(-1,80); composer.append(self.editor); self.targets['editor']=self.editor
        key=Gtk.EventControllerKey(); key.set_propagation_phase(Gtk.PropagationPhase.CAPTURE); key.connect('key-pressed',self.editor_key); self.editor.add_controller(key)
        row=box(); self.mention=label('@centaur','name'); self.mention.set_hexpand(True); row.append(self.mention)
        self.stop_button=button('Stop',lambda:self.service.send('cancel')); row.append(self.stop_button)
        self.send_button=button('Send',self.send,'comment-enter-default.svg'); row.append(self.send_button); self.targets['send']=self.send_button
        composer.append(row); chat.append(composer)
        self.footer=label('','small muted'); chat.append(self.footer)
        self.panes.set_end_child(chat); self.panes.set_resize_end_child(False); self.panes.set_shrink_end_child(False)
        self.stack.add_named(self.panes,'workspace')
        self.set_tool('draw')

    @staticmethod
    def clear(widget):
        while widget.get_first_child():
            widget.remove(widget.get_first_child())

    def navigate(self,page):
        self.page=page
        self.stack.set_visible_child_name(page)
        for key,item in self.nav.items():
            (item.add_css_class if key==page else item.remove_css_class)('selected')
            item.centaur_image.set_from_file(str(ASSETS/item.centaur_icon.replace('default','selected' if key==page else 'default')))
        workspace=page=='workspace'
        self.modes.set_visible(workspace); self.invite_button.set_visible(workspace and not self.data.get('remote',False))
        self.breadcrumb_arrow.set_visible(workspace); self.breadcrumb.set_visible(workspace)
        if workspace:
            GLib.idle_add(self.start_preview)

    def set_mode(self,mode):
        self.mode=mode
        for key,item in self.mode_buttons.items():
            (item.add_css_class if key==mode else item.remove_css_class)('selected')
            item.centaur_icon_state()
        self.build_tools.set_visible(mode=='Build')
        self.ink.set_can_target(mode=='Build')

    def set_tool(self,tool):
        self.tool=tool
        for key,item in self.tool_buttons.items():
            (item.add_css_class if key==tool else item.remove_css_class)('selected')
            if hasattr(item,'centaur_icon_state'): item.centaur_icon_state()

    def receive(self,data):
        if data.get('type')=='error':
            self.pending_message=None; self.send_button.set_sensitive(self.data.get('connected',False))
            self.error_label.set_text(data.get('message','Could not complete that action.')); self.error_label.set_visible(True); return
        if data.get('type')=='sent': return
        if data.get('type')!='snapshot': return
        old_id=self.project.get('id')
        self.data=data; self.project=data.get('project',{})
        new_id=self.project.get('id')
        buffer=self.editor.get_buffer()
        if old_id!=new_id:
            if old_id: self.drafts[old_id]=buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),False)
            buffer.set_text(self.drafts.get(new_id,'')); self.pending_message=None
        pending=self.pending_message
        if pending and any(m.get('id') not in pending['seen'] and m.get('text')==pending['text'] and m.get('author')==data.get('author') for m in self.project.get('messages',[])):
            if buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),False)==pending['text']: buffer.set_text('')
            self.pending_message=None
        self.join_progress.set_text(data.get('joinStatus','') if data.get('joining') else '')
        self.cancel_join.set_visible(data.get('joining',False))
        self.agent_name_button.set_sensitive(bool(self.project) and not data.get('remote',False))
        self.stop_sharing_button.set_visible(bool(self.project.get('sharing',{}).get('enabled')) and not data.get('remote',False))
        self.identity.set_label(data.get('author','Your settings'))
        if not self.name.has_focus(): self.name.set_text(data.get('author',''))
        self.agent_detail.set_text('OMP · '+('Available on this host' if data.get('agentAvailable') else 'Agent unavailable'))
        key=json.dumps(data.get('projects',[]),sort_keys=True)
        if self.project_key!=key:
            self.project_key=key; self.refresh_cards()
        if self.project:
            if old_id!=self.project['id']: self.navigate('workspace')
            self.breadcrumb.set_text(self.project.get('name',''))
            model=data.get('agentModel','')
            model=model.replace('openai-codex/','OpenAI Codex · ').replace('gpt-','GPT ').replace('-',' ').replace(' sol',' Sol')
            status=data.get('status','')
            self.chat_status.set_text(status+' · '+(model or 'Model not reported yet') if data.get('agentAvailable') else status+' · Agent unavailable')
            self.mention.set_text('@'+self.project.get('agentName','centaur'))
            self.stop_button.set_visible(data.get('busy',False)); self.send_button.set_sensitive(data.get('connected',False) and self.pending_message is None)
            self.footer.set_text('Chatting as '+data.get('author','')+' · '+os.environ.get('CENTAUR_GTK4_BUILD_ID','dev'))
            messages=json.dumps([self.project.get('id'),self.project.get('messages',[])],sort_keys=True)
            if messages!=self.message_key:
                self.message_key=messages; self.refresh_messages()
            self.refresh_proposal()
            if self.page=='workspace': GLib.idle_add(self.start_preview)
        elif old_id:
            self.stop_preview(); self.navigate('projects')
        self.ink.queue_draw()
        invitation=data.get('invitation','')
        if invitation and invitation!=self.last_invite:
            self.last_invite=invitation
            self.invitation_dialog(invitation)

    def refresh_cards(self):
        self.clear(self.cards)
        for key in list(self.targets):
            if key.startswith('open-'): del self.targets[key]
        projects=self.data.get('projects',[])
        self.empty_projects.set_visible(not projects)
        for project in projects:
            card=margins(box(True,12,'project-card'),16); card.set_size_request(210,140)
            row=box(); title=label(project['name'],'name',True); title.set_hexpand(True); row.append(title)
            menu=Gtk.MenuButton(); menu.add_css_class('meatball'); menu.set_tooltip_text('Project options')
            menu.set_child(Gtk.Image.new_from_file(str(ASSETS/'tile-menu.svg')))
            pop=Gtk.Popover(); actions=box(True,4)
            rename=button('Rename',lambda p=project:self.rename(p)); rename.set_sensitive(not project.get('remote',False)); actions.append(rename)
            actions.append(button('Leave project' if project.get('remote') else 'Delete project',lambda p=project:self.delete(p),css='danger'))
            pop.set_child(actions); menu.set_popover(pop); row.append(menu); card.append(row)
            card.append(label(project.get('description',''),'muted',True))
            open_button=button('Open',lambda p=project:self.service.send('open',projectId=p['id']))
            self.targets['open-'+project['id']]=open_button
            card.append(open_button)
            self.cards.append(card)

    def refresh_messages(self):
        self.clear(self.messages)
        for message in self.project.get('messages',[]):
            item=box(True,6); head=box()
            author=message.get('author','')
            if message.get('kind') in ('agent','system') and author.lower().lstrip('@')=='centaur': author='Centaur'
            name=label(author,'name'); name.set_hexpand(True); head.append(name)
            try: time=datetime.fromisoformat(message['time'].replace('Z','+00:00')).astimezone().strftime('%H:%M')
            except (KeyError,ValueError): time=''
            head.append(label(time,'small muted')); item.append(head)
            item.append(label(message.get('text',''),'message',True)); self.messages.append(item)
        def bottom():
            adj=self.chat_scroll.get_vadjustment(); adj.set_value(max(0,adj.get_upper()-adj.get_page_size())); return False
        GLib.idle_add(bottom)

    def refresh_proposal(self):
        self.clear(self.proposal)
        proposal=self.project.get('proposal',{})
        conflict=proposal.get('conflict')
        if isinstance(conflict,dict):
            self.proposal.append(label(conflict.get('reason','Agreement needed'),'message',True))
            authors=proposal.get('authors',[]); accepted=proposal.get('accepted',[])
            self.proposal.append(label('Agreement: '+', '.join(accepted)+' / '+', '.join(authors),'small muted',True))
            agree=button('Agree to this change',lambda:self.service.send('accept'))
            agree.set_sensitive(self.data.get('author') in authors and self.data.get('author') not in accepted and not self.data.get('busy'))
            self.proposal.append(agree); self.targets['accept']=agree
        self.proposal.set_visible(bool(conflict))

    def send(self):
        buffer=self.editor.get_buffer(); text=buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),False)
        if text.strip() and self.data.get('connected') and self.pending_message is None:
            fields={'text':text}
            agent='@'+self.project.get('agentName','centaur').lower()
            if agent in text.lower() and self.viewport:
                try:
                    # Capture only the canvas, including aligned annotations;
                    # the conversation and other application windows stay out.
                    paintable=Gtk.WidgetPaintable.new(self.overlay)
                    snapshot=Gtk.Snapshot.new()
                    width,height=self.overlay.get_width(),self.overlay.get_height()
                    snapshot.append_color(Gdk.RGBA(red=.94,green=.945,blue=.93,alpha=1),Graphene.Rect().init(0,0,width,height))
                    paintable.snapshot(snapshot,width,height)
                    node=snapshot.to_node()
                    texture=self.window.get_renderer().render_texture(node,None)
                    target=Path(self.data['sourcePath']).parent/'.centaur'/('context-'+uuid.uuid4().hex+'.png')
                    target.parent.mkdir(exist_ok=True)
                    if not texture.save_to_png(str(target)): raise RuntimeError('PNG export failed')
                    fields.update(image=str(target),imageRevision=self.project['revision'])
                except Exception as error:
                    self.error_label.set_text('Could not attach the canvas image. Drawing coordinates are included. '+str(error))
                    self.error_label.set_visible(True)
            self.pending_message={'text':text,'seen':{m['id'] for m in self.project.get('messages',[])}}
            self.send_button.set_sensitive(False)
            if not self.service.send('message',**fields): self.pending_message=None

    def editor_key(self,controller,keyval,keycode,state):
        if keyval in (Gdk.KEY_Return,Gdk.KEY_KP_Enter) and not state & Gdk.ModifierType.SHIFT_MASK:
            self.send(); return True
        return False

    def form(self,title,fields,submit,action='Save'):
        dialog=Gtk.Window(title=title,transient_for=self.window,modal=True,default_width=420)
        self.active_form=dialog
        content=margins(box(True,12),24); entries={}
        for key,caption,value in fields:
            content.append(label(caption,'name')); entry=Gtk.Entry(text=value); entries[key]=entry; content.append(entry)
        row=box(); row.append(button('Cancel',dialog.destroy))
        def done():
            values={key:entry.get_text() for key,entry in entries.items()}
            if all(value.strip() for value in values.values()):
                submit(values); dialog.destroy()
        for entry in entries.values(): entry.connect('activate',lambda e:done())
        row.append(button(action,done,css='primary')); content.append(row); dialog.set_child(content); dialog.present()
        next(iter(entries.values())).grab_focus()

    def new_project(self):
        self.form('New project',[('name','Project name','')],lambda v:self.service.send('create',name=v['name'],description=''))

    def rename(self,project):
        self.form('Rename project',[('name','Project name',project['name'])],lambda v:self.service.send('rename',projectId=project['id'],name=v['name']))

    def delete(self,project):
        leave=project.get('remote',False)
        self.notice('Leave project?' if leave else 'Delete project?',
                    'Leave '+project['name']+' on this device?' if leave else 'Delete '+project['name']+'? Its files and conversation will be moved to the recovery folder.',
                    lambda:self.service.send('leave' if leave else 'delete',projectId=project['id']), 'Leave' if leave else 'Delete')

    def notice(self,title,text,confirm=None,action='OK'):
        dialog=Gtk.Window(title=title,transient_for=self.window,modal=True,default_width=420)
        content=margins(box(True,16),24); content.append(label(text,None,True)); row=box()
        if confirm: row.append(button('Cancel',dialog.destroy))
        def done():
            if confirm: confirm()
            dialog.destroy()
        row.append(button(action,done,css='primary')); content.append(row); dialog.set_child(content); dialog.present()

    def join(self):
        self.form('Join project',[('name','Your name',self.data.get('author','')),('code','Invitation','')],lambda v:self.service.send('join',**v), 'Join')

    def invite(self):
        self.service.send('invite',address='iroh')

    def invitation_dialog(self,code):
        self.notice('Invite someone','Keep Centaur’s host machine online. Share this invitation with the person joining.\n\n'+code,
                    lambda:self.window.get_display().get_clipboard().set(code),'Copy invitation')

    def grid_settings(self):
        grid=self.data.get('grid',{})
        dialog=Gtk.Window(title='Canvas grid',transient_for=self.window,modal=True)
        content=margins(box(True,12),20)
        enabled=Gtk.CheckButton(label='Show grid',active=grid.get('enabled',False)); content.append(enabled)
        size=Gtk.SpinButton.new_with_range(2,64,1); size.set_value(grid.get('size',8)); content.append(label('Grid size')); content.append(size)
        opacity=Gtk.SpinButton.new_with_range(0,100,1); opacity.set_value(grid.get('opacity',50)); content.append(label('Opacity (%)')); content.append(opacity)
        def done():
            self.service.send('grid',enabled=enabled.get_active(),size=size.get_value_as_int(),opacity=opacity.get_value_as_int()); dialog.destroy()
        content.append(button('Done',done)); dialog.set_child(content); dialog.present()

    def zoom_changed(self):
        if self.viewport: self.viewport.set_zoom(ZOOM_MODES[self.zoom.get_selected()])
        self.ink.queue_draw()

    def start_preview(self,force=False):
        if self.closing or self.page!='workspace' or not self.project: return False
        if self.project.get('appFormat')!='gtk4-v1':
            self.preview_status='This Qt project is preserved. Open it with Qt Centaur.'; return False
        key=(self.project['id'],self.project.get('revision'))
        if key==self.preview_key and not force: return False
        if not self.overlay.get_realized(): return False
        try:
            path=Path(self.data['sourcePath']); bundle=load_bundle(path)
            self.stop_preview()
            self.backend=CasildaBackend()
            self.viewport=PreviewViewport(self.backend.widget,bundle['width'],bundle['height'])
            self.preview_holder.append(self.viewport)
            self.preview_key=key
            runtime=Path(self.runtime.name)/self.project['id']; runtime.mkdir(exist_ok=True)
            self.child_report=runtime/'client.json'; self.child_report.unlink(missing_ok=True)
            def launch():
                if self.closing or self.preview_key!=key or not self.backend: return False
                try:
                    self.viewport.set_zoom(ZOOM_MODES[self.zoom.get_selected()])
                    self.backend.start(AppSpec((os.environ['CENTAUR_GTK_RUNNER'],str(path)),bundle['width'],bundle['height']),runtime,self.child_report)
                    self.preview_status='Connecting native app…'
                except Exception as error: self.preview_status='Could not launch app: '+str(error)
                return False
            GLib.idle_add(launch)
        except Exception as error:
            self.preview_status='Could not open app: '+str(error)
        return False

    def stop_preview(self):
        if self.backend: self.backend.stop()
        if self.viewport:
            self.viewport.release(); self.preview_holder.remove(self.viewport)
        self.backend=self.viewport=None; self.preview_key=None

    def ink_begin(self,gesture,x,y):
        if self.mode!='Build' or not self.data.get('connected'): gesture.set_state(Gtk.EventSequenceState.DENIED); return
        self.ink_origin=(x,y); self.points=[self.app_point(x,y)]; self.ink.queue_draw()

    def ink_update(self,gesture,dx,dy):
        if self.points and len(self.points)<4096:
            self.points.append(self.app_point(self.ink_origin[0]+dx,self.ink_origin[1]+dy)); self.ink.queue_draw()

    def ink_end(self,gesture,dx,dy):
        if self.points:
            # Normalised app coordinates, explicitly recorded with a full-app
            # frame; they stay aligned as the canvas is zoomed and panned.
            self.service.send('annotation',annotation={'tool':self.tool,'points':self.points,'frame':{'x':0,'y':0,'width':1,'height':1}})
            self.points=[]; self.ink.queue_draw()

    def app_point(self,x,y):
        if not self.viewport: return {'x':0,'y':0}
        g=self.viewport.describe()
        return {'x':max(0,min(1,(x-g['app_x'])/g['scale']/g['app_width'])),
                'y':max(0,min(1,(y-g['app_y'])/g['scale']/g['app_height']))}

    def draw_ink(self,area,cr,width,height):
        if not self.viewport: return
        g=self.viewport.describe(); scale=g['scale']
        grid=self.data.get('grid',{})
        if grid.get('enabled'):
            step=max(2,grid.get('size',8)*scale); cr.set_source_rgba(.73,.90,1,grid.get('opacity',50)/100); cr.set_line_width(.7)
            x=g['app_x']%step
            while x<width: cr.move_to(x,0); cr.line_to(x,height); x+=step
            y=g['app_y']%step
            while y<height: cr.move_to(0,y); cr.line_to(width,y); y+=step
            cr.stroke()
        marks=[a for a in self.project.get('annotations',[]) if a.get('revision')==self.project.get('revision')]
        if self.points: marks.append({'points':self.points,'tool':self.tool})
        cr.set_source_rgb(.2,.4,.9); cr.set_line_width(2); cr.set_line_cap(1)
        for mark in marks:
            points=mark.get('points',[])
            if not points: continue
            if mark.get('tool')=='comment': points=[points[0],points[-1]]
            for i,p in enumerate(points):
                x=g['app_x']+p['x']*g['app_width']*scale; y=g['app_y']+p['y']*g['app_height']*scale
                (cr.move_to if i==0 else cr.line_to)(x,y)
            cr.stroke()
            if mark.get('tool')=='comment' and len(points)>1:
                import math
                a,b=points[0],points[-1]
                angle=math.atan2((b['y']-a['y'])*g['app_height'],(b['x']-a['x'])*g['app_width'])
                x=g['app_x']+b['x']*g['app_width']*scale; y=g['app_y']+b['y']*g['app_height']*scale
                for offset in (-.5,.5):
                    cr.move_to(x,y); cr.line_to(x-10*math.cos(angle+offset),y-10*math.sin(angle+offset))
                cr.stroke()

    def poll(self):
        if self.closing: return False
        if self.backend and self.backend.process:
            if self.backend.process.poll() is not None: self.preview_status='App stopped · Restart app to try again'
            elif self.child_report.exists(): self.preview_status=''
        self.preview_label.set_text(self.preview_status)
        geometry=self.viewport.describe() if self.viewport else None
        if geometry != getattr(self,'ink_geometry',None):
            self.ink_geometry=geometry; self.ink.queue_draw()
        if self.reports:
            self.reports.mkdir(parents=True,exist_ok=True)
            data={'pid':os.getpid(),'page':self.page,'windowSize':[self.window.get_width(),self.window.get_height()],
                  'form':self.active_form.get_title() if self.active_form and self.active_form.get_visible() else None,'project':self.project,'projects':self.data.get('projects',[]),'status':self.data.get('status'),
                  'previewStatus':self.preview_status,'viewport':self.viewport.describe() if self.viewport else None,
                  'error':self.error_label.get_text() if self.error_label.get_visible() else '',
                  'childPid':self.backend.process.pid if self.backend and self.backend.process else None,'mode':self.mode,'targets':{}}
            try: data['child']=json.loads(self.child_report.read_text()) if self.backend else None
            except (AttributeError,FileNotFoundError,ValueError): data['child']=None
            for name,widget in self.targets.items():
                if not widget.get_mapped(): continue
                ok,r=widget.compute_bounds(self.window)
                if ok: data['targets'][name]=[r.get_x(),r.get_y(),r.get_width(),r.get_height()]
            target=self.reports/'shell.json'; target.with_suffix('.tmp').write_text(json.dumps(data)); target.with_suffix('.tmp').replace(target)
        return True

    def close(self):
        self.closing=True; self.stop_preview()
        if hasattr(self,'service'): self.service.close()
        self.runtime.cleanup()
        return False

    def do_shutdown(self):
        if not self.closing: self.close()
        Gtk.Application.do_shutdown(self)


def main():
    parser=argparse.ArgumentParser(description='Centaur GTK4 development preview')
    parser.add_argument('--data-dir',type=Path,default=Path.home()/'.local/share/Centaur/GTK4')
    parser.add_argument('--report-dir',type=Path)
    parser.add_argument('--stop-host',action='store_true')
    parser.add_argument('--version',action='version',version='Centaur GTK4 0.4.0-preview+'+os.environ.get('CENTAUR_GTK4_BUILD_ID','dev'))
    args=parser.parse_args()
    os.environ['PATH']=str(Path.home()/'.local/bin')+os.pathsep+os.environ.get('PATH','')
    root=args.data_dir.expanduser().resolve(); root.mkdir(parents=True,exist_ok=True)
    if args.stop_host: return subprocess.call([os.environ['CENTAUR_GTK_HOST'],'--stop','--data-dir',str(root)])
    app=Centaur(root,args.report_dir)
    for signum in (signal.SIGINT,signal.SIGTERM): GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,signum,lambda:(app.quit(),GLib.SOURCE_REMOVE)[1])
    return app.run([])


if __name__=='__main__': raise SystemExit(main())
