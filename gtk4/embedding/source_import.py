"""Read-only source acquisition/inspection. Never builds or imports project code.

The coordinator owns state and chat; this bounded worker only touches its own
managed import directory. Git configuration, filters, hooks and submodules from
the source are never used. Preview execution is a separate explicit action.
"""
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import urlsplit, unquote

MAX_FILES, MAX_BYTES, MAX_FILE = 20000, 128*1024*1024, 16*1024*1024
SKIP = {'.git', '.hg', '.svn', 'node_modules', '.venv', 'venv', '__pycache__',
        '.ssh', '.aws', '.gnupg', '.centaur', 'result', 'target', 'build', 'dist'}
SECRET = re.compile(r'(^\.env($|\.)|credentials|secrets?\.|^id_(rsa|ed25519)|\.(pem|key|p12|pfx)$|^\.netrc$|^\.npmrc$)', re.I)
TOKEN = re.compile(r'(?:github_pat_|gh[pousr]_|sk-[A-Za-z0-9]|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY|(?i:api[_-]?key|access[_-]?token|password)\s*[=:]\s*[\"\']?[^\s\"\']{12,})')


class ImportError(ValueError):
    pass


def inside(path, parent):
    try: path.relative_to(parent); return True
    except ValueError: return False


def github_url(value):
    return github_source(value)['repository']+'.git'


def github_source(value):
    url=urlsplit(value.strip())
    match=re.fullmatch(r'/([A-Za-z0-9][A-Za-z0-9_.-]*)/([A-Za-z0-9][A-Za-z0-9_.-]*?)(?:\.git)?(?:/tree/(.+?))?/?',url.path)
    if url.scheme!='https' or url.netloc!='github.com' or url.query or url.fragment:
        match=None
    if not match or match[2] in ('.', '..'):
        raise ImportError('Use a GitHub repository or branch URL without credentials.')
    tail=unquote(match[3] or '').rstrip('/')
    if tail and (any(p in ('','.','..') for p in tail.split('/')) or any(c in tail for c in '\\?*[\x00\r\n')):
        raise ImportError('That GitHub branch URL is invalid.')
    return {'repository':'https://github.com/'+match[1]+'/'+match[2], 'tree':tail}


def branches(value, branch=None, allow_missing=False):
    parsed=github_source(value); url=github_url(value)
    # HEAD's symbolic target determines the default, never branch-name guesses.
    # https://git-scm.com/docs/git-ls-remote
    raw=git(['ls-remote','--symref','--',url,'HEAD','refs/heads/*']).decode('utf-8')
    refs={}; default=None
    for line in raw.splitlines():
        left,_,ref=line.partition('\t')
        if left.startswith('ref: refs/heads/') and ref=='HEAD': default=left[len('ref: refs/heads/'):]
        elif ref.startswith('refs/heads/') and re.fullmatch('[a-f0-9]{40}|[a-f0-9]{64}',left): refs[ref[len('refs/heads/'):]]=left
    if not refs: raise ImportError('No branches are available. Check this machine’s access to the repository.')
    tail=parsed['tree']; directory=''
    matches=[name for name in refs if tail==name or tail.startswith(name+'/')]
    inferred=max(matches,key=len) if matches else None
    if tail and not inferred and not branch and not allow_missing: raise ImportError('I couldn’t retrieve the branch in that URL. Please check the selection and try again.')
    if inferred: directory=tail[len(inferred):].lstrip('/')
    selected=branch if branch else inferred or default
    missing=selected not in refs or bool(tail and not inferred and not branch)
    if missing and not allow_missing: raise ImportError('I couldn’t retrieve that branch. Please check the selection and try again.')
    return {'repository':parsed['repository'],'sourceUrl':value.strip(),'defaultBranch':default,
            'branches':sorted(refs),'branch':None if missing else selected,'commit':refs.get(selected) if not missing else None,'directory':directory,
            'selectionError':'That branch is unavailable. Please choose another branch.' if missing else ''}


def relative(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or any(part in ('', '.', '..') for part in value.split('/')) or '\\' in value or '\x00' in value:
        raise ImportError('That file is outside the imported source.')
    return path


def excluded(path):
    return any(p in SKIP or SECRET.search(p) for p in path.parts)


def git(args, cwd=None, consume=None):
    env = {k:v for k,v in os.environ.items() if not k.startswith(('GIT_', 'SSH_ASKPASS'))}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_TERMINAL_PROMPT='0', GIT_LFS_SKIP_SMUDGE='1')
    # Keep the user's credential helper (e.g. gh), but disable source-controlled
    # execution and protocol rewrites. No token is accepted in a source URL.
    command = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'protocol.ext.allow=never',
               '-c', 'protocol.file.allow=always', '-c', 'submodule.recurse=false', *args]
    process=subprocess.Popen(command,cwd=cwd,env=env,stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL,start_new_session=True)
    try:
        if consume:
            consume(process.stdout); process.wait(timeout=100); output=b''
        else: output=process.communicate(timeout=100)[0]
        if process.returncode:
            raise ImportError('Could not read that repository. Check its address and this machine’s GitHub access, then retry.')
        return output
    finally:
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try: process.wait(timeout=1)
            except subprocess.TimeoutExpired: os.killpg(process.pid,signal.SIGKILL); process.wait()
        process.stdout.close()


