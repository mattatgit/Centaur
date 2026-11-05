"""Asynchronous GTK client of the existing non-visual Centaur service."""
import json
import os
import subprocess
import threading


class Service:
    def __init__(self, root, callback):
        from gi.repository import GLib
        self.callback = callback
        self.closing = False
        self.process = subprocess.Popen([os.environ['CENTAUR_GTK_BRIDGE'], '--data-dir', str(root)],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        text=True, bufsize=1)
        def read():
            try:
                for line in self.process.stdout:
                    if len(line) > 8*1024*1024:
                        break
                    try:
                        value = json.loads(line)
                    except ValueError:
                        continue
                    GLib.idle_add(self.deliver, value)
            finally:
                self.process.wait()
                if not self.closing:
                    GLib.idle_add(self.deliver, {'type':'error', 'message':'The local service stopped. Reopen Centaur to reconnect; your projects are saved.'})
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()

    def deliver(self, value):
        if not self.closing:
            self.callback(value)
        return False

    def send(self, kind, **fields):
        try:
            self.process.stdin.write(json.dumps({'type':kind, **fields})+'\n')
            self.process.stdin.flush()
            return True
        except (BrokenPipeError, OSError, ValueError):
            self.deliver({'type':'error', 'message':'The local service is unavailable. Your draft stays here.'})
            return False

    def close(self):
        self.closing = True
        self.process.stdin.close()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=2)
        self.process.stdout.close()
