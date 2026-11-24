import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gtk4/embedding'))
from chat_identity import message_profile


class HistoricalAuthors(unittest.TestCase):
    people=[{'id':'host','name':'Matt'}, {'id':'guest-new','name':'Matt (2)','displayName':'Matt',
             'profileId':'stable','previousIds':['guest-old'],'avatar':'guest-photo'}]

    def appearance(self,participant=None,profile=None,viewer='guest-new'):
        return message_profile({'author':'Matt','participant':participant,'profileId':profile},
                               self.people,viewer,['local-proof'],'Matt')

    def test_renamed_duplicate_and_past_memberships(self):
        for identity,profile in [('guest-new',None),('guest-old',None),('older','stable')]:
            guest=self.appearance(identity,profile)
            self.assertTrue(guest['self'])
            self.assertEqual(guest['displayName'],'Matt')
            self.assertEqual(guest['avatar'],'guest-photo')
            self.assertFalse(self.appearance(identity,profile,'host')['self'])

    def test_local_receipt_and_unattributable_history(self):
        self.assertTrue(self.appearance('local-proof')['self'])
        for unknown in [None,'another-guest','local:Someone else']:
            self.assertEqual(self.appearance(unknown),{'self':False})
        self.assertFalse(self.appearance('local:Matt')['self'])
        self.assertTrue(self.appearance('local:Matt',viewer='host')['self'])
