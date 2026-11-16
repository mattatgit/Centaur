"""Trusted adversarial fixture, run only inside the Phase 3 proof sandbox."""
import errno
import json
import os
from pathlib import Path
import sys
import time

mode=sys.argv[1]
def emit(value): print(json.dumps(value),flush=True)
def denied(fn):
    try: fn()
    except OSError as e:
        assert e.errno in (errno.EPERM,errno.EACCES,errno.ENOENT,errno.EROFS),str(e)
        return e.errno
    raise AssertionError('Operation unexpectedly permitted')

if mode=='isolation':
    assert Path('/source/manifest.txt').read_text()=='unfamiliar application\n'
    for path in ['/etc/os-release','/etc/passwd','/root','/home/matt','/run/user','/run/dbus',
                 '/nix/var/nix/daemon-socket/socket','/source/escape','/source/host-secret']:
        denied(lambda p=path: Path(p).read_bytes())
    denied(lambda:Path('/source/manifest.txt').write_text('changed'))
    denied(lambda:Path('/new-root-file').write_text('changed'))
    assert set(os.environ)=={'HOME','PATH','LANG','TMPDIR','PWD'},sorted(os.environ)
    assert os.environ['PWD']=='/source'
    assert list(Path(os.environ['HOME']).iterdir())==[]
    fds={}
    for p in Path('/proc/self/fd').iterdir():
        try: fds[p.name]=os.readlink(p)
        except FileNotFoundError: pass
    assert all(int(n)<3 for n in fds),fds
    status=Path('/proc/self/status').read_text()
    values=dict(line.split(':',1) for line in status.splitlines() if ':' in line)
    assert values['NoNewPrivs'].strip()=='1'
    assert values['Seccomp'].strip()=='2'
    assert int(values['CapEff'].strip(),16)==0 and int(values['CapBnd'].strip(),16)==0
    # Measure inherited descriptors before native modules open their own runtime
    # libraries. libffi on this VM retains a descriptor to its read-only .so.
    import socket
    import ctypes
    for family in [socket.AF_INET,socket.AF_INET6,socket.AF_UNIX,socket.AF_NETLINK]:
        denied(lambda f=family:socket.socket(f,socket.SOCK_STREAM))
    libc=ctypes.CDLL(None,use_errno=True)
    assert libc.unshare(0x10000000)==-1 and ctypes.get_errno()==errno.EPERM
    assert libc.mount(b'none',b'/source',b'tmpfs',0,None)==-1 and ctypes.get_errno()==errno.EPERM
    assert libc.ptrace(0,0,None,None)==-1 and ctypes.get_errno()==errno.EPERM
    assert libc.ioctl(0,0x5412,0)==-1 and ctypes.get_errno()==errno.EPERM
    emit({'isolation':True,'namespaces':{n:os.readlink('/proc/self/ns/'+n) for n in ['mnt','pid','user','net','ipc','uts','cgroup']},
          'capabilities':0,'noNewPrivileges':True,'seccomp':True,'inheritedDescriptors':len(fds),
          'runtimeStoreEntries':sorted(os.listdir('/nix/store'))})
elif mode=='scratch':
    total=0
    try:
        for i in range(128):
            path=Path('/tmp' if i%2 else os.environ['HOME'])/str(i)
            with path.open('wb') as f:
                for j in range(8):
                    f.write(b'x'*65536);f.flush();total+=65536
    except OSError as e:
        assert e.errno==errno.ENOSPC,(e,total)
        assert 6*1024*1024<=total<=8*1024*1024,total
        emit({'scratchBytesWritten':total,'aggregateQuota':True})
    else: raise AssertionError('Scratch quota not enforced')
elif mode=='file-limit':
    import signal
    signal.signal(signal.SIGXFSZ,signal.SIG_IGN)
    try:
        with Path('/tmp/oversized').open('wb') as f:
            for i in range(64): f.write(b'x'*65536);f.flush()
    except OSError as e:
        assert e.errno==errno.EFBIG,e
        emit({'fileBytes':Path('/tmp/oversized').stat().st_size})
    else: raise AssertionError('File limit not enforced')
elif mode=='pids':
    count=0
    try:
        for i in range(100):
            child=os.fork()
            if child==0:
                time.sleep(60);os._exit(0)
            count+=1
    except OSError as e:
        assert e.errno==errno.EAGAIN and 1<count<32,(e,count)
        emit({'forkedChildren':count,'processLimit':True})
    else: raise AssertionError('Process limit not enforced')
elif mode=='memory':
    emit({'memoryTestStarted':True})
    chunks=[]
    for i in range(512):chunks.append(bytearray(1024*1024))
    raise AssertionError('Memory limit not enforced')
elif mode=='cpu':
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:pass
    emit({'cpuLoopFinished':True})
elif mode=='output':
    while True:os.write(1,b'x'*4096)
elif mode=='descendants':
    # Double fork, new session and ignore SIGTERM; cgroup stop must still win.
    ready_read,ready_write=os.pipe()
    if os.fork()==0:
        os.close(ready_read)
        os.setsid()
        if os.fork()!=0:os._exit(0)
        import signal
        signal.signal(signal.SIGTERM,signal.SIG_IGN)
        os.write(ready_write,b'ready');os.close(ready_write)
        while True:time.sleep(1)
    os.close(ready_write)
    assert os.read(ready_read,5)==b'ready'
    os.close(ready_read)
    emit({'descendantReady':True,'doubleForked':True,'newSession':True,'ignoresSigterm':True})
    while True:time.sleep(1)
else:raise ValueError('Unknown proof fixture')
