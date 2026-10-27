#!/usr/bin/env python3
"""Keep Cachix's uploader, but query existence in the selected cache only.

Cachix's bulk endpoint can count paths in cache.nixos.org as present even
though the selected cache cannot serve them. This CI-only loopback adapter
replaces that query with direct, public HEAD checks. Compression, uploads,
retries, managed signing and authentication remain in the official client.
API reference: github.com/cachix/cachix/blob/master/cachix-api/src/Cachix/API.hs
"""
import concurrent.futures
import http.server
import json
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.request


class NoCredentialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def open_api(request):
    # Fail closed on redirects rather than forwarding a bearer token to a
    # different host. The API upload routes do not need HTTP redirects.
    return urllib.request.build_opener(NoCredentialRedirect()).open(request, timeout=120)


class CacheProxy(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, cache):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', cache):
            raise ValueError('Invalid cache name')
        self.cache = cache
        self.prefix = '/api/v1/cache/' + cache
        super().__init__(('127.0.0.1', 0), CacheRequest)

    def missing(self, hashes):
        if not isinstance(hashes, list) or len(hashes) > 32768:
            raise ValueError('Invalid path query')
        if not all(isinstance(value, str) and re.fullmatch(r'[0-9a-z]{32}', value) for value in hashes):
            raise ValueError('Invalid store hash')

        def absent(value):
            request = urllib.request.Request(
                'https://' + self.cache + '.cachix.org/' + value + '.narinfo', method='HEAD')
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    if response.status != 200:
                        raise ValueError('Unexpected cache response')
                return None
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    return value
                raise

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            return [value for value in pool.map(absent, hashes) if value is not None]


class CacheRequest(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # Never log requests or credential headers.

    def respond(self, status, body=b'', content_type='application/json'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def forward(self):
        prefix = self.server.prefix
        if self.path != prefix and not self.path.startswith(prefix + '/'):
            self.respond(403)
            return
        if self.headers.get('Transfer-Encoding'):
            self.respond(411)
            return
        size = int(self.headers.get('Content-Length', '0'))
        if size < 0 or size > 2 * 1024 * 1024:
            self.respond(413)
            return
        body = self.rfile.read(size) if size else None
        try:
            if self.command == 'POST' and self.path == prefix + '/narinfo':
                missing = self.server.missing(json.loads(body or b'null'))
                self.respond(200, json.dumps(missing).encode())
                return
            # Only this exact production API host receives the CLI's credential.
            # Presigned NAR uploads go directly from Cachix to its storage service.
            headers = {key: value for key, value in self.headers.items()
                       if key.lower() not in {'host', 'content-length', 'connection', 'transfer-encoding', 'accept-encoding'}}
            request = urllib.request.Request(
                'https://app.cachix.org' + self.path, data=body, headers=headers, method=self.command)
            with open_api(request) as response:
                self.respond(response.status, response.read(), response.headers.get('Content-Type', 'application/json'))
        except urllib.error.HTTPError as error:
            self.respond(error.code, error.read())
        except (ValueError, TypeError):
            self.respond(400, b'{"error":"Invalid cache query"}')
        except Exception:
            self.respond(502, b'{"error":"Could not contact the cache service"}')

    do_GET = forward
    do_HEAD = forward
    do_POST = forward


def main():
    if len(sys.argv) != 3:
        raise SystemExit('Usage: push-full-cachix-closure.py CACHE STORE_PATH')
    with CacheProxy(sys.argv[1]) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            subprocess.run(['cachix', '--host', 'http://127.0.0.1:' + str(server.server_port),
                            'push', sys.argv[1], sys.argv[2]], check=True)
        finally:
            server.shutdown()
            thread.join()


if __name__ == '__main__':
    main()
