"""Draft pointer lifecycle and app anchoring, independent of GTK rendering."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gtk4/embedding'))
from comment_pointer import CommentPointer
from annotations import AnnotationSpace
from viewport_model import ViewportModel,ZOOM_MODES


class CommentPointerTests(unittest.TestCase):
    def test_two_click_placement_stops_tracking_and_keeps_reference(self):
        model=ViewportModel(520,640); geometry=model.geometry(960,840)
        pointer=CommentPointer(); pointer.start('project',1,(20,30))
        pointer.move((40,50)); self.assertEqual(pointer.head(geometry,(0,0)),(40,50))
        space=AnnotationSpace.capture(geometry,960,840)
        self.assertTrue(pointer.place(space,300,320)); pointer.move((500,600))
        self.assertEqual(pointer.head(geometry,(0,0)),(300,320))
        self.assertEqual(pointer.target['revision'],1)
        self.assertFalse(pointer.place(space,400,420))

    def test_target_survives_zoom_pan_resize_and_outside_app_locations(self):
        geometry=ViewportModel(520,640).geometry(960,840)
        pointer=CommentPointer(); pointer.start('project',2,(0,0))
        space=AnnotationSpace.capture(geometry,960,840)
        pointer.place(space,geometry['app_x']-20,geometry['app_y']+200)
        for zoom in ZOOM_MODES:
            current=ViewportModel(520,640,mode=zoom,pan_x=20,pan_y=-15).geometry(720,760)
            x,y=pointer.head(current,(24,48))
            self.assertAlmostEqual(x,24+current['app_x']-20*current['scale'])
            self.assertAlmostEqual(y,48+current['app_y']+200*current['scale'])

    def test_acknowledging_an_older_message_cannot_erase_a_new_pointer(self):
        pointer=CommentPointer(); pointer.start('project',1,(0,0)); sent=pointer.token
        pointer.start('project',1,(100,200))
        self.assertFalse(pointer.clear(sent)); self.assertEqual(pointer.phase,'following')
        self.assertTrue(pointer.clear(pointer.token)); self.assertEqual(pointer.phase,'idle')
        self.assertIsNone(pointer.target)

    def test_cancel_and_reactivation_do_not_reuse_the_previous_target(self):
        pointer=CommentPointer(); geometry=ViewportModel(520,640).geometry(960,840)
        pointer.start('one',1,(0,0)); pointer.place(AnnotationSpace.capture(geometry,960,840),10,20)
        pointer.clear(); pointer.start('two',3,(30,40))
        self.assertEqual(pointer.project,'two'); self.assertEqual(pointer.revision,3)
        self.assertIsNone(pointer.target); self.assertEqual(pointer.head(geometry,(0,0)),(30,40))


if __name__=='__main__': unittest.main()
