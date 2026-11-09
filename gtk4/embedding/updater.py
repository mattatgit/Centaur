"""GTK-only, signed-binary updater. No app-data writes or local builds.

The old package's detached helper owns the transaction through restart/rollback.
All subprocess calls use argument arrays; manifests never supply commands.
"""
import argparse
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import time
import urllib.error
import urllib.request
import uuid

CACHE = 'https://mattatgit-centaur.cachix.org'
KEY = 'mattatgit-centaur.cachix.org-1:ouvsfGud6lFrvNNxpE1S5yGkNFm9J2WKtnIm38OSQ58='
FEED = 'https://api.github.com/repos/mattatgit/Centaur/releases/tags/gtk4-preview'
ALLOWED_BINS = {'centaur-gtk4','centaur-gtk4-preview','centaur-gtk4-bridge',
                'centaur-gtk4-test','centaur-gtk4-check','centaur-gtk4-integration-check',
                'centaur-gtk4-update','centaur-gtk4-updater-check','centaur-host','centaur-network'}
NIX_FLAGS = ['--extra-experimental-features','nix-command flakes','--max-jobs','0',
             '--builders','','--option','fallback','false','--option','require-sigs','true']


class UpdateError(Exception): pass


def profile_path(): return Path.home()/'.local/state/nix/profiles/centaur-gtk4'
def state_path(): return Path(os.environ.get('XDG_STATE_HOME',Path.home()/'.local/state'))/'centaur-gtk4-updater'


