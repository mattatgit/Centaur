"""Cancellable branch discovery; no GTK widgets or project writes in this worker."""
import json
import os
import subprocess
import threading


class BranchLookup:
    def __init__(self):
        self.serial=0; self.process=None; self.lock=threading.Lock()

    def cancel(self):
        with self.lock:
            self.serial+=1
            if self.process and self.process.poll() is None: self.process.terminate()

    def start(self,location,branch,deliver):
        self.cancel(); serial=self.serial
        def work():
            process=None
            try:
                with self.lock:
                    if serial!=self.serial: return
                    process=subprocess.Popen([os.environ['CENTAUR_GTK_IMPORT_TOOL']],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
                    self.process=process
                output=process.communicate(json.dumps({'mode':'branches','location':location,'branch':branch}),timeout=110)[0]
                result=json.loads(output) if len(output)<2*1024*1024 else {'ok':False}
            except (OSError,ValueError,KeyError,subprocess.SubprocessError):
                result={'ok':False,'message':'Couldn’t load branches. Check the repository address and access.'}
            finally:
                if process and process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=2)
                    except subprocess.TimeoutExpired: process.kill(); process.wait()
                with self.lock:
                    if self.process is process: self.process=None
            if serial==self.serial: deliver(result)
        threading.Thread(target=work,daemon=True).start()
