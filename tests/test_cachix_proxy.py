import importlib.util
import http.server
import json
import pathlib
import threading
import unittest
import urllib.error
import urllib.request
from unittest import mock

spec = importlib.util.spec_from_file_location('cachix_proxy', pathlib.Path(__file__).resolve().parents[1] / 'scripts/push-full-cachix-closure.py')
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)


class Response:
    status = 200
    headers = {'Content-Type': 'application/json'}

    def __init__(self, body=b'{}'):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass


class CacheProxyTests(unittest.TestCase):
    def test_query_checks_selected_cache_instead_of_upstream(self):
        present, missing = 'a' * 32, 'b' * 32
        def fetch(request, **_kwargs):
            self.assertEqual(request.get_method(), 'HEAD')
            self.assertEqual(request.get_header('User-agent'), 'centaur-cache-publisher/0.2')
            self.assertTrue(request.full_url.startswith('https://centaur-test.cachix.org/'))
            self.assertIsNone(request.get_header('Authorization'))
            if missing in request.full_url:
                raise urllib.error.HTTPError(request.full_url, 404, 'Missing', {}, None)
            return Response()
        with proxy.CacheProxy('centaur-test') as server, mock.patch.object(proxy.urllib.request, 'urlopen', side_effect=fetch):
            self.assertEqual(server.missing([present, missing]), [missing])

    def test_service_failure_is_not_reported_as_a_cache_hit(self):
        with proxy.CacheProxy('centaur-test') as server:
            with mock.patch.object(proxy.urllib.request, 'urlopen', side_effect=OSError('offline')):
                with self.assertRaises(OSError):
                    server.missing(['a' * 32])
            with self.assertRaises(ValueError):
                server.missing(['../../other-service'])

    def test_only_expected_api_receives_credentials_and_bulk_query_is_replaced(self):
        real_urlopen = urllib.request.urlopen
        upstream = []
        def fetch(request, **kwargs):
            upstream.append(request)
            self.assertEqual(request.full_url, 'https://app.cachix.org/api/v1/cache/centaur-test')
            self.assertEqual(request.get_header('Authorization'), 'Bearer test-only')
            return Response(b'{"isPublic":true}')
        with proxy.CacheProxy('centaur-test') as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = 'http://127.0.0.1:' + str(server.server_port)
                with mock.patch.object(proxy, 'open_api', side_effect=fetch), mock.patch.object(server, 'missing', return_value=['b' * 32]):
                    request = urllib.request.Request(base + server.prefix, headers={'Authorization': 'Bearer test-only'})
                    with real_urlopen(request) as response:
                        self.assertTrue(json.load(response)['isPublic'])
                    request = urllib.request.Request(base + server.prefix + '/narinfo', data=json.dumps(['b' * 32]).encode())
                    with real_urlopen(request) as response:
                        self.assertEqual(json.load(response), ['b' * 32])
                    request = urllib.request.Request(base + server.prefix + '/' + 'b' * 32 + '.narinfo', method='HEAD')
                    with self.assertRaises(urllib.error.HTTPError) as absent:
                        real_urlopen(request)
                    self.assertEqual(absent.exception.code, 404)
                    with self.assertRaises(urllib.error.HTTPError) as denied:
                        real_urlopen(base + '/api/v1/cache/other-cache')
                    self.assertEqual(denied.exception.code, 403)
                self.assertEqual(len(upstream), 1)
            finally:
                server.shutdown()
                thread.join()

    def test_api_redirects_are_not_followed_with_credentials(self):
        paths = []
        class Redirect(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                paths.append(self.path)
                self.send_response(302)
                self.send_header('Location', '/credential-target')
                self.end_headers()

        with http.server.ThreadingHTTPServer(('127.0.0.1', 0), Redirect) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                request = urllib.request.Request('http://127.0.0.1:' + str(server.server_port) + '/original',
                                                 headers={'Authorization': 'Bearer test-only'})
                with self.assertRaises(urllib.error.HTTPError) as redirect:
                    proxy.open_api(request)
                self.assertEqual(redirect.exception.code, 302)
                self.assertEqual(paths, ['/original'])
            finally:
                server.shutdown()
                thread.join()


if __name__ == '__main__':
    unittest.main()
