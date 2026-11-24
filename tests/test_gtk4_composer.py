import io
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gtk4/embedding'))
from attachment_model import figma_reference, image_filename, mentions_agent, mention_suffix, prepare_image, stored_image


class ComposerModelTests(unittest.TestCase):
    def test_mentions_are_cursor_relative_and_case_insensitive(self):
        self.assertTrue(mentions_agent('Hello @ATLAS!', 'Atlas'))
        self.assertFalse(mentions_agent('mail@atlas.example and @atlas-two', 'Atlas'))
        self.assertEqual(mention_suffix('Hello @aT',9,['Atlas']),'las')
        for text, pos in [('a@a',3), ('@Atlas',6), ('@Atl',2), ('@at!',4)]:
            self.assertEqual(mention_suffix(text,pos,['Atlas']),'')

    def test_links_preserve_original_branch_and_node(self):
        url='https://www.figma.com/design/abcd/branch/ef01/Flow-ideas?node-id=12-3&t=a'
        self.assertEqual(figma_reference(url),{'type':'figma','name':'Flow ideas','url':url})
        for bad in (url.replace('www.figma.com','www.figma.com.example'),url+'&node-id=1-2',url.replace('Flow-ideas','..'),url.replace('https:','http:')):
            self.assertIsNone(figma_reference(bad))

    def test_encoding_and_scoped_paths(self):
        try: from PIL import Image
        except ImportError: self.skipTest('Pillow required for codec test')
        for fmt in ('PNG','WEBP','JPEG'):
            image=Image.new('RGBA' if fmt=='PNG' else 'RGB',(320,240),'blue')
            raw=io.BytesIO(); image.save(raw,format=fmt)
            ref,data=prepare_image(raw.getvalue())
            with Image.open(io.BytesIO(data)) as restored:
                self.assertEqual(restored.size,image.size)
            with tempfile.TemporaryDirectory() as directory:
                folder=Path(directory); path=folder/image_filename(ref); path.write_bytes(data)
                self.assertEqual(stored_image(folder,ref),path)
                self.assertIsNone(stored_image(folder,dict(ref,hash='../other')))
        with self.assertRaises(ValueError): prepare_image(b'not an image')