def write_json(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temporary=path.with_name(path.name+'.tmp')
    with open(temporary,'w',opener=lambda p,f:os.open(p,f,0o600)) as stream:
        json.dump(value,stream); stream.flush(); os.fsync(stream.fileno())
    temporary.replace(path)


def read_json(path):
    try: return json.loads(Path(path).read_text())
    except (OSError,ValueError): return {}


def validate_manifest(value):
    try:
        revision=value['sourceRevision']; store=value['storePath']
        if not re.fullmatch('[a-f0-9]{40}',revision): raise ValueError()
        if not re.fullmatch(r'/nix/store/[0-9a-df-np-sv-z]{32}-centaur-gtk4-preview-[A-Za-z0-9.+_-]+',store): raise ValueError()
        if (value['schemaVersion']!=1 or value['updateProtocol']!=1 or
            value['branch']!='codex/gtk4-migration' or value['system']!='aarch64-linux' or
            value['packageAttribute']!='gtk4-preview' or value['cacheUrl']!=CACHE or
            KEY not in value['publicSigningKeys'] or value['verifiedSignedClosureDownload'] is not True or
            not isinstance(value['sourceTimestamp'],int) or value['sourceTimestamp']<=0 or
            not value['version'].startswith('Centaur GTK4 ') or
            not revision.startswith(value['version'].rsplit('+',1)[-1]) or
            len(value['version'].rsplit('+',1)[-1])<7): raise ValueError()
        datetime.fromisoformat(value['publishedAt'])
    except (KeyError,TypeError,ValueError,AttributeError):
        raise UpdateError('The published update details could not be verified.') from None
    return value


def check_update(current_id,source_timestamp,fetch=None):
    if fetch is None:
        def fetch():
            request=urllib.request.Request(FEED,headers={'User-Agent':'Centaur-GTK4-Updater','Cache-Control':'no-cache'})
            try:
                with urllib.request.urlopen(request,timeout=20) as response:
                    payload=response.read(65537)
                if len(payload)>65536: raise UpdateError('The update response is too large.')
                release=json.loads(payload)
                if release.get('tag_name')!='gtk4-preview' or release.get('draft') is not False or release.get('prerelease') is not True:
                    raise UpdateError('The update publication could not be verified.')
                return json.loads(release['body'])
            except urllib.error.HTTPError as error:
                if error.code==404: raise UpdateError('No published update is available yet.') from None
                raise UpdateError('Could not check for updates. Try again later.') from None
            except (OSError,ValueError): raise UpdateError('Could not check for updates. Try again later.') from None
    manifest=validate_manifest(fetch())
    if manifest['sourceRevision'].startswith(current_id) or manifest['sourceTimestamp']<=source_timestamp: return None
    return manifest


def process_identity(pid):
    try:
        # /proc stat's command can contain spaces and parentheses.
        fields=Path(f'/proc/{int(pid)}/stat').read_text().rsplit(')',1)[1].split()
        return None if fields[0]=='Z' else fields[19]
    except (OSError,ValueError,IndexError): return None


class Runtime:
    def __init__(self,work): self.work=Path(work)

    def run(self,args,timeout=600,env=None):
        try:
            with (self.work/'helper.log').open('a') as log:
                result=subprocess.run(args,stdout=subprocess.PIPE,stderr=log,text=True,timeout=timeout,env=env)
        except subprocess.TimeoutExpired: raise UpdateError('The update took too long. Your previous app is preserved; try again later.') from None
        except OSError: raise UpdateError('Could not run the updater. Your previous app is preserved.') from None
        if result.returncode: raise UpdateError('The update could not complete. Your previous version is preserved.')
        return result.stdout.strip()

    def nix(self,*args): return self.run(['nix',*NIX_FLAGS,*args])

    def download(self,manifest):
        path=manifest['storePath']
        self.nix('copy','--from',CACHE,'--extra-trusted-public-keys',KEY,path)
        self.nix('build','--offline','--out-link',str(self.work/'candidate'),path)
        # Existing dependencies may only have nixos.org signatures locally.
        # Import this cache's signatures before requiring them for the closure.
        self.nix('store','copy-sigs','--substituter',CACHE,'--recursive',path)
        # Require this cache's signature for every runtime object, even if it
        # was already present locally from another source.
        self.nix('store','verify','--recursive','--sigs-needed','1',
                 '--option','trusted-public-keys',KEY,'--option','substituters','',path)
        for name in ('centaur-gtk4','centaur-gtk4-update','centaur-host','centaur-gtk4-preview','centaur-gtk4-bridge','centaur-network'):
            if not os.access(Path(path)/'bin'/name,os.X_OK): raise UpdateError('The published package is incomplete.')
        if self.run([path+'/bin/centaur-gtk4','--version'],timeout=20)!=manifest['version']:
            raise UpdateError('The downloaded version does not match the published update.')

    def root_previous(self,path): self.nix('build','--offline','--out-link',str(self.work/'previous'),path)
    def activate(self,profile,path): self.nix('build','--offline','--no-link','--profile',str(profile),path)

    def stop_host(self,package,data,token=''):
        hosts=[]
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit(): continue
            try:
                if entry.stat().st_uid!=os.getuid(): continue
                args=[os.fsdecode(a) for a in (entry/'cmdline').read_bytes().split(b'\0') if a]
                if not args or Path(args[0]).name not in ('centaur-host','.centaur-host-wrapped'): continue
                if any(args[i]=='--data-dir' and args[i+1]==str(data) for i in range(len(args)-1)):
                    hosts.append((int(entry.name),process_identity(int(entry.name))))
            except (OSError,ValueError): continue
        args=[str(Path(package)/'bin/centaur-host'),'--stop-if-idle','--data-dir',str(data)]
        if token: args+=['--update-token',token]
        self.run(args,timeout=20)
        # The local socket/lock can close before TLS/Iroh destructors finish.
        # Wait for the actual old process before a new host binds its ports.
        deadline=time.monotonic()+8
        while any(identity and process_identity(pid)==identity for pid,identity in hosts):
            if time.monotonic()>deadline: raise UpdateError('The previous host is still closing. No new version was activated.')
            time.sleep(.1)

    def release_host(self,package,data,token):
        self.run([str(Path(package)/'bin/centaur-host'),'--finish-update',token,'--data-dir',str(data)],timeout=15)

    def wait_parent(self,pid,identity):
        deadline=time.monotonic()+30
        while process_identity(pid)==identity:
            if time.monotonic()>deadline: raise UpdateError('Centaur did not close. The installed version was not changed.')
            time.sleep(.1)

    def launch(self,package,data,work,token,omp):
        env=dict(os.environ); env['CENTAUR_UPDATE_STARTING']=token
        if omp: env['CENTAUR_AGENT']=omp
        # The wrapper's interpreter/module paths must follow the NEW package.
        for name in ('PYTHONPATH','PYTHONHOME'): env.pop(name,None)
        with (self.work/'application.log').open('a') as log:
            args=[str(Path(package)/'bin/centaur-gtk4'),'--data-dir',str(data),'--update-session',str(work)]
            report=read_json(self.work/'request.json').get('reportDir')
            if report: args+=['--report-dir',report]
            return subprocess.Popen(args,env=env,stdout=log,stderr=log,
                                    start_new_session=True,close_fds=True)

    def ready(self,process,work,build_id):
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            value=read_json(Path(work)/'ready.json')
            if value.get('pid')==process.pid and value.get('buildId')==build_id and value.get('connected'): return
            if process.poll() is not None: break
            time.sleep(.1)
        raise UpdateError('The new version did not start correctly. Restoring the previous version.')

    def stop_child(self,process):
        if process and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=8)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=3)


