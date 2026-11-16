"""Engineering adversaries using the production isolation engine. Not an app API."""
from pathlib import Path
from boundary import CONFIG, run as isolated, supported

HERE=Path(__file__).resolve().parent
MODES={'isolation','scratch','file-limit','pids','memory','cpu','output','descendants',
       'version-python','version-git','version-gcc'}

def run(mode,source,**kwargs):
    if mode not in MODES:raise ValueError('Unknown fixture; no arbitrary argv')
    command={
        'version-python':[CONFIG['python'],'-I','-S','--version'],
        'version-git':[CONFIG['git'],'--no-pager','--version'],
        'version-gcc':[CONFIG['gcc'],'--version'],
    }.get(mode,[CONFIG['python'],'-I','-S','/probe.py',mode])
    return {'mode':mode,**isolated(source,command,[(str(HERE/'inner.py'),'/probe.py')],**kwargs)}
