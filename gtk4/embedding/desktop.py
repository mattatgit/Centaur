"""Per-user desktop integration for the separate, installed GTK4 profile."""
import os
from pathlib import Path
from updater import profile_path, read_json, write_json

APP_ID='org.centaur.Gtk4'
ENVIRONMENT=('GSK_RENDERER','GDK_BACKEND','LIBGL_ALWAYS_SOFTWARE','CENTAUR_AGENT')


def settings_path():
    return Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'centaur-gtk4/desktop.json'


def launch_settings():
    value=read_json(settings_path())
    if not isinstance(value,dict): return None
    environment=value.get('environment',{})
    for key,item in (environment.items() if isinstance(environment,dict) else ()):
        if key in ENVIRONMENT and isinstance(item,str): os.environ[key]=item
    data=value.get('dataDir')
    return Path(data) if isinstance(data,str) and Path(data).is_absolute() else None


def register(package,data):
    package=Path(package); profile=profile_path()
    executable=profile/'bin/centaur-gtk4'
    if not executable.is_file() or executable.resolve()!=(package/'bin/centaur-gtk4').resolve(): return False
    # Remember launch configuration, never credentials. The menu entry must
    # retain the current VM renderer, custom project root and OMP executable.
    write_json(settings_path(),{'dataDir':str(data),'environment':{key:os.environ[key] for key in ENVIRONMENT if key in os.environ}})
    share=Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))
    def link(source,destination):
        destination.parent.mkdir(parents=True,exist_ok=True)
        # Leave user-created desktop entries/icons alone. Our links follow the
        # dedicated profile across updates instead of pinning an old package.
        if not destination.exists() and not destination.is_symlink(): destination.symlink_to(source)
    icons=profile/'share/icons/hicolor'
    link(icons/'index.theme',share/'icons/hicolor/index.theme')
    for source in icons.rglob(APP_ID+'*'):
        if source.is_file(): link(source,share/'icons/hicolor'/source.relative_to(icons))
    link(profile/'share/applications'/(APP_ID+'.desktop'),share/'applications'/(APP_ID+'.desktop'))
    return True
