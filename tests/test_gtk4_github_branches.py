"""Real Git refs/clones; network transport alone is substituted with a fixture."""
import sys
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gtk4/embedding'))
import source_import as imports


class GitHubBranchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.repo=self.root/'repo'; self.repo.mkdir()
        self.repo_git('init','-qb','main'); self.repo_git('config','user.name','Test'); self.repo_git('config','user.email','test@example.test')
        (self.repo/'app.swift').write_text('macOS SOURCE'); self.repo_git('add','.'); self.repo_git('commit','-qm','macOS app')
        self.repo_git('checkout','-qb','linux-nix'); self.repo_git('rm','app.swift')
        (self.repo/'flake.nix').write_text('LINUX NIX SOURCE'); self.repo_git('add','.'); self.repo_git('commit','-qm','Linux app')
        self.repo_git('checkout','-qb','feature/new-ui'); (self.repo/'src').mkdir(); (self.repo/'src/ui.py').write_text('LINUX UI')
        self.repo_git('add','.'); self.repo_git('commit','-qm','Nested UI')
        self.repo_git('checkout','-q','main')
        self.addCleanup(patch.stopall); patch.object(imports,'github_url',return_value=str(self.repo)).start()
        self.url='https://github.com/example/app'

    def repo_git(self,*args):
        return subprocess.check_output(['git','-C',str(self.repo),*args],text=True).strip()

    def test_default_is_resolved_from_remote_head(self):
        info=imports.branches(self.url)
        self.assertEqual(info['branch'],'main'); self.assertEqual(info['defaultBranch'],'main')
        self.assertEqual(info['commit'],self.repo_git('rev-parse','main'))

    def test_branch_url_preselects_linux_and_acquires_only_its_verified_source(self):
        value=self.url+'/tree/linux-nix'; info=imports.branches(value)
        self.assertEqual(info['branch'],'linux-nix')
        root=self.root/'copy'; result=imports.acquire(root,{'type':'github','location':value})
        self.assertEqual(result['branch'],'linux-nix'); self.assertEqual(result['commit'],self.repo_git('rev-parse','linux-nix'))
        self.assertEqual((root/'source/flake.nix').read_text(),'LINUX NIX SOURCE'); self.assertFalse((root/'source/app.swift').exists())
        self.assertEqual((self.repo/'app.swift').read_text(),'macOS SOURCE')

    def test_slash_ref_uses_longest_actual_branch_not_first_segment(self):
        info=imports.branches(self.url+'/tree/feature/new-ui/src')
        self.assertEqual(info['branch'],'feature/new-ui'); self.assertEqual(info['directory'],'src')
        result=imports.acquire(self.root/'nested',{'type':'github','location':self.url+'/tree/feature/new-ui/src'})
        self.assertEqual(result['directory'],'src'); self.assertEqual((self.root/'nested/source/src/ui.py').read_text(),'LINUX UI')

    def test_manual_branch_selection_overrides_url_and_preserves_previous_copy(self):
        first=self.root/'first'; second=self.root/'second'
        imports.acquire(first,{'type':'github','location':self.url})
        (first/'source/app.swift').write_text('USER CHANGES')
        result=imports.acquire(second,{'type':'github','location':self.url,'branch':'linux-nix'})
        self.assertEqual(result['branch'],'linux-nix'); self.assertEqual((first/'source/app.swift').read_text(),'USER CHANGES')

    def test_missing_deleted_and_inaccessible_branches_never_fall_back(self):
        for value,branch in [(self.url+'/tree/missing',None),(self.url,'missing')]:
            with self.subTest(value=value),self.assertRaises(imports.ImportError): imports.branches(value,branch)
        info=imports.branches(self.url+'/tree/missing',allow_missing=True)
        self.assertIsNone(info['branch']); self.assertIn('main',info['branches']); self.assertTrue(info['selectionError'])
        self.assertEqual(imports.branches(self.url+'/tree/missing','linux-nix')['branch'],'linux-nix')
        self.repo_git('branch','-D','linux-nix')
        with self.assertRaises(imports.ImportError): imports.acquire(self.root/'deleted',{'type':'github','location':self.url,'branch':'linux-nix'})
        self.assertFalse((self.root/'deleted/source').exists())
        with patch.object(imports,'git',side_effect=imports.ImportError('Access unavailable')),self.assertRaises(imports.ImportError): imports.branches(self.url)

    def test_changed_remote_commit_is_detected_before_source_is_published(self):
        original=imports.git
        def moved(args,**kwargs):
            if args[0]=='clone':
                self.repo_git('checkout','-q','linux-nix'); (self.repo/'new.txt').write_text('new'); self.repo_git('add','.'); self.repo_git('commit','-qm','Moved ref')
            return original(args,**kwargs)
        with patch.object(imports,'git',side_effect=moved),self.assertRaisesRegex(imports.ImportError,'changed'):
            imports.acquire(self.root/'moved',{'type':'github','location':self.url,'branch':'linux-nix'})
        self.assertFalse((self.root/'moved/source').exists())

    def test_missing_directory_does_not_become_a_different_branch(self):
        with self.assertRaises(imports.ImportError): imports.acquire(self.root/'bad-dir',{'type':'github','location':self.url+'/tree/feature/new-ui/missing'})
        self.assertFalse((self.root/'bad-dir/source').exists())

    def test_url_parser_rejects_credentials_traversal_and_wrong_hosts(self):
        for value in ('https://token@github.com/a/b/tree/main','https://github.com/a/b/tree/../secret','https://github.com/a/b/tree/a%2F..%2Fb','https://elsewhere.test/a/b'):
            with self.subTest(value=value),self.assertRaises(imports.ImportError): imports.github_source(value)
        self.assertEqual(imports.github_source(self.url+'/tree/feature%2Fnew-ui')['tree'],'feature/new-ui')


if __name__=='__main__': unittest.main()