class Transaction:
    def __init__(self,work,runtime=None):
        self.work=Path(work); self.runtime=runtime or Runtime(work)
        self.request=read_json(self.work/'request.json'); self.profile=profile_path()
        self.previous=None; self.child=None; self.host_stopped=False; self.switched=False

    def status(self,phase,message,**extra):
        write_json(self.work/'status.json',{'phase':phase,'message':message,**extra})

    def preflight(self):
        if not self.profile.is_symlink(): raise UpdateError('Use the dedicated GTK4 installation before updating in Settings.')
        self.previous=str(self.profile.resolve(strict=True))
        names={entry.name for entry in (self.profile/'bin').iterdir() if not entry.name.startswith('.')}
        if not {'centaur-gtk4','centaur-host'}<=names or names-ALLOWED_BINS:
            raise UpdateError('This is not a dedicated GTK4 profile. Nothing was changed.')
        data=Path(self.request['dataDir']).resolve()
        qt_roots={Path.home()/'.local/share/Centaur/Centaur',
                  Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))/'Centaur/Centaur'}
        qt_config=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'centaur-launcher/data-dir'
        if qt_config.is_file():
            configured=Path(qt_config.read_text().strip())
            if configured.is_absolute(): qt_roots.add(configured)
        if data in {p.resolve() for p in qt_roots} or data==self.profile.resolve(): raise UpdateError('The GTK4 updater cannot use the Qt data directory.')
        if self.request.get('package')!=str((self.profile/'bin/centaur-gtk4').resolve().parent.parent):
            # Python wrappers remain below bin; package is supplied by Nix.
            package=self.request.get('package','')
            if not package or (Path(package)/'bin/centaur-gtk4').resolve()!=(self.profile/'bin/centaur-gtk4').resolve():
                raise UpdateError('This window is not running from the dedicated GTK4 profile. Reopen its installed shortcut first.')
        return data

    def apply(self,manifest,approval):
        data=self.preflight(); runtime=self.runtime; token=uuid.uuid4().hex
        self.status('downloading','Downloading and verifying the update…')
        runtime.root_previous(self.previous); runtime.download(manifest)
        if str(self.profile.resolve())!=self.previous: raise UpdateError('The installed profile changed during download. Nothing was replaced.')
        write_json(self.work/'resume.json',approval.get('resume',{}))
        self.status('ready','Download verified. Waiting for Centaur to finish its work…')
        if not approval.get('approved'):
            deadline=time.monotonic()+1800
            while time.monotonic()<deadline:
                approval=read_json(self.work/'approve.json')
                if approval.get('approved'): break
                if process_identity(self.request['parentPid'])!=self.request['parentIdentity']:
                    raise UpdateError('The window closed before the update was ready. The installed version was not changed.')
                time.sleep(.2)
            else: raise UpdateError('The update was not activated. Try again when Centaur is idle.')
            write_json(self.work/'resume.json',approval.get('resume',{}))
        runtime.wait_parent(self.request['parentPid'],self.request['parentIdentity'])
        committed=False
        try:
            self.status('restarting','Restarting Centaur…')
            if str(self.profile.resolve())!=self.previous: raise UpdateError('The installed profile changed. Reopen the installed app and try again.')
            runtime.stop_host(self.previous,data); self.host_stopped=True
            write_json(state_path()/'recovery.json',{'previous':self.previous,'candidate':manifest['storePath'],
                       'profile':str(self.profile),'dataDir':str(data),'work':str(self.work),'token':token})
            runtime.activate(self.profile,manifest['storePath']); self.switched=True
            (self.work/'ready.json').unlink(missing_ok=True)
            self.child=runtime.launch(manifest['storePath'],data,self.work,token,self.request.get('omp',''))
            runtime.ready(self.child,self.work,manifest['version'].rsplit('+',1)[-1])
            runtime.release_host(manifest['storePath'],data,token)
            committed=True
            self.status('complete','Centaur updated.',version=manifest['version'])
            write_json(state_path()/'last-update.json',{'phase':'complete','version':manifest['version'],'work':str(self.work)})
        except Exception as error:
            if committed: return  # A receipt-write failure cannot undo a healthy, resumed host.
            runtime.stop_child(self.child)
            if not self.host_stopped:
                self.status('failed',str(error))
                self.child=runtime.launch(self.previous,data,self.work,'',self.request.get('omp',''))
                raise UpdateError(str(error)) from error
            # A launch failure may have left a detached, held host. Its idle
            # gate prevents new requests until success or rollback.
            try:
                if self.switched: runtime.stop_host(manifest['storePath'],data,token)
                runtime.activate(self.profile,self.previous)
                self.status('recovered','The update could not start. Your previous version has been restored.')
            except Exception:
                self.status('recovery-required','The update failed. Opening your previous app; its profile recovery details are saved.')
            (self.work/'ready.json').unlink(missing_ok=True)
            self.child=runtime.launch(self.previous,data,self.work,'',self.request.get('omp',''))
            raise UpdateError(str(error)) from error


