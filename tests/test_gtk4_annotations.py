"""Cross-app marks retain their meaning across independent canvas transforms."""
import importlib.util
from pathlib import Path
import sys
import unittest

BASE=Path(__file__).resolve().parents[1]/'gtk4/embedding'
def load(name):
    spec=importlib.util.spec_from_file_location(name,BASE/(name+'.py'))
    module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module); return module
annotations=load('annotations'); viewport=load('viewport_model')


class AnnotationTests(unittest.TestCase):
    def test_crossing_each_app_edge_at_every_zoom_retains_outside_points(self):
        for zoom in viewport.ZOOM_MODES:
            model=viewport.ViewportModel(520,640,mode=zoom); geometry=model.geometry(960,840)
            space=annotations.AnnotationSpace.capture(geometry,960,840)
            for x,y in ((geometry['app_x']-12,400),(geometry['app_x']+520*geometry['scale']+12,400),
                        (400,max(0,geometry['app_y']-12)),(400,min(840,geometry['app_y']+640*geometry['scale']+12))):
                point=space.point(x,y); actual=annotations.position(point,space.frame,geometry)
                self.assertAlmostEqual(actual[0],max(0,min(960,x))); self.assertAlmostEqual(actual[1],max(0,min(840,y)))
                self.assertTrue(all(0<=v<=1 for v in (*point.values(),*space.frame.values())))
            self.assertLess(space.point(geometry['app_x']-12,400)['x'],space.frame['x'])

    def test_saved_stroke_reprojects_to_other_window_zoom_pan_and_resize(self):
        first=viewport.ViewportModel(520,640,mode='75%'); source=first.geometry(960,840)
        space=annotations.AnnotationSpace.capture(source,960,840)
        expected=[(-.08,.35),(.2,.35),(-.08,.4),(1.08,.55)]
        points=[space.point(source['app_x']+x*520*source['scale'],source['app_y']+y*640*source['scale']) for x,y in expected]
        for mode in viewport.ZOOM_MODES:
            target=viewport.ViewportModel(520,640,mode=mode,pan_x=25,pan_y=-30)
            for width,height in ((720,756),(1100,680),(1200,1000)):
                geometry=target.geometry(width,height)
                for point,(x,y) in zip(points,expected):
                    actual=annotations.position(point,space.frame,geometry)
                    self.assertAlmostEqual(actual[0],geometry['app_x']+x*520*geometry['scale'])
                    self.assertAlmostEqual(actual[1],geometry['app_y']+y*640*geometry['scale'])

    def test_reference_includes_clipped_app_and_points_stay_in_existing_wire_range(self):
        model=viewport.ViewportModel(1440,900,mode='150%',pan_x=100,pan_y=-50)
        geometry=model.geometry(720,500); space=annotations.AnnotationSpace.capture(geometry,720,500)
        for x,y in ((-20,-10),(740,520),(0,250),(360,500)):
            point=space.point(x,y)
            self.assertTrue(all(0<=v<=1 for v in (*point.values(),*space.frame.values())))
            self.assertEqual(annotations.position(point,space.frame,geometry),(max(0,min(720,x)),max(0,min(500,y))))

    def test_legacy_app_normalized_marks_are_unchanged(self):
        geometry=viewport.ViewportModel(520,640).geometry(960,840)
        for frame in (None,{'x':0,'y':0,'width':1,'height':1}):
            self.assertEqual(annotations.position({'x':.25,'y':.5},frame,geometry),(350,420))

    def test_invalid_frames_do_not_produce_invalid_render_coordinates(self):
        geometry=viewport.ViewportModel(520,640).geometry(960,840)
        for frame in ({'x':0,'y':0,'width':0,'height':1},{'x':0,'y':0,'width':float('nan'),'height':1}):
            with self.assertRaises(ValueError): annotations.position({'x':0,'y':0},frame,geometry)


if __name__=='__main__': unittest.main()
