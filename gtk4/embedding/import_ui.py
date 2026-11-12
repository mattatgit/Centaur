"""Figma 27:741 import form, using Centaur's native overlay and controls."""
from pathlib import Path
from gi.repository import Gtk, GLib
from ui import label, button
from source_import import github_url, ImportError


def suggested_name(value):
    return value.strip().rstrip('/').rsplit('/',1)[-1].removesuffix('.git').replace('_',' ').replace('-',' ').strip()


def show_import(owner, retry=False):
    dialog,card=owner.dialog('Import a project',408)
    owner.clear(card); card.add_css_class('import-dialog'); card.set_spacing(0)
    form=Gtk.Fixed(); form.set_size_request(360,400); card.append(form)
    def place(widget,x,y,width,height):
        widget.set_size_request(width,height); form.put(widget,x,y); return widget
    place(label('Import a project','import-title'),0,0,360,36)
    place(Gtk.Separator(),0,48,360,1)
    place(label('Name','import-caption'),0,62,360,12)
    name=place(Gtk.Entry(placeholder_text='Give the Centaur project a name',max_length=100,css_classes=['import-field']),0,80,360,40)
    place(label('Source','import-caption'),0,142,360,12)
    source_box=place(Gtk.Overlay(css_classes=['import-source']),0,160,360,40)
    source=Gtk.Entry(placeholder_text='Choose a folder or enter a Github repo URL',css_classes=['import-field','import-source-entry'])
    source.set_hexpand(True); source_box.set_child(source)
    selected={'folder':None,'nameEdited':False,'settingName':False}
    def suggest(*unused):
        if selected['folder'] and source.get_text()!=selected['folder']: selected['folder']=None
        if not selected['nameEdited']:
            selected['settingName']=True; name.set_text(suggested_name(source.get_text())); selected['settingName']=False
        submit.set_sensitive(bool(name.get_text().strip() and source.get_text().strip()))
    def name_changed(entry):
        if not selected['settingName']: selected['nameEdited']=True
        submit.set_sensitive(bool(name.get_text().strip() and source.get_text().strip()))
    def chosen(chooser,result):
        try:
            folder=chooser.select_folder_finish(result)
            if folder and folder.get_path() and dialog.get_visible():
                selected['folder']=folder.get_path(); source.set_text(folder.get_path())
        except GLib.Error: pass # native cancel is not an import error
    def choose():
        chooser=Gtk.FileDialog(title='Choose a project folder',modal=True)
        chooser.select_folder(owner.window,None,chosen)
    pick=button('Choose',choose,'import-folder.svg','import-choose',tone='plain',width=88,height=24)
    pick.set_halign(Gtk.Align.END); pick.set_valign(Gtk.Align.CENTER); pick.set_margin_end(8); source_box.add_overlay(pick)
    place(label('Prompt','import-caption'),0,222,360,12)
    prompt=Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR,accepts_tab=False,css_classes=['import-prompt'])
    prompt_box=Gtk.Overlay(css_classes=['import-prompt-box'])
    scroll=Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER); scroll.set_child(prompt); prompt_box.set_child(scroll)
    placeholder=label('Let the Centaur agent know if you have any instructions','import-placeholder',True)
    placeholder.set_can_target(False); placeholder.set_halign(Gtk.Align.START); placeholder.set_valign(Gtk.Align.START)
    placeholder.set_margin_start(16); placeholder.set_margin_top(12); placeholder.set_margin_end(16); prompt_box.add_overlay(placeholder)
    prompt.get_buffer().connect('changed',lambda b:placeholder.set_visible(b.get_char_count()==0))
    place(prompt_box,0,240,360,88)
    place(Gtk.Separator(),0,352,352,1)
    error=label('','import-error error',True); error.set_visible(False); owner.targets['import-error']=error
    # Inline validation occupies unused lower-left space, never replaces chat.
    place(error,0,361,168,39)
    def done():
        try:
            value=source.get_text().strip()
            if selected['folder'] or Path(value).is_absolute():
                if not Path(value).is_dir(): raise ImportError('That folder is unavailable.')
                spec={'type':'folder','location':str(Path(value).absolute())}
            else: spec={'type':'github','location':github_url(value)}
            if not name.get_text().strip(): raise ImportError('Give the project a name.')
            buf=prompt.get_buffer(); instructions=buf.get_text(buf.get_start_iter(),buf.get_end_iter(),False)
            if retry:
                owner.service.send('retryImport',source=spec)
            else:
                owner.service.send('importProject',name=name.get_text().strip(),source=spec,instructions=instructions)
            owner.dismiss_dialog(dialog)
        except (ValueError,OSError) as exc:
            error.set_text(str(exc)); error.set_visible(True)
    cancel=place(button('Cancel',lambda:owner.dismiss_dialog(dialog),tone='plain',width=69),203,368,69,32)
    submit=place(button('Import',done,tone='dark',width=80),280,368,80,32); submit.set_sensitive(False)
    name.connect('changed',name_changed); source.connect('changed',suggest); source.connect('activate',lambda e:done() if submit.is_sensitive() else None)
    owner.targets.update({'import-name':name,'import-source':source,'import-choose':pick,'import-prompt':prompt,'import-submit':submit,'import-cancel':cancel})
    if retry:
        name.set_text(owner.project.get('name','')); name.set_editable(False)
        prompt.get_buffer().set_text((owner.project.get('import') or {}).get('instructions','')); prompt.set_editable(False)
    dialog.present(); (source if retry else name).grab_focus()