def acquire(root, source):
    if (root/'source').exists():
        return inspect(root)
    root.mkdir(parents=True, exist_ok=True,mode=0o700); root.chmod(0o700)
    work = Path(tempfile.mkdtemp(prefix='acquire-', dir=root))
    destination=work/'source'; destination.mkdir()
    count=total=skipped=0
    def save(name, stream, size, executable=False):
        nonlocal count,total,skipped
        path=relative(name)
        if excluded(path): skipped+=1; return
        count+=1; total+=size
        if count>MAX_FILES or total>MAX_BYTES or size>MAX_FILE:
            raise ImportError('This source is too large for the first import prototype (128 MB, 20,000 files, 16 MB per file).')
        target=destination/str(path); target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as output: shutil.copyfileobj(stream,output,1024*1024)
        target.chmod(0o700 if executable else 0o600)
    try:
        provenance={}
        if source['type']=='github':
            url=github_url(source['location'])
            resolved=branches(source['location'],source.get('branch'))
            history=work/'history.git'
            git(['clone','--bare','--single-branch','--branch',resolved['branch'],'--',url,str(history)])
            actual=git(['--git-dir='+str(history),'rev-parse','refs/heads/'+resolved['branch']+'^{commit}']).decode().strip()
            head=git(['--git-dir='+str(history),'symbolic-ref','HEAD']).decode().strip()
            if actual!=resolved['commit'] or head!='refs/heads/'+resolved['branch']:
                raise ImportError('That branch changed while it was being copied. Please retry; no other branch was used.')
            if resolved['directory'] and git(['--git-dir='+str(history),'cat-file','-t',actual+':'+resolved['directory']]).strip()!=b'tree':
                raise ImportError('The folder in that URL is unavailable on the selected branch.')
            provenance={k:resolved[k] for k in ('repository','sourceUrl','branch','commit','directory')}
            # Preserve committed bytes, rather than a release archive whose
            # .gitattributes may omit files or substitute version placeholders.
            # https://git-scm.com/docs/git-archive#_attributes
            (history/'info').mkdir(exist_ok=True)
            (history/'info/attributes').write_text('* -export-ignore -export-subst\n')
            # git archive doesn't checkout filters, hooks, .gitmodules or LFS.
            def unpack(stream):
                nonlocal skipped
                with tarfile.open(fileobj=stream,mode='r|') as files:
                    for item in files:
                        if item.isfile(): save(item.name,files.extractfile(item),item.size,bool(item.mode&0o111))
                        elif not item.isdir(): skipped+=1
            git(['--git-dir='+str(history),'archive','--format=tar','HEAD'],consume=unpack)
            # Prevent accidental upstream writes even when inspecting manually.
            git(['--git-dir='+str(history),'config','remote.origin.pushurl','disabled://centaur-import'])
        elif source['type']=='folder':
            original=Path(source['location'])
            if not original.is_absolute() or not original.is_dir() or original.is_symlink():
                raise ImportError('That folder is unavailable. Choose a local project folder and retry.')
            original=original.resolve()
            if inside(root.resolve(),original):
                raise ImportError('Choose the project folder, rather than a folder containing Centaur’s own data.')
            for directory, folders, files in os.walk(original,followlinks=False):
                folders[:]=[f for f in folders if not excluded(PurePosixPath(f)) and not (Path(directory)/f).is_symlink()]
                for name in files:
                    file=Path(directory)/name
                    if file.is_symlink() or not file.is_file(): skipped+=1; continue
                    with file.open('rb') as stream:
                        stat=file.stat(); save(file.relative_to(original).as_posix(),stream,stat.st_size,bool(stat.st_mode&0o111))
            # Preserve reachable local history independently of the working copy.
            # Do not follow worktree .git files or copy source configuration/hooks.
            if (original/'.git').is_dir() and not (original/'.git').is_symlink():
                git(['clone','--bare','--no-local','--no-hardlinks','--',str(original),str(work/'history.git')])
                git(['--git-dir='+str(work/'history.git'),'remote','remove','origin'])
        else: raise ImportError('Choose a local folder or a GitHub repository.')
        if not count: raise ImportError('That folder has no importable source files. Choose the application’s source folder.')
        (work/'source').rename(root/'source')
        if (work/'history.git').exists(): (work/'history.git').rename(root/'history.git')
        result=inspect(root); result.update(fileCount=count,bytes=total,omitted=skipped,**provenance)
        return result
    finally: shutil.rmtree(work,ignore_errors=True)


