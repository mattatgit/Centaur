"""The typed bundle cannot extract arbitrary paths or blur GTK/Qt formats."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('bundle',ROOT/'gtk4/embedding/bundle.py')
bundle=importlib.util.module_from_spec(spec); spec.loader.exec_module(bundle)


class BundleTests(unittest.TestCase):
    def check_bundle(self, value):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'App.gtk.json'; path.write_text(json.dumps(value))
            return bundle.load_bundle(path)

    def test_starter_separates_behaviour_layout_and_style(self):
        value=json.loads((ROOT/'templates/App.gtk.json').read_text())
        self.assertEqual(self.check_bundle(value),value)

    def test_arbitrary_paths_and_additional_files_are_refused(self):
        value=json.loads((ROOT/'templates/App.gtk.json').read_text())
        value['files']['../credentials']='no'
        with self.assertRaises(ValueError): self.check_bundle(value)

    def test_malformed_runtime_dimensions_behaviour_and_layout_are_refused(self):
        original=json.loads((ROOT/'templates/App.gtk.json').read_text())
        for change in ({'format':'qml'},{'width':True},{'height':0},{'width':999999}):
            with self.subTest(change=change), self.assertRaises(ValueError): self.check_bundle({**original,**change})
        for filename,source in [('app.py','def broken('),('app.ui','<html/>')]:
            value=json.loads(json.dumps(original)); value['files'][filename]=source
            with self.subTest(filename=filename), self.assertRaises((ValueError,SyntaxError)): self.check_bundle(value)


if __name__=='__main__': unittest.main()
