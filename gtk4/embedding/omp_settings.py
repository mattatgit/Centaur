"""OMP's documented settings RPC, isolated from the project/agent process.

Never prompts a model, registers tools, reads credential files, or forwards raw
RPC data to reports. Authentication changes require an explicit Settings action.
"""
import json
import os
import signal
import subprocess
import tempfile
import threading
import uuid


COMMANDS=frozenset(('get_login_providers','get_available_models','get_state',
                    'set_model','login','get_logout_accounts','logout'))


class OmpSettings:
    def __init__(self, executable, deliver, dispatch, later=None):
        self.executable=executable; self.deliver=deliver; self.dispatch=dispatch
        self.process=None; self.work=None; self.pending={}; self.lock=threading.Lock(); self.closed=False
        self.state_lock=threading.RLock(); self.later=later

    def start(self):
        process=self.process
        if process and process.poll() is None: return
        if process: self.failed(process)
        if self.work: self.work.cleanup()
        self.work=tempfile.TemporaryDirectory(prefix='centaur-omp-settings-')
        self.process=subprocess.Popen([self.executable,'--mode','rpc','--no-session','--no-skills',
            '--no-rules','--no-tools','--no-extensions','--no-lsp','--no-title'],cwd=self.work.name,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            start_new_session=True,text=True,bufsize=1)
        threading.Thread(target=self.read,args=(self.process,),daemon=True).start()

    def request(self,kind,callback,**fields):
        if kind not in COMMANDS: raise ValueError('Unsupported settings operation')
        if self.closed:
            self.dispatch(callback,{'success':False}); return None
        ident=None
        try:
            self.start(); ident=uuid.uuid4().hex
            with self.state_lock: self.pending[ident]=callback
            self.write({'id':ident,'type':kind,**fields})
            delay=180 if kind=='login' else 45
            if self.later: self.later(delay,lambda:self.expire(ident))
            else:
                timer=threading.Timer(delay,lambda:self.dispatch(self.expire,ident)); timer.daemon=True; timer.start()
            return ident
        except (OSError,ValueError):
            with self.state_lock: pending=self.pending.pop(ident,None) if ident else callback
            if pending: self.dispatch(pending,{'success':False})
            return None

    def write(self,value):
        with self.lock:
            process=self.process
            if process is None: raise BrokenPipeError('Settings process stopped')
            process.stdin.write(json.dumps(value)+'\n'); process.stdin.flush()

    def read(self,process):
        try:
            while not self.closed:
                line=process.stdout.readline(1024*1024+1)
                if not line or len(line)>1024*1024: break
                try: value=json.loads(line)
                except ValueError: continue
                if value.get('type')=='response': self.dispatch(self.response,value)
                elif value.get('type')=='extension_ui_request': self.dispatch(self.deliver,value)
        except (OSError,ValueError): pass
        finally:
            self.dispatch(self.failed,process)

    def response(self,value):
        with self.state_lock: callback=self.pending.pop(value.get('id'),None)
        if callback and not self.closed: callback(value)
        return False

    def failed(self,process=None):
        with self.state_lock:
            if process is not None and process is not self.process: return False
            callbacks=list(self.pending.values()); self.pending.clear()
            stopped=self.process; self.process=None
        if stopped: self.stop_process(stopped)
        if not self.closed:
            for callback in callbacks: callback({'success':False})
        return False

    def expire(self,ident):
        with self.state_lock: callback=self.pending.pop(ident,None)
        if callback and not self.closed:
            self.failed(self.process); callback({'success':False})
        return False

    def answer(self,ident,value=None,cancelled=False):
        try: self.write({'type':'extension_ui_response','id':ident,'value':value,'cancelled':cancelled})
        except (OSError,ValueError): pass

    def close(self):
        if self.closed: return
        with self.state_lock:
            self.closed=True; self.pending.clear(); process=self.process; self.process=None
        if process: self.stop_process(process)
        if self.work: self.work.cleanup()

    @staticmethod
    def stop_process(process):
        try:
            os.killpg(process.pid,signal.SIGTERM); process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL); process.wait(timeout=2)
        except ProcessLookupError: process.wait(timeout=2)
        for stream in (process.stdin,process.stdout):
            try: stream.close()
            except (OSError,ValueError): pass
