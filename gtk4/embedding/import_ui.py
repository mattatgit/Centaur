"""Figma import form, with source then branch as requested by the owner."""
from pathlib import Path
from gi.repository import Gtk, GLib, Pango
from ui import box, label, button, Svg
from source_import import github_source, ImportError
from import_lookup import BranchLookup


def suggested_name(value):
    try: value=github_source(value)['repository']
    except ValueError: pass
    return value.strip().rstrip('/').rsplit('/',1)[-1].removesuffix('.git').replace('_',' ').replace('-',' ').strip()


def show_import(owner, retry=False):
    dialog,card=owner.dialog('Import a project',408)
    owner.clear(card); card.add_css_class('import-dialog'); card.set_spacing(0); card.set_overflow(Gtk.Overflow.VISIBLE)
    title=label('Import a project','import-title'); title.set_size_request(-1,36); card.append(title)
    divider=Gtk.Separator(); divider.set_margin_top(12); card.append(divider)
    def field(caption,widget,top=22):
        group=box(True,6); group.set_margin_top(top)
        cap=label(caption,'import-caption'); cap.set_size_request(-1,12); group.append(cap); group.append(widget); card.append(group)
        return group
    name=Gtk.Entry(placeholder_text='Give the Centaur project a name',max_length=100,width_chars=1,css_classes=['import-field'])
    name.set_size_request(-1,40); field('Name',name,13)
    source_box=Gtk.Overlay(css_classes=['import-source']); source_box.set_size_request(-1,40)
    source=Gtk.Entry(placeholder_text='Choose a folder or enter a Github repo URL',width_chars=1,css_classes=['import-field','import-source-entry'])
    source.set_hexpand(True); source_box.set_child(source); field('Source',source_box)
    branch_button=Gtk.MenuButton(css_classes=['import-branch']); branch_button.set_size_request(-1,40)
    branch_row=box(spacing=8); branch_caption=label('Loading branches…','import-branch-caption'); branch_caption.set_hexpand(True); branch_caption.set_ellipsize(Pango.EllipsizeMode.END)
    branch_row.append(branch_caption); arrow=Svg('import-branch-arrow.svg',24); branch_row.append(arrow); branch_button.set_child(branch_row)
    branch_group=field('Select a branch',branch_button); branch_group.set_visible(False)
    popover=Gtk.Popover(has_arrow=False,position=Gtk.PositionType.BOTTOM,css_classes=['import-branch-menu']); branch_button.set_popover(popover)
    popover.connect('notify::visible',lambda p,_:(arrow.add_css_class if p.get_visible() else arrow.remove_css_class)('open'))
    pop_content=box(True,0); popover.set_child(pop_content)
    search=Gtk.Entry(placeholder_text='Search branches',width_chars=1,css_classes=['import-branch-search']); search.set_size_request(-1,32); pop_content.append(search)
    choices=box(True,0); scroller=Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,min_content_height=24,max_content_height=240,propagate_natural_height=True)
    scroller.set_child(choices); pop_content.append(scroller)
    selected={'folder':None,'nameEdited':False,'settingName':False,'branch':None,'resolved':None,'pending':0,'remembered':None,'rememberedLocation':None}
    lookup=BranchLookup()
    def close():
        if selected['pending']: GLib.source_remove(selected['pending']); selected['pending']=0
        lookup.cancel()
    dialog.on_close=close
    def escape_popup():
        if popover.get_visible(): popover.popdown(); return True
        return False
    dialog.escape_handler=escape_popup
    def valid(*unused):
        value=source.get_text().strip()
        folder=Path(value).is_absolute()
        submit.set_sensitive(bool(name.get_text().strip() and value and (folder or selected['branch'])))
    def rebuild(*unused):
        for key in list(owner.targets):
            if key.startswith('import-branch-option-'): del owner.targets[key]
        owner.clear(choices); info=selected['resolved'] or {}; query=search.get_text().casefold()
        for index,branch in enumerate(info.get('branches',[])):
            if query not in branch.casefold(): continue
            def choose_branch(value=branch):
                selected['branch']=value; branch_caption.set_text(value); popover.popdown(); error.set_visible(False); rebuild(); valid()
            option=Gtk.Button(css_classes=['branch-option']); option.set_size_request(-1,24)
            row=box(spacing=8); text=label(branch); text.set_hexpand(True); text.set_ellipsize(Pango.EllipsizeMode.END); row.append(text)
            tick=Svg('import-branch-tick.svg',24); tick.set_visible(branch==selected['branch']); row.append(tick); option.set_child(row)
            option.connect('clicked',lambda b,cb=choose_branch:cb()); choices.append(option)
            owner.targets['import-branch-option-'+branch]=option
        search.set_visible(len(info.get('branches',[]))>8)
    search.connect('changed',rebuild)
    def discovered(value,result):
        if not dialog.get_visible() or source.get_text().strip()!=value: return False
        selected['resolved']=result if result.get('ok') else None
        selected['branch']=result.get('branch') if result.get('ok') else None
        branch_button.set_sensitive(bool(result.get('ok')))
        branch_caption.set_text(selected['branch'] or ('Choose a branch' if result.get('ok') else 'Branches unavailable'))
        if not result.get('ok') or result.get('selectionError'):
            error.set_text(result.get('message') or result.get('selectionError') or 'Couldn’t load branches.'); error.set_visible(True)
        rebuild(); valid(); return False
    def begin_lookup(value):
        selected['pending']=0
        remembered=selected['remembered'] if value==selected['rememberedLocation'] else None
        lookup.start(value,remembered,lambda result:GLib.idle_add(discovered,value,result)); return False
    def suggest(*unused):
        value=source.get_text().strip(); lookup.cancel()
        if selected['pending']: GLib.source_remove(selected['pending']); selected['pending']=0
        selected['resolved']=None; selected['branch']=None; error.set_visible(False)
        if selected['folder'] and value!=selected['folder']: selected['folder']=None
        if not selected['nameEdited']:
            selected['settingName']=True; name.set_text(suggested_name(value)); selected['settingName']=False
        try: github_source(value); github=True
        except ValueError: github=False
        branch_group.set_visible(github)
        if github:
            branch_caption.set_text('Loading branches…'); branch_button.set_sensitive(False)
            selected['pending']=GLib.timeout_add(400,begin_lookup,value)
        valid()
    def name_changed(entry):
        if not selected['settingName']: selected['nameEdited']=True
        valid()
    def chosen(chooser,result):
        try:
            folder=chooser.select_folder_finish(result)
            if folder and folder.get_path() and dialog.get_visible():
                selected['folder']=folder.get_path(); selected['remembered']=None; source.set_text(folder.get_path())
        except GLib.Error: pass
    def choose(): Gtk.FileDialog(title='Choose a project folder',modal=True).select_folder(owner.window,None,chosen)
    pick=button('Choose',choose,'import-folder.svg','import-choose',tone='plain',width=88,height=24)
    pick.set_halign(Gtk.Align.END); pick.set_valign(Gtk.Align.CENTER); pick.set_margin_end(8); source_box.add_overlay(pick)
    prompt=Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR,accepts_tab=False,css_classes=['import-prompt'])
    prompt_box=Gtk.Overlay(css_classes=['import-prompt-box']); prompt_box.set_size_request(-1,88)
    scroll=Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER); scroll.set_child(prompt); prompt_box.set_child(scroll)
    placeholder=label('Let the Centaur agent know if you have any instructions','import-placeholder',True)
    placeholder.set_can_target(False); placeholder.set_halign(Gtk.Align.START); placeholder.set_valign(Gtk.Align.START)
    placeholder.set_margin_start(16); placeholder.set_margin_top(12); placeholder.set_margin_end(16); prompt_box.add_overlay(placeholder)
    prompt.get_buffer().connect('changed',lambda b:placeholder.set_visible(b.get_char_count()==0))
    field('Prompt',prompt_box)
    divider=Gtk.Separator(); divider.set_margin_top(24); card.append(divider)
    error=label('','import-error error',True); error.set_visible(False); error.set_margin_top(8); card.append(error)
    footer=box(spacing=8); footer.set_margin_top(15); footer.set_halign(Gtk.Align.END); card.append(footer)
    def done():
        try:
            value=source.get_text().strip()
            if Path(value).is_absolute():
                if not Path(value).is_dir(): raise ImportError('That folder is unavailable.')
                spec={'type':'folder','location':str(Path(value).absolute())}
            else:
                github_source(value)
                if not selected['branch']: raise ImportError('Choose an available branch first.')
                spec={'type':'github','location':value,'branch':selected['branch']}
            if not name.get_text().strip(): raise ImportError('Give the project a name.')
            buf=prompt.get_buffer(); instructions=buf.get_text(buf.get_start_iter(),buf.get_end_iter(),False)
            sent=owner.service.send('retryImport',source=spec) if retry else owner.service.send('importProject',name=name.get_text().strip(),source=spec,instructions=instructions)
            if sent: owner.dismiss_dialog(dialog)
        except (ValueError,OSError) as exc: error.set_text(str(exc)); error.set_visible(True)
    cancel=button('Cancel',lambda:owner.dismiss_dialog(dialog),tone='plain',width=69); footer.append(cancel)
    submit=button('Import',done,tone='dark',width=80); submit.set_sensitive(False); footer.append(submit)
    name.connect('changed',name_changed); source.connect('changed',suggest); source.connect('activate',lambda e:done() if submit.is_sensitive() else None)
    owner.targets.update({'import-name':name,'import-source':source,'import-choose':pick,'import-prompt':prompt,'import-submit':submit,'import-cancel':cancel,
                          'import-error':error,'import-branch':branch_button,'import-branch-label':branch_caption,'import-branch-search':search,'import-branch-options':choices,'import-branch-arrow':arrow})
    if retry:
        name.set_text(owner.project.get('name','')); name.set_editable(False)
        prompt.get_buffer().set_text((owner.project.get('import') or {}).get('instructions','')); prompt.set_editable(False)
        spec=owner.data.get('importSource') or {}; selected['remembered']=spec.get('branch'); selected['rememberedLocation']=spec.get('location')
        source.set_text(spec.get('location') or (owner.project.get('import') or {}).get('sourceUrl',''))
    dialog.present(); (source if retry else name).grab_focus()
