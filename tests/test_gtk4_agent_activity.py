import importlib.util
from pathlib import Path
import unittest


spec=importlib.util.spec_from_file_location('agent_activity',Path(__file__).parents[1]/'gtk4/embedding/agent_activity.py')
activity=importlib.util.module_from_spec(spec);spec.loader.exec_module(activity)


class AgentActivityTest(unittest.TestCase):
    def test_waiting_information_does_not_invent_work_or_claim_a_stall(self):
        value={'phase':'waiting','startedAt':'2026-11-18T00:00:00Z','updatedAt':'2026-11-18T00:00:00Z'}
        from datetime import datetime
        now=datetime.fromisoformat('2026-11-18T00:00:00+00:00').timestamp()
        self.assertEqual(activity.caption(value,now+10),'Waiting for agent response…')
        self.assertEqual(activity.caption(value,now+65),'Still waiting for the agent… · 1m 05s')
        self.assertNotIn('stall',activity.caption(value,now+180))
        value.update(phase='searching',updatedAt='2026-11-18T00:01:04Z')
        self.assertEqual(activity.caption(value,now+65),'Searching project files… · 1m 05s')
        value['phase']='made-up-model-output'
        self.assertNotIn('made-up',activity.caption(value,now+65))

    def test_details_use_only_public_lifecycle_fields_and_verified_source_status(self):
        value={'code':'agent_deadline','layer':'centaur.agent','lastActivePhase':'processing',
               'elapsedMs':180012,'deadlineMs':180000,'lastProviderActivityMs':2500,
               'events':18,'streamUpdates':12,'sourceComparisonAvailable':True,'sourceUnchanged':False,
               'stderr':'SECRET','thinking':'PRIVATE','delta':'PRIVATE','providerPayload':'SECRET'}
        text=activity.details_text(value)
        self.assertIn('centaur.agent',text);self.assertIn('180.0s',text)
        self.assertIn('changed during this request',text)
        self.assertNotIn('SECRET',text);self.assertNotIn('PRIVATE',text)
        value['sourceComparisonAvailable']=False;value['sourceUnchanged']=True
        self.assertIn('unchanged state could not be verified',activity.details_text(value))


if __name__=='__main__':unittest.main()
