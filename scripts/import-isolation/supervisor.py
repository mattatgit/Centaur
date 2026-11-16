"""Engineering-only Phase 3 isolation supervisor. Not an agent command API.

No shell, imported executable or model-supplied argv is accepted. The test driver
selects a compiled-in adversarial fixture or a fixed packaged version command.
Do not wire this proof interface into the application as a general executor.
"""
import errno
import json
import os
from pathlib import Path
import platform
import resource
import selectors
import subprocess
import sys
import tempfile
import time
import uuid

HERE=Path(__file__).resolve().parent
CONFIG=json.loads((HERE/'config.json').read_text())
MODES={'isolation','scratch','file-limit','pids','memory','cpu','output','descendants',
       'version-python','version-git','version-gcc'}
MEMORY=128*1024*1024
SCRATCH=8*1024*1024
OUTPUT=32768
WALL_SECONDS=8

def supported():
    if platform.system()!='Linux' or platform.machine()!='aarch64':
        raise RuntimeError('ARM64 Linux is required; no fallback')
    if os.geteuid()==0:raise RuntimeError('This proof requires an unprivileged account')
    if 'nixos' not in Path('/etc/os-release').read_text().lower():
        raise RuntimeError('This proof must run on NixOS')

def source_fd(path):
    # Open each component without following symlinks, retaining the directory
    # descriptor until bwrap mounts it. No string-prefix escape checks.
    path=Path(path)
    if not path.is_absolute() or '..' in path.parts:raise ValueError('Invalid source')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        for part in path.parts[1:]:
            new=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            os.close(fd);fd=new
        return fd
    except BaseException:
        os.close(fd);raise

def group_values(group):
    values={}
    for name in ['memory.max','memory.swap.max','memory.oom.group','pids.max','cpu.max','memory.events','cpu.stat','cgroup.events']:
        p=group/name
        try:values[name]=p.read_text().strip()
        except OSError as e:
            # cgroup files disappear or return ENODEV while the service manager
            # removes an empty group. Missing effective limits at startup still
            # fail the independent checks in inside().
            if e.errno not in (errno.ENOENT,errno.ENODEV):raise
    return values

