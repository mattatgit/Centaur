"""Kill the real sandbox supervisor after its daemon's readiness handshake.

Disposable engineering fixtures only, on ARM64 NixOS UTM. No product tool is
registered and no project or profile is opened.
"""
import argparse
import errno
import platform
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--proof',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    assert platform.system()=='Linux' and platform.machine()=='aarch64'
    assert 'ID=nixos' in Path('/etc/os-release').read_text()
    share=args.proof.resolve()/'share/centaur-isolation'
    config=json.loads((share/'config.json').read_text())
    records=[]
    with tempfile.TemporaryDirectory(prefix='centaur-controller-death-') as tmp:
        root=Path(tmp);source=root/'source';source.mkdir();(source/'manifest.txt').write_text('unchanged')
        for signum in (signal.SIGTERM,signal.SIGKILL):
            ready=root/'ready.json';ready.unlink(missing_ok=True)
            child=root/'controller.py'
            child.write_text('import sys,json,os\nfrom pathlib import Path\n'+
                'sys.path.insert(0,'+repr(str(share))+')\nimport boundary,supervisor\n'+
                'popen=boundary.subprocess.Popen\nread=boundary.os.read\nunit=""\n'+
                'def start(command,*a,**kw):\n global unit\n'+
                ' if command[0]==boundary.CONFIG["systemdRun"]:unit=next(v[7:] for v in command if v.startswith("--unit="))\n'+
                ' return popen(command,*a,**kw)\n'+
                'def capture(fd,size):\n data=read(fd,size)\n'+
                ' if b"descendantReady" in data:\n  pending=Path('+repr(str(ready.with_suffix('.pending')))+')\n  pending.write_text(json.dumps({"unit":unit}))\n  pending.replace('+repr(str(ready))+')\n'+
                ' return data\n'+
                'boundary.subprocess.Popen=start\nboundary.os.read=capture\n'+
                'supervisor.run("descendants",'+repr(str(source))+')\n')
            proc=subprocess.Popen([config['python'],'-I','-S',str(child)],stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,close_fds=True)
            unit=None
            def control(*fields):
                return subprocess.run([config['systemctl'],'--user','--no-pager',*fields],capture_output=True,text=True,timeout=4)
            try:
                end=time.monotonic()+5
                while not ready.exists() and proc.poll() is None and time.monotonic()<end:time.sleep(.02)
                assert ready.exists(),proc.communicate(timeout=5)[1].decode()
                unit=json.loads(ready.read_text())['unit']
                group=control('show',unit,'--property=ControlGroup','--value').stdout.strip()
                assert group.startswith('/user.slice/')
                cgroup=Path('/sys/fs/cgroup'+group)
                assert 'populated 1' in (cgroup/'cgroup.events').read_text()
                started=time.monotonic();proc.send_signal(signum);proc.wait(timeout=4)
                def alive():
                    try:return 'populated 1' in (cgroup/'cgroup.events').read_text()
                    except OSError as error:
                        if error.errno not in (errno.ENOENT,errno.ENODEV):raise
                        return False
                end=started+10
                while alive() and time.monotonic()<end:
                    try:
                        if 'populated 1' not in (cgroup/'cgroup.events').read_text():break
                    except OSError as error:
                        if error.errno not in (errno.ENOENT,errno.ENODEV):raise
                        break
                    time.sleep(.02)
                remains=alive()
                assert not remains,'Supervisor death left descendants'
                elapsed=round(time.monotonic()-started,3)
                if signum==signal.SIGTERM:assert elapsed<3,elapsed
                records.append({'signal':signum.name,'daemonReadinessHandshake':True,'elapsed':elapsed,'descendantsRemain':False})
            finally:
                if proc.poll() is None:proc.kill();proc.wait(timeout=3)
                proc.stderr.close()
                if unit:control('stop',unit);control('reset-failed',unit)
        assert (source/'manifest.txt').read_text()=='unchanged'
    result={'passed':True,'originalUnchanged':True,'cases':records}
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)

if __name__=='__main__':main()
