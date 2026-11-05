"""Exercise FD ownership, private data paths and process shutdown without GTK."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('backend', Path(__file__).resolve().parents[1] / 'gtk4/embedding/backend.py')
backend = importlib.util.module_from_spec(spec)
sys.modules['backend'] = backend
spec.loader.exec_module(backend)


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.fd, self.writer = os.pipe()
        self.addCleanup(os.close, self.writer)
        self.preview = backend.CasildaBackend.__new__(backend.CasildaBackend)
        self.preview.widget = type('Connection', (), {'get_client_socket_fd': lambda _: self.fd})()
        self.preview.process = None
        self.addCleanup(self.preview.stop)

    def test_child_isolated_and_stopped_without_touching_parent_environment(self):
        report = self.root / 'report.json'
        script = 'import json,os,pathlib,time; pathlib.Path(os.environ["CENTAUR_GTK4_PROBE_REPORT"]).write_text(json.dumps(dict(os.environ))); time.sleep(30)'
        with patch.dict(os.environ, DISPLAY=':test', WAYLAND_DISPLAY='desktop-test'):
            self.preview.start(backend.AppSpec((sys.executable, '-c', script)), self.root, report)
            process = self.preview.process
            deadline = time.monotonic() + 5
            while not report.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            env = json.loads(report.read_text())
            self.assertNotIn('DISPLAY', env)
            self.assertNotIn('WAYLAND_DISPLAY', env)
            self.assertEqual(env['GDK_BACKEND'], 'wayland')
            self.assertEqual(env['XDG_DATA_HOME'], str(self.root / 'data'))
            self.assertEqual(os.environ['WAYLAND_DISPLAY'], 'desktop-test')
            with self.assertRaises(OSError):
                os.fstat(self.fd)
            self.preview.stop()
            self.assertIsNotNone(process.poll())
            self.preview.stop()

    def test_failed_spawn_closes_connection(self):
        with self.assertRaises(FileNotFoundError):
            self.preview.start(backend.AppSpec(('/centaur-test/no-such-program',)), self.root, self.root / 'report')
        with self.assertRaises(OSError):
            os.fstat(self.fd)
        self.assertIsNone(self.preview.process)


if __name__ == '__main__':
    unittest.main()
