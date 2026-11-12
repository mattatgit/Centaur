"""Actual source-copy, inspection, adaptation and failure boundaries."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gtk4/embedding'))
import source_import as imports


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.original=self.root/'original'; self.original.mkdir()
        self.managed=self.root/'centaur/project/.centaur/import'

    def acquire(self):
        return imports.acquire(self.managed,{'type':'folder','location':str(self.original)})

    def test_folder_is_a_separate_copy_and_never_runs_project_code(self):
        marker=self.root/'executed'
        (self.original/'main.py').write_text(f'open({str(marker)!r},"w").write("BAD")')
        (self.original/'README.md').write_text('Original')
        result=self.acquire()
        self.assertEqual(result['framework'],'Python'); self.assertFalse(marker.exists())
        (self.managed/'source/README.md').write_text('Adaptation')
        self.assertEqual((self.original/'README.md').read_text(),'Original')

    def test_unsupported_source_is_preserved_and_identified(self):
        (self.original/'App.swift').write_text('import SwiftUI\nstruct App {}')
        result=self.acquire()
        self.assertEqual(result['framework'],'iOS / Swift')
        self.assertEqual(result['files']['App.swift'],'import SwiftUI\nstruct App {}')
        self.assertFalse(result['candidate'])

    def test_secrets_dependencies_and_external_symlinks_do_not_reach_agent(self):
        (self.original/'.env').write_text('secret')
        (self.original/'node_modules').mkdir(); (self.original/'node_modules/dependency.js').write_text('dependency')
        (self.original/'app.py').write_text('api_key="sk-1234567890Secret"')
        (self.original/'README.md').symlink_to('/etc/passwd')
        result=self.acquire()
        self.assertNotIn('.env',result['paths']); self.assertNotIn('node_modules/dependency.js',result['paths'])
        self.assertNotIn('README.md',result['paths']); self.assertIn('omitted',result['files']['app.py'])

    def test_inspection_cannot_escape_managed_source(self):
        (self.original/'main.py').write_text('pass'); self.acquire()
        for name in ('../state.json','/etc/passwd','foo/../../secret','a\\b','a//b'):
            with self.subTest(name=name),self.assertRaises(imports.ImportError): imports.read_files(self.managed,[name])
        (self.managed/'source/escape').symlink_to('/etc/passwd')
        self.assertEqual(imports.read_files(self.managed,['escape'])['escape'],'[File unavailable]')

    def test_inspection_is_bounded_and_binary_safe(self):
        (self.original/'large.py').write_text('x'*48000)
        (self.original/'binary').write_bytes(b'\x00\xff'); self.acquire()
        files=imports.read_files(self.managed,['large.py','binary'])
        self.assertLess(len(files['large.py']),24100); self.assertIn('Truncated',files['large.py'])
        self.assertEqual(files['binary'],'[Binary file]')
        with self.assertRaises(imports.ImportError): imports.read_files(self.managed,['large.py']*13)

    def test_failed_copy_can_retry_without_partial_source(self):
        (self.original/'main.py').write_text('pass')
        with patch.object(imports,'MAX_BYTES',1),self.assertRaises(imports.ImportError): self.acquire()
        self.assertFalse((self.managed/'source').exists())
        self.assertEqual(list(self.managed.glob('acquire-*')),[])
        self.assertEqual(self.acquire()['fileCount'],1)

    def test_source_unavailable_and_recursive_data_selection_rejected(self):
        with self.assertRaises(imports.ImportError): imports.acquire(self.managed,{'type':'folder','location':str(self.root/'missing')})
        with self.assertRaises(imports.ImportError): imports.acquire(self.original/'centaur/import',{'type':'folder','location':str(self.original)})

    def test_github_urls_never_accept_tokens_or_executable_protocols(self):
        self.assertEqual(imports.github_url('https://github.com/mattatgit/landline'),'https://github.com/mattatgit/landline.git')
        self.assertEqual(imports.github_url('https://github.com/mattatgit/landline.git/'),'https://github.com/mattatgit/landline.git')
        for value in ('https://token@github.com/a/b','ext::evil','file:///tmp/a','https://github.com/a/b/tree/main','https://github.com/a/b?token=secret','https://example.com/a/b'):
            with self.subTest(value=value),self.assertRaises(imports.ImportError): imports.github_url(value)

    def test_repository_export_rules_cannot_omit_or_rewrite_source(self):
        subprocess.run(['git','init','-q',str(self.original)],check=True)
        (self.original/'.gitattributes').write_text('hidden.swift export-ignore\nversion.txt export-subst\n')
        (self.original/'hidden.swift').write_text('Original source')
        (self.original/'version.txt').write_text('$Format:%H$')
        subprocess.run(['git','-C',str(self.original),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.original),'-c','user.name=Test','-c','user.email=test@example.test','commit','-qm','Source'],check=True)
        # Exercise the actual bare-clone/archive path against a local Git
        # fixture; only URL validation/network transport are substituted.
        with patch.object(imports,'github_url',return_value=str(self.original)):
            imports.acquire(self.managed,{'type':'github','location':'https://github.com/test/source'})
        self.assertEqual((self.managed/'source/hidden.swift').read_text(),'Original source')
        self.assertEqual((self.managed/'source/version.txt').read_text(),'$Format:%H$')

    def test_git_history_and_uncommitted_edits_preserved_without_source_configuration(self):
        subprocess.run(['git','init','-q',str(self.original)],check=True)
        (self.original/'README.md').write_text('committed')
        subprocess.run(['git','-C',str(self.original),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.original),'-c','user.name=Test','-c','user.email=test@example.test','commit','-qm','Original'],check=True)
        (self.original/'README.md').write_text('working tree')
        self.acquire()
        self.assertEqual((self.managed/'source/README.md').read_text(),'working tree')
        history=self.managed/'history.git'
        self.assertEqual(subprocess.check_output(['git','--git-dir='+str(history),'show','HEAD:README.md'],text=True),'committed')
        self.assertNotIn('remote "origin"',(history/'config').read_text())
        self.assertFalse((self.managed/'source/.git').exists())

    def test_direct_bundle_is_syntax_checked_without_execution(self):
        bundle=json.loads((Path(__file__).resolve().parents[1]/'templates/App.gtk.json').read_text())
        bundle['files']['app.py']='raise RuntimeError("MUST NOT EXECUTE")\n'+bundle['files']['app.py']
        (self.original/'App.gtk.json').write_text(json.dumps(bundle))
        self.assertTrue(self.acquire()['candidate'])
        self.assertTrue((self.managed/'candidate.gtk.json').exists())

    def test_malformed_bundle_still_imports_as_preserved_source(self):
        (self.original/'App.gtk.json').write_text('["not a bundle"]')
        self.assertFalse(self.acquire()['candidate'])
        self.assertEqual((self.managed/'source/App.gtk.json').read_text(),'["not a bundle"]')

    def test_source_executable_modes_preserved_without_granting_other_users_access(self):
        script=self.original/'run.sh'; script.write_text('#!/bin/sh\nexit 0\n'); script.chmod(0o755)
        self.acquire()
        self.assertEqual((self.managed/'source/run.sh').stat().st_mode&0o777,0o700)
        self.assertEqual(self.managed.stat().st_mode&0o777,0o700)

    def test_adaptation_writes_only_new_separate_output_versions(self):
        (self.original/'App.swift').write_text('Original iOS app'); self.acquire()
        request={'target':'css-js','files':{'index.html':'<h1>Staging</h1>','css/main.css':'body {}'}}
        first=imports.stage(self.managed,request); second=imports.stage(self.managed,request)
        self.assertNotEqual(first['output'],second['output'])
        self.assertEqual((self.managed/first['output']/'index.html').read_text(),'<h1>Staging</h1>')
        self.assertEqual((self.managed/'source/App.swift').read_text(),'Original iOS app')
        for name in ('../../source/App.swift','/tmp/escape','.env'):
            with self.subTest(name=name),self.assertRaises(imports.ImportError): imports.stage(self.managed,{'files':{name:'BAD'}})

    def test_cli_failure_is_conversational_without_local_paths_or_diagnostics(self):
        response=subprocess.run([sys.executable,str(Path(imports.__file__))],input=json.dumps({'root':str(self.managed),'mode':'acquire','source':{'type':'folder','location':'/missing'}}),text=True,capture_output=True)
        self.assertEqual(response.returncode,1); reply=json.loads(response.stdout)
        self.assertFalse(reply['ok']); self.assertNotIn('Traceback',response.stdout); self.assertNotIn('/missing',response.stdout)


if __name__=='__main__': unittest.main()
