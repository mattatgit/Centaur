"""Settings uses supported RPC commands without acquiring model/tool access."""
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gtk4/embedding'))
from omp_settings import OmpSettings


class OmpSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.record=self.root/'arguments.json'
        executable=self.root/'omp'
        executable.write_text('#!'+sys.executable+'\n'+'''
import json,os,pathlib,sys
pathlib.Path(RECORD).write_text(json.dumps({'args':sys.argv[1:],'cwd':os.getcwd()}))
for line in sys.stdin:
 command=json.loads(line)
 if command.get('type')=='extension_ui_response': continue
 if command['type']=='get_available_models': data={'models':[{'provider':'fixture','id':'discovered-model-928','name':'From runtime'}]}
 elif command['type']=='get_login_providers': data={'providers':[{'id':'fixture','authenticated':True}]}
 else: data={'selected':command.get('modelId')}
 print(json.dumps({'type':'tool_execution_start','toolName':'bash'}),flush=True)
 print(json.dumps({'type':'response','id':'unrelated','success':True,'data':{}}),flush=True)
 print(json.dumps({'type':'response','id':command['id'],'success':True,'data':data}),flush=True)
'''.replace('RECORD',repr(str(self.record))))
        executable.chmod(0o700); self.replies=queue.Queue(); self.events=queue.Queue()
        self.client=OmpSettings(str(executable),self.events.put,lambda cb,*args:cb(*args),later=lambda *args:None)
        self.addCleanup(self.client.close)

    def test_read_live_catalog_and_select_through_correlated_rpc(self):
        self.client.request('get_available_models',self.replies.put)
        reply=self.replies.get(timeout=5)
        self.assertEqual(reply['data']['models'][0]['id'],'discovered-model-928')
        self.client.request('set_model',self.replies.put,provider='fixture',modelId='discovered-model-928')
        self.assertEqual(self.replies.get(timeout=5)['data']['selected'],'discovered-model-928')
        record=json.loads(self.record.read_text())
        for flag in ('--no-session','--no-tools','--no-extensions','--no-rules','--no-skills','--no-lsp','--no-title'):
            self.assertIn(flag,record['args'])
        self.assertNotEqual(record['cwd'],str(self.root))
        self.assertTrue(self.events.empty(),'Unexpected model/tool events reached the UI')

    def test_prompt_and_terminal_operations_are_not_exposed(self):
        for kind in ('prompt','bash','exec','set_tools','register_host_uri'):
            with self.assertRaises(ValueError): self.client.request(kind,self.replies.put)
        self.assertIsNone(self.client.process)

    def test_shutdown_reaps_settings_process_and_private_work_directory(self):
        self.client.request('get_login_providers',self.replies.put); self.replies.get(timeout=5)
        process=self.client.process; directory=Path(self.client.work.name)
        self.client.close()
        self.assertIsNotNone(process.poll()); self.assertFalse(directory.exists())

    def test_a_stopped_settings_process_can_be_refreshed_without_stale_callbacks(self):
        self.client.request('get_login_providers',self.replies.put); self.replies.get(timeout=5)
        previous=self.client.process; previous.kill(); previous.wait(timeout=5)
        self.client.request('get_available_models',self.replies.put)
        self.assertEqual(self.replies.get(timeout=5)['data']['models'][0]['id'],'discovered-model-928')
        self.assertNotEqual(self.client.process.pid,previous.pid)


if __name__=='__main__': unittest.main()
