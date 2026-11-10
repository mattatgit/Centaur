"""GTK desktop integration stays per-user, follows updates and preserves launch configuration."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]/'gtk4/embedding'; sys.path.insert(0,str(BASE))
spec=importlib.util.spec_from_file_location('gtk_desktop',BASE/'desktop.py')
desktop=importlib.util.module_from_spec(spec); spec.loader.exec_module(desktop)


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name).resolve(); self.profile=self.home/'profile'
        self.package=self.home/'package'; (self.package/'bin').mkdir(parents=True)
        (self.package/'bin/centaur-gtk4').touch()
        for path in ('applications/org.centaur.Gtk4.desktop','icons/hicolor/index.theme',
                     'icons/hicolor/scalable/apps/org.centaur.Gtk4.svg'):
            target=self.package/'share'/path; target.parent.mkdir(parents=True,exist_ok=True); target.write_text('fixture')
        self.profile.symlink_to(self.package)
        self.env={'XDG_DATA_HOME':str(self.home/'data'),'XDG_CONFIG_HOME':str(self.home/'config'),
                  'GSK_RENDERER':'cairo','CENTAUR_AGENT':'/home/matt/.local/bin/omp','SECRET_TOKEN':'never store this'}
        self.addCleanup(patch.stopall)
        patch.object(desktop,'profile_path',return_value=self.profile).start()
        patch.dict(os.environ,self.env).start()

    def test_register_follows_profile_and_restores_custom_data_renderer_and_agent(self):
        data=self.home/'custom project data'
        self.assertTrue(desktop.register(self.package,data))
        entry=self.home/'data/applications/org.centaur.Gtk4.desktop'
        self.assertEqual(os.readlink(entry),str(self.profile/'share/applications/org.centaur.Gtk4.desktop'))
        config=desktop.settings_path().read_text(); self.assertNotIn('SECRET_TOKEN',config)
        with patch.dict(os.environ,{},clear=True):
            os.environ['XDG_CONFIG_HOME']=self.env['XDG_CONFIG_HOME']
            self.assertEqual(desktop.launch_settings(),data)
            self.assertEqual(os.environ['GSK_RENDERER'],'cairo')
            self.assertEqual(os.environ['CENTAUR_AGENT'],'/home/matt/.local/bin/omp')
        newer=self.home/'new-package'; self.package.rename(newer)
        self.profile.unlink(); self.profile.symlink_to(newer)
        self.assertEqual(entry.resolve(),newer/'share/applications/org.centaur.Gtk4.desktop')

    def test_development_run_does_not_register_or_modify_custom_entries(self):
        self.assertFalse(desktop.register(self.home/'other-package',self.home/'data'))
        self.assertFalse(desktop.settings_path().exists())
        entry=self.home/'data/applications/org.centaur.Gtk4.desktop'; entry.parent.mkdir(parents=True); entry.write_text('custom launcher')
        desktop.register(self.package,self.home/'app-data')
        self.assertEqual(entry.read_text(),'custom launcher')

    def test_broken_settings_fall_back_without_importing_unrelated_environment(self):
        desktop.settings_path().parent.mkdir(parents=True)
        desktop.settings_path().write_text('{"dataDir":"relative","environment":{"PATH":"bad","GSK_RENDERER":"cairo"}}')
        previous=os.environ.get('PATH')
        self.assertIsNone(desktop.launch_settings()); self.assertEqual(os.environ.get('PATH'),previous)
        desktop.settings_path().write_text('[]'); self.assertIsNone(desktop.launch_settings())


if __name__=='__main__': unittest.main()
