"""Exercise real child failures, retries, stderr draining and cancellation budgets."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tarfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gtk4/embedding'))
import source_import as imports


class GitDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        imports._network_used=0; imports._network_budget=6
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.plan=self.root/'plan.json'
        script=self.root/'git'
        script.write_text('#!'+sys.executable+'\n'+'''
import json,os,sys,time
from pathlib import Path
plan=Path(os.environ['CENTAUR_TEST_GIT_PLAN']); data=json.loads(plan.read_text())
calls=data.setdefault('calls',[]); action=data['actions'][min(len(calls),len(data['actions'])-1)]
calls.append(sys.argv[1:]); plan.write_text(json.dumps(data))
if action.get('partial'):
    path=Path(sys.argv[-1]); path.mkdir(); (path/'partial').write_text('incomplete')
if action.get('requireClean') and Path(sys.argv[-1]).exists(): raise SystemExit(7)
sys.stderr.write(action.get('stderr','')); sys.stderr.flush()
sys.stdout.write(action.get('stdout','')); sys.stdout.flush()
time.sleep(action.get('delay',0)); raise SystemExit(action.get('code',0))
''')
        script.chmod(0o700)
        self.env=patch.dict(os.environ,PATH=str(self.root)+os.pathsep+os.environ.get('PATH',''),CENTAUR_TEST_GIT_PLAN=str(self.plan))
        self.env.start(); self.addCleanup(self.env.stop)
        self.pause=patch.object(imports.time,'sleep'); self.pause.start(); self.addCleanup(self.pause.stop)

    def plan_actions(self,*actions): self.plan.write_text(json.dumps({'actions':actions}))
    def calls(self): return json.loads(self.plan.read_text())['calls']
    def remote(self): return imports.git(['ls-remote','--','https://github.com/example/app.git','HEAD'])

    def test_transient_dns_retries_same_repository_and_returns_success(self):
        self.plan_actions({'code':128,'stderr':'fatal: Could not resolve host: github.com'}, {'stdout':'VERIFIED HEAD'})
        self.assertEqual(self.remote(),b'VERIFIED HEAD')
        self.assertEqual(len(self.calls()),2); self.assertEqual(self.calls()[0],self.calls()[1])

    def test_failed_clone_retries_only_its_private_partial_directory(self):
        history=self.root/'history.git'; prior=self.root/'prior-source'; prior.write_text('USER WORK')
        self.plan_actions({'code':128,'stderr':'Could not resolve host: github.com','partial':True}, {'requireClean':True})
        imports.git(['clone','--bare','--single-branch','--branch','linux-nix','--','https://github.com/example/app.git',str(history)],cleanup=history)
        self.assertEqual(self.calls()[0],self.calls()[1]); self.assertIn('linux-nix',self.calls()[1])
        self.assertEqual(prior.read_text(),'USER WORK'); self.assertFalse(history.exists())
        history.mkdir()
        with self.assertRaises(imports.ImportError): imports.git(['clone'],cleanup=history)
        self.assertTrue(history.exists())

    def test_persistent_dns_failure_has_a_bounded_retry_and_specific_reason(self):
        self.plan_actions({'code':128,'stderr':'fatal: Could not resolve host: github.com'})
        with self.assertRaises(imports.ImportError) as raised: self.remote()
        error=raised.exception
        self.assertEqual(len(self.calls()),3); self.assertIn('resolve',str(error))
        self.assertNotIn('sign-in',str(error)); self.assertEqual(error.diagnostic['category'],'dns')
        self.assertEqual(error.diagnostic['operation'],'ls-remote'); self.assertEqual(error.diagnostic['exitCode'],128)
        self.assertEqual(error.diagnostic['attempts'],3)

    def test_auth_certificate_storage_missing_ref_and_unknown_failures_are_distinct_without_retry(self):
        cases=[('Authentication failed','authentication'),('SSL certificate problem','certificate'),
               ('No space left on device','storage'),('Remote branch missing not found','branch'),('Unexpected Git error','git')]
        messages=set()
        for detail,category in cases:
            with self.subTest(category=category):
                self.plan_actions({'code':128,'stderr':detail})
                with self.assertRaises(imports.ImportError) as raised: self.remote()
                self.assertEqual(len(self.calls()),1); self.assertEqual(raised.exception.diagnostic['category'],category)
                messages.add(str(raised.exception))
        self.assertEqual(len(messages),len(cases))

    def test_diagnostics_redact_credentials_urls_paths_and_bound_stderr(self):
        secret='ghp_'+'A'*30
        self.plan_actions({'code':128,'stderr':'x'*10000+f"\nfatal: https://user:{secret}@github.com/private/repo?token=VALUE '/home/private/source'\nAuthorization: Bearer TOPSECRET\n"})
        with self.assertRaises(imports.ImportError) as raised: self.remote()
        detail=json.dumps(raised.exception.diagnostic)
        for value in (secret,'TOPSECRET','/home/private','user:','?token=','private/repo'):
            self.assertNotIn(value,detail)
        self.assertLess(len(raised.exception.diagnostic['detail']),2001)
        self.assertNotIn('fatal:',str(raised.exception))

    def test_streaming_stdout_is_not_corrupted_or_blocked_by_large_stderr(self):
        self.plan_actions({'stdout':'ARCHIVE BYTES','stderr':'progress\n'*20000})
        consumed=[]
        self.assertEqual(imports.git(['archive'],consume=lambda stream:consumed.append(stream.read())),b'')
        self.assertEqual(consumed,[b'ARCHIVE BYTES'])

    def test_deadline_terminates_child_and_prevents_further_retries(self):
        self.plan_actions({'delay':10})
        start=time.monotonic()
        with patch.object(imports,'_git_deadline',start+0.5),self.assertRaises(imports.ImportError) as raised: self.remote()
        self.assertLess(time.monotonic()-start,3); self.assertEqual(len(self.calls()),1)
        self.assertEqual(raised.exception.diagnostic['category'],'timeout')

    def test_archive_failure_preserves_git_reason_when_tar_is_empty(self):
        self.plan_actions({'code':128,'stderr':'fatal: not a valid object name: HEAD'})
        def consume(stream):
            with tarfile.open(fileobj=stream,mode='r|') as archive: list(archive)
        with self.assertRaises(imports.ImportError) as raised: imports.git(['archive'],consume=consume)
        self.assertEqual(raised.exception.diagnostic['operation'],'archive')
        self.assertIn('not a valid object',raised.exception.diagnostic['detail'])

    def test_network_budget_spans_operations_and_caps_new_worker_allowance(self):
        imports._network_budget=2
        self.plan_actions({'code':128,'stderr':'Could not resolve host: github.com'})
        with self.assertRaises(imports.ImportError): self.remote()
        self.assertEqual(len(self.calls()),2); self.assertEqual(imports._network_used,2)
        with self.assertRaises(imports.ImportError): self.remote()
        self.assertEqual(len(self.calls()),2)


if __name__=='__main__': unittest.main()
