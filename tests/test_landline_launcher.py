"""Check the packaged test entry point without running an app or touching data."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/landline-embedding-test.sh'


class LandlineLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='centaur-landline-launcher-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.output = self.root / 'launch.json'
        app = self.root / 'fake-centaur'
        app.write_text('#!' + sys.executable + '\n' + '''import json, os, pathlib, sys
pathlib.Path(os.environ['TEST_OUTPUT']).write_text(json.dumps({
    'args': sys.argv[1:], 'software': os.environ.get('LIBGL_ALWAYS_SOFTWARE'),
    'backend': os.environ.get('QT_QUICK_BACKEND'),
    'vendor': os.environ.get('__EGL_VENDOR_LIBRARY_FILENAMES'),
    'drivers': os.environ.get('LIBGL_DRIVERS_PATH')}))
''')
        app.chmod(0o755)
        self.env = dict(os.environ, CENTAUR_TEST_CENTAUR=str(app), CENTAUR_TEST_LANDLINE='/test/landline',
                        CENTAUR_TEST_MESA_VENDOR='/test/vendor.json', CENTAUR_TEST_MESA_DRIVERS='/test/drivers',
                        TEST_OUTPUT=str(self.output))
        for variable in ('LIBGL_ALWAYS_SOFTWARE', 'QT_QUICK_BACKEND', '__EGL_VENDOR_LIBRARY_FILENAMES', 'LIBGL_DRIVERS_PATH'):
            self.env.pop(variable, None)

    def launch(self, *args):
        return subprocess.run(['bash', str(SCRIPT)] + list(args), env=self.env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

    def test_manual_launch_has_fixed_executable_and_size(self):
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stdout)
        data = json.loads(self.output.read_text())
        self.assertEqual(data['args'], ['--native-app-test', '/test/landline', '--native-app-size', '320x672'])
        self.assertIsNone(data['software'])

    def test_software_smoke_test_preserves_screenshot_argument(self):
        screenshot = str(self.root / 'test image.png')
        result = self.launch('--software', '--smoke-test', '--screenshot', screenshot)
        self.assertEqual(result.returncode, 0, result.stdout)
        data = json.loads(self.output.read_text())
        self.assertIn('--native-app-smoke-test', data['args'])
        self.assertEqual(data['args'][-2:], ['--screenshot', screenshot])
        self.assertEqual(data['software'], '1')
        self.assertEqual(data['backend'], 'software')
        self.assertEqual(data['vendor'], '/test/vendor.json')
        self.assertEqual(data['drivers'], '/test/drivers')

    def test_unknown_options_do_not_launch(self):
        for option in ('--data-dir', '--omp', '--demo', '--unexpected'):
            with self.subTest(option=option):
                self.assertNotEqual(self.launch(option).returncode, 0)
                self.assertFalse(self.output.exists())

    def test_incomplete_screenshot_does_not_launch(self):
        self.assertNotEqual(self.launch('--screenshot').returncode, 0)
        self.assertFalse(self.output.exists())

    def test_help_does_not_launch(self):
        self.assertEqual(self.launch('--help').returncode, 0)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
