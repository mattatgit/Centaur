import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gtk4/embedding'))
from build_display import compact_version, project_build_mentions


class BuildDisplayTests(unittest.TestCase):
    def test_compact_versions_keep_nonzero_patch_and_abbreviate_long_revision(self):
        self.assertEqual(compact_version('0.4.0-preview+4f32d67'),'V0.4 4f32d67')
        self.assertEqual(compact_version('0.4.1+'+'a'*40),'V0.4.1 aaaaaaa')
        self.assertEqual(compact_version('0.4.0-preview+dev'),'0.4.0-preview+dev')

    def test_only_named_generated_build_references_are_formatted(self):
        text='Landline v0.4.0-preview+4f32d67 includes a fix for Deui v0.3.0-preview+abcd012.'
        self.assertEqual(project_build_mentions(text,'Landline'),
                         'Landline V0.4 4f32d67 includes a fix for Deui v0.3.0-preview+abcd012.')
        self.assertEqual(project_build_mentions(text,'Land'),text)
