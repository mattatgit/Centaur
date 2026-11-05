"""App geometry stays invariant while display transforms and bounds change."""
import importlib.util
from pathlib import Path
import sys
import unittest

spec = importlib.util.spec_from_file_location('viewport_model', Path(__file__).resolve().parents[1] / 'gtk4/embedding/viewport_model.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class ViewportTests(unittest.TestCase):
    def test_resize_recentres_without_resizing_app_or_changing_zoom(self):
        model = module.ViewportModel(460, 600)
        for width, height in ((900,700),(1000,800),(340,300)):
            g = model.geometry(width,height)
            self.assertEqual(g['scale'], 1)
            self.assertEqual((g['app_width'],g['app_height']), (460,600))
            self.assertEqual(g['app_x']+230, width/2)
            self.assertEqual(g['app_y']+300, height/2)

    def test_coordinate_round_trip_at_every_zoom(self):
        model = module.ViewportModel(1440,900)
        for mode in module.ZOOM_MODES:
            model.select(mode,800,600)
            g = model.geometry(800,600)
            for x,y in ((0,0),(310,420),(1440,900)):
                actual = model.app_point(g['app_x']+x*g['scale'],g['app_y']+y*g['scale'],800,600)
                self.assertAlmostEqual(actual[0],x)
                self.assertAlmostEqual(actual[1],y)

    def test_fit_reacts_to_resize_without_changing_logical_dimensions(self):
        model = module.ViewportModel(1440,900,mode='Fit')
        first = model.geometry(800,600)
        larger = model.geometry(1200,900)
        self.assertGreater(larger['scale'],first['scale'])
        for g,w,h in ((first,800,600),(larger,1200,900)):
            self.assertGreaterEqual(g['app_x'],16)
            self.assertGreaterEqual(g['app_y'],16)
            self.assertLessEqual(g['app_x']+1440*g['scale'],w-16+1e-6)
            self.assertLessEqual(g['app_y']+900*g['scale'],h-16+1e-6)

    def test_pan_is_bounded_and_zoom_preserves_centre_anchor(self):
        model = module.ViewportModel(1440,900)
        model.pan_x, model.pan_y = 100,60
        before = model.app_point(400,300,800,600)
        model.select('150%',800,600)
        after = model.app_point(400,300,800,600)
        self.assertEqual(before,after)
        model.pan_x = model.pan_y = 100000
        g = model.geometry(800,600)
        self.assertAlmostEqual(g['app_x'],16)
        self.assertAlmostEqual(g['app_y'],16)
        model.select('Fit',800,600)
        self.assertEqual((model.pan_x,model.pan_y),(0,0))


if __name__ == '__main__':
    unittest.main()
