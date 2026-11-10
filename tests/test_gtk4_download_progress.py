"""Real streamed subprocess output and Nix compressed-byte accounting."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

BASE=Path(__file__).resolve().parents[1]/'gtk4/embedding'
sys.path.insert(0,str(BASE))
from download_progress import DownloadProgress, download_plan, path_info, progress_message
spec=importlib.util.spec_from_file_location('progress_updater',BASE/'updater.py')
updater=importlib.util.module_from_spec(spec); spec.loader.exec_module(updater)

CACHE=updater.CACHE
URL=CACHE+'/nar/test.nar.zst'
def event(action,id=1,**fields): return '@nix '+json.dumps(dict(action=action,id=id,**fields))+'\n'


class DownloadProgressTests(unittest.TestCase):
    def test_plan_excludes_present_paths_and_uses_compressed_not_nar_size(self):
        a='/nix/store/'+'a'*32+'-one'; b='/nix/store/'+'b'*32+'-two'
        remote={a:{'downloadSize':123400000,'narSize':999999999,'url':'nar/one.nar.zst'},
                b:{'downloadSize':468500000,'narSize':999999999,'url':'nar/two.nar.zst'}}
        self.assertEqual(download_plan(CACHE,remote,{a:{},b:None}),{CACHE+'/nar/two.nar.zst':468500000})
        self.assertEqual(download_plan(CACHE,remote,remote),{})
        self.assertEqual(path_info([dict(remote[a],path=a)]),{a:dict(remote[a],path=a)})
        with self.assertRaises(ValueError): path_info({'/tmp/not-a-store-path':{}})
        with self.assertRaises(ValueError): download_plan(CACHE,{a:{'url':'nar/a','downloadSize':True}},{a:None})

    def test_live_bytes_parallel_retries_duplicates_and_metadata_exclusion(self):
        updates=[]; other=CACHE+'/nar/other.nar.zst'
        tracker=DownloadProgress(CACHE,{URL:200000000,other:268500000},lambda *v:updates.append(v))
        tracker.feed(event('start',type=101,fields=[URL]))
        tracker.feed(event('start',id=2,type=100,fields=['uncompressed-copy']))
        tracker.feed(event('result',id=2,type=105,fields=[999999999,999999999]))
        tracker.feed(event('start',id=3,type=101,fields=[CACHE+'/test.narinfo']))
        tracker.feed(event('result',id=3,type=105,fields=[999999,999999]))
        tracker.feed(event('result',type=105,fields=[123400000,200000000,0,0])); tracker.flush()
        self.assertEqual(progress_message(*updates[-1]),'Downloaded 123.4 of 468.5 MB')
        tracker.feed(event('stop'))
        tracker.feed(event('start',id=4,type=101,fields=[URL]))
        tracker.feed(event('result',id=4,type=105,fields=[100,200000000])); tracker.flush()
        self.assertEqual(updates[-1],(123400000,468500000))
        tracker.feed(event('result',id=4,type=105,fields=[200000000,200000000]))
        tracker.feed(event('start',id=5,type=101,fields=[other]))
        tracker.feed(event('result',id=5,type=105,fields=[268500001,268500000])); tracker.flush()
        self.assertEqual(updates[-1],(468500000,468500000))

    def test_unknown_totals_malformed_events_and_cached_zero(self):
        updates=[]; tracker=DownloadProgress(CACHE,None,lambda *v:updates.append(v))
        for line in ('plain diagnostic','@nix {bad','@nix null',event('start',type=101,fields=[]),
                     event('result',type=105,fields=[-1,10])):
            tracker.feed(line)
        tracker.feed(event('start',type=101,fields=[URL]))
        tracker.feed(event('result',type=105,fields=[123400000,0])); tracker.flush()
        self.assertEqual(progress_message(*updates[-1]),'Downloaded 123.4 MB')
        tracker=DownloadProgress(CACHE,{},lambda *v:updates.append(v))
        self.assertEqual(updates[-1],(0,0))

    def test_stream_is_consumed_before_exit_without_blocking_on_stdout(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root); finished=root/'finished'; updates=[]
            tracker=DownloadProgress(CACHE,{URL:3000000},lambda *v:updates.append((*v,finished.exists())))
            script='import sys,time,pathlib\n'
            script+='sys.stdout.write("x"*200000); sys.stdout.flush()\n'
            lines=[event('start',type=101,fields=[URL])]+[
                event('result',type=105,fields=[done,3000000]) for done in (1000000,2000000,3000000)]
            for line in lines: script+='sys.stderr.write('+repr(line)+'); sys.stderr.flush(); time.sleep(.25)\n'
            script+='pathlib.Path('+repr(str(finished))+').touch()\n'
            updater.Runtime(root).copy_with_progress([sys.executable,'-c',script],tracker,timeout=5)
            self.assertTrue(any(0<done<total and not ended for done,total,ended in updates))
            self.assertEqual(updates[-1][:2],(3000000,3000000))
            self.assertIn('x'*200000,(root/'helper.log').read_text())

    def test_failed_or_stalled_download_does_not_report_completion(self):
        with tempfile.TemporaryDirectory() as root:
            runtime=updater.Runtime(root); tracker=DownloadProgress(CACHE,{URL:100},lambda *v:None)
            with self.assertRaisesRegex(updater.UpdateError,'download failed'):
                runtime.copy_with_progress([sys.executable,'-c','raise SystemExit(1)'],tracker)
            with self.assertRaisesRegex(updater.UpdateError,'took too long'):
                runtime.copy_with_progress([sys.executable,'-c','import time; time.sleep(5)'],tracker,timeout=.1)

    def test_pending_byte_burst_is_published_while_nix_is_quiet_but_still_running(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root); finished=root/'finished'; updates=[]
            tracker=DownloadProgress(CACHE,{URL:3000000},lambda *v:updates.append((*v,finished.exists())))
            lines=event('start',type=101,fields=[URL])+event('result',type=105,fields=[3000000,3000000])
            script='import sys,time,pathlib; sys.stderr.write('+repr(lines)+'); sys.stderr.flush(); time.sleep(.8); pathlib.Path('+repr(str(finished))+').touch()'
            updater.Runtime(root).copy_with_progress([sys.executable,'-c',script],tracker,timeout=5)
            self.assertIn((3000000,3000000,False),updates,'Pending bytes were hidden until Nix exited')


if __name__=='__main__': unittest.main()
