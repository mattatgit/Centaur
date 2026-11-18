"""Clone selected project state/source privately inside the VM; never identities."""
from pathlib import Path
import os,sys,json,subprocess,time,threading,shutil,uuid,hashlib,argparse,platform

def main():
    parser=argparse.ArgumentParser(description='Reproduce a GTK edit in disposable NixOS data; export only lifecycle/shape metadata.')
    parser.add_argument('--project',type=Path,required=True,help='Existing project directory, read only')
    parser.add_argument('--product',type=Path,required=True,help='Built GTK4 package directory')
    parser.add_argument('--output',type=Path,required=True,help='New private output directory')
    parser.add_argument('--agent',default=shutil.which('omp') or str(Path.home()/'.local/bin/omp'))
    parser.add_argument('--model',default='openai-codex/gpt-6.1-sol')
    parser.add_argument('--request',required=True)
    args=parser.parse_args()
    assert platform.machine()=='aarch64' and 'ID=nixos' in Path('/etc/os-release').read_text()
    original=args.project.resolve();folder=args.output.resolve()
    if not folder.is_relative_to(Path('/tmp').resolve()) or folder==original or original in folder.parents:
        raise ValueError('Use a fresh disposable output outside the original project, under /tmp.')
    os.umask(0o077);folder.mkdir(mode=0o700);label=folder.name;product=args.product.resolve()
    owner_before={n:hashlib.sha256((original/n).read_bytes()).hexdigest() for n in ('App.gtk.json','.centaur/state.json')}
    s=json.loads((original/'.centaur/state.json').read_text());newid=str(uuid.uuid4());data=folder/'data';project=data/'projects'/newid;project.mkdir(parents=True,mode=0o700);(project/'.centaur').mkdir()
    source=(original/'App.gtk.json').read_bytes();assert json.loads(source).get('format')=='gtk4-v1';(project/'App.gtk.json').write_bytes(source)
    s['id']=newid;s['agentQueue']=[];s['proposal']={}
    for k in ('activeRequest','networkAcks','sharing','agentActivity'):s.pop(k,None)
    (project/'.centaur/state.json').write_text(json.dumps(s,ensure_ascii=False,separators=(',',':')))
    if s.get('import'):
        storage=s['import']['storage'];assert str(uuid.UUID(storage))==storage
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gtk4/embedding'))
        from import_policy import excluded
        def omitted(path,names):
            return [n for n in names if (Path(path)/n).is_symlink() or excluded(Path(n)) or not ((Path(path)/n).is_file() or (Path(path)/n).is_dir())]
        managed=original/'.centaur/import'/storage/'source';assert not managed.is_symlink()
        shutil.copytree(managed,project/'.centaur/import'/storage/'source',ignore=omitted)
    for cmd in (['git','-c','init.templateDir=','init','-q',str(project)],['git','-C',str(project),'add','App.gtk.json','.centaur/state.json'],['git','-C',str(project),'-c','user.name=Disposable verification','-c','user.email=verification@invalid','-c','core.hooksPath=/dev/null','commit','-qm','Disposable baseline']):subprocess.run(cmd,check=True,capture_output=True,env=dict(os.environ,GIT_CONFIG_GLOBAL='/dev/null',GIT_CONFIG_NOSYSTEM='1'))
    observer=folder/'omp-observer';observer.write_text('#!'+sys.executable+'\n'+Path(__file__).with_name('observe-omp-stream.py').read_text());observer.chmod(0o700)
    env=dict(os.environ,CENTAUR_AGENT=str(observer),CENTAUR_OBSERVATIONS=str(folder/'observations'),CENTAUR_MODEL=args.model,CENTAUR_REAL_OMP=args.agent,CENTAUR_HOST=str(product/'bin/centaur-host'),CENTAUR_GTK_HOST=str(product/'bin/centaur-host'),CENTAUR_GTK_RUNNER=str(product/'bin/centaur-gtk4-preview'),CENTAUR_GTK_IMPORT_TOOL=str(product/'bin/centaur-gtk4-import'),CENTAUR_AUTHOR='Matt')
    state={};errors=[];phases=[]
    p=subprocess.Popen([str(product/'bin/centaur-gtk4-bridge'),'--data-dir',str(data)],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
    def receive():
     for line in p.stdout:
      try:v=json.loads(line)
      except ValueError:continue
      if v.get('type')=='snapshot':
       state.clear();state.update(v)
       phase=v.get('project',{}).get('agentActivity',{}).get('phase')
       if phase and phase not in phases:phases.append(phase)
      elif v.get('type')=='error':errors.append('coordinator_error')
    threading.Thread(target=receive,daemon=True).start()
    def send(t,**v):p.stdin.write(json.dumps(dict(type=t,**v))+'\n');p.stdin.flush()
    def until(fn,seconds=20):
     end=time.monotonic()+seconds
     while time.monotonic()<end:
      if fn():return
      time.sleep(.05)
     raise TimeoutError('Disposable coordinator did not reach its expected state')
    summary={'label':label,'ownerProfileActivated':False,'privateSourceCopyOnlyInVm':True};start=time.monotonic()
    try:
     until(lambda:state.get('snapshotReady'));send('open',projectId=newid);until(lambda:state.get('project',{}).get('id')==newid)
     before=len(state['project']['messages']);send('message',text=args.request)
     until(lambda:state.get('busy'),10)
     until(lambda:not state.get('busy') and len(state.get('project',{}).get('messages',[]))>before+1,240)
     current=state['project'];summary.update(seconds=round(time.monotonic()-start,3),revisionBefore=s['revision'],revisionAfter=current['revision'],sourceChanged=(project/'App.gtk.json').read_bytes()!=source,failureDetails=[m['agentDiagnostics'] for m in current['messages'][before:] if m.get('agentDiagnostics')],completionMessageKinds=[m.get('kind') for m in current['messages'][before:]],coordinatorErrors=errors)
    except Exception as e:summary.update(error=type(e).__name__,seconds=round(time.monotonic()-start,3))
    finally:
     if p.poll() is None:
      send('cancel');p.stdin.close();p.wait(timeout=8)
     subprocess.run([str(product/'bin/centaur-host'),'--data-dir',str(data),'--stop'],env=env,capture_output=True,timeout=10)
     summary['ownerSourceAndStateUnchanged']=all(hashlib.sha256((original/n).read_bytes()).hexdigest()==h for n,h in owner_before.items());assert summary['ownerSourceAndStateUnchanged']
     summary['observedPhases']=phases
     saved=json.loads((project/'.centaur/state.json').read_text());local=saved.get('importLocal',{});rid=local.get('requestId')
     summary['brokerResults']=[{'operation':r.get('operation'),'ok':r.get('ok'),'files':list(r.get('data',{}).get('files',{}))} for r in local.get('diagnostics',{}).get('results',[]) if r.get('requestId')==rid]
     summary['unchangedFiles']=[k for k,v in json.loads((project/'App.gtk.json').read_text())['files'].items() if v==json.loads(source)['files'][k]]
     summary['runs']=[json.loads(x.read_text()) for x in sorted((folder/'observations').glob('run-*.json'))]
     (folder/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('REPRODUCTION_SUMMARY='+json.dumps(summary),flush=True)


if __name__ == "__main__":
    main()
