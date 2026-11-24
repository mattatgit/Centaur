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
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlsplit


@contextlib.contextmanager
def measured_cache(cache, progress):
    records = {}
    lock = threading.RLock()
    prefix = '/' + secrets.token_hex(16) + '/'
    upstream = urlsplit(cache)

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_HEAD(self):
            self.serve(False)

        def do_GET(self):
            self.serve(True)

        def serve(self, body):
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
                request = urllib.request.Request(source,headers={'Accept-Encoding':'identity'},method='HEAD' if archive and not body else 'GET')
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
                                with lock: progress.record(archive,count)
                    else:
                        data = response.read(262145)
                        if len(data)>262144: raise ValueError('Oversize cache record')
                        if key.endswith('.narinfo'):
                            match = re.search(rb'^URL: ([^\r\n]+)$',data,re.M)
                            if not match: raise ValueError('Missing archive')
                            url = urljoin(cache+'/',match[1].decode('ascii'))
                            dest = urlsplit(url)
                            if (dest.scheme,dest.netloc)!=(upstream.scheme,upstream.netloc) or not dest.path.startswith(upstream.path.rstrip('/')+'/nar/'):
                                raise ValueError('Unexpected archive origin')
                            name = 'nar/' + hashlib.sha256(url.encode()).hexdigest()+'.nar'
                            with lock: records[name]=url
                            data=data[:match.start(1)]+name.encode()+data[match.end(1):]
                        self.send_response(200)
                        self.send_header('Content-Length',str(len(data)))
                        self.end_headers(); response_started=True
                        if body: self.wfile.write(data)
            except urllib.error.HTTPError as error:
                if not response_started: self.send_error(error.code)
            except (OSError,ValueError,UnicodeError):
                if not response_started: self.send_error(502)

    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'+prefix.rstrip('/')
    finally:
        server.shutdown(); server.server_close(); thread.join()
        with lock: progress.flush()
