"""Count the compressed archive bytes delivered to Nix, including daemon installs.

The short-lived listener serves only the chosen cache's narinfo and the exact
archives named by those records. Nix still verifies the original signatures
and archive hashes. The URL field in a narinfo is a transport location.
"""
import contextlib
import hashlib
import http.server
import re
import secrets
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlsplit


class RelayUnavailable(Exception):
    """Retry the same signed transfer using Nix's native HTTP client."""


@contextlib.contextmanager
def measured_cache(cache, progress, status=None):
    records = {}
    lock = threading.RLock()
    prefix = '/' + secrets.token_hex(16) + '/'
    upstream = urlsplit(cache)
    checked = set()
    reported = 0
    last_notice = 0
    started = time.monotonic()
    failure = None
    invalid_record = False
    closed = False
    saw_payload = False

    def poll():
        nonlocal reported, last_notice
        with lock:
            if invalid_record:
                raise ValueError('The cache supplied an invalid download record.')
            if failure:
                raise RelayUnavailable(failure)
            if saw_payload:
                return
            now = time.monotonic()
            if now-started >= 45:
                raise RelayUnavailable('No archive bytes arrived through the local download helper in 45 seconds.')
            if status and checked and len(checked) != reported and now-last_notice >= 1:
                reported, last_notice = len(checked), now
                status(f'Checking download files… {reported} checked')

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_HEAD(self):
            self.serve(False)

        def do_GET(self):
            self.serve(True)

        def serve(self, body):
            nonlocal failure, saw_payload, invalid_record
            if not self.path.startswith(prefix):
                self.send_error(404)
                return
            key = self.path[len(prefix):]
            with lock:
                archive = records.get(key)
            if not archive and key != 'nix-cache-info' and not re.fullmatch(r'[0-9a-df-np-sv-z]{32}\.narinfo', key):
                self.send_error(404)
                return
            source = archive or urljoin(cache + '/',key)
            response_started = False
            try:
                request = urllib.request.Request(source,headers={'Accept-Encoding':'identity','User-Agent':'Centaur GTK4 updater'},method='HEAD' if archive and not body else 'GET')
                with urllib.request.urlopen(request,timeout=25) as response:
                    if archive:
                        self.send_response(200)
                        if response.headers.get('Content-Length'):
                            self.send_header('Content-Length',response.headers['Content-Length'])
                        self.end_headers()
                        response_started = True
                        if body:
                            count = 0
                            while data := response.read(65536):
                                self.wfile.write(data)
                                count += len(data)
                                with lock:
                                    if closed: return
                                    saw_payload = True
                                    progress.record(archive,count)
                    else:
                        data = response.read(262145)
                        if len(data)>262144: raise ValueError('Oversize cache record')
                        if key.endswith('.narinfo'):
                            match = re.search(rb'^URL: ([^\r\n]+)\r?$',data,re.M)
                            if not match: raise ValueError('Missing archive')
                            url = urljoin(cache+'/',match[1].decode('ascii'))
                            dest = urlsplit(url)
                            if (dest.scheme,dest.netloc)!=(upstream.scheme,upstream.netloc) or not dest.path.startswith(upstream.path.rstrip('/')+'/nar/'):
                                raise ValueError('Unexpected archive origin')
                            name = 'nar/' + hashlib.sha256(url.encode()).hexdigest()+'.nar'
                            with lock:
                                records[name]=url
                                checked.add(key)
                            data=data[:match.start(1)]+name.encode()+data[match.end(1):]
                        self.send_response(200)
                        self.send_header('Content-Length',str(len(data)))
                        self.end_headers(); response_started=True
                        if body: self.wfile.write(data)
            except urllib.error.HTTPError as error:
                if error.code in (408, 429, 500, 502, 503, 504):
                    with lock: failure = f'Cache returned HTTP {error.code} through the local helper.'
                if not response_started: self.send_error(error.code)
            except (BrokenPipeError, ConnectionResetError) as error:
                if not response_started:
                    with lock: failure = f'Cache connection failed ({type(error).__name__}).'
                    self.send_error(502)
            except OSError as error:
                with lock: failure = f'Cache connection failed ({type(getattr(error,"reason",error)).__name__}).'
                if not response_started: self.send_error(502)
            except (ValueError,UnicodeError):
                with lock: invalid_record = True
                if not response_started: self.send_error(502)

    try:
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    except OSError as error:
        raise RelayUnavailable('The local download helper could not start.') from error
    def heartbeat():
        with lock: progress.tick()
    server.service_actions=heartbeat
    thread=threading.Thread(target=server.serve_forever,args=(.2,),daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'+prefix.rstrip('/'), poll
    finally:
        with lock: closed = True
        server.shutdown(); server.server_close(); thread.join()
        with lock: progress.flush()
