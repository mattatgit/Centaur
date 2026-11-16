"""Production broker boundary tests. Actual execution only on the ARM64 UTM VM."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gtk4/embedding'))
import import_broker as broker

class SandboxBrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.source=self.root/'source';self.source.mkdir()
    def tearDown(self):self.tmp.cleanup()
    def call(self,operation,**fields):return broker.execute(self.root,dict(operation=operation,**fields))

    def test_model_cannot_choose_command_root_environment_or_execute_project_code(self):
        (self.source/'build.sh').write_text('touch MUST_NOT_EXECUTE')
        with patch.object(subprocess,'Popen',side_effect=AssertionError('Invalid authority reached process launch')):
            for tool in [dict(operation='runtime_version',runtime='python',command='build.sh'),
                         dict(operation='runtime_version',runtime='python',root='/'),
                         dict(operation='runtime_version',runtime='build.sh'),
                         dict(operation='validate_manifest',path='../secret.json'),
                         dict(operation='validate_manifest',path='build.sh'),
                         dict(operation='validate_manifest',path='file.json',env={'PATH':'/source'})]:
                self.assertEqual(broker.execute(self.root,tool)['error']['code'],'invalid_request' if tool.get('path')!='../secret.json' else 'invalid_path')

    @unittest.skipUnless(os.environ.get('CENTAUR_IMPORT_SANDBOX'),'Requires packaged ARM64 NixOS UTM sandbox')
    def test_real_fixed_versions_and_manifest_results_are_bounded_and_read_only(self):
        for runtime in ('python','git','gcc'):
            result=self.call('runtime_version',runtime=runtime)
            self.assertTrue(result['ok'],result);self.assertTrue(result['execution']['isolated'])
            self.assertFalse(result['execution']['descendantsRemain']);self.assertEqual(result['execution']['exitCode'],0)
            self.assertEqual(result['data']['availability'],'packagedDiagnosticRuntime')
        for name,text,valid in [('package.json','{"name":"sample","scripts":{"preinstall":"touch MUST_NOT_EXECUTE"}}',True),
                                ('Cargo.toml','[package]\nname = "sample"\n',True),
                                ('broken.json','{"a": }',False),('bad.toml','[package',False),
                                ('deep.json','['*1500+'0'+']'*1500,'bounded')]:
            path=self.source/name;path.write_text(text);before=hashlib.sha256(path.read_bytes()).hexdigest()
            result=self.call('validate_manifest',path=name)
            self.assertTrue(result['ok'],result)
            if valid=='bounded':
                self.assertIn(result['data']['valid'],(True,None))
                if result['data']['valid'] is None:self.assertEqual(result['data']['code'],'parse_limit')
            else:self.assertEqual(result['data']['valid'],valid)
            self.assertEqual(before,hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertNotIn('preinstall',json.dumps(result));self.assertNotIn('sample',json.dumps(result))
        self.assertFalse((self.source/'MUST_NOT_EXECUTE').exists())
        adaptation=self.root/'adaptations/version-one';adaptation.mkdir(parents=True)
        (adaptation/'package.json').write_text('{}')
        result=broker.execute(self.root,{'operation':'validate_manifest','scope':'adaptation','path':'package.json'},'adaptations/version-one')
        self.assertTrue(result['ok'],result)

    def test_secrets_symlinks_binary_and_oversized_input_never_enter_sandbox(self):
        (self.source/'.env.json').write_text('PRIVATE')
        (self.source/'token.json').write_text('{"x":"ghp_'+'A'*30+'"}')
        (self.source/'link.json').symlink_to('/etc/passwd')
        (self.source/'binary.json').write_bytes(b'\x00')
        (self.source/'huge.json').write_text('x'*240001)
        with patch.dict(os.environ,{'CENTAUR_IMPORT_SANDBOX':'/unused'}),patch.object(subprocess,'Popen',side_effect=AssertionError('Omitted source entered sandbox')):
            for path in ('.env.json','token.json','link.json','binary.json','huge.json'):
                result=self.call('validate_manifest',path=path);self.assertFalse(result['ok'],result)
                self.assertNotIn('PRIVATE',json.dumps(result));self.assertNotIn('A'*30,json.dumps(result))

    def test_missing_boundary_has_no_host_process_fallback(self):
        with patch.dict(os.environ,{'CENTAUR_IMPORT_SANDBOX':''}),patch.object(subprocess,'Popen',side_effect=AssertionError('Fallback')):
            result=self.call('runtime_version',runtime='python')
            self.assertTrue(result['sourceAvailable']);self.assertEqual(result['error']['code'],'isolation_unavailable')

if __name__=='__main__':unittest.main()
