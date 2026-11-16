"""Repeatable Phase 3 proof; run only in the ARM64 NixOS UTM VM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import tempfile
from supervisor import CONFIG,run,supported

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();supported()
    here=Path(__file__).resolve().parent
    report={'schemaVersion':1,'architecture':platform.machine(),'kernel':platform.release(),'uid':os.getuid(),
            'package':str(here.parents[1]),'versions':CONFIG['versions'],
            'policySha256':hashlib.sha256(Path(CONFIG['filter']).read_bytes()).hexdigest(),
            'installedSourceSha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in here.glob('*.py')},
            'runtimeClosurePaths':len(Path(CONFIG['closure']).read_text().splitlines()),
            'commandInterfaceEnabled':False,'checks':[],'passed':False}
    def check(name,fn):
        print('Checking '+name,flush=True)
        value=fn();report['checks'].append({'name':name,**value})
        args.output.write_text(json.dumps(report,indent=2)+'\n')
    with tempfile.TemporaryDirectory(prefix='centaur-isolation-fixture-') as tmp:
        root=Path(tmp);source=root/'source';source.mkdir()
        (source/'manifest.txt').write_text('unfamiliar application\n')
        secret=root/'synthetic-provider-secret';secret.write_text('synthetic-not-a-real-credential')
        (source/'escape').symlink_to(secret)
        (source/'host-secret').symlink_to('/home/matt/.config/centaur/never-read-real-data')
        def source_hashes():
            return {str(p.relative_to(source)):
                    ('link:'+os.readlink(p) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest())
                    for p in source.rglob('*')}
        original=source_hashes()
        held=secret.open('rb');os.set_inheritable(held.fileno(),True)
        # Establish that host sockets really can be created, rather than passing
        # because the entire VM lacks a network or Unix-socket facility.
        sockets=[socket.socket(socket.AF_INET,socket.SOCK_STREAM),socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)]
        sockets[0].bind(('127.0.0.1',0));sockets[0].listen()
        sockets[1].bind(str(root/'owner-agent.sock'));sockets[1].listen()
        try:
            def invoke(mode,**kwargs):
                r=run(mode,source,**kwargs)
                assert not r['descendantsRemain'],r
                assert source_hashes()==original
                return r
            def isolation():
                r=invoke('isolation');assert r['exit']==0,r
                data=json.loads(r['output'])
                assert all(v!=r['hostNamespaces'][n] for n,v in data['namespaces'].items()),data
                assert set(data.pop('runtimeStoreEntries'))=={Path(p).name for p in Path(CONFIG['closure']).read_text().splitlines()}
                assert secret.read_text()=='synthetic-not-a-real-credential'
                return {'passed':True,'effectiveLimits':r['telemetry']['effective'],**data}
            check('filesystem-credentials-environment-fds-network-namespaces-seccomp',isolation)
            def refused_command():
                try:run('shell',source)
                except ValueError:return {'passed':True,'refused':True}
                raise AssertionError('Unknown command was accepted')
            check('unknown-command-refused',refused_command)
            for mode in ['version-python','version-git','version-gcc','scratch','file-limit','pids']:
                def simple(mode=mode):
                    r=invoke(mode);assert r['exit']==0,r
                    return {'passed':True,'observation':r['output'].strip(),'elapsed':r['elapsed']}
                check(mode,simple)
            def memory():
                r=invoke('memory');assert r['exit']!=0 and 'memoryTestStarted' in r['output'],r
                assert r['telemetry'].get('oomKills',0)>0 or 'Result=oom-kill' in r['unitState'],r
                return {'passed':True,'oomKills':r['telemetry'].get('oomKills',0),'unitState':r['unitState']}
            check('memory-exhaustion',memory)
            def cpu():
                r=invoke('cpu');assert r['exit']==0 and r['telemetry'].get('throttled',0)>0,r
                assert 500000<r['telemetry']['cpuUsec']<2200000,r
                return {'passed':True,'cpuUsec':r['telemetry']['cpuUsec'],'throttledPeriods':r['telemetry']['throttled'],'elapsed':r['elapsed']}
            check('effective-cpu-quota',cpu)
            def output():
                r=invoke('output');assert r['reason']=='output-limit' and len(r['output'])==32768,r
                return {'passed':True,'retainedBytes':len(r['output']),'elapsed':r['elapsed']}
            check('bounded-output',output)
            for name,kwargs in [('wall-time-and-daemon-cleanup',{}),('cancel-process-tree',{'cancel':True}),
                                ('controller-death-runtime-cleanup',{'abandon':True})]:
                def descendants(kwargs=kwargs):
                    r=invoke('descendants',**kwargs);assert 'descendantReady' in r['output'],r
                    ready=json.loads(r['output'].splitlines()[0])
                    assert all(ready.get(k) is True for k in ['doubleForked','newSession','ignoresSigterm']),r
                    assert r['reason']!='watchdog',r
                    if not kwargs or kwargs.get('abandon'):
                        assert r['exit']!=0 and 'Result=timeout' in r['unitState'] and 7<=r['elapsed']<11,r
                    return {'passed':True,'elapsed':r['elapsed'],'reason':r['reason'],'unitState':r['unitState'],
                            'daemonReadinessHandshake':ready,'descendantsRemain':False}
                check(name,descendants)
            for fault in ['missing-bwrap','mismatched-limits','invalid-filter','missing-manager']:
                def unavailable(fault=fault):
                    try:r=invoke('isolation',fault=fault)
                    except FileNotFoundError:
                        assert fault=='missing-manager';return {'passed':True,'refused':True}
                    assert r['exit']!=0 and '"isolation": true' not in r['output'],r
                    return {'passed':True,'refused':True}
                check('fail-closed-'+fault,unavailable)
            report['originalHashesUnchanged']=True
            report['passed']=True
        finally:
            held.close()
            for s in sockets:s.close()
            args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'checks':len(report['checks']),'commandInterfaceEnabled':False}),flush=True)

if __name__=='__main__':main()