def inside(job_path):
    supported()
    job=json.loads(Path(job_path).read_text())
    if job['mode'] not in MODES:raise ValueError('Unknown fixture')
    assert os.stat(CONFIG['bwrap']).st_mode & 0o6000==0,'Setuid/setgid launcher refused'
    relative=Path('/proc/self/cgroup').read_text().strip().split('::',1)[1]
    group=Path('/sys/fs/cgroup'+relative)
    limits=group_values(group)
    assert limits['memory.max']==str(MEMORY),'Memory controller unavailable or ineffective'
    assert limits['memory.swap.max']=='0','Swap controller unavailable or ineffective'
    assert limits['memory.oom.group']=='1','OOM process-tree policy unavailable or ineffective'
    assert limits['pids.max']=='32','Process controller unavailable or ineffective'
    quota,period=map(int,limits['cpu.max'].split())
    assert quota>0 and quota*4==period,'CPU controller unavailable or ineffective'
    assert resource.getrlimit(resource.RLIMIT_CORE)==(0,0)
    assert resource.getrlimit(resource.RLIMIT_FSIZE)==(1024*1024,1024*1024)
    assert resource.getrlimit(resource.RLIMIT_NOFILE)==(64,64)
    if job.get('fault')=='mismatched-limits':raise RuntimeError('Injected missing effective limit')
    record=Path(job['record'])
    pending_record=record.with_suffix('.pending')
    pending_record.write_text(json.dumps({'group':str(group),'limits':limits}))
    os.replace(pending_record,record)
    fd=source_fd(job['source'])
    filter_path=CONFIG['filter']
    if job.get('fault')=='invalid-filter':filter_path=job['emptyFilter']
    policy=os.open(filter_path,os.O_RDONLY|os.O_NOFOLLOW)
    os.set_inheritable(fd,True);os.set_inheritable(policy,True)
    args=[CONFIG['bwrap'],'--unshare-user','--unshare-pid','--unshare-ipc','--unshare-net',
          '--unshare-uts','--unshare-cgroup','--disable-userns','--assert-userns-disabled',
          '--new-session','--die-with-parent','--cap-drop','ALL','--clearenv',
          '--dir','/nix','--dir','/nix/store']
    # Mount individual pinned runtime closure paths, never the host store.
    for path in Path(CONFIG['closure']).read_text().splitlines():
        assert path.startswith('/nix/store/') and len(Path(path).parts)==4
        args+=['--ro-bind',path,path]
    args+=['--ro-bind-fd',str(fd),'/source','--ro-bind',str(HERE/'inner.py'),'/probe.py',
           '--proc','/proc','--dir','/dev']
    for name in ['null','zero','random','urandom']:
        args+=['--dev-bind','/dev/'+name,'/dev/'+name]
    args+=['--symlink','/proc/self/fd','/dev/fd',
           '--size',str(SCRATCH),'--tmpfs','/scratch','--dir','/scratch/tmp','--dir','/scratch/home',
           '--symlink','/scratch/tmp','/tmp','--dir','/home','--symlink','/scratch/home','/home/sandbox',
           '--dir','/run','--setenv','HOME','/home/sandbox','--setenv','TMPDIR','/tmp',
           '--setenv','PATH','/no-executables','--setenv','LANG','C.UTF-8','--chdir','/source',
           '--seccomp',str(policy),'--remount-ro','/proc','--remount-ro','/']
    mode=job['mode']
    command={
        'version-python':[CONFIG['python'],'-I','-S','--version'],
        'version-git':[CONFIG['git'],'--no-pager','--version'],
        'version-gcc':[CONFIG['gcc'],'--version'],
    }.get(mode,[CONFIG['python'],'-I','-S','/probe.py',mode])
    args+=['--']+command
    if job.get('fault')=='missing-bwrap':args[0]='/nonexistent/centaur-bwrap'
    # systemd owns the process tree. Nothing sensitive is inherited even by bwrap.
    os.execve(args[0],args,{'LANG':'C'})

def control(*args):
    return subprocess.run([CONFIG['systemctl'],'--user','--no-pager',*args],
                          stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                          timeout=4,close_fds=True,text=True)

def unit_properties():
    return ['MemoryMax=128M','MemorySwapMax=0','TasksMax=32','CPUQuota=25%',
            'RuntimeMaxSec=8s','KillMode=control-group','TimeoutStopSec=500ms',
            'SendSIGKILL=yes','OOMPolicy=kill',
            'LimitCORE=0','LimitNOFILE=64','LimitFSIZE=1M','UMask=0077']

