"""Private packaged transport for the broker's fixed diagnostics."""
import json
import re
import sys
import subprocess
from boundary import CONFIG,HERE,run

def main():
    request=json.loads(sys.stdin.buffer.read(8193))
    operation=request['operation']
    if operation=='runtime_version' and set(request)=={'operation','runtime','source'}:
        runtime=request['runtime']
        command={'python':[CONFIG['python'],'-I','-S','--version'],
                 'git':[CONFIG['git'],'--no-pager','--version'],
                 'gcc':[CONFIG['gcc'],'--version']}[runtime]
        mounts=[]
    elif operation=='validate_manifest' and set(request)=={'operation','path','source'}:
        path=request['path']
        if (not isinstance(path,str) or len(path)>1024 or '\\' in path or
            any(p in ('','.','..') for p in path.split('/')) or
            any(ord(c)<32 for c in path) or not path.endswith(('.json','.toml'))):raise ValueError('Invalid manifest')
        command=[CONFIG['python'],'-I','-S','/diagnostic.py',operation,path]
        mounts=[(str(HERE/'diagnostic.py'),'/diagnostic.py')]
    else:raise ValueError('Unknown fixed diagnostic')
    result=run(request['source'],command,mounts)
    state=dict(line.split('=',1) for line in result['unitState'].splitlines() if '=' in line)
    metadata={'isolated':result['exit']==0 and not result['descendantsRemain'],'elapsed':result['elapsed'],'exitCode':result['exit'],
              'reason':result['reason'],'serviceResult':state.get('Result','unavailable'),
              'descendantsRemain':result['descendantsRemain']}
    # No systemd/Bubblewrap/host stderr text crosses the private protocol.
    if result['reason']!='completed' or result['exit']!=0 or result['descendantsRemain']:
        code={'output-limit':'output_limit','cancelled':'interrupted','watchdog':'timeout'}.get(result['reason'],'isolation_unavailable')
        if state.get('Result')=='timeout':code='timeout'
        elif state.get('Result')=='oom-kill':code='resource_limit'
        return {'ok':False,'error':{'code':code},'execution':metadata}
    text=result['output']
    if operation=='runtime_version':
        # Only the version token of the host-chosen executable enters context.
        pattern={'python':r'^Python ([0-9]+\.[0-9]+\.[0-9]+)',
                 'git':r'^git version ([0-9]+\.[0-9]+\.[0-9]+)',
                 'gcc':r'^gcc.*? ([0-9]+\.[0-9]+\.[0-9]+)'}[runtime]
        match=re.search(pattern,text)
        if not match:raise ValueError('Unexpected version output')
        data={'runtime':runtime,'version':match[1],'availability':'packagedDiagnosticRuntime'}
    else:
        data=json.loads(text)
        if not isinstance(data,dict) or set(data)-{'valid','format','code','line','column'}:raise ValueError('Unexpected parser output')
    return {'ok':True,'data':data,'execution':metadata}

if __name__=='__main__':
    try:result=main()
    except (OSError,ValueError,KeyError,TypeError,RuntimeError,subprocess.SubprocessError):result={'ok':False,'error':{'code':'isolation_unavailable'}}
    print(json.dumps(result))
