"""Typed sandbox diagnostics over policy-filtered managed source selections."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from import_policy import ImportError, relative

OPERATIONS={'runtime_version','validate_manifest'}

def validate(tool):
    operation=tool.get('operation')
    fields={'runtime_version':{'runtime'},'validate_manifest':{'path'}}
    if operation not in fields or set(tool)-fields[operation]-{'operation','scope'}:
        raise ImportError('Choose a fixed diagnostic operation.',code='invalid_request')
    if tool.get('scope','source') not in ('source','adaptation'):
        raise ImportError('Choose source or adaptation.',code='invalid_request')
    if operation=='runtime_version' and tool.get('runtime') not in ('python','git','gcc'):
        raise ImportError('Choose a packaged diagnostic runtime.',code='invalid_request')
    if operation=='validate_manifest':
        path=relative(tool.get('path'))
        if path.suffix not in ('.json','.toml'):
            raise ImportError('Choose a JSON or TOML manifest.',code='invalid_request')


def execute(root,tool,output=None):
    from import_broker import Tree,error_code
    result={'schemaVersion':1,'operation':tool.get('operation'),'scope':tool.get('scope','source'),
            'ok':False,'sourceAvailable':False,'truncated':False}
    tree=None;proc=None
    try:
        validate(tool)
        base=Path(root)/'source'
        if result['scope']=='adaptation':
            parts=relative(output).parts
            if len(parts)!=2 or parts[0]!='adaptations':
                raise ImportError('No adaptation is available.',code='source_unavailable')
            base=Path(root).joinpath(*parts)
        tree=Tree(base);result['sourceAvailable']=True
        launcher=os.environ.get('CENTAUR_IMPORT_SANDBOX','')
        if not launcher or not Path(launcher).is_absolute():
            raise ImportError('Isolated diagnostics are unavailable.',code='isolation_unavailable')
        # A new private snapshot contains only requested policy-filtered text.
        # The command never mounts the original tree, history or host paths.
        with tempfile.TemporaryDirectory(prefix='centaur-diagnostic-snapshot-') as tmp:
            source=Path(tmp)/'source';source.mkdir(mode=0o700)
            request={k:v for k,v in tool.items() if k!='scope'};request['source']=str(source)
            if tool['operation']=='validate_manifest':
                text,truncated=tree.text(tool['path'])
                if truncated or len(text.encode())>240000:
                    raise ImportError('Choose a smaller manifest.',code='input_limit')
                target=source/tool['path'];target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(text);target.chmod(0o400)
            # No inherited provider/configuration environment enters the helper.
            env={k:os.environ[k] for k in ('XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS') if k in os.environ}
            env['LANG']='C'
            proc=subprocess.Popen([launcher],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL,env=env,close_fds=True)
            raw,_=proc.communicate(json.dumps(request).encode(),timeout=16)
            if len(raw)>48000:raise ImportError('Diagnostic output limit reached.',code='output_limit')
            reply=json.loads(raw)
            if not isinstance(reply,dict) or set(reply)-{'ok','data','execution','error'}:
                raise ValueError('Invalid private result')
            result.update(reply)
    except (ImportError,OSError,ValueError,TypeError,subprocess.SubprocessError) as error:
        result['ok']=False;result.pop('data',None)
        result['error']={'code':error_code(error) if isinstance(error,ImportError) else 'isolation_unavailable'}
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=1.5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=1)
        if tree:tree.close()
    return result
