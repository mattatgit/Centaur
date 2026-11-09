"""Native GTK4 Centaur frontend; service owns projects, identity and coordination."""
import argparse
import uuid
import json
import os
import re
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
from ui import (ASSETS, SIDEBAR, COMPACT_SIDEBAR, HEADER, CHAT_WIDTH, CHAT_MIN,
                CHAT_MAX, Svg, ProjectGrid, Composer, Stepper, Switch, WidthLimit,
                label, box, margins, button, button_text, selected)


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
        self.open_id = None
        self.targets = {}

    def do_activate(self):
        provider = Gtk.CssProvider()
        provider.load_from_path(str(Path(__file__).with_name('shell.css')))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.window = Gtk.ApplicationWindow(application=self, title='Centaur', default_width=1440, default_height=944,
                                            decorated=not bool(os.environ.get('CENTAUR_GTK4_TEST_UNDECORATED')))
        self.window.set_size_request(360, 680)
        self.root_overlay = Gtk.Overlay()
        root = box(spacing=0); self.root_overlay.set_child(root)
        self.sidebar = box(True, 0, 'sidebar'); self.sidebar.set_size_request(SIDEBAR, -1)
        brand_row = box(spacing=0); brand_row.set_size_request(-1, HEADER)
        brand = button('', lambda:self.navigate('projects'), 'centaur.svg', 'brand', tone='plain', width=32, icon_size=32)
        brand.set_margin_start(24); brand.set_valign(Gtk.Align.CENTER); brand.set_tooltip_text('Projects')
        brand_row.append(brand); self.sidebar.append(brand_row); self.sidebar_brand = brand
        self.nav = {}; self.nav_labels = []
        links = box(True, 0); links.set_margin_top(24); links.set_margin_start(8); links.set_margin_end(8)
        for key, title, icon in [('projects','Projects','project-icon-default.svg'),('systems','Design Systems','ds-icon-default.svg'),('settings','Settings','settings-icon-default.svg')]:
            item = button(title, lambda k=key:self.navigate(k), icon, 'navigation', tone='plain', height=40, icon_size=32)
            item.get_child().set_halign(Gtk.Align.START)
            self.nav[key] = item; self.nav_labels.append(item.centaur_label); self.targets['sidebar-'+key] = item
            self.targets['nav-'+key] = item; links.append(item)
        self.sidebar.append(links)
        spacer = box(); spacer.set_vexpand(True); self.sidebar.append(spacer)
        self.identity = button('', lambda:self.navigate('settings'), css='profile', tone='plain', height=88)
        profile = box(spacing=16); profile.set_valign(Gtk.Align.CENTER)
        self.profile_avatar = label('M', 'profile-avatar'); self.profile_avatar.set_size_request(40,40); self.profile_avatar.set_xalign(.5)
        profile.append(self.profile_avatar)
        self.profile_text = box(True, 8); self.profile_name = label('', 'nav-label'); self.profile_name.set_ellipsize(Pango.EllipsizeMode.END)
        self.profile_text.append(self.profile_name); self.profile_text.append(label('This device', 'small muted')); profile.append(self.profile_text)
        self.identity.set_child(profile); self.sidebar.append(self.identity); root.append(self.sidebar)
        content = box(True,0); content.set_hexpand(True)
        self.top = Gtk.CenterBox(); self.top.add_css_class('topbar'); self.top.set_size_request(-1,HEADER)
        self.top_start = box(spacing=8); self.top_start.set_margin_start(24); self.top_start.set_valign(Gtk.Align.CENTER)
        self.workspace_brand = button('',lambda:self.navigate('projects'),'centaur.svg','brand',tone='plain',width=32,icon_size=32)
        self.workspace_brand.set_tooltip_text('Projects'); self.top_start.append(self.workspace_brand)
        self.projects_crumb = button('Projects',lambda:self.navigate('projects'),tone='plain'); self.top_start.append(self.projects_crumb)
        self.breadcrumb_arrow = Svg('breadcrumb-arrow.svg',16); self.top_start.append(self.breadcrumb_arrow)
        self.breadcrumb = label('', 'breadcrumb'); self.breadcrumb.set_ellipsize(Pango.EllipsizeMode.END); self.top_start.append(self.breadcrumb)
        self.page_title = label('Projects','section-title'); self.top_start.append(self.page_title); self.top.set_start_widget(self.top_start)
        self.modes = margins(box(spacing=0,css='mode-switch'),0); self.modes.set_valign(Gtk.Align.CENTER)
        self.mode_buttons = {}
        for title,icon in [('Interact','interact-grey.svg'),('Build','comment-grey.svg')]:
            item = button(title,lambda t=title:self.set_mode(t),icon,'mode-button',tone='plain',width=112)
            self.mode_buttons[title] = item; self.modes.append(item); self.targets['mode-'+title] = item
        self.top.set_center_widget(self.modes)
        self.targets['mode-switch']=self.modes
        self.top_actions = box(spacing=8); self.top_actions.set_margin_end(24); self.top_actions.set_valign(Gtk.Align.CENTER)
        self.join_button = button('Join project',self.join,tone='plain'); self.top_actions.append(self.join_button); self.targets['join'] = self.join_button
        self.create_button = button('+ New project',self.new_project,tone='dark'); self.top_actions.append(self.create_button); self.targets['create'] = self.create_button
        self.import_button = button('Import',lambda:None); self.import_button.set_sensitive(False); self.top_actions.append(self.import_button)
        self.invite_button = button('Invite',self.invite,tone='plain'); self.top_actions.append(self.invite_button)
        self.deploy_button = button('Deploy',lambda:self.notice('Deploy','Deployment is planned for a later version.'),'share.svg'); self.top_actions.append(self.deploy_button)
        self.top.set_end_widget(self.top_actions); content.append(self.top)
        self.stack = Gtk.Stack(hexpand=True,vexpand=True,hhomogeneous=False,vhomogeneous=False)
        self.stack.set_margin_end(8); self.stack.set_margin_bottom(8); content.append(self.stack)
        root.append(content)
        self.modal_shade = box(css='modal-shade'); self.modal_shade.set_hexpand(True); self.modal_shade.set_vexpand(True)
        self.root_overlay.add_overlay(self.modal_shade); self.modal_shade.set_visible(False)
        self.error_label = margins(label('','error toast',True),24); self.error_label.set_halign(Gtk.Align.CENTER); self.error_label.set_valign(Gtk.Align.END)
        self.root_overlay.add_overlay(self.error_label); self.error_label.set_visible(False)
        self.window.set_child(self.root_overlay)
        self.build_projects(); self.build_workspace(); self.build_systems(); self.build_settings()
        self.navigate('projects'); self.set_mode('Interact')
        self.window.connect('close-request',lambda w:self.close()); self.window.present()
        self.service = Service(self.root,self.receive)
        GLib.timeout_add(200,self.poll)

    def build_projects(self):
        page = box(True,0,'panel')
        self.projects_inner = margins(box(True,24),40); self.projects_inner.set_vexpand(True); page.append(self.projects_inner)
        scroll = Gtk.ScrolledWindow(vexpand=True,hexpand=True,hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.cards = ProjectGrid(); scroll.set_child(self.cards)
        overlay = Gtk.Overlay(vexpand=True); overlay.set_child(scroll)
        self.empty_projects = box(True,16,'empty-project'); self.empty_projects.set_size_request(-1,264)
        self.empty_projects.append(label('What shall we make?','empty-heading',True))
        self.empty_projects.append(label('A family planner, a little game, a shared collection. Every project becomes its own native app.','empty-description muted',True))
        spacer=box(); spacer.set_vexpand(True); self.empty_projects.append(spacer)
        first=button('Create your first project',self.new_project,tone='lime'); first.set_halign(Gtk.Align.START); self.empty_projects.append(first)
        self.empty_limit=WidthLimit(self.empty_projects,424); overlay.add_overlay(self.empty_limit); self.projects_inner.append(overlay)
        self.join_progress=label('','small muted',True); self.projects_inner.append(self.join_progress); self.join_progress.set_visible(False)
        self.cancel_join=button('Cancel join',lambda:self.service.send('cancelJoin')); self.cancel_join.set_halign(Gtk.Align.START)
        self.projects_inner.append(self.cancel_join); self.cancel_join.set_visible(False)
        self.stack.add_named(page,'projects')

    def build_systems(self):
        page=Gtk.Overlay(); page.add_css_class('panel'); page.set_child(box())
        group=box(True,16); group.set_halign(Gtk.Align.CENTER); group.set_valign(Gtk.Align.CENTER)
        image=Gtk.Picture.new_for_filename(str(ASSETS/'design-system-empty-suitcase.png'))
        image.set_content_fit(Gtk.ContentFit.CONTAIN); image.set_size_request(176,176); image.set_halign(Gtk.Align.CENTER)
        group.append(image)
        for text,css in [('No design systems added yet','muted'),('Design-system import is not available yet.','small muted')]:
            item=label(text,css,True); item.set_xalign(.5); group.append(item)
        page.add_overlay(group); self.stack.add_named(page,'systems')

    def build_settings(self):
        page=box(True,0,'panel'); scroll=Gtk.ScrolledWindow(vexpand=True,hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.settings_inner=margins(box(True,24),40); self.settings_limit=WidthLimit(self.settings_inner,720)
        scroll.set_child(self.settings_limit); page.append(scroll)
        def section(title):
            group=box(True,16); group.append(label(title,'section-title')); self.settings_inner.append(group); return group
        def rule(): self.settings_inner.append(Gtk.Separator())
        space=section('Your space'); space.append(label('Your name'))
        self.name=Gtk.Entry(max_length=50); self.name.set_size_request(-1,40); space.append(self.name)
        self.name.connect('activate',lambda e:self.save_name())
        focus=Gtk.EventControllerFocus(); focus.connect('leave',lambda c:self.save_name()); self.name.add_controller(focus)
        space.append(label('People in this conversation see this name.','small muted',True)); rule()
        agent=section('Agent'); self.agent_detail=label('','',True); agent.append(self.agent_detail)
        self.agent_path=label('','small muted',True); agent.append(self.agent_path)
        self.agent_model=label('','small muted',True); agent.append(self.agent_model)
        agent.append(label('Sign in and select a model in OMP. Credentials stay with the agent on this device.','small muted',True))
        self.agent_name_caption=label("Address this project's agent as"); agent.append(self.agent_name_caption)
        self.agent_name_button=Gtk.Entry(max_length=30); self.agent_name_button.set_size_request(-1,40); agent.append(self.agent_name_button)
        self.agent_name_button.connect('activate',lambda e:self.save_agent_name())
        focus=Gtk.EventControllerFocus(); focus.connect('leave',lambda c:self.save_agent_name()); self.agent_name_button.add_controller(focus)
        self.project_settings_actions=box(spacing=8); self.open_repo_button=button('Open repo',self.open_repo)
        self.project_settings_actions.append(self.open_repo_button)
        self.project_settings_actions.append(button('Restart app',self.restart_app,'reload.svg'))
        self.archive_button=button('Archive',lambda:self.notice('Archive this project?','Your app and conversation stay saved in the project folder.',lambda:self.service.send('archive',projectId=self.project['id']),'Archive'))
        self.project_settings_actions.append(self.archive_button); agent.append(self.project_settings_actions); rule()
        group=section('Grid'); self.settings_grid=self.grid_controls(group); rule()
        storage=section('Collaboration and storage')
        storage.append(label('Invite people from a project to collaborate across computers. The background host keeps sharing while its Centaur window is closed. Keep the host computer awake.','small muted',True))
        storage.append(label(str(self.root),'small muted',True))
        open_folder=button('Open data folder',lambda:Gio.AppInfo.launch_default_for_uri(self.root.as_uri(),None)); open_folder.set_halign(Gtk.Align.START); storage.append(open_folder)
        self.back_to_app=button('Back to app',lambda:self.navigate('workspace')); self.back_to_app.set_halign(Gtk.Align.START); storage.append(self.back_to_app)
        self.stop_sharing_button=button('Stop sharing this project',lambda:self.notice('Stop sharing?','Disconnect guests from this project?',lambda:self.service.send('stopSharing'),'Stop sharing'))
        self.stop_sharing_button.set_halign(Gtk.Align.START); storage.append(self.stop_sharing_button)
        storage.append(label('Centaur v'+self.version(),'small muted')); self.stack.add_named(page,'settings')

    def build_workspace(self):
        wrapper=margins(box(spacing=0),16); wrapper.set_margin_top(0)
        self.panes=Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL,wide_handle=True); self.panes.set_hexpand(True); self.panes.set_vexpand(True)
        wrapper.append(self.panes)
        self.overlay=Gtk.Overlay(hexpand=True,vexpand=True); self.overlay.add_css_class('canvas-panel'); self.overlay.set_overflow(Gtk.Overflow.HIDDEN)
        self.preview_holder=box(True,0); self.preview_holder.set_hexpand(True); self.preview_holder.set_vexpand(True)
        self.overlay.set_child(self.preview_holder); self.targets['canvas']=self.overlay
        self.ink=Gtk.DrawingArea(hexpand=True,vexpand=True); self.ink.set_draw_func(self.draw_ink); self.overlay.add_overlay(self.ink)
        draw=Gtk.GestureDrag(button=1); draw.connect('drag-begin',self.ink_begin); draw.connect('drag-update',self.ink_update); draw.connect('drag-end',self.ink_end); self.ink.add_controller(draw)
        pan=Gtk.GestureDrag(button=2)
        pan.connect('drag-begin',lambda g,x,y:self.viewport.drag_begin(g,x,y) if self.viewport else None)
        pan.connect('drag-update',lambda g,x,y:self.viewport.drag_update(g,x,y) if self.viewport else None); self.ink.add_controller(pan)
        self.grid_button=button('',self.toggle_grid,'grid.svg','grid-toggle',width=24,height=24)
        self.grid_button.set_tooltip_text('Show grid'); self.grid_button.set_halign(Gtk.Align.START); self.grid_button.set_valign(Gtk.Align.START)
        self.grid_button.set_margin_start(8); self.grid_button.set_margin_top(8); self.overlay.add_overlay(self.grid_button); self.targets['grid']=self.grid_button
        tools=box(spacing=8); tools.set_halign(Gtk.Align.END); tools.set_valign(Gtk.Align.START); tools.set_margin_top(8); tools.set_margin_end(8)
        self.zoom=Gtk.DropDown.new_from_strings(ZOOM_MODES); self.zoom.add_css_class('zoom'); self.zoom.set_selected(2); self.zoom.set_size_request(80,32)
        self.zoom.connect('notify::selected',lambda c,p:self.zoom_changed()); tools.append(self.zoom); self.targets['zoom']=self.zoom
        tools.append(button('Centre',lambda:self.viewport.centre() if self.viewport else None))
        restart=button('',lambda:self.start_preview(force=True),'reload.svg',width=32); restart.set_tooltip_text('Restart app'); tools.append(restart)
        self.overlay.add_overlay(tools)
        self.preview_label=label('','small muted',True); self.preview_label.set_halign(Gtk.Align.CENTER); self.preview_label.set_valign(Gtk.Align.CENTER); self.preview_label.set_can_target(False)
        self.overlay.add_overlay(self.preview_label)
        self.build_tools=box(spacing=8,css='tools'); self.build_tools.set_halign(Gtk.Align.CENTER); self.build_tools.set_valign(Gtk.Align.END); self.build_tools.set_margin_bottom(16)
        self.tool_buttons={}
        for tool,title,icon,width in [('draw','✎  Draw',None,80),('comment','Comment','arrow.svg',104)]:
            item=button(title,lambda t=tool:self.set_tool(t),icon,width=width)
            self.tool_buttons[tool]=item; self.build_tools.append(item)
        self.undo_button=button('↶  Undo',lambda:self.service.send('undo'),width=80); self.build_tools.append(self.undo_button); self.targets['undo']=self.undo_button
        self.overlay.add_overlay(self.build_tools); self.panes.set_start_child(self.overlay); self.panes.set_resize_start_child(True); self.panes.set_shrink_start_child(False)
        self.chat=box(True,0,'chat'); self.chat.set_size_request(CHAT_MIN,-1)
        self.targets['chat-panel']=self.chat
        chat=margins(box(True,16),24); chat.set_vexpand(True); self.chat.append(chat)
        heading=box(True,8); heading.append(label('Chat','chat-heading'))
        self.chat_status=label('Connecting…','chat-status muted'); self.chat_status.set_ellipsize(Pango.EllipsizeMode.END); heading.append(self.chat_status)
        chat.append(heading); chat.append(Gtk.Separator())
        self.chat_scroll=Gtk.ScrolledWindow(vexpand=True,hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.messages=box(True,24); self.chat_scroll.set_child(self.messages)
        message_overlay=Gtk.Overlay(vexpand=True); message_overlay.set_child(self.chat_scroll)
        self.empty_chat=box(True,16); self.empty_chat.set_halign(Gtk.Align.FILL); self.empty_chat.set_valign(Gtk.Align.CENTER)
        self.empty_chat.append(label('Start with a conversation.','empty-heading',True))
        self.empty_chat.append(label('Talk to each other here. When you’re ready for help, mention @centaur.','message',True))
        self.empty_chat.append(label('Sketch on the canvas or point with Comment. Your marks accompany the next request to the agent.','message muted',True))
        message_overlay.add_overlay(self.empty_chat); chat.append(message_overlay)
        self.busy=box(spacing=8,css='busy'); self.busy_text=label('Centaur is working…','chat-status muted'); self.busy_text.set_hexpand(True); self.busy.append(self.busy_text)
        self.stop_button=button('Stop',lambda:self.service.send('cancel'),tone='plain'); self.busy.append(self.stop_button); chat.append(self.busy); self.busy.set_visible(False)
        self.proposal=box(True,8,'proposal'); chat.append(self.proposal); self.proposal.set_visible(False)
        self.editor=Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR,accepts_tab=False); self.editor.add_css_class('message'); self.targets['editor']=self.editor
        key=Gtk.EventControllerKey(); key.set_propagation_phase(Gtk.PropagationPhase.CAPTURE); key.connect('key-pressed',self.editor_key); self.editor.add_controller(key)
        row=box(spacing=8); self.mention=button('@centaur',self.insert_mention,tone='plain'); row.append(self.mention)
        spacer=box(); spacer.set_hexpand(True); row.append(spacer)
        self.send_button=button('',self.send,'comment-enter-active.svg',tone='dark',width=32,icon_size=24); self.send_button.set_tooltip_text('Send message'); row.append(self.send_button); self.targets['send']=self.send_button
        self.composer=Composer(self.editor,row); chat.append(self.composer)
        self.targets['composer']=self.composer
        self.editor.get_buffer().connect('changed',lambda b:self.update_send())
        footer=box(spacing=8); self.footer=label('','chat-time muted'); self.footer.set_hexpand(True); self.footer.set_ellipsize(Pango.EllipsizeMode.END)
        footer.append(self.footer); self.version_label=label('v'+self.version(),'version muted'); footer.append(self.version_label); chat.append(footer)
        footer_click=Gtk.GestureClick(); footer_click.connect('released',lambda g,n,x,y:self.navigate('settings')); self.footer.add_controller(footer_click); self.footer.set_cursor_from_name('pointer')
        self.panes.set_end_child(self.chat); self.panes.set_resize_end_child(False); self.panes.set_shrink_end_child(False)
        self.stack.add_named(wrapper,'workspace'); self.set_tool('draw'); self.initial_pane=True

    @staticmethod
    def version(): return '0.4.0-preview+'+os.environ.get('CENTAUR_GTK4_BUILD_ID','dev')

    def save_name(self):
        text=self.name.get_text().strip()
        if hasattr(self,'service') and text and text!=self.data.get('author') and not self.data.get('remote'): self.service.send('author',name=text)

    def save_agent_name(self):
        text=self.agent_name_button.get_text().strip()
        if hasattr(self,'service') and text and self.project and text!=self.project.get('agentName') and not self.data.get('remote'): self.service.send('agentName',name=text)

    def open_repo(self):
        if self.data.get('sourcePath'): Gio.AppInfo.launch_default_for_uri(Path(self.data['sourcePath']).parent.as_uri(),None)

    def restart_app(self):
        if self.project:
            self.navigate('workspace'); GLib.idle_add(lambda:self.start_preview(force=True))

    def insert_mention(self):
        buffer=self.editor.get_buffer(); buffer.insert_at_cursor('@'+self.project.get('agentName','centaur')+' '); self.editor.grab_focus()

    def update_send(self):
        buffer=self.editor.get_buffer(); text=buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),False)
        self.send_button.set_sensitive(bool(text.strip()) and self.data.get('connected',False) and self.pending_message is None)

    @staticmethod
    def clear(widget):
        while widget.get_first_child():
            widget.remove(widget.get_first_child())

    def navigate(self,page):
        self.page=page
        self.stack.set_visible_child_name(page)
        for key,item in self.nav.items():
            selected(item,key==page)
        workspace=page=='workspace'
        self.top_start.set_margin_start(24 if workspace else 0)
        self.sidebar.set_visible(not workspace); self.modes.set_visible(workspace)
        for item in (self.workspace_brand,self.projects_crumb,self.breadcrumb_arrow,self.breadcrumb,self.invite_button,self.deploy_button): item.set_visible(workspace)
        self.page_title.set_visible(not workspace); self.page_title.set_text({'projects':'Projects','systems':'Design Systems','settings':'Settings'}.get(page,''))
        self.join_button.set_visible(page=='projects'); self.create_button.set_visible(page=='projects'); self.import_button.set_visible(page=='systems')
        self.targets['nav-projects']=self.projects_crumb if workspace else self.nav['projects']
        self.window.set_size_request(1000 if workspace else 360,680)
        if workspace:
            GLib.idle_add(self.start_preview)
        else:
            self.stop_preview()

    def set_mode(self,mode):
        self.mode=mode
        for key,item in self.mode_buttons.items():
            selected(item,key==mode)
        self.build_tools.set_visible(mode=='Build')
        self.ink.set_can_target(mode=='Build')

    def set_tool(self,tool):
        self.tool=tool
        for key,item in self.tool_buttons.items():
            selected(item,key==tool)

    def receive(self,data):
        if data.get('type')=='error':
            self.pending_message=None; self.update_send()
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
        self.join_progress.set_visible(data.get('joining',False))
        if hasattr(self,'join_submit'): self.update_join()
        self.cancel_join.set_visible(data.get('joining',False))
        self.agent_name_button.set_sensitive(bool(self.project) and not data.get('remote',False))
        self.stop_sharing_button.set_visible(bool(self.project.get('sharing',{}).get('enabled')) and not data.get('remote',False))
        self.profile_name.set_text(data.get('author','Your settings')); self.profile_avatar.set_text(data.get('author','?')[:1].upper())
        if not self.name.get_state_flags() & Gtk.StateFlags.FOCUS_WITHIN: self.name.set_text(data.get('author',''))
        self.name.set_sensitive(not data.get('remote',False))
        self.agent_detail.set_text('OMP is available' if data.get('agentAvailable') else 'OMP is not connected')
        self.agent_path.set_text('OMP runs on the project host.' if data.get('remote') else data.get('agentExecutable') or 'Launch Centaur with your OMP executable configured.')
        self.agent_model.set_text(data.get('agentModel') or 'The model is reported after an agent request.')
        for widget in (self.agent_name_caption,self.agent_name_button,self.project_settings_actions,self.back_to_app): widget.set_visible(bool(self.project))
        for widget in (self.open_repo_button,self.archive_button): widget.set_visible(not data.get('remote',False))
        if not self.agent_name_button.get_state_flags() & Gtk.StateFlags.FOCUS_WITHIN: self.agent_name_button.set_text(self.project.get('agentName','centaur'))
        self.sync_grid()
        key=json.dumps(data.get('projects',[]),sort_keys=True)
        if self.project_key!=key:
            self.project_key=key; self.refresh_cards()
        if self.project:
            if old_id!=self.project['id'] or self.open_id==self.project['id']:
                self.open_id=None; self.navigate('workspace')
            self.breadcrumb.set_text(self.project.get('name',''))
            model=data.get('agentModel','')
            model=model.replace('openai-codex/','OpenAI Codex · ').replace('gpt-','GPT ').replace('-',' ').replace(' sol',' Sol')
            status=data.get('status','')
            self.chat_status.set_text(status+' · '+(model or 'Model not reported yet') if data.get('agentAvailable') else status+' · Agent unavailable')
            button_text(self.mention,'@'+self.project.get('agentName','centaur'))
            self.composer.placeholder.set_text('Message, or ask @'+self.project.get('agentName','centaur'))
            self.busy.set_visible(data.get('busy',False)); self.update_send()
            queued=self.project.get('queueCount',0)
            self.busy_text.set_text(self.project.get('agentName','centaur').capitalize()+' is working…'+(' · '+str(queued)+' queued' if queued else ''))
            footer='Chatting as '+data.get('author','')+' · Shift + Enter for a new line'
            self.footer.set_text(footer); self.footer.set_tooltip_text(footer)
            remote=data.get('remote',False); button_text(self.invite_button,'Shared' if remote else 'Invite'); self.invite_button.set_sensitive(not remote)
            self.undo_button.set_sensitive(any(a.get('author')==data.get('author') and a.get('revision')==self.project.get('revision') for a in self.project.get('annotations',[])))
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
        if hasattr(self,'join_dialog') and self.join_dialog.get_visible():
            self.join_feedback.set_text(data.get('joinStatus',''))
            if data.get('remote') and data.get('connected'): self.dismiss_dialog(self.join_dialog)

    def refresh_cards(self):
        self.cards.clear()
        for key in list(self.targets):
            if key.startswith(('open-','menu-')): del self.targets[key]
        projects=self.data.get('projects',[])
        self.empty_projects.set_visible(not projects)
        for project in projects:
            card=Gtk.Overlay(); open_button=Gtk.Button(); open_button.add_css_class('project-card')
            open_button.connect('clicked',lambda b,p=project:self.open_project(p['id']))
            content=box(True,16)
            badge=label(project['name'][:1].upper(),'project-badge'); badge.set_xalign(.5); badge.set_size_request(56,56); badge.set_halign(Gtk.Align.START); content.append(badge)
            text=box(True,8); title=label(project['name'],'project-title'); title.set_ellipsize(Pango.EllipsizeMode.END); text.append(title)
            description=label(project.get('description') or 'A new idea, ready to take shape.','project-description muted',True)
            description.set_lines(2); description.set_ellipsize(Pango.EllipsizeMode.END); text.append(description); content.append(text)
            spacer=box(); spacer.set_vexpand(True); content.append(spacer); content.append(Gtk.Separator())
            content.append(label(('Shared project' if project.get('connected') else 'Shared · host unavailable') if project.get('remote') else 'Native app','project-meta muted'))
            open_button.set_child(content); card.set_child(open_button)
            menu=Gtk.MenuButton(); menu.add_css_class('meatball'); menu.set_tooltip_text('Project options')
            menu.set_child(Svg('tile-menu.svg',24)); menu.set_size_request(32,32); menu.set_halign(Gtk.Align.END); menu.set_valign(Gtk.Align.START)
            menu.set_margin_top(24); menu.set_margin_end(16)
            pop=Gtk.Popover(has_arrow=False,position=Gtk.PositionType.BOTTOM); pop.add_css_class('project-menu'); actions=box(True,0)
            def action(callback,popover=pop): popover.popdown(); callback()
            rename=button('Rename',lambda p=project,a=action:a(lambda:self.rename(p)),tone='plain',height=40)
            rename.get_child().set_halign(Gtk.Align.START); rename.set_sensitive(not project.get('remote',False)); actions.append(rename)
            delete=button('Leave project' if project.get('remote') else 'Delete',lambda p=project,a=action:a(lambda:self.delete(p)),tone='plain',height=40)
            delete.get_child().set_halign(Gtk.Align.START); actions.append(delete)
            self.targets['menu-rename-'+project['id']]=rename; self.targets['menu-delete-'+project['id']]=delete
            pop.set_child(actions); menu.set_popover(pop); card.add_overlay(menu)
            self.targets['open-'+project['id']]=open_button
            self.targets['menu-'+project['id']]=menu
            self.cards.append(card)

    def refresh_messages(self):
        self.clear(self.messages)
        self.empty_chat.set_visible(not self.project.get('messages'))
        for message in self.project.get('messages',[]):
            item=box(True,8); head=box(spacing=8)
            author=message.get('author','')
            agent=message.get('kind')!='human'
            if agent:
                author=author.lstrip('@')
                if author.lower()=='centaur': author='Centaur'
            avatar=label(author[:1].upper(),'avatar agent' if agent else 'avatar'); avatar.set_xalign(.5); avatar.set_size_request(24,24); head.append(avatar)
            self.targets['chat-avatar']=avatar
            name=label(author,'chat-name'); name.set_hexpand(True); name.set_ellipsize(Pango.EllipsizeMode.END); head.append(name)
            try: time=datetime.fromisoformat(message['time'].replace('Z','+00:00')).astimezone().strftime('%H:%M')
            except (KeyError,ValueError): time=''
            head.append(label(time,'chat-time muted')); item.append(head)
            text=message.get('text','')
            if message.get('kind')=='agent' and re.fullmatch(r'Applied the (agreed )?change\. Revision \d+ is ready to try\.',text): text='Updated the app.'
            body=label(text,'message muted' if message.get('kind')=='system' else 'message',True); body.set_selectable(True)
            self.chat_body=body
            item.append(body); self.messages.append(item)
        def bottom():
            adj=self.chat_scroll.get_vadjustment(); adj.set_value(max(0,adj.get_upper()-adj.get_page_size())); return False
        GLib.idle_add(bottom)

    def refresh_proposal(self):
        self.clear(self.proposal)
        proposal=self.project.get('proposal',{})
        conflict=proposal.get('conflict')
        if isinstance(conflict,dict):
            self.proposal.append(label('Resolve conflicting requests','chat-name',True))
            self.proposal.append(label(conflict.get('reason','Agreement needed'),'chat-name',True))
            authors=proposal.get('authors',[]); accepted=proposal.get('accepted',[])
            for author in authors: self.proposal.append(label(('✓  ' if author in accepted else '○  ')+author,'chat-name'))
            agree=button('Agree to compromise',lambda:self.service.send('accept'),tone='dark')
            agree.set_sensitive(self.data.get('author') in authors and self.data.get('author') not in accepted and not self.data.get('busy'))
            self.proposal.append(agree); self.targets['accept']=agree
            self.proposal.append(label('Only people whose requests conflict need to agree.','small muted',True))
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
                    snapshot=Gtk.Snapshot.new()
                    width,height=self.overlay.get_width(),self.overlay.get_height()
                    snapshot.append_color(Gdk.RGBA(red=1,green=1,blue=1,alpha=1),Graphene.Rect().init(0,0,width,height))
                    # Canvas controls now float over the preview. Keep them out
                    # of agent context, just as when they lived outside it.
                    for layer in (self.preview_holder,self.ink):
                        Gtk.WidgetPaintable.new(layer).snapshot(snapshot,width,height)
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

    def dialog(self,title,width=424):
        if self.active_form: self.dismiss_dialog(self.active_form)
        dialog=Gtk.Window(title=title,transient_for=self.window,modal=True,decorated=False,default_width=width,resizable=False)
        dialog.add_css_class('dialog'); self.active_form=dialog; self.modal_shade.set_visible(True)
        content=box(True,16,'dialog-card'); content.append(label(title,'dialog-title',True)); dialog.set_child(content)
        dialog.connect('notify::visible',lambda d,p:self.modal_shade.set_visible(False) if not d.get_visible() and self.active_form is d else None)
        key=Gtk.EventControllerKey()
        def escape(c,keyval,keycode,state):
            if keyval==Gdk.KEY_Escape:
                if dialog is getattr(self,'join_dialog',None): self.service.send('cancelJoin')
                self.dismiss_dialog(dialog); return True
            return False
        key.connect('key-pressed',escape); dialog.add_controller(key)
        return dialog,content

    def dismiss_dialog(self,dialog):
        dialog.destroy()
        if self.active_form is dialog: self.active_form=None; self.modal_shade.set_visible(False)

    def form(self,title,fields,submit,action='Save',width=400):
        dialog,content=self.dialog(title,width); entries={}
        for key,caption,value in fields:
            content.append(label(caption)); entry=Gtk.Entry(text=value); entry.set_size_request(-1,40); entries[key]=entry; content.append(entry)
        def done():
            values={key:entry.get_text() for key,entry in entries.items()}
            if all(value.strip() for value in values.values()): submit(values); self.dismiss_dialog(dialog)
        row=box(spacing=8); row.set_halign(Gtk.Align.END)
        row.append(button('Cancel',lambda:self.dismiss_dialog(dialog),tone='plain'))
        save=button(action,done,tone='dark'); row.append(save); content.append(row)
        def valid(e): save.set_sensitive(all(e.get_text().strip() for e in entries.values()))
        for entry in entries.values(): entry.connect('activate',lambda e:done()); entry.connect('changed',valid)
        valid(None); dialog.present(); first=next(iter(entries.values())); first.grab_focus(); first.select_region(0,-1)

    def open_project(self,project_id):
        self.open_id=project_id; self.service.send('open',projectId=project_id)

    def new_project(self):
        dialog,content=self.dialog('Make something together',464); content.add_css_class('new-project-dialog')
        content.append(label('One project, one native app.','project-description muted',True))
        name=Gtk.Entry(placeholder_text='Project name',max_length=100); name.add_css_class('new-project-field'); name.set_size_request(-1,40); content.append(name)
        description=Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR,accepts_tab=False); description.add_css_class('new-project-field')
        content.append(self.text_field(description,'What would you like to make?',css='new-project-description'))
        row=box(spacing=8); row.set_halign(Gtk.Align.END)
        row.append(button('Cancel',lambda:self.dismiss_dialog(dialog),tone='plain'))
        def done():
            if name.get_text().strip():
                buffer=description.get_buffer(); text=buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),False)
                self.service.send('create',name=name.get_text(),description=text); self.dismiss_dialog(dialog)
        create=button('Create project',done,tone='dark'); create.set_sensitive(False); row.append(create); content.append(row)
        name.connect('changed',lambda e:create.set_sensitive(bool(e.get_text().strip())))
        name.connect('activate',lambda e:done())
        dialog.present(); name.grab_focus()

    def rename(self,project):
        self.form('Rename project',[('name','Project name',project['name'])],lambda v:self.service.send('rename',projectId=project['id'],name=v['name']))

    def delete(self,project):
        leave=project.get('remote',False)
        self.notice('Leave project?' if leave else 'Delete project?',
                    'Leave '+project['name']+' on this device?' if leave else 'Delete '+project['name']+'? Its files and conversation will be moved to the recovery folder.',
                    lambda:self.service.send('leave' if leave else 'delete',projectId=project['id']), 'Leave' if leave else 'Delete')

    def notice(self,title,text,confirm=None,action='OK'):
        dialog,content=self.dialog(title)
        content.append(label(text,None,True)); row=box(spacing=8); row.set_halign(Gtk.Align.END)
        cancel=button('Cancel',lambda:self.dismiss_dialog(dialog),tone='plain')
        if confirm: row.append(cancel)
        def done():
            if confirm: confirm()
            self.dismiss_dialog(dialog)
        row.append(button(action,done,tone='dark')); content.append(row); dialog.present()
        if confirm: cancel.grab_focus()

    def join(self):
        dialog,content=self.dialog('Join project',480); self.join_dialog=dialog
        name=Gtk.Entry(text=self.data.get('author',''),placeholder_text='Your name',max_length=50); name.set_size_request(-1,40); content.append(name)
        self.join_name=name
        invitation=Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR,accepts_tab=False); invitation.add_css_class('small')
        self.join_code=invitation
        content.append(self.text_field(invitation,'Paste the invitation code'))
        content.append(label('Only join people you trust. The shared native app runs on this device. You don’t need to set up OMP to participate.','small muted',True))
        self.join_feedback=label('','small muted',True); content.append(self.join_feedback)
        def done():
            buffer=invitation.get_buffer(); code=buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),False)
            if name.get_text().strip() and code.strip() and not self.data.get('joining'): self.service.send('join',name=name.get_text(),code=code)
        row=box(spacing=8); row.set_halign(Gtk.Align.END)
        row.append(button('Cancel',lambda:(self.service.send('cancelJoin'),self.dismiss_dialog(dialog)),tone='plain'))
        self.join_submit=button('Join project',done,tone='dark'); row.append(self.join_submit); content.append(row)
        name.connect('changed',lambda e:self.update_join()); invitation.get_buffer().connect('changed',lambda b:self.update_join()); self.update_join()
        key=Gtk.EventControllerKey(); key.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key.connect('key-pressed',lambda c,k,code,state:(done(),True)[1] if k in (Gdk.KEY_Return,Gdk.KEY_KP_Enter) and not state&Gdk.ModifierType.SHIFT_MASK else False)
        invitation.add_controller(key); dialog.present(); name.grab_focus(); name.select_region(0,-1)

    def invite(self):
        dialog,content=self.dialog('Invite people',504); self.invite_dialog=dialog
        content.append(label('Invite people nearby or on another network. Keep this computer awake; sharing continues when you close its Centaur window.',None,True))
        row=box(spacing=8); caption=label('Local network only'); caption.set_hexpand(True); row.append(caption)
        address=Gtk.Entry(text=self.data.get('localAddress',''),placeholder_text='192.168.1.10'); address.set_size_request(-1,40); address.set_visible(False)
        local=Switch(False,lambda active:address.set_visible(active)); row.append(local); content.append(row); content.append(address)
        self.invite_create=button('Create invitation',lambda:self.service.send('invite',address=address.get_text() if local.get_active() else 'iroh'),tone='dark')
        self.invite_create.set_halign(Gtk.Align.START); content.append(self.invite_create)
        self.invite_result=box(True,16); content.append(self.invite_result)
        members=self.project.get('sharing',{}).get('members',[])
        if members: content.append(label('Members: '+', '.join(members),'small muted',True))
        row=box(spacing=8)
        if self.project.get('sharing',{}).get('enabled'): row.append(button('Stop sharing',lambda:(self.service.send('stopSharing'),self.dismiss_dialog(dialog))))
        spacer=box(); spacer.set_hexpand(True); row.append(spacer); row.append(button('Done',lambda:self.dismiss_dialog(dialog),tone='plain')); content.append(row)
        dialog.present(); self.invitation_dialog(self.data.get('invitation',''))

    def update_join(self):
        joining=self.data.get('joining',False); self.join_name.set_sensitive(not joining); self.join_code.set_sensitive(not joining)
        buffer=self.join_code.get_buffer(); text=buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),False)
        self.join_submit.set_sensitive(not joining and bool(self.join_name.get_text().strip()) and bool(text.strip()))
        button_text(self.join_submit,'Connecting…' if joining else 'Join project')

    @staticmethod
    def text_field(view,placeholder,css='text-field'):
        field=Gtk.Overlay(); field.add_css_class(css); field.set_size_request(-1,104)
        scroll=Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER); scroll.set_child(view); field.set_child(scroll)
        hint=label(placeholder,'muted',True); hint.set_halign(Gtk.Align.START); hint.set_valign(Gtk.Align.START); hint.set_can_target(False)
        field.add_overlay(hint); view.get_buffer().connect('changed',lambda buffer:hint.set_visible(not buffer.get_char_count()))
        return field

    def invitation_dialog(self,code):
        if not hasattr(self,'invite_dialog') or not self.invite_dialog.get_visible(): return
        self.clear(self.invite_result)
        if not code: return
        self.invite_result.append(label('Send this code to one person. It can be used once and expires in 20 minutes.','small muted',True))
        text=Gtk.TextView(editable=False,wrap_mode=Gtk.WrapMode.WORD_CHAR); text.add_css_class('small'); text.get_buffer().set_text(code)
        field=Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER); field.add_css_class('text-field'); field.set_size_request(-1,104); field.set_child(text); self.invite_result.append(field)
        copy=button('Copy invitation',lambda:self.window.get_display().get_clipboard().set(code)); copy.set_halign(Gtk.Align.START); self.invite_result.append(copy)

    def send_grid(self,**fields):
        if getattr(self,'syncing_grid',False) or not hasattr(self,'service'): return
        values=dict(self.data.get('grid',{})); values.update(fields); self.service.send('grid',**values)

    def toggle_grid(self): self.send_grid(enabled=not self.data.get('grid',{}).get('enabled',False))

    def grid_controls(self,content):
        controls={}
        def row(caption,widget):
            line=box(spacing=16); text=label(caption); text.set_hexpand(True); line.append(text); line.append(widget); content.append(line)
        controls['enabled']=Switch(False,lambda value:self.send_grid(enabled=value)); row('Show grid',controls['enabled'])
        colour=button('#BAE6FF',self.grid_colour,width=112); controls['colour']=colour; colour.centaur_label.add_css_class('colour-label')
        swatch=Gtk.DrawingArea(content_width=16,content_height=16,valign=Gtk.Align.CENTER)
        def draw(area,cr,width,height):
            color=Gdk.RGBA(); color.parse(self.data.get('grid',{}).get('color','#BAE6FF'))
            cr.set_source_rgba(color.red,color.green,color.blue,1); cr.rectangle(0,0,width,height); cr.fill()
            cr.set_source_rgb(.9,.91,.9); cr.set_line_width(1); cr.rectangle(.5,.5,width-1,height-1); cr.stroke()
        swatch.set_draw_func(draw); colour.get_child().prepend(swatch); controls['swatch']=swatch; row('Grid colour',colour)
        controls['size']=Stepper(8,2,64,lambda value:self.send_grid(size=value)); size=box(spacing=8); size.append(controls['size']); size.append(label('pt','small muted')); row('Grid point size',size)
        opacity=Gtk.DropDown.new_from_strings([str(n)+'%' for n in range(0,101,10)]); opacity.set_size_request(128,40); opacity.set_selected(5)
        opacity.connect('notify::selected',lambda w,p:self.send_grid(opacity=w.get_selected()*10)); controls['opacity']=opacity; row('Grid opacity',opacity)
        content.append(label('Saved on this device. The grid is aligned with the native app.','small muted',True)); return controls

    def sync_grid(self):
        values=self.data.get('grid',{}); self.syncing_grid=True
        selected(self.grid_button,values.get('enabled',False))
        for controls in (self.settings_grid,getattr(self,'popup_grid',{})):
            if not controls: continue
            controls['enabled'].set_active(values.get('enabled',False)); controls['size'].set_value(values.get('size',8))
            controls['opacity'].set_selected(round(values.get('opacity',50)/10)); button_text(controls['colour'],values.get('color','#BAE6FF').upper())
            controls['swatch'].queue_draw()
        self.syncing_grid=False

    def grid_colour(self):
        dialog=Gtk.ColorDialog(title='Grid colour',with_alpha=False); color=Gdk.RGBA(); color.parse(self.data.get('grid',{}).get('color','#BAE6FF'))
        def done(dialog,result):
            try:
                value=dialog.choose_rgba_finish(result)
                self.send_grid(color='#'+''.join(f'{round(channel*255):02x}' for channel in (value.red,value.green,value.blue)))
            except GLib.Error: pass
        dialog.choose_rgba(self.window,color,None,done)

    def grid_settings(self):
        dialog,content=self.dialog('Canvas grid',400); self.popup_grid=self.grid_controls(content); self.sync_grid()
        done=button('Done',lambda:self.dismiss_dialog(dialog),tone='plain'); done.set_halign(Gtk.Align.END); content.append(done); dialog.present()

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
                if not self.backend.widget.get_realized() or self.backend.widget.get_width()!=bundle['width']+192 or self.backend.widget.get_height()!=bundle['height']+192:
                    return True
                try:
                    self.viewport.set_zoom(ZOOM_MODES[self.zoom.get_selected()])
                    self.backend.start(AppSpec((os.environ['CENTAUR_GTK_RUNNER'],str(path)),bundle['width'],bundle['height']),runtime,self.child_report)
                    self.preview_status='Connecting native app…'
                except Exception as error: self.preview_status='Could not launch app: '+str(error)
                return False
            GLib.timeout_add(16,launch)
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
            colour=Gdk.RGBA(); colour.parse(grid.get('color','#BAE6FF'))
            step=max(2,grid.get('size',8)*scale); cr.set_source_rgba(colour.red,colour.green,colour.blue,grid.get('opacity',50)/100); cr.set_line_width(.7)
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
        # Preserve the reference breakpoints and the chat width on window resize.
        compact=self.window.get_width()<760
        self.sidebar.set_size_request(COMPACT_SIDEBAR if compact else SIDEBAR,-1)
        (self.sidebar.add_css_class if compact else self.sidebar.remove_css_class)('compact')
        for item in self.nav_labels: item.set_visible(not compact)
        self.profile_text.set_visible(not compact)
        button_text(self.create_button,'+ New' if self.window.get_width()<600 else '+ New project')
        self.projects_inner.set_margin_top(24 if self.stack.get_width()<720 else 40)
        for edge in ('bottom','start','end'): getattr(self.projects_inner,'set_margin_'+edge)(self.projects_inner.get_margin_top())
        setting_margin=24 if self.stack.get_width()<600 else 40
        margins(self.settings_inner,setting_margin); self.settings_limit.maximum=640+2*setting_margin
        if self.page=='workspace' and self.panes.get_width()>0:
            available=self.panes.get_width()-8
            if self.initial_pane:
                self.panes.set_position(available-CHAT_WIDTH); self.initial_pane=False
            elif self.chat.get_width()>CHAT_MAX: self.panes.set_position(available-CHAT_MAX)
        if hasattr(self,'invite_create'):
            self.invite_create.set_sensitive(not self.data.get('inviting',False)); button_text(self.invite_create,'Preparing invitation…' if self.data.get('inviting') else 'Create invitation')
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
            data['layout']={'sidebarVisible':self.sidebar.get_visible(),'sidebarWidth':self.sidebar.get_width(),
                            'chatWidth':self.chat.get_width(),'tileColumns':__import__('ui').columns(self.cards.get_width()),'gridWidth':self.cards.get_width(),
                            'bodyFont':self.chat_body.get_pango_context().get_font_description().to_string() if hasattr(self,'chat_body') else None,
                            'statusFont':self.chat_status.get_pango_context().get_font_description().to_string(),
                            'headerText':self.chat_status.get_text()}
            try: data['child']=json.loads(self.child_report.read_text()) if self.backend else None
            except (AttributeError,FileNotFoundError,ValueError): data['child']=None
            for name,widget in self.targets.items():
                if not widget.get_mapped(): continue
                ok,r=widget.compute_bounds(self.window)
                if ok: data['targets'][name]=[r.get_x(),r.get_y(),r.get_width(),r.get_height()]
            target=self.reports/'shell.json'; target.with_suffix('.tmp').write_text(json.dumps(data)); target.with_suffix('.tmp').replace(target)
        return True

    def close(self):
        if self.closing: return False
        self.closing=True; self.stop_preview()
        if hasattr(self,'service'): self.service.close()
        self.composer.release(); self.cards.clear(); self.settings_limit.release(); self.empty_limit.release()
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
