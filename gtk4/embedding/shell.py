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
from annotations import AnnotationSpace, position as annotation_position
from comment_pointer import CommentPointer,paint_arrow
from update_ui import UpdateControls
from desktop import APP_ID, launch_settings, register as register_desktop
from import_ui import show_import
from agent_activity import caption as activity_caption, details_text as activity_details
from ui import (ASSETS, SIDEBAR, COMPACT_SIDEBAR, HEADER, CHAT_WIDTH, CHAT_MIN,
                CHAT_MAX, Svg, original, picture, close_art, send_art, ProjectGrid, Composer, Stepper, Switch, WidthLimit, Modal, ZoomMenu,
                label, box, margins, button, button_text, selected, accessible)


class Centaur(Gtk.Application):
    def __init__(self, root, report_dir=None, update_session=None):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.root = root
        self.reports = report_dir
        self.update_session = update_session
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
        self.comment=CommentPointer(); self.pointer_position=None; self.comment_geometry=None

    def do_activate(self):
        icons=Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        icons.add_search_path(str(Path(os.environ['CENTAUR_GTK_PACKAGE'])/'share/icons'))
        Gtk.Window.set_default_icon_name(APP_ID)
        provider = Gtk.CssProvider()
        provider.load_from_path(str(Path(__file__).with_name('shell.css')))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.window = Gtk.ApplicationWindow(application=self, title='Centaur', default_width=1440, default_height=1024,decorated=True)
        self.window.add_css_class('centaur-window')
        self.window.set_icon_name(APP_ID)
        self.window.set_size_request(360, 680)
        self.native_pointer=None; self.native_pointer_serial=0
        if self.reports:
            native_motion=Gtk.EventControllerMotion(propagation_phase=Gtk.PropagationPhase.CAPTURE)
            def report_pointer(controller,x,y):
                self.native_pointer=(x,y); self.native_pointer_serial+=1
            native_motion.connect('motion',report_pointer); self.window.add_controller(native_motion)
            native_motion.connect('enter',report_pointer)
        self.root_overlay = Gtk.Overlay()
        self.root_overlay.add_css_class('centaur-content')
        self.root_overlay.set_overflow(Gtk.Overflow.HIDDEN)
        motion=Gtk.EventControllerMotion(); motion.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        motion.connect('motion',self.pointer_motion); self.root_overlay.add_controller(motion)
        place=Gtk.GestureClick(button=1); place.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        place.connect('pressed',self.place_comment); self.root_overlay.add_controller(place)
        escape=Gtk.EventControllerKey(); escape.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        escape.connect('key-pressed',self.comment_key); self.root_overlay.add_controller(escape)
        root = box(spacing=0); self.root_overlay.set_child(root)
        self.sidebar = box(True, 0, 'sidebar'); self.sidebar.set_size_request(SIDEBAR, -1)
        self.nav = {}; self.nav_labels = []
        links = box(True, 8); links.set_margin_top(40); links.set_margin_start(24); links.set_margin_end(24)
        self.links=links
        for key, title, icon in [('projects','Projects','v2/bab90.svg'),('systems','Design systems','v2/4f431.svg'),('settings','Settings','v2/2adf1.svg')]:
            item = button(title, lambda k=key:self.navigate(k), icon, 'navigation', tone='plain', height=32, icon_size=16)
            row=item.get_child(); row.set_halign(Gtk.Align.START)
            icon=item.centaur_image; row.remove(icon); slot=box(spacing=0); slot.set_size_request(32,32); slot.set_halign(Gtk.Align.CENTER); slot.append(icon); row.prepend(slot)
            self.nav[key] = item; self.nav_labels.append(item.centaur_label); self.targets['sidebar-'+key] = item
            self.targets['nav-'+key] = item; links.append(item)
        self.sidebar.append(links)
        spacer = box(); spacer.set_vexpand(True); self.sidebar.append(spacer)
        self.identity = button('', lambda:self.navigate('settings'), css='profile', tone='plain', height=88)
        profile = box(spacing=16); profile.set_valign(Gtk.Align.CENTER)
        self.profile_avatar = Gtk.Overlay(css_classes=['profile-avatar']); self.profile_avatar.set_size_request(40,40); self.profile_avatar.set_overflow(Gtk.Overflow.HIDDEN)
        self.profile_avatar.set_child(picture(ASSETS/'v2/dc3c7.png',40))
        profile.append(self.profile_avatar)
        self.profile_text = box(True, 8); self.profile_name = label('', 'nav-label'); self.profile_name.set_ellipsize(Pango.EllipsizeMode.END)
        self.profile_text.append(self.profile_name); self.profile_text.append(label('This device', 'small muted')); profile.append(self.profile_text)
        self.identity.set_child(profile); self.sidebar.append(self.identity); root.append(self.sidebar)
        content = box(True,0); content.set_hexpand(True)
        self.top = Gtk.CenterBox(); self.top.add_css_class('topbar'); self.top.set_size_request(-1,HEADER)
        self.top_start = box(spacing=8); self.top_start.set_margin_start(24); self.top_start.set_valign(Gtk.Align.CENTER)
        self.workspace_brand = button('',lambda:self.navigate('projects'),'v2/d9e08.svg','brand',tone='plain',width=32,icon_size=32)
        accessible(self.workspace_brand,'Projects'); self.top_start.append(self.workspace_brand)
        self.projects_crumb = button('Projects',lambda:self.navigate('projects'),tone='plain'); self.top_start.append(self.projects_crumb)
        self.breadcrumb_arrow = label('→','breadcrumb muted'); self.top_start.append(self.breadcrumb_arrow)
        self.breadcrumb = label('', 'breadcrumb'); self.breadcrumb.set_ellipsize(Pango.EllipsizeMode.END); self.top_start.append(self.breadcrumb)
        self.top.set_start_widget(self.top_start)
        self.modes = margins(box(spacing=0,css='mode-switch'),0); self.modes.set_valign(Gtk.Align.CENTER)
        self.mode_buttons = {}
        for title,width in [('Interact',64),('Build',72)]:
            item = button(title,lambda t=title:self.set_mode(t),css='mode-button',tone='plain',width=width,height=24)
            self.mode_buttons[title] = item; self.modes.append(item); self.targets['mode-'+title] = item
        # Modes belong to the canvas toolbar below the integrated window header.
        self.targets['mode-switch']=self.modes
        self.top_actions = box(spacing=8); self.top_actions.set_margin_end(24); self.top_actions.set_valign(Gtk.Align.CENTER)
        self.create_menu=box(spacing=0,css='project-create-split'); self.create_menu.set_size_request(96,32)
        create_main=button('Create',self.new_project,css='project-create-main',tone='dark',width=64)
        self.create_menu.append(create_main); self.targets['create-main']=create_main
        create_caption=create_main.centaur_label
        create_caption.set_size_request(39,16); create_main.get_child().set_halign(Gtk.Align.START)
        arrow_menu=Gtk.MenuButton(css_classes=['project-create-arrow']); arrow_menu.set_size_request(32,32)
        accessible(arrow_menu,'Create, import or join a project')
        chevron=original('dd02a.svg',24); arrow_menu.set_child(chevron); self.create_menu.append(arrow_menu)
        create_pop=Gtk.Popover(has_arrow=False,position=Gtk.PositionType.BOTTOM); create_pop.add_css_class('project-menu')
        create_pop.add_css_class('create-project-menu')
        create_pop.set_halign(Gtk.Align.END)
        create_actions=box(True,0)
        def project_action(callback): create_pop.popdown(); callback()
        for key,title,callback in [('create','Create project',self.new_project),('import','Import project',lambda:show_import(self)),('join','Join project',self.join)]:
            action=button(title,lambda cb=callback:project_action(cb),tone='plain',height=24)
            action.get_child().set_halign(Gtk.Align.START); create_actions.append(action); self.targets[key]=action
            self.targets[key+'-option-caption']=action.centaur_label
        create_pop.set_child(create_actions); arrow_menu.set_popover(create_pop)
        create_hover=[False]
        def create_state(*unused):
            opened=create_pop.get_visible()
            chevron.set_from_file(str(ASSETS/'v2'/('15a28.svg' if opened or create_hover[0] else 'dd02a.svg')))
            (chevron.add_css_class if opened else chevron.remove_css_class)('open')
        create_motion=Gtk.EventControllerMotion()
        create_motion.connect('enter',lambda c,x,y:(create_hover.__setitem__(0,True),create_state()))
        create_motion.connect('leave',lambda c:(create_hover.__setitem__(0,False),create_state()))
        self.create_menu.add_controller(create_motion); create_pop.connect('notify::visible',create_state)
        self.top_actions.append(self.create_menu); self.targets['project-menu']=arrow_menu
        self.targets['project-create-split']=self.create_menu
        self.targets.update({'create-caption':create_caption,'create-arrow':chevron,'create-actions':create_actions})
        self.import_button = button('Import',lambda:None,tone='dark'); self.import_button.set_sensitive(False); self.top_actions.append(self.import_button)
        self.invite_button = button('Invite',self.invite,tone='outline',width=62); self.top_actions.append(self.invite_button)
        self.deploy_button = button('Deploy',lambda:self.notice('Deploy','Deployment is planned for a later version.'),tone='dark',width=72); self.top_actions.append(self.deploy_button)
        self.targets.update({'invite':self.invite_button,'deploy':self.deploy_button})
        self.saved_status=box(spacing=8,css='saved-status'); self.saved_status.set_valign(Gtk.Align.CENTER)
        self.saved_status.set_size_request(127,32); self.targets['saved-status']=self.saved_status
        self.saved_status.set_margin_end(52)
        self.saved_tick=original('9ed11.svg',24); self.saved_status.append(self.saved_tick)
        self.saved_caption=label('Changes saved','small'); self.saved_status.append(self.saved_caption); self.top_actions.append(self.saved_status)
        self.window_controls=Gtk.WindowControls(side=Gtk.PackType.END,decoration_layout=':close')
        self.window_controls.set_valign(Gtk.Align.CENTER); self.top_actions.append(self.window_controls)
        self.top.set_end_widget(self.top_actions)
        handle=Gtk.WindowHandle(child=self.top); handle.add_css_class('integrated-header')
        handle.set_overflow(Gtk.Overflow.HIDDEN)
        self.window.set_titlebar(handle)
        # GtkWindowControls retains the real window.close action and platform
        # accessibility/keyboard behaviour; only its supplied artwork changes.
        def style_controls():
            child=self.window_controls.get_first_child()
            while child:
                if isinstance(child,Gtk.Button) and child.has_css_class('close'):
                    child.set_child(close_art()); child.set_tooltip_text(None); accessible(child,'Close'); self.targets['window-close']=child
                child=child.get_next_sibling()
            return False
        GLib.idle_add(style_controls)
        self.stack = Gtk.Stack(hexpand=True,vexpand=True,hhomogeneous=False,vhomogeneous=False)
        self.stack.set_margin_end(8); self.stack.set_margin_bottom(8); content.append(self.stack)
        root.append(content)
        self.error_label = margins(label('','error toast',True),24); self.error_label.set_halign(Gtk.Align.CENTER); self.error_label.set_valign(Gtk.Align.END)
        self.root_overlay.add_overlay(self.error_label); self.error_label.set_visible(False)
        self.window.set_child(self.root_overlay)
        self.build_projects(); self.build_workspace(); self.build_systems(); self.build_settings()
        self.navigate('projects'); self.set_mode('Interact')
        self.window.connect('close-request',lambda w:self.close()); self.window.present()
        self.service = Service(self.root,self.receive)
        os.environ.pop('CENTAUR_UPDATE_STARTING',None)
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
        from settings_ui import SettingsView
        self.settings=SettingsView(self)

    def build_workspace(self):
        wrapper=box(spacing=0); wrapper.set_margin_start(8)
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
        self.canvas_bar=box(spacing=8,css='canvas-bar'); self.canvas_bar.set_size_request(-1,55)
        self.canvas_bar.append(self.modes)
        spacer=box(); spacer.set_hexpand(True); self.canvas_bar.append(spacer)
        restart=button('',lambda:self.start_preview(force=True),'v2/1abf7.svg',tone='plain',width=24,height=24,icon_size=12)
        accessible(restart,'Reload preview'); self.canvas_bar.append(restart); self.targets['reload']=restart
        self.grid_button=button('',self.toggle_grid,'v2/36f8d.svg','grid-toggle',tone='plain',width=24,height=24,icon_size=12)
        accessible(self.grid_button,'Show grid'); self.canvas_bar.append(self.grid_button); self.targets['grid']=self.grid_button
        self.zoom=ZoomMenu(ZOOM_MODES)
        self.zoom.connect('notify::selected',lambda c,p:self.zoom_changed()); self.canvas_bar.append(self.zoom); self.targets['zoom']=self.zoom
        self.preview_label=label('','small muted',True); self.preview_label.set_halign(Gtk.Align.CENTER); self.preview_label.set_valign(Gtk.Align.CENTER); self.preview_label.set_can_target(False)
        self.overlay.add_overlay(self.preview_label)
        from v2_ui import ImportWaiting, WorkingMark, rule
        self.import_working=ImportWaiting(); self.overlay.add_overlay(self.import_working); self.import_working.set_visible(False)
        self.build_tools=box(spacing=8,css='tools'); self.build_tools.set_halign(Gtk.Align.CENTER); self.build_tools.set_valign(Gtk.Align.END); self.build_tools.set_margin_bottom(16)
        self.tool_buttons={}
        for tool,title,icon in [('draw','Draw','v2/3f1c5.svg'),('comment','Comment','v2/e0a15.svg')]:
            item=button('',lambda t=tool:self.set_tool(t),icon,'canvas-tool',width=32)
            accessible(item,title)
            if tool=='comment': item.centaur_image.art_height=15.2939
            self.tool_buttons[tool]=item; self.build_tools.append(item)
            self.targets['tool-'+tool]=item
            self.targets['tool-'+tool+'-icon']=item.centaur_image
        self.undo_button=button('',self.undo,'v2/00bcd.svg','canvas-tool',width=32)
        accessible(self.undo_button,'Undo')
        self.build_tools.append(self.undo_button); self.targets['undo']=self.undo_button; self.targets['build-tools']=self.build_tools
        self.targets['undo-icon']=self.undo_button.centaur_image
        self.overlay.add_overlay(self.build_tools); self.canvas_column=box(True,0,'canvas-panel'); self.canvas_column.set_overflow(Gtk.Overflow.HIDDEN)
        self.canvas_column.append(self.canvas_bar); self.canvas_column.append(rule('2115d.svg')); self.canvas_column.append(self.overlay)
        self.panes.set_end_child(self.canvas_column); self.panes.set_resize_end_child(True); self.panes.set_shrink_end_child(False)
        self.chat=box(True,0,'chat'); self.chat.set_size_request(CHAT_MIN,-1)
        self.targets['chat-panel']=self.chat
        chat=box(True,0); chat.set_vexpand(True); self.chat.append(chat)
        heading=box(spacing=8,css='chat-header'); heading.set_size_request(-1,55); heading.append(label('Chat','chat-heading'))
        self.chat_status=label('Connecting…','chat-status muted'); self.chat_status.set_hexpand(True); self.chat_status.set_xalign(1); self.chat_status.set_ellipsize(Pango.EllipsizeMode.END); heading.append(self.chat_status)
        chat.append(heading)
        divider=rule('50b82.svg'); chat.append(divider)
        self.chat_scroll=Gtk.ScrolledWindow(vexpand=True,hexpand=True,hscrollbar_policy=Gtk.PolicyType.NEVER,
                                          vscrollbar_policy=Gtk.PolicyType.EXTERNAL)
        # V2 chat cards have a 16px gap; text retains its 18px line spacing.
        self.messages=box(True,16); self.messages.set_margin_top(16); self.messages.set_margin_bottom(16)
        self.messages.set_margin_start(16); self.messages.set_margin_end(0); self.chat_scroll.set_child(self.messages)
        scroll_row=box(spacing=0); scroll_row.append(self.chat_scroll)
        self.chat_scrollbar=Gtk.Scrollbar(orientation=Gtk.Orientation.VERTICAL,adjustment=self.chat_scroll.get_vadjustment())
        self.chat_scrollbar.add_css_class('chat-scrollbar'); self.chat_scrollbar.set_margin_top(16); self.chat_scrollbar.set_margin_bottom(16)
        self.chat_scrollbar.set_sensitive(False)
        self.chat_scroll_generation=0; self.chat_follow=True; self.chat_follow_generation=0
        scroll_input=Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        scroll_input.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        def scrolled(*unused):
            self.chat_scroll_generation+=1; self.chat_follow=False; return False
        scroll_input.connect('scroll',scrolled); self.chat_scroll.add_controller(scroll_input)
        scroll_keys=Gtk.EventControllerKey()
        def scroll_key(controller,keyval,*unused):
            if keyval in (Gdk.KEY_Up,Gdk.KEY_Down,Gdk.KEY_Page_Up,Gdk.KEY_Page_Down,Gdk.KEY_Home,Gdk.KEY_End): scrolled()
            return False
        scroll_keys.connect('key-pressed',scroll_key); self.chat_scroll.add_controller(scroll_keys)
        scroll_drag=Gtk.GestureClick(); scroll_drag.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        scroll_drag.connect('pressed',scrolled); self.chat_scrollbar.add_controller(scroll_drag)
        self.chat_scroll.get_vadjustment().connect('changed',lambda a:self.chat_scrollbar.set_sensitive(a.get_upper()>a.get_page_size()))
        def range_changed(adjustment):
            if self.chat_follow and self.chat_follow_generation==self.chat_scroll_generation:
                GLib.idle_add(self.settle_chat_bottom,self.message_key,self.chat_scroll_generation)
        self.chat_scroll.get_vadjustment().connect('changed',range_changed)
        scroll_row.append(self.chat_scrollbar)
        message_overlay=Gtk.Overlay(vexpand=True); message_overlay.set_child(scroll_row)
        self.empty_chat=box(True,16); self.empty_chat.set_halign(Gtk.Align.FILL); self.empty_chat.set_valign(Gtk.Align.CENTER)
        self.empty_chat.set_margin_start(24); self.empty_chat.set_margin_end(32)
        self.empty_chat.append(label('Start with a conversation.','empty-heading',True))
        self.empty_chat.append(label('Talk to each other here. When you’re ready for help, mention @centaur.','message',True))
        self.empty_chat.append(label('Sketch on the canvas or point with Comment. Your marks accompany the next request to the agent.','message muted',True))
        message_overlay.add_overlay(self.empty_chat); chat.append(message_overlay)
        self.busy=box(spacing=8,css='busy'); self.working_mark=WorkingMark(); self.busy.append(self.working_mark); self.busy_text=label('Centaur is working…','chat-status muted'); self.busy_text.set_hexpand(True); self.busy.append(self.busy_text)
        self.busy_text.set_ellipsize(Pango.EllipsizeMode.END)
        self.stop_button=button('Stop',lambda:self.service.send('cancel'),tone='plain'); self.busy.append(self.stop_button); self.busy.set_visible(False)
        self.targets['activity-tile']=self.busy; self.targets['activity-text']=self.busy_text
        self.targets['stop-agent']=self.stop_button
        self.proposal=box(True,8,'proposal'); chat.append(self.proposal); self.proposal.set_visible(False)
        self.import_actions=box(spacing=8); chat.append(self.import_actions); self.import_actions.set_visible(False)
        self.import_run=button('Run preview',lambda:self.service.send('runImport')); self.import_actions.append(self.import_run)
        self.import_retry=button('Retry import',lambda:show_import(self,retry=True)); self.import_actions.append(self.import_retry)
        self.targets.update({'import-run':self.import_run,'import-retry':self.import_retry})
        self.editor=Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR,accepts_tab=False); self.editor.add_css_class('message'); self.targets['editor']=self.editor
        key=Gtk.EventControllerKey(); key.set_propagation_phase(Gtk.PropagationPhase.CAPTURE); key.connect('key-pressed',self.editor_key); self.editor.add_controller(key)
        row=box(spacing=8); self.mention=button('@centaur',self.insert_mention,tone='plain'); row.append(self.mention)
        spacer=box(); spacer.set_hexpand(True); row.append(spacer)
        self.send_button=button('',self.send,css='send-button',tone='soft',width=32)
        self.send_button.set_child(send_art()); accessible(self.send_button,'Send message'); row.append(self.send_button); self.targets['send']=self.send_button
        self.composer=Composer(self.editor,row); chat.append(self.composer)
        self.targets['composer']=self.composer
        self.editor.get_buffer().connect('changed',lambda b:self.update_send())
        self.update_footer=box(spacing=8); chat.append(self.update_footer)
        for item in (heading,self.proposal,self.import_actions,self.composer,self.update_footer):
            item.set_margin_start(16); item.set_margin_end(16)
        for item in (self.proposal,self.import_actions,self.composer,self.update_footer): item.set_margin_top(16)
        self.update_footer.set_margin_top(0); self.update_footer.set_size_request(-1,48)
        self.targets.update({'chat-messages':self.messages,'chat-scrollbar':self.chat_scrollbar,'chat-divider':divider,'chat-scroller':self.chat_scroll})
        self.comment_overlay=Gtk.DrawingArea(hexpand=True,vexpand=True); self.comment_overlay.set_can_target(False)
        self.comment_overlay.set_draw_func(lambda a,cr,w,h:paint_arrow(cr,*self.comment_points()))
        self.root_overlay.add_overlay(self.comment_overlay)
        self.panes.set_start_child(self.chat); self.panes.set_resize_start_child(False); self.panes.set_shrink_start_child(False)
        self.stack.add_named(wrapper,'workspace'); self.set_tool('draw'); self.initial_pane=True

    @staticmethod
    def version(): return '0.4.0-preview+'+os.environ.get('CENTAUR_GTK4_BUILD_ID','dev')

    def save_name(self): self.settings.flush('name')

    def save_agent_name(self): self.settings.flush('agent')

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
        if page!='workspace': self.cancel_comment()
        self.page=page
        if page=='settings' and hasattr(self,'updates') and not self.updates.checked: self.updates.check()
        if page=='settings' and hasattr(self,'settings'): self.settings.refresh()
        self.stack.set_visible_child_name(page)
        if page=='projects' and hasattr(self,'cards'): self.refresh_cards()
        for key,item in self.nav.items():
            selected(item,key==page)
        self.nav['projects'].centaur_image.set_from_file(str(ASSETS/'v2'/('bab90.svg' if page=='projects' else 'aef7a.svg')))
        self.nav['settings'].centaur_image.set_from_file(str(ASSETS/'v2'/('e1970.svg' if page=='settings' else '2adf1.svg')))
        workspace=page=='workspace'
        self.top_start.set_margin_start(24)
        self.sidebar.set_visible(not workspace); self.modes.set_visible(workspace)
        self.saved_status.set_visible(page=='settings')
        for item in (self.projects_crumb,self.breadcrumb_arrow,self.breadcrumb,self.invite_button,self.deploy_button): item.set_visible(workspace)
        self.create_menu.set_visible(page=='projects'); self.import_button.set_visible(page=='systems')
        self.targets['nav-projects']=self.projects_crumb if workspace else self.nav['projects']
        self.window.set_size_request(1000 if workspace else 360,680)
        if workspace:
            GLib.idle_add(self.start_preview)
        else:
            self.stop_preview()

    def set_mode(self,mode):
        if mode!='Build': self.cancel_comment()
        self.mode=mode
        for key,item in self.mode_buttons.items():
            selected(item,key==mode)
        self.build_tools.set_visible(mode=='Build')
        self.ink.set_can_target(mode=='Build')

    def set_tool(self,tool):
        self.tool=tool
        if tool=='comment' and self.viewport and self.data.get('connected'):
            bounds=self.tool_buttons['comment'].compute_bounds(self.root_overlay)[1]
            self.comment.start(self.project.get('id'),self.project.get('revision'),
                               self.pointer_position or (bounds.get_x()+16,bounds.get_y()+16))
            self.comment_overlay.queue_draw()
            self.ink.set_cursor_from_name('crosshair')
        elif tool=='draw': self.cancel_comment()
        for key,item in self.tool_buttons.items():
            selected(item,key==tool)
        self.tool_buttons['draw'].centaur_image.set_from_file(str(ASSETS/('v2/3f1c5.svg' if tool=='draw' else 'toolbar-draw.svg')))


    def cancel_comment(self):
        self.comment.clear()
        if hasattr(self,'comment_overlay'): self.comment_overlay.queue_draw()
        if hasattr(self,'ink'): self.ink.set_cursor_from_name(None)

    def comment_key(self,controller,keyval,keycode,state):
        if keyval==Gdk.KEY_Escape and self.comment.phase!='idle': self.cancel_comment(); return True
        return False

    def pointer_motion(self,controller,x,y):
        self.pointer_position=(x,y)
        if self.comment.phase=='following':
            self.comment.move((x,y)); self.comment_overlay.queue_draw()

    def place_comment(self,gesture,count,x,y):
        if self.comment.phase!='following' or self.mode!='Build' or not self.viewport: return
        if self.root_overlay.pick(x,y,Gtk.PickFlags.DEFAULT) is not self.ink: return
        ok,canvas=self.ink.compute_bounds(self.root_overlay)
        if not ok: return
        space=AnnotationSpace.capture(self.viewport.describe(),canvas.get_width(),canvas.get_height())
        if self.comment.place(space,x-canvas.get_x(),y-canvas.get_y()):
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            self.ink.set_cursor_from_name(None); self.editor.grab_focus(); self.comment_overlay.queue_draw()

    def comment_points(self):
        if self.comment.phase=='idle' or self.page!='workspace' or not self.viewport: return None,None
        ok,canvas=self.ink.compute_bounds(self.root_overlay); good,composer=self.composer.compute_bounds(self.root_overlay)
        if not ok or not good: return None,None
        head=self.comment.head(self.viewport.describe(),(canvas.get_x(),canvas.get_y()))
        return (composer.get_x()+12,composer.get_y()+12),head

    def undo(self):
        if self.comment.phase!='idle': self.cancel_comment()
        else: self.service.send('undo')

    def receive(self,data):
        if data.get('type') in ('settingsSaved','error'): self.settings.receive(data)
        if data.get('type')=='settingsSaved': return
        if data.get('type')=='error':
            if data.get('code')=='local_service_disconnected':
                self.project.pop('agentActivity',None); self.data['busy']=False
                self.message_key=None; self.refresh_messages(); self.working_mark.set_working(False); self.update_send()
            self.pending_message=None; self.update_send()
            self.error_label.set_text(data.get('message','Could not complete that action.')); self.error_label.set_visible(True); return
        if data.get('type')=='sent': return
        if data.get('type')!='snapshot': return
        old_id=self.project.get('id')
        self.data=data; self.project=data.get('project',{})
        if getattr(self,'requested_grid',None)==data.get('grid'): self.requested_grid=None
        new_id=self.project.get('id')
        buffer=self.editor.get_buffer()
        if old_id!=new_id:
            self.chat_follow=True; self.chat_follow_generation=self.chat_scroll_generation
            self.cancel_comment()
            if old_id: self.drafts[old_id]=buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),False)
            buffer.set_text(self.drafts.get(new_id,'')); self.pending_message=None
        pending=self.pending_message
        if pending and any(m.get('id') not in pending['seen'] and m.get('text')==pending['text'].strip()[:12000] and m.get('author')==data.get('author')
                           and (pending.get('comment') is None or m.get('comment')==pending['comment']) for m in self.project.get('messages',[])):
            if buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),False)==pending['text']: buffer.set_text('')
            self.pending_message=None
            if self.comment.clear(pending.get('commentToken')):
                self.comment_overlay.queue_draw(); self.ink.set_cursor_from_name(None)
        if self.comment.phase!='idle' and self.comment.revision!=self.project.get('revision'): self.cancel_comment()
        self.join_progress.set_text(data.get('joinStatus','') if data.get('joining') else '')
        self.join_progress.set_visible(data.get('joining',False))
        if hasattr(self,'join_submit'): self.update_join()
        self.cancel_join.set_visible(data.get('joining',False))
        self.profile_name.set_text(data.get('author','Your settings'))
        self.settings.receive(data)
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
            self.update_send()
            queued=self.project.get('queueCount',0)
            activity=self.current_activity()
            self.busy_text.set_text(activity_caption(activity)+(' · '+str(queued)+' queued' if queued else ''))
            remote=data.get('remote',False); button_text(self.invite_button,'Shared' if remote else 'Invite'); self.invite_button.set_sensitive(not remote)
            self.deploy_button.set_sensitive(not remote)
            self.undo_button.set_sensitive(self.comment.phase!='idle' or any(a.get('author')==data.get('author') and a.get('revision')==self.project.get('revision') for a in self.project.get('annotations',[])))
            messages=json.dumps([self.project.get('id'),self.project.get('messages',[]),activity.get('requestId'),activity.get('afterMessage')],sort_keys=True)
            if messages!=self.message_key:
                self.message_key=messages; self.refresh_messages()
            self.refresh_proposal()
            imported=self.project.get('import') or {}; phase=imported.get('status')
            local=not data.get('remote',False)
            self.import_run.set_visible(local and phase=='readyToRun'); self.import_run.set_sensitive(not data.get('updateBlocked'))
            self.import_retry.set_visible(local and bool(imported) and phase not in ('fetching','inspecting','investigating') and not data.get('busy'))
            button_text(self.import_retry,'Retry import' if phase in ('failed','interrupted') else 'Change source')
            self.import_actions.set_visible(any(w.get_visible() for w in (self.import_run,self.import_retry)))
            working=bool(imported) and not imported.get('previewReady')
            self.import_working.set_visible(working)
            self.import_working.update(phase)
            self.working_mark.set_working(bool(activity))
            if self.page=='workspace': GLib.idle_add(self.start_preview)
        elif old_id:
            self.stop_preview(); self.navigate('projects')
        self.ink.queue_draw()
        invitation=data.get('invitation','')
        if invitation and invitation!=self.last_invite:
            self.last_invite=invitation
            self.invitation_dialog(invitation)
        if hasattr(self,'join_dialog') and self.join_dialog.get_visible():
            self.join_feedback.set_text(data.get('joinStatus','')); self.join_feedback.set_visible(bool(data.get('joinStatus')))
            if data.get('remote') and data.get('connected'): self.dismiss_dialog(self.join_dialog)
        self.updates.restore()

    @staticmethod
    def edited_time(value):
        try:
            updated=datetime.fromisoformat(value.replace('Z','+00:00')).astimezone()
            seconds=max(0,(datetime.now().astimezone()-updated).total_seconds())
            if seconds<60: return 'Edited just now'
            if seconds<3600: return 'Edited '+str(int(seconds//60))+'m ago'
            if seconds<86400: return 'Edited '+str(int(seconds//3600))+'h ago'
            return 'Edited '+updated.strftime('%d %b')
        except (AttributeError,TypeError,ValueError): return 'Saved project'

    def thumbnail_path(self, project):
        # Screenshot caches belong to Centaur's own project metadata, including
        # guest caches. No imported originals or accepted app files are changed.
        return self.root/('shared' if project.get('remote') else 'projects')/project['id']/'.centaur/thumbnail.png'

    def capture_thumbnail(self):
        if not self.backend or not self.viewport or self.preview_key==getattr(self,'thumbnail_key',None): return
        if not self.child_report.exists() or self.backend.process.poll() is not None: return
        try:
            width,height=self.viewport.model.app_width,self.viewport.model.app_height
            snapshot=Gtk.Snapshot.new(); rect=Graphene.Rect().init(0,0,width,height)
            snapshot.push_clip(rect); snapshot.translate(Graphene.Point().init(-96,-96))
            Gtk.WidgetPaintable.new(self.backend.widget).snapshot(snapshot,width+192,height+192)
            snapshot.pop(); node=snapshot.to_node()
            if not node: return
            texture=self.window.get_renderer().render_texture(node,rect)
            target=self.thumbnail_path(self.project); target.parent.mkdir(exist_ok=True)
            descriptor,name=tempfile.mkstemp(dir=target.parent,prefix='.thumbnail-',suffix='.png'); os.close(descriptor)
            temporary=Path(name)
            try:
                if texture.save_to_png(str(temporary)):
                    temporary.replace(target); self.thumbnail_key=self.preview_key
            finally: temporary.unlink(missing_ok=True)
        except (OSError,RuntimeError,AttributeError,TypeError):
            # Thumbnails are optional; a missing cache uses the supplied clay.
            self.thumbnail_key=self.preview_key

    def refresh_cards(self):
        self.cards.clear()
        for key in list(self.targets):
            if key.startswith(('open-','menu-')): del self.targets[key]
        projects=self.data.get('projects',[])
        self.empty_projects.set_visible(not projects)
        for project in projects:
            card=Gtk.Overlay(); open_button=Gtk.Button(); open_button.add_css_class('project-card')
            open_button.connect('clicked',lambda b,p=project:self.open_project(p['id']))
            open_button.set_overflow(Gtk.Overflow.HIDDEN)
            content=box(True,0)
            thumbnail=Gtk.Overlay(css_classes=['project-thumbnail']); thumbnail.set_size_request(-1,208)
            thumbnail.set_child(box())
            path=self.thumbnail_path(project)
            if path.exists():
                image=Gtk.Picture.new_for_filename(str(path)); image.set_content_fit(Gtk.ContentFit.CONTAIN); image.set_can_shrink(True)
                thumbnail.add_overlay(image)
            else:
                image=picture(ASSETS/'v2/dc3c7.png',72); image.set_halign(Gtk.Align.CENTER); image.set_valign(Gtk.Align.CENTER)
                image.set_opacity(.2); thumbnail.add_overlay(image)
            content.append(thumbnail)
            text=box(True,5); text.set_size_request(-1,72); text.set_margin_start(16); text.set_margin_end(48)
            title=label(project['name'],'project-title'); title.set_ellipsize(Pango.EllipsizeMode.END); title.set_margin_top(16); text.append(title)
            app_type=project.get('appType') or {'gtk4-v1':'GTK4 App','qml-v1':'Qt App'}.get(project.get('appFormat'),'Native app')
            edited=self.edited_time(project.get('updated'))
            meta=label(app_type+' · '+edited,'project-meta muted'); meta.set_ellipsize(Pango.EllipsizeMode.END); text.append(meta)
            content.append(text); open_button.set_child(content); card.set_child(open_button)
            menu=Gtk.MenuButton(); menu.add_css_class('meatball'); accessible(menu,'Project options for '+project['name'])
            menu_icon=original('a7b49.svg',16); menu_icon.set_content_height(4)
            menu.set_child(menu_icon); menu.set_size_request(32,32); menu.set_halign(Gtk.Align.END); menu.set_valign(Gtk.Align.START)
            menu.set_margin_top(228); menu.set_margin_end(16)
            pop=Gtk.Popover(has_arrow=False,position=Gtk.PositionType.BOTTOM); pop.add_css_class('project-menu'); actions=box(True,0)
            def action(callback,popover=pop): popover.popdown(); callback()
            rename=button('Rename',lambda p=project,a=action:a(lambda:self.rename(p)),tone='plain',height=24)
            rename.get_child().set_halign(Gtk.Align.START); rename.set_sensitive(not project.get('remote',False)); actions.append(rename)
            imported=project.get('import') or {}
            if not project.get('remote') and imported.get('storage') and imported.get('framework'):
                inspect=button('Open adaptation' if imported.get('output') else 'Open source',
                    lambda p=project,a=action:a(lambda:self.open_imported(p)),tone='plain',height=24)
                inspect.get_child().set_halign(Gtk.Align.START); actions.append(inspect)
                self.targets['menu-source-'+project['id']]=inspect
            delete=button('Leave project' if project.get('remote') else 'Delete',lambda p=project,a=action:a(lambda:self.delete(p)),tone='plain',height=24)
            delete.get_child().set_halign(Gtk.Align.START); actions.append(delete)
            self.targets['menu-rename-'+project['id']]=rename; self.targets['menu-delete-'+project['id']]=delete
            pop.set_child(actions); menu.set_popover(pop); card.add_overlay(menu)
            self.targets['open-'+project['id']]=open_button
            self.targets['menu-'+project['id']]=menu
            self.cards.append(card)

    def open_imported(self,project):
        info=project.get('import') or {}
        base=(self.root/'projects'/project['id']/'.centaur/import').resolve()
        path=(base/info['storage']/(info.get('output') or 'source')).resolve()
        if not path.is_relative_to(base) or not path.is_dir():
            self.notice('Source unavailable','The saved imported source could not be found.'); return
        Gio.AppInfo.launch_default_for_uri(path.as_uri(),None)

    def current_activity(self):
        if self.data.get('remote') and not self.data.get('connected'): return {}
        return self.project.get('agentActivity') or {}

    def settle_chat_bottom(self,key,generation):
        if self.chat_follow and generation==self.chat_scroll_generation and key==self.message_key:
            adj=self.chat_scroll.get_vadjustment(); adj.set_value(max(0,adj.get_upper()-adj.get_page_size()))
        return False

    def refresh_messages(self):
        adj=self.chat_scroll.get_vadjustment()
        follow=(adj.get_value()>=max(0,adj.get_upper()-adj.get_page_size())-24 or
                (self.chat_follow and self.chat_follow_generation==self.chat_scroll_generation))
        generation=self.chat_scroll_generation
        self.chat_follow=follow; self.chat_follow_generation=generation
        for key in list(self.targets):
            if key.startswith('agent-details-'): del self.targets[key]
        activity=self.current_activity()
        self.busy.set_visible(bool(activity))
        child=self.messages.get_first_child()
        while child:
            following=child.get_next_sibling()
            if child!=self.busy or not activity: self.messages.remove(child)
            child=following
        self.message_rows=[]
        def put_activity(after=None):
            # Reordering an existing child preserves its frame clock while
            # concurrent human messages arrive; progress never rebuilds it.
            if self.busy.get_parent() is None: self.messages.append(self.busy)
            self.messages.reorder_child_after(self.busy,after)
        inserted=False
        if activity and not activity.get('afterMessage'): put_activity(); inserted=True
        self.empty_chat.set_visible(not self.project.get('messages') and not activity)
        for message in self.project.get('messages',[]):
            item=box(spacing=8,css='chat-card'); column=box(True,2); column.set_hexpand(True); head=box(spacing=8)
            author=message.get('author','')
            agent=message.get('kind')!='human'
            if not agent: item.add_css_class('human')
            if agent:
                author=author.lstrip('@')
                if author.lower()=='centaur': author='Centaur'
            if agent:
                avatar=box(css='avatar agent'); mark=original('2fe69.svg' if message.get('kind')=='system' else '144b3.svg',32); avatar.append(mark); avatar.set_halign(Gtk.Align.START)
                self.targets['chat-agent-avatar']=avatar; self.targets['chat-agent-mark']=mark
            else:
                if author==self.data.get('author') and self.settings.avatar_path.exists():
                    avatar=Gtk.Overlay(css_classes=['avatar']); avatar.set_overflow(Gtk.Overflow.HIDDEN); avatar.set_child(picture(self.settings.avatar_path,32,cover=True))
                else:
                    avatar=label(author[:1].upper(),'avatar'); avatar.set_xalign(.5)
            avatar.set_size_request(32,32); avatar.set_valign(Gtk.Align.START); item.append(avatar)
            self.targets['chat-avatar']=avatar
            name=label(author,'chat-name'); name.set_ellipsize(Pango.EllipsizeMode.END); name.set_valign(Gtk.Align.BASELINE); head.append(name)
            try: time=datetime.fromisoformat(message['time'].replace('Z','+00:00')).astimezone().strftime('%H:%M')
            except (KeyError,ValueError): time=''
            stamp=label(time,'chat-time muted'); stamp.set_valign(Gtk.Align.BASELINE); head.append(stamp); column.append(head)
            text=message.get('text','')
            if message.get('kind')=='agent' and re.fullmatch(r'Applied the (agreed )?change\. Revision \d+ is ready to try\.',text): text='Updated the app.'
            body=label(text,'chat-comment muted' if message.get('kind')=='system' else 'chat-comment',True); body.set_selectable(True); body.set_yalign(0)
            attributes=Pango.AttrList()
            for mention in re.finditer(r'(?<!\w)@[\w-]+',text):
                weight=Pango.attr_weight_new(Pango.Weight.SEMIBOLD)
                weight.start_index=len(text[:mention.start()].encode('utf-8'))
                weight.end_index=len(text[:mention.end()].encode('utf-8'))
                attributes.insert(weight)
            body.set_attributes(attributes)
            self.chat_body=body
            column.append(body); item.append(column); self.messages.append(item)
            if message.get('agentDiagnostics'):
                details=message['agentDiagnostics']
                action=button('Request details',lambda d=details:self.show_agent_details(d),tone='plain')
                action.set_halign(Gtk.Align.START); column.append(action)
                self.targets['agent-details-'+message['id']]=action
            self.message_rows.append((avatar,name,stamp,body))
            self.targets.update({'chat-name':name,'chat-body':body,'chat-time':stamp})
            if activity and activity.get('afterMessage')==message.get('id'):
                put_activity(item); inserted=True
        if activity and not inserted:
            last=self.messages.get_last_child()
            put_activity(last if last!=self.busy else self.busy.get_prev_sibling())
        message_key=self.message_key
        def bottom():
            if follow and generation==self.chat_scroll_generation and message_key==self.message_key:
                self.settle_chat_bottom(message_key,generation)
            return False
        def after_layout(widget,clock):
            # Tick runs before GTK's layout phase; its queued idle runs after
            # that frame has updated the scroll adjustment's actual range.
            GLib.idle_add(bottom)
            return False
        self.messages.add_tick_callback(after_layout)

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
            if self.comment.phase=='placed': fields['comment']=self.comment.target
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
                    if self.comment.phase=='placed':
                        cr=snapshot.append_cairo(Graphene.Rect().init(0,0,width,height))
                        cr.rectangle(0,0,width,height); cr.clip()
                        bounds=self.ink.compute_bounds(self.root_overlay)[1]
                        cr.translate(-bounds.get_x(),-bounds.get_y()); paint_arrow(cr,*self.comment_points()); del cr
                    node=snapshot.to_node()
                    texture=self.window.get_renderer().render_texture(node,None)
                    target=Path(self.data['sourcePath']).parent/'.centaur'/('context-'+uuid.uuid4().hex+'.png')
                    target.parent.mkdir(exist_ok=True)
                    if not texture.save_to_png(str(target)): raise RuntimeError('PNG export failed')
                    fields.update(image=str(target),imageRevision=self.project['revision'])
                except Exception as error:
                    self.error_label.set_text('Could not attach the canvas image. Drawing coordinates are included. '+str(error))
                    self.error_label.set_visible(True)
            self.pending_message={'text':text,'seen':{m['id'] for m in self.project.get('messages',[])},'commentToken':self.comment.token,'comment':fields.get('comment')}
            self.send_button.set_sensitive(False)
            if not self.service.send('message',**fields): self.pending_message=None

    def editor_key(self,controller,keyval,keycode,state):
        if keyval in (Gdk.KEY_Return,Gdk.KEY_KP_Enter) and not state & Gdk.ModifierType.SHIFT_MASK:
            self.send(); return True
        return False

    def dialog(self,title,width=424):
        if self.active_form: self.dismiss_dialog(self.active_form)
        dialog=Modal(self,title,width); self.active_form=dialog
        content=box(True,16,'dialog-card'); content.append(label(title,'dialog-title',True)); dialog.set_child(content)
        self.targets['dialog-card']=content
        key=Gtk.EventControllerKey(); key.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        def escape(c,keyval,keycode,state):
            if keyval==Gdk.KEY_Escape:
                if hasattr(dialog,'escape_handler') and dialog.escape_handler(): return True
                if dialog is getattr(self,'join_dialog',None): self.service.send('cancelJoin')
                self.dismiss_dialog(dialog); return True
            return False
        key.connect('key-pressed',escape); dialog.add_controller(key)
        return dialog,content

    def dismiss_dialog(self,dialog):
        dialog.destroy()
        if self.active_form is dialog: self.active_form=None

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
        from v2_ui import form_card,field,prompt_field,cancel_button
        dialog,content,footer=form_card(self,'Create a project')
        name=Gtk.Entry(placeholder_text='Give the project a name',max_length=100,width_chars=1,css_classes=['import-field'])
        name.set_size_request(-1,40); field(content,'Name',name)
        prompt,widget=prompt_field('What would you like to make?'); field(content,'Prompt',widget)
        cancel_button(self,dialog,footer)
        def done():
            if not name.get_text().strip(): return
            buf=prompt.get_buffer(); text=buf.get_text(buf.get_start_iter(),buf.get_end_iter(),False)
            if self.service.send('create',name=name.get_text().strip(),description=text): self.dismiss_dialog(dialog)
        create=button('Create project',done,tone='dark',width=104); footer.append(create)
        name.connect('changed',lambda e:create.set_sensitive(bool(e.get_text().strip())))
        name.connect('activate',lambda e:done()); create.set_sensitive(False)
        self.targets.update({'create-name':name,'create-prompt':prompt,'create-submit':create})
        dialog.present(); name.grab_focus()

    def rename(self,project):
        self.form('Rename project',[('name','Project name',project['name'])],lambda v:self.service.send('rename',projectId=project['id'],name=v['name']))

    def delete(self,project):
        leave=project.get('remote',False)
        dialog,card=self.dialog('Leave project?' if leave else 'Delete project?',288)
        self.clear(card); card.add_css_class('delete-dialog'); card.set_spacing(0); card.set_overflow(Gtk.Overflow.HIDDEN)
        hero=Gtk.Overlay(css_classes=['delete-hero']); hero.set_size_request(-1,128); hero.set_child(box())
        clay=picture(ASSETS/'v2/dc3c7.png',72); clay.set_halign(Gtk.Align.CENTER); clay.set_valign(Gtk.Align.CENTER)
        hero.add_overlay(clay); card.append(hero)
        title=label('Leave this project?' if leave else 'Please confirm delete','dialog-title',True)
        title.set_xalign(.5); title.set_size_request(-1,24); title.set_margin_top(25); card.append(title)
        text=label(('Leave '+project['name']+' on this device?') if leave else 'The app and conversation will move\nto the recovery folder.','delete-description',True)
        text.set_size_request(-1,36); text.set_xalign(.5); text.set_justify(Gtk.Justification.CENTER); card.append(text)
        row=box(spacing=16); row.set_margin_top(19); row.set_margin_bottom(24); row.set_margin_start(24); row.set_margin_end(24); card.append(row)
        cancel=button('Cancel',lambda:self.dismiss_dialog(dialog),tone='soft',width=112); row.append(cancel)
        def done():
            if self.service.send('leave' if leave else 'delete',projectId=project['id']): self.dismiss_dialog(dialog)
        confirm=button('Leave' if leave else 'Yes, delete',done,css='delete-confirm',tone='dark',width=112); row.append(confirm)
        self.targets['delete-confirm']=confirm; dialog.present(); cancel.grab_focus()

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

    def show_agent_details(self,details):
        dialog,content=self.dialog('Agent request details',408)
        text=activity_details(details);body=label(text,'small',True);body.set_selectable(True);content.append(body)
        row=box(spacing=8);row.set_halign(Gtk.Align.END)
        copy=button('Copy details',lambda:self.window.get_clipboard().set(text),tone='plain')
        done=button('Done',lambda:self.dismiss_dialog(dialog),tone='dark')
        row.append(copy);row.append(done);content.append(row)
        self.targets.update({'agent-details-copy':copy,'agent-details-done':done})
        dialog.present()

    def join(self):
        from v2_ui import form_card,field,prompt_field,cancel_button
        if not self.data.get('author','').strip():
            self.navigate('settings'); self.name.grab_focus(); return
        dialog,content,footer=form_card(self,'Join a project'); self.join_dialog=dialog
        invitation,widget=prompt_field('Paste the invite code here'); self.join_code=invitation
        field(content,'Invite code',widget)
        self.join_feedback=label('','small muted',True); self.join_feedback.set_visible(False); content.append(self.join_feedback)
        cancel_button(self,dialog,footer,lambda:self.service.send('cancelJoin'))
        def done():
            buf=invitation.get_buffer(); code=buf.get_text(buf.get_start_iter(),buf.get_end_iter(),False)
            name=self.data.get('author','').strip()
            if name and code.strip() and not self.data.get('joining'): self.service.send('join',name=name,code=code)
        self.join_submit=button('Join project',done,tone='dark',width=94); footer.append(self.join_submit)
        invitation.get_buffer().connect('changed',lambda b:self.update_join()); self.update_join()
        self.targets.update({'join-code':invitation,'join-submit':self.join_submit})
        key=Gtk.EventControllerKey(); key.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key.connect('key-pressed',lambda c,k,code,state:(done(),True)[1] if k in (Gdk.KEY_Return,Gdk.KEY_KP_Enter) and not state&Gdk.ModifierType.SHIFT_MASK else False)
        invitation.add_controller(key); dialog.present(); invitation.grab_focus()

    def invite(self):
        from v2_ui import form_card,field,cancel_button
        dialog,content,footer=form_card(self,'Invite someone to collaborate'); self.invite_dialog=dialog
        entry=Gtk.Entry(editable=False,width_chars=1,css_classes=['import-field','invite-code'])
        entry.set_size_request(-1,40); overlay=Gtk.Overlay(); overlay.set_child(entry)
        self.invite_code_entry=entry
        copy=button('Copy',lambda:self.window.get_display().get_clipboard().set(entry.get_text()),tone='plain',width=49,height=24)
        copy.set_halign(Gtk.Align.END); copy.set_valign(Gtk.Align.CENTER); copy.set_margin_end(8); overlay.add_overlay(copy)
        self.invite_copy=copy; field(content,'Invite code',overlay)
        content.set_spacing(0)
        content.set_margin_bottom(0)
        hint=label('Send this code to one person. It can be used once and expires in 20 minutes.','small muted',True)
        hint.set_size_request(-1,48); content.append(hint)
        self.invite_result=box(True,8); content.append(self.invite_result)
        cancel_button(self,dialog,footer)
        footer.append(button('Done',lambda:self.dismiss_dialog(dialog),tone='dark',width=72))
        self.targets.update({'invite-code':entry,'invite-copy':copy})
        dialog.present()
        # Each opening creates a fresh single-use invitation using the existing
        # coordinator; copying never generates a second invitation.
        entry.set_placeholder_text('Preparing invitation…'); copy.set_sensitive(False)
        self.service.send('invite',address='iroh')

    def update_join(self):
        joining=self.data.get('joining',False); self.join_code.set_sensitive(not joining)
        buffer=self.join_code.get_buffer(); text=buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),False)
        self.join_submit.set_sensitive(not joining and bool(self.data.get('author','').strip()) and bool(text.strip()))
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
        self.invite_code_entry.set_text(code); self.invite_copy.set_sensitive(bool(code))

    def send_grid(self,**fields):
        if getattr(self,'syncing_grid',False) or not hasattr(self,'service'): return
        values=dict(getattr(self,'requested_grid',None) or self.data.get('grid',{})); values.update(fields)
        self.requested_grid=values; self.settings.send('grid',**values)

    def toggle_grid(self): self.send_grid(enabled=not self.data.get('grid',{}).get('enabled',False))

    def grid_controls(self,content):
        controls={}
        def row(caption,widget):
            line=box(spacing=16); text=label(caption); text.set_hexpand(True); line.append(text); line.append(widget); content.append(line)
        controls['enabled']=Switch(False,lambda value:self.send_grid(enabled=value)); row('Show grid',controls['enabled'])
        colour=button('#BAE6FF',self.grid_colour,css='colour-button',width=112); controls['colour']=colour; colour.centaur_label.add_css_class('colour-label')
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
            if 'enabled' in controls: controls['enabled'].set_active(values.get('enabled',False))
            controls['size'].set_value(values.get('size',8))
            if hasattr(controls['opacity'],'set_selected'): controls['opacity'].set_selected(round(values.get('opacity',50)/10))
            else: controls['opacity'].set_value(values.get('opacity',50))
            button_text(controls['colour'],values.get('color','#BAE6FF').upper())
            if isinstance(controls['swatch'],Gtk.DrawingArea): controls['swatch'].queue_draw()
            else:
                provider=getattr(controls['swatch'],'color_provider',None)
                if provider is None:
                    provider=Gtk.CssProvider(); controls['swatch'].color_provider=provider
                    controls['swatch'].get_style_context().add_provider(provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                provider.load_from_string('.grid-swatch { background: '+values.get('color','#BAE6FF')+'; border-radius: 4px; }')
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
        if self.project.get('import') and not self.project['import'].get('previewReady'):
            self.stop_preview(); self.preview_status=''; return False
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
        if self.tool!='draw' or self.mode!='Build' or not self.data.get('connected') or not self.viewport:
            gesture.set_state(Gtk.EventSequenceState.DENIED); return
        self.stroke_space=AnnotationSpace.capture(self.viewport.describe(),self.ink.get_width(),self.ink.get_height())
        self.ink_origin=(x,y); self.points=[self.stroke_space.point(x,y)]; self.ink.queue_draw()

    def ink_point(self,x,y):
        point=self.stroke_space.point(x,y)
        if self.tool=='comment' and len(self.points)>1: self.points[-1]=point
        elif len(self.points)<4096 and (not self.points or point!=self.points[-1]): self.points.append(point)

    def ink_update(self,gesture,dx,dy):
        if self.points:
            self.ink_point(self.ink_origin[0]+dx,self.ink_origin[1]+dy); self.ink.queue_draw()

    def ink_end(self,gesture,dx,dy):
        if self.points:
            self.ink_point(self.ink_origin[0]+dx,self.ink_origin[1]+dy)
            self.service.send('annotation',annotation={'tool':self.tool,'points':self.points,'frame':self.stroke_space.frame})
            self.points=[]; self.ink.queue_draw()

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
        if self.points: marks.append({'points':self.points,'tool':self.tool,'frame':self.stroke_space.frame})
        cr.set_source_rgb(.2,.4,.9); cr.set_line_width(2); cr.set_line_cap(1)
        for mark in marks:
            points=mark.get('points',[])
            if not points: continue
            if mark.get('tool')=='comment': points=[points[0],points[-1]]
            try: positions=[annotation_position(p,mark.get('frame'),g) for p in points]
            except (ValueError,KeyError,TypeError): continue
            for i,(x,y) in enumerate(positions):
                (cr.move_to if i==0 else cr.line_to)(x,y)
            cr.stroke()
            if mark.get('tool')=='comment' and len(points)>1:
                import math
                a,b=positions[0],positions[-1]
                angle=math.atan2(b[1]-a[1],b[0]-a[0]); x,y=b
                for offset in (-.5,.5):
                    cr.move_to(x,y); cr.line_to(x-10*math.cos(angle+offset),y-10*math.sin(angle+offset))
                cr.stroke()

    def window_bounds(self,widget):
        ok,rect=widget.compute_bounds(self.window)
        if ok and isinstance(widget.get_native(),Gtk.Popover):
            # Pinned GTK includes the parent surface translation when crossing
            # the popover's native surface. Reports use visible window-widget
            # coordinates, just like normal child targets and native input.
            x,y=self.window.get_surface_transform()
            rect=Graphene.Rect().init(rect.get_x()-x,rect.get_y()-y,rect.get_width(),rect.get_height())
        return ok,rect

    def poll(self):
        if self.closing: return False
        self.updates.tick()
        activity=self.current_activity()
        self.working_mark.set_working(bool(activity))
        if activity:
            queued=self.project.get('queueCount',0)
            self.busy_text.set_text(activity_caption(activity)+(' · '+str(queued)+' queued' if queued else ''))
        comment_geometry=self.comment_points()
        if comment_geometry!=self.comment_geometry:
            self.comment_geometry=comment_geometry; self.comment_overlay.queue_draw()
        self.undo_button.set_sensitive(self.comment.phase!='idle' or any(a.get('author')==self.data.get('author') and a.get('revision')==self.project.get('revision') for a in self.project.get('annotations',[])))
        # Preserve the reference breakpoints and the chat width on window resize.
        compact=self.window.get_width()<760
        self.sidebar.set_size_request(COMPACT_SIDEBAR if compact else SIDEBAR,-1)
        (self.sidebar.add_css_class if compact else self.sidebar.remove_css_class)('compact')
        for item in self.nav_labels: item.set_visible(not compact)
        self.links.set_margin_start(16 if compact else 24); self.links.set_margin_end(16 if compact else 24)
        for item in self.nav.values(): item.get_child().set_halign(Gtk.Align.CENTER if compact else Gtk.Align.START)
        self.profile_text.set_visible(not compact)
        self.projects_inner.set_margin_top(24 if self.stack.get_width()<720 else 40)
        for edge in ('bottom','start','end'): getattr(self.projects_inner,'set_margin_'+edge)(self.projects_inner.get_margin_top())
        setting_margin=24 if self.stack.get_width()<648 else 72
        margins(self.settings_inner,setting_margin); self.settings_inner.set_margin_top(48)
        self.settings_limit.maximum=504+2*setting_margin
        if self.page=='workspace' and self.panes.get_width()>0:
            available=self.panes.get_width()-8
            if self.initial_pane:
                self.panes.set_position(CHAT_WIDTH); self.initial_pane=False
            elif self.chat.get_width()>CHAT_MAX: self.panes.set_position(CHAT_MAX)
        if hasattr(self,'invite_create'):
            self.invite_create.set_sensitive(not self.data.get('inviting',False)); button_text(self.invite_create,'Preparing invitation…' if self.data.get('inviting') else 'Create invitation')
        if self.backend and self.backend.process:
            if self.backend.process.poll() is not None: self.preview_status='App stopped · Restart app to try again'
            elif self.child_report.exists():
                self.preview_status=''; self.capture_thumbnail()
        self.preview_label.set_text('' if self.import_working.get_visible() else self.preview_status)
        geometry=self.viewport.describe() if self.viewport else None
        if geometry != getattr(self,'ink_geometry',None):
            self.ink_geometry=geometry; self.ink.queue_draw()
        if self.reports:
            self.reports.mkdir(parents=True,exist_ok=True)
            data={'pid':os.getpid(),'page':self.page,'windowSize':[self.window.get_width(),self.window.get_height()],
                  'surfaceOffset':list(self.window.get_surface_transform()),
                  'nativePointer':self.native_pointer,'nativePointerSerial':self.native_pointer_serial,
                  'windowChrome':{'decorated':self.window.get_decorated(),'headerHeight':self.top.get_height(),'closeAction':self.targets['window-close'].get_action_name() if 'window-close' in self.targets else None},
                  'workingAnimation':{'mapped':self.working_mark.get_mapped(),'running':self.working_mark.tick is not None,
                      'opacities':self.working_mark.frame_opacities,'motionProperty':self.working_mark.motion_property,
                      'preference':int(self.working_mark.settings.get_property(self.working_mark.motion_property))},
                  'settings':{'pending':bool(self.settings.pending or self.settings.debounces or self.settings.agent_pending),'failed':self.settings.failed,'status':self.saved_caption.get_text()},
                  'grid':self.data.get('grid',{}),
                  'focus':self.window.get_focus().__gtype__.name if self.window.get_focus() else None,
                  'form':self.active_form.get_title() if self.active_form and self.active_form.get_visible() else None,'project':self.project,'projects':self.data.get('projects',[]),'status':self.data.get('status'),
                  'previewStatus':self.preview_status,'viewport':self.viewport.describe() if self.viewport else None,
                  'error':self.error_label.get_text() if self.error_label.get_visible() else '',
                  'childPid':self.backend.process.pid if self.backend and self.backend.process else None,'mode':self.mode,'targets':{}}
            data['focusedTargets']=[name for name,widget in self.targets.items() if widget.has_focus()]
            data['activity']={'inConversation':self.busy.get_parent()==self.messages,
                'widget':id(self.busy),'caption':self.busy_text.get_text(),
                'animationEpoch':getattr(self.working_mark,'epoch',None),
                'requestId':self.current_activity().get('requestId'),'phase':self.current_activity().get('phase')}
            focus=self.window.get_focus()
            if focus!=getattr(self,'report_focus',None):
                self.report_focus=focus; self.report_focus_sequence=getattr(self,'report_focus_sequence',0)+1
            data['focusSequence']=getattr(self,'report_focus_sequence',0)
            data['tooltipWindows']=[type(w).__name__ for w in Gtk.Window.list_toplevels() if w.get_visible() and w.get_css_name()=='tooltip']
            data['layout']={'sidebarVisible':self.sidebar.get_visible(),'sidebarWidth':self.sidebar.get_width(),
                            'chatWidth':self.chat.get_width(),'tileColumns':__import__('ui').columns(self.cards.get_width()),'gridWidth':self.cards.get_width(),
                            'bodyFont':self.chat_body.get_pango_context().get_font_description().to_string() if hasattr(self,'chat_body') else None,
                            'statusFont':self.chat_status.get_pango_context().get_font_description().to_string(),
                            'headerText':self.chat_status.get_text()}
            data['chatRows']=[]
            data['assetSlots']=[]
            data['tooltipWidgets']=[]
            def asset_slots(widget):
                if widget.get_has_tooltip(): data['tooltipWidgets'].append({'type':type(widget).__name__,'text':widget.get_tooltip_text()})
                filename=getattr(widget,'filename',None)
                if filename and widget.get_mapped() and Path(filename).is_relative_to(ASSETS):
                    ok,rect=self.window_bounds(widget)
                    if ok and rect.get_width()>0 and rect.get_height()>0: data['assetSlots'].append({'file':str(Path(filename).relative_to(ASSETS)),
                        'bounds':[rect.get_x(),rect.get_y(),rect.get_width(),rect.get_height()]})
                child=widget.get_first_child()
                while child:
                    asset_slots(child); child=child.get_next_sibling()
            asset_slots(self.window)
            # The integrated native header precedes the content overlay.
            # Report pointer geometry in the same window coordinates as all
            # other targets; painting and capture retain overlay coordinates.
            origin=self.root_overlay.compute_bounds(self.window)[1]
            reported_comment=[None if point is None else (point[0]+origin.get_x(),point[1]+origin.get_y()) for point in comment_geometry]
            data['commentPointer']={'phase':self.comment.phase,'tail':reported_comment[0],'head':reported_comment[1],
                                    'reference':self.comment.target,'token':self.comment.token}
            adjustment=self.chat_scroll.get_vadjustment()
            data['chatScroll']={'upper':adjustment.get_upper(),'pageSize':adjustment.get_page_size(),
                                'value':adjustment.get_value(),'scrollable':self.chat_scrollbar.get_sensitive()}
            for widgets in getattr(self,'message_rows',[])[:4]:
                row={}
                for key,widget in zip(('avatar','name','time','body'),widgets):
                    ok,rect=self.window_bounds(widget)
                    if not ok or rect.get_width()<=0 or rect.get_height()<=0: continue
                    entry={'bounds':[rect.get_x(),rect.get_y(),rect.get_width(),rect.get_height()]}
                    if isinstance(widget,Gtk.Label):
                        iterator=widget.get_layout().get_iter(); baselines=[]
                        while True:
                            baselines.append(rect.get_y()+widget.get_layout_offsets()[1]+iterator.get_baseline()/Pango.SCALE)
                            if not iterator.next_line(): break
                        entry['baselines']=baselines
                    row[key]=entry
                if len(row)==4: data['chatRows'].append(row)
            data['updater']={'version':self.version(),'status':self.updates.status.get_text(),
                             'footerLabel':self.updates.footer_labels.get_visible_child().get_text(),
                             'footerStatus':self.updates.footer_status.get_text(),
                             'badgeVisible':self.updates.badge.get_visible(),
                             'footerSensitive':self.updates.footer_button.get_sensitive(),
                             'footerFocused':self.updates.footer_focused,
                             'footerHovered':self.updates.footer_hovered,
                             'available':bool(self.updates.manifest),'running':bool(self.updates.process),
                             'work':str(self.updates.work) if self.updates.work else None,
                             'package':os.environ.get('CENTAUR_GTK_PACKAGE')}
            theme=Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            data['branding']={'appIcon':self.window.get_icon_name(),'fullIcon':theme.has_icon(APP_ID),
                              'symbolicIcon':theme.has_icon(APP_ID+'-symbolic')}
            if self.active_form and self.active_form.get_title()=='Import a project':
                data['importDialog']={'canImport':self.targets['import-submit'].get_sensitive(),
                    'failure':getattr(self,'import_discovery_failure',None),
                    'branchVisible':self.targets['import-branch'].get_mapped(),
                    'branchLabel':self.targets['import-branch-label'].get_text(),
                    'branches':[k[len('import-branch-option-'):] for k,v in self.targets.items() if k.startswith('import-branch-option-') and v.get_mapped()],
                    'nameFocused':bool(self.targets['import-name'].get_state_flags() & Gtk.StateFlags.FOCUS_WITHIN)}
            try: data['child']=json.loads(self.child_report.read_text()) if self.backend else None
            except (AttributeError,FileNotFoundError,ValueError): data['child']=None
            for name,widget in self.targets.items():
                if not widget.get_mapped(): continue
                ok,r=self.window_bounds(widget)
                if ok and r.get_width()>0 and r.get_height()>0: data['targets'][name]=[r.get_x(),r.get_y(),r.get_width(),r.get_height()]
            target=self.reports/'shell.json'; target.with_suffix('.tmp').write_text(json.dumps(data)); target.with_suffix('.tmp').replace(target)
        return True

    def close(self):
        if self.closing: return False
        self.settings.close()
        self.closing=True; self.stop_preview()
        if self.active_form: self.dismiss_dialog(self.active_form)
        if hasattr(self,'service'): self.service.close()
        self.composer.release(); self.cards.clear(); self.settings_limit.release(); self.empty_limit.release()
        self.runtime.cleanup()
        return False

    def do_shutdown(self):
        if not self.closing: self.close()
        Gtk.Application.do_shutdown(self)


def main():
    parser=argparse.ArgumentParser(description='Centaur GTK4 development preview')
    parser.add_argument('--data-dir',type=Path)
    parser.add_argument('--desktop-launch',action='store_true')
    parser.add_argument('--report-dir',type=Path)
    parser.add_argument('--update-session',type=Path)
    parser.add_argument('--stop-host',action='store_true')
    parser.add_argument('--version',action='version',version='Centaur GTK4 0.4.0-preview+'+os.environ.get('CENTAUR_GTK4_BUILD_ID','dev'))
    args=parser.parse_args()
    desktop_root=launch_settings() if args.desktop_launch else None
    os.environ['PATH']=str(Path.home()/'.local/bin')+os.pathsep+os.environ.get('PATH','')
    root=(args.data_dir or desktop_root or Path.home()/'.local/share/Centaur/GTK4').expanduser().resolve(); root.mkdir(parents=True,exist_ok=True)
    if args.stop_host: return subprocess.call([os.environ['CENTAUR_GTK_HOST'],'--stop','--data-dir',str(root)])
    try: register_desktop(os.environ['CENTAUR_GTK_PACKAGE'],root)
    except OSError as error: print('Could not register the GTK4 desktop icon: '+str(error),file=sys.stderr)
    app=Centaur(root,args.report_dir,args.update_session)
    for signum in (signal.SIGINT,signal.SIGTERM): GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,signum,lambda:(app.quit(),GLib.SOURCE_REMOVE)[1])
    return app.run([])


if __name__=='__main__': raise SystemExit(main())
