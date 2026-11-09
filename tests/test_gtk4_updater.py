"""Updater transaction failures use disposable profiles/process doubles only."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'gtk4/embedding'))
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path); result=importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result
updater=module('gtk4_updater',ROOT/'gtk4/embedding/updater.py')
publisher=module('gtk4_publisher',ROOT/'scripts/publish-gtk4-update.py')


def manifest():
    return {'schemaVersion':1,'updateProtocol':1,'branch':'codex/gtk4-migration','system':'aarch64-linux',
            'packageAttribute':'gtk4-preview','sourceRevision':'b'*40,'sourceTimestamp':200,
            'storePath':'/nix/store/'+'a'*32+'-centaur-gtk4-preview-0.4.0-preview',
            'cacheUrl':updater.CACHE,'publicSigningKeys':[updater.KEY],
            'verifiedSignedClosureDownload':True,'version':'Centaur GTK4 0.4.0-preview+bbbbbbb',
            'publishedAt':'2026-11-09T00:00:00+00:00'}


class Runtime:
    def __init__(self,case,fail=None): self.case=case; self.fail=fail; self.calls=[]
    def action(self,name,*args):
        self.calls.append((name,*map(str,args)))
        if self.fail==name: raise updater.UpdateError('simulated '+name)
    def root_previous(self,path): self.action('root',path)
    def download(self,value,**kwargs): self.action('download',value['storePath'])
    def wait_parent(self,pid,identity): self.action('parent-exit',pid,identity)
    def stop_host(self,package,data,token=''): self.action('stop',package,data,token)
    def activate(self,profile,path):
        self.action('activate',path)
        temporary=profile.with_name('next'); temporary.symlink_to(path); temporary.replace(profile)
    def launch(self,package,data,work,token,omp): self.action('launch',package,data,token,omp); return object()
    def ready(self,process,work,build): self.action('health',build)
    def release_host(self,package,data,token): self.action('release',package,data,token)
    def stop_child(self,process): self.action('close-child')


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name).resolve(); self.addCleanup(patch.stopall)
        patch.object(Path,'home',return_value=self.home).start()
        patch.dict(os.environ,{'XDG_STATE_HOME':str(self.home/'state'),'XDG_DATA_HOME':str(self.home/'data')}).start()
        self.old=self.home/'old'; self.new=self.home/'new'
        for package in (self.old,self.new):
            (package/'bin').mkdir(parents=True)
            for name in ('centaur-gtk4','centaur-host','.centaur-gtk4-wrapped'): (package/'bin'/name).touch()
        self.profile=updater.profile_path(); self.profile.parent.mkdir(parents=True); self.profile.symlink_to(self.old)
        self.work=updater.state_path()/'run-test'; self.work.mkdir(parents=True)
        self.data=self.home/'gtk-data'; self.data.mkdir(); (self.data/'project.json').write_text('saved conversation and identity')
        self.qt=self.home/'data/Centaur/Centaur'; self.qt.mkdir(parents=True); (self.qt/'unchanged').write_text('Qt project')
        self.request={'package':str(self.old),'dataDir':str(self.data),'parentPid':123,'parentIdentity':'start-1','omp':'/home/matt/.local/bin/omp'}
        updater.write_json(self.work/'request.json',self.request)
        self.value=manifest(); self.value['storePath']=str(self.new)

    def transaction(self,fail=None):
        runtime=Runtime(self,fail); return updater.Transaction(self.work,runtime),runtime

    def assert_preserved(self):
        self.assertEqual((self.data/'project.json').read_text(),'saved conversation and identity')
        self.assertEqual((self.qt/'unchanged').read_text(),'Qt project')

    def test_discovery_only_newer_successfully_published_gtk_binary(self):
        value=manifest()
        self.assertEqual(updater.check_update('aaaaaaa',100,lambda:value),value)
        self.assertIsNone(updater.check_update('bbbbbbb',100,lambda:value))
        self.assertIsNone(updater.check_update('aaaaaaa',200,lambda:value))
        for key,bad in [('system','x86_64-linux'),('branch','codex/native-prototype'),('packageAttribute','default'),
                        ('cacheUrl','https://other.example'),('publicSigningKeys',['attacker:key']),
                        ('verifiedSignedClosureDownload',False),('updateProtocol',2),('storePath','/tmp/evil'),
                        ('sourceRevision','b;echo nope'),('version','Centaur GTK4 wrong')]:
            candidate=copy.deepcopy(value); candidate[key]=bad
            with self.subTest(key=key),self.assertRaises(updater.UpdateError): updater.validate_manifest(candidate)

    def test_success_orders_verification_before_stop_and_atomic_activation_before_health(self):
        transaction,runtime=self.transaction()
        transaction.apply(self.value,{'approved':True,'resume':{'projectId':'family','drafts':{'family':'unsent text'}}})
        self.assertEqual([c[0] for c in runtime.calls],['root','download','parent-exit','stop','activate','launch','health','release'])
        self.assertEqual(self.profile.resolve(),self.new)
        self.assertEqual(runtime.calls[5][-1],'/home/matt/.local/bin/omp')
        self.assertEqual(updater.read_json(self.work/'resume.json')['drafts']['family'],'unsent text')
        self.assertEqual(updater.read_json(self.work/'status.json')['phase'],'complete')
        self.assertEqual(updater.read_json(updater.state_path()/'recovery.json')['previous'],str(self.old))
        self.assert_preserved()

    def test_failed_download_or_signature_verification_never_stops_host(self):
        transaction,runtime=self.transaction('download')
        with self.assertRaises(updater.UpdateError): transaction.apply(self.value,{'approved':True})
        self.assertEqual(self.profile.resolve(),self.old)
        self.assertNotIn('stop',[c[0] for c in runtime.calls]); self.assert_preserved()

    def test_crash_timeout_or_rejected_start_restores_previous_and_relaunches_it(self):
        for failure in ('health','release'):
            with self.subTest(failure=failure):
                transaction,runtime=self.transaction(failure)
                with self.assertRaises(updater.UpdateError): transaction.apply(self.value,{'approved':True})
                self.assertEqual(self.profile.resolve(),self.old)
                self.assertEqual(updater.read_json(self.work/'status.json')['phase'],'recovered')
                self.assertEqual(runtime.calls[-1][0:2],('launch',str(self.old)))
                self.assertTrue(any(c[0]=='stop' and c[1]==str(self.new) for c in runtime.calls))
                self.assert_preserved()

    def test_activation_failure_keeps_old_profile_and_opens_old_app(self):
        transaction,runtime=self.transaction()
        original=runtime.activate
        def activate(profile,path):
            if path==str(self.new): raise updater.UpdateError('switch failed')
            return original(profile,path)
        runtime.activate=activate
        with self.assertRaises(updater.UpdateError): transaction.apply(self.value,{'approved':True})
        self.assertEqual(self.profile.resolve(),self.old)
        self.assertEqual(runtime.calls[-1][0:2],('launch',str(self.old))); self.assert_preserved()

    def test_busy_host_is_not_interrupted_or_replaced(self):
        transaction,runtime=self.transaction('stop')
        with self.assertRaises(updater.UpdateError): transaction.apply(self.value,{'approved':True})
        self.assertEqual(self.profile.resolve(),self.old)
        self.assertFalse(any(c[0]=='launch' and c[1]==str(self.new) for c in runtime.calls))
        self.assert_preserved()

    def test_rollback_failure_retains_journal_and_launches_old_store_package(self):
        transaction,runtime=self.transaction('health')
        original=runtime.activate
        def activate(profile,path):
            if path==str(self.old): raise updater.UpdateError('daemon stopped during rollback')
            return original(profile,path)
        runtime.activate=activate
        with self.assertRaises(updater.UpdateError): transaction.apply(self.value,{'approved':True})
        self.assertEqual(updater.read_json(self.work/'status.json')['phase'],'recovery-required')
        self.assertEqual(updater.read_json(updater.state_path()/'recovery.json')['previous'],str(self.old))
        self.assertEqual(runtime.calls[-1][0:2],('launch',str(self.old))); self.assert_preserved()

    def test_refuse_mixed_profile_wrong_installation_or_qt_data(self):
        for invalid in ('mixed','wrong-package','qt-data'):
            with self.subTest(invalid=invalid):
                request=dict(self.request)
                if invalid=='mixed': (self.old/'bin/unrelated-editor').touch()
                if invalid=='wrong-package': request['package']=str(self.new)
                if invalid=='qt-data': request['dataDir']=str(self.qt)
                updater.write_json(self.work/'request.json',request)
                transaction,runtime=self.transaction()
                with self.assertRaises(updater.UpdateError): transaction.apply(self.value,{'approved':True})
                self.assertEqual(runtime.calls,[])
                (self.old/'bin/unrelated-editor').unlink(missing_ok=True)
                self.assert_preserved()

    def test_window_closes_during_download_no_activation(self):
        transaction,runtime=self.transaction()
        with patch.object(updater,'process_identity',return_value=None),self.assertRaises(updater.UpdateError): transaction.apply(self.value,{})
        self.assertEqual(self.profile.resolve(),self.old)
        self.assertNotIn('stop',[c[0] for c in runtime.calls])

    def test_profile_changed_during_download_is_not_overwritten(self):
        transaction,runtime=self.transaction()
        original=runtime.download
        def download(value,**kwargs):
            original(value)
            next_profile=self.profile.with_name('external-update'); next_profile.symlink_to(self.new); next_profile.replace(self.profile)
        runtime.download=download
        with self.assertRaises(updater.UpdateError): transaction.apply(self.value,{'approved':True})
        self.assertEqual(self.profile.resolve(),self.new)
        self.assertNotIn('stop',[c[0] for c in runtime.calls]); self.assert_preserved()

    def test_legacy_and_custom_qt_data_roots_are_protected(self):
        for qt in (self.home/'.local/share/Centaur/Centaur',self.home/'custom-qt'):
            qt.mkdir(parents=True,exist_ok=True)
            if qt.name=='custom-qt':
                settings=Path(os.environ.get('XDG_CONFIG_HOME',self.home/'.config'))/'centaur-launcher'
                settings.mkdir(parents=True,exist_ok=True); (settings/'data-dir').write_text(str(qt))
            updater.write_json(self.work/'request.json',dict(self.request,dataDir=str(qt)))
            transaction,runtime=self.transaction()
            with self.assertRaises(updater.UpdateError): transaction.apply(self.value,{'approved':True})
            self.assertEqual(runtime.calls,[])

    def test_real_runtime_invocations_disable_all_builders_and_verify_cache_signatures(self):
        runtime=updater.Runtime(self.work); calls=[]
        def run(args,**kwargs):
            calls.append(args); return subprocess.CompletedProcess(args,0,'')
        with patch.object(subprocess,'run',side_effect=run):
            runtime.activate(self.profile,'/nix/store/already-realised')
            runtime.nix('copy','--from',updater.CACHE,'/nix/store/already-realised')
            runtime.nix('store','verify','--recursive','--sigs-needed','1','--option','trusted-public-keys',updater.KEY,'/nix/store/already-realised')
        for args in calls:
            self.assertEqual(args[args.index('--max-jobs')+1],'0'); self.assertEqual(args[args.index('--builders')+1],'')
            self.assertIn('require-sigs',args); self.assertNotIn('--no-check-sigs',args)
        self.assertIn('--offline',calls[0]); self.assertIn(updater.KEY,calls[2])

    def test_publication_is_single_atomic_body_update_and_refuses_old_or_unsigned(self):
        calls=[]; value=manifest()
        def request(method,path,body=None):
            calls.append((method,path,body))
            return {'id':42,'body':json.dumps(dict(value,sourceTimestamp=100))} if method=='GET' else {'html_url':'ok'}
        publisher.publish(value,request)
        self.assertEqual([c[0] for c in calls],['GET','PATCH'])
        self.assertEqual(json.loads(calls[-1][2]['body']),value)
        with self.assertRaises(ValueError): publisher.publish(dict(value,verifiedSignedClosureDownload=False),request)
        with self.assertRaises(ValueError): publisher.publish(dict(value,sourceTimestamp=50),request)


if __name__=='__main__': unittest.main()