def run(mode,source,*,fault=None,cancel=False,abandon=False):
    supported()
    if mode not in MODES:raise ValueError('Unknown fixture; no arbitrary argv')
    if fault not in (None,'missing-bwrap','mismatched-limits','invalid-filter','missing-manager'):
        raise ValueError('Unknown fault injection')
    unit='centaur-isolation-proof-'+uuid.uuid4().hex+'.service'
    host_ns={n:os.readlink('/proc/self/ns/'+n) for n in ['mnt','pid','user','net','ipc','uts','cgroup']}
    with tempfile.TemporaryDirectory(prefix='centaur-isolation-job-') as tmp:
        root=Path(tmp);record=root/'started.json';job_path=root/'job.json'
        (root/'empty.bpf').touch(mode=0o600)
        job_path.write_text(json.dumps({'mode':mode,'source':str(source),'record':str(record),
                                       'fault':fault,'emptyFilter':str(root/'empty.bpf')}))
        command=[CONFIG['systemdRun'],'--user','--unit='+unit,'--wait','--pipe',
                 '--service-type=exec','--expand-environment=no','--quiet']
        command+=['--property='+p for p in unit_properties()]
        command += [CONFIG['python'],'-I','-S',str(HERE/'supervisor.py'),'--inside',str(job_path)]
        if fault=='missing-manager':command[0]='/nonexistent/centaur-systemd-run'
        output=bytearray();reason='completed';group=None;telemetry={};started=time.monotonic()
        env={k:os.environ[k] for k in ['XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS'] if k in os.environ}
        env.update({'LANG':'C','CENTAUR_FAKE_TOKEN':'never-inherit-this-synthetic-token',
                    'SSH_AUTH_SOCK':'/never-share-agent','PYTHONPATH':'/never-share-pythonpath'})
        proc=None
        try:
            proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                  env=env,close_fds=True)
            selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ)
            cancelled=False;abandoned=False;eof=False
            while not eof or proc.poll() is None:
                if record.exists() and group is None:
                    saved=json.loads(record.read_text());group=Path(saved['group']);telemetry['effective']=saved['limits']
                if group is not None and group.exists():
                    current=group_values(group)
                    telemetry['last']=current
                    events=dict(line.split() for line in current.get('memory.events','').splitlines())
                    telemetry['oomKills']=max(telemetry.get('oomKills',0),int(events.get('oom_kill',0)))
                    cpu=dict(line.split() for line in current.get('cpu.stat','').splitlines())
                    telemetry['cpuUsec']=max(telemetry.get('cpuUsec',0),int(cpu.get('usage_usec',0)))
                    telemetry['throttled']=max(telemetry.get('throttled',0),int(cpu.get('nr_throttled',0)))
                if b'descendantReady' in output and not cancelled and cancel:
                    reason='cancelled';cancelled=True;control('stop','--no-block',unit)
                if b'descendantReady' in output and not abandoned and abandon:
                    reason='abandoned-controller';abandoned=True;proc.kill()
                if time.monotonic()-started>12:
                    reason='watchdog';control('kill','--kill-whom=all','--signal=KILL',unit)
                    if proc.poll() is None:proc.kill()
                    break
                for key,_ in selector.select(0.02):
                    chunk=os.read(key.fileobj.fileno(),8192)
                    if not chunk:selector.unregister(key.fileobj);eof=True
                    elif len(output)<OUTPUT:
                        output.extend(chunk[:OUTPUT-len(output)])
                        if len(output)>=OUTPUT and reason=='completed':
                            reason='output-limit';control('kill','--kill-whom=all','--signal=KILL',unit)
            if proc.poll() is None:proc.kill()
            proc.wait(timeout=3)
            selector.close();proc.stdout.close()
            state=control('show',unit,'--property=Result,ExecMainStatus,ExecMainCode,ActiveState').stdout
            # A killed frontend does not imply a killed service. Wait for the
            # independent systemd runtime/cgroup kill when simulating a crash.
            if abandon:
                deadline=started+11
                while group and group.exists() and time.monotonic()<deadline:time.sleep(0.05)
                state=control('show',unit,'--property=Result,ExecMainStatus,ExecMainCode,ActiveState').stdout
            try:alive=group is not None and 'populated 1' in (group/'cgroup.events').read_text()
            except OSError as e:
                if e.errno not in (errno.ENOENT,errno.ENODEV):raise
                alive=False
            result={'mode':mode,'reason':reason,'exit':proc.returncode,'output':output.decode('utf-8','replace'),
                    'elapsed':round(time.monotonic()-started,3),'telemetry':telemetry,'unitState':state,
                    'descendantsRemain':alive,'hostNamespaces':host_ns}
            return result
        finally:
            if proc is not None and proc.poll() is None:proc.kill();proc.wait(timeout=3)
            control('stop',unit);control('reset-failed',unit)

if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--inside':inside(sys.argv[2])
    else:raise SystemExit('Engineering proof stage only; no arbitrary command interface')