def run_transaction(work):
    work=Path(work).resolve(); base=state_path(); base.mkdir(parents=True,exist_ok=True,mode=0o700)
    if work.parent!=base.resolve() or not work.name.startswith('run-'): raise UpdateError('Invalid update transaction.')
    with (base/'lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise UpdateError('Another Centaur update is already running.') from None
        transaction=Transaction(work)
        try: transaction.apply(validate_manifest(read_json(work/'manifest.json')), {})
        except Exception as error:
            if read_json(work/'status.json').get('phase') not in ('recovered','recovery-required'): transaction.status('failed',str(error))
            raise


def main():
    parser=argparse.ArgumentParser(description='Centaur GTK4 detached updater')
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--transaction',type=Path)
    mode.add_argument('--recover',action='store_true')
    args=parser.parse_args()
    if platform.system()!='Linux' or platform.machine() not in ('aarch64','arm64') or os.geteuid()==0:
        raise SystemExit('The GTK4 updater runs as your normal user on ARM64 Linux.')
    try:
        if args.recover:
            recovery=read_json(state_path()/'recovery.json'); work=Path(recovery['work']).resolve()
            if work.parent!=state_path().resolve() or recovery['profile']!=str(profile_path()): raise UpdateError('Invalid recovery record.')
            with (state_path()/'lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                runtime=Runtime(work)
                runtime.stop_host(recovery['candidate'],recovery['dataDir'],recovery['token'])
                runtime.activate(profile_path(),recovery['previous'])
                write_json(work/'status.json',{'phase':'recovered','message':'Previous version restored.'})
                runtime.launch(recovery['previous'],recovery['dataDir'],work,'',read_json(work/'request.json').get('omp',''))
        else: run_transaction(args.transaction)
    except Exception as error: print(str(error)); return 1
    return 0


if __name__=='__main__': raise SystemExit(main())