def read_files(root, paths, output=None):
    source=(root/'source').resolve()
    if output is not None:
        source=(root/str(relative(output))).resolve()
        if not inside(source,(root/'adaptations').resolve()):
            raise ImportError('That adaptation is outside the project’s output.')
    result={}; total=0
    if len(paths)>12: raise ImportError('Inspect up to 12 source files at a time.')
    for name in paths:
        path=relative(name)
        if excluded(path): result[name]='[Private or generated file omitted]'; continue
        file=source/str(path)
        if file.is_symlink() or not inside(file.resolve(),source) or not file.is_file():
            result[name]='[File unavailable]'; continue
        with file.open('rb') as stream: raw=stream.read(24000)
        total+=len(raw)
        if total>96000: result[name]='[Inspection byte limit reached]'; continue
        try: text=raw.decode('utf-8')
        except UnicodeError: result[name]='[Binary file]'; continue
        if '\x00' in text or TOKEN.search(text): result[name]='[Potential credentials omitted]'
        else: result[name]=text+('\n[Truncated]' if file.stat().st_size>24000 else '')
    return result


def inspect(root):
    source=root/'source'
    paths=sorted(p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file() and not p.is_symlink())
    names={PurePosixPath(p).name for p in paths}
    framework=('GTK4 bundle' if 'App.gtk.json' in paths else 'Nix / Rust' if 'flake.nix' in names and 'Cargo.toml' in names
               else 'Rust' if 'Cargo.toml' in names else 'Web / JavaScript' if 'package.json' in names
               else 'iOS / Swift' if any(p.endswith(('.swift','.xcodeproj/project.pbxproj')) for p in paths)
               else 'Python' if any(p.endswith('.py') for p in paths) else 'Unknown')
    preferred=['App.gtk.json','flake.nix','Cargo.toml']
    preferred += sorted([p for p in paths if PurePosixPath(p).name in ('Cargo.toml','flake.nix','package.json','pyproject.toml')],key=lambda p:(len(PurePosixPath(p).parts),p))
    preferred += ['README.md']+[p for p in paths if p.endswith(('/main.rs','/lib.rs'))][:3]
    preferred += [p for p in paths if p.endswith(('.swift','.py','.ui','.html','.css','.js','.tsx'))][:7]
    files=read_files(root,[p for p in dict.fromkeys(preferred) if p in paths][:12])
    candidate=False
    if 'App.gtk.json' in paths:
        from bundle import load_bundle
        try:
            bundle=load_bundle(source/'App.gtk.json') # syntax only, NEVER construct()
            (root/'candidate.gtk.json').write_text(json.dumps(bundle))
            candidate=True
        except (ValueError,SyntaxError,KeyError,TypeError,AttributeError): pass
    return dict(framework=framework,paths=paths[:1500],inventoryTruncated=len(paths)>1500,files=files,candidate=candidate)


def stage(root, data):
    files=data.get('files',{})
    if not isinstance(files,dict) or not 1<=len(files)<=48 or sum(len(v.encode()) for v in files.values() if isinstance(v,str))>256000:
        raise ImportError('That adaptation is too large. Ask for a smaller step.')
    for name,contents in files.items():
        path=relative(name)
        if excluded(path) or not isinstance(contents,str) or TOKEN.search(contents):
            raise ImportError('That adaptation contains an unsafe file or possible credential.')
    output=root/'adaptations'; output.mkdir(exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='version-',dir=output))
    for name,contents in files.items():
        target=folder/str(relative(name)); target.parent.mkdir(parents=True,exist_ok=True); target.write_text(contents)
    output=folder.relative_to(root).as_posix()
    return {'output':output,'target':str(data.get('target',''))[:80],
            'inspection':{'paths':list(files),'files':read_files(root,list(files)[:12],output)}}


def main():
    def interrupted(*unused): raise ImportError('The import was interrupted. Your source is unchanged; please retry.')
    signal.signal(signal.SIGTERM,interrupted)
    try:
        request=json.load(sys.stdin); mode=request['mode']
        root=Path(request.get('root','.')).resolve()
        if mode=='branches': result=branches(request['location'],request.get('branch'),allow_missing=True)
        elif mode=='acquire': result=acquire(root,request['source'])
        elif mode=='read':
            scope=request.get('scope','source')
            if scope not in ('source','adaptation'): raise ImportError('Choose source or adaptation files to inspect.')
            if scope=='adaptation' and not isinstance(request.get('output'),str):
                raise ImportError('No adaptation is available to inspect yet.')
            result={'scope':scope,'files':read_files(root,request['paths'],request['output'] if scope=='adaptation' else None)}
        elif mode=='stage': result=stage(root,request)
        elif mode=='bundle':
            from bundle import load_bundle
            path=root/'candidate.gtk.json'; path.write_text(json.dumps(request['bundle']))
            load_bundle(path); result={'candidate':True}
        else: raise ImportError('Unknown import operation.')
        print(json.dumps({'ok':True,**result}))
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError,tarfile.TarError) as error:
        message=str(error) if isinstance(error,ImportError) else 'The import was interrupted or could not be read. Your source is unchanged; please retry.'
        print(json.dumps({'ok':False,'message':message})); return 1
    return 0


if __name__=='__main__': raise SystemExit(main())
