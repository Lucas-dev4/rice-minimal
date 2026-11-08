"""Visual safety, auth preservation, read-only diagnostics and single-session routing."""
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import tomllib
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extras'))
import lockscreen
import rice
import doctor
from theme import theme


class Final(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state=Path(self.temp.name)
        self.old=theme.STATE
        theme.STATE=self.state
        self.addCleanup(setattr,theme,'STATE',self.old)

    def test_lock_renderer_contains_only_visual_settings_and_native_login(self):
        rendered=lockscreen.render({'wallpaper':'/tmp/quoted " file.png'},'refined')
        data=tomllib.loads(rendered)
        self.assertEqual(set(data['lockscreen']),lockscreen.VISUAL_KEYS)
        self.assertEqual(data['lockscreen']['blur_intensity'],0)
        self.assertEqual([w['type'] for w in data['lockscreen_widgets']['widget'].values()],['login_box'])
        self.assertNotIn('font_family',rendered)
        self.assertTrue(any(w['type']=='login_box' for w in data['lockscreen_widgets']['widget'].values()))
        self.assertEqual(data['lockscreen']['wallpaper'],'/tmp/quoted " file.png')

    def test_auth_overrides_survive_visual_override_filter(self):
        original='''[lockscreen]
allow_empty_password = false
fingerprint = true
grace_period_seconds = 0
lock_before_suspend = true
blur_intensity = 0.7
[lockscreen_widgets]
enabled = false
[lockscreen_widgets.widget.test]
type = "label"
[shell]
polkit_agent = true
'''
        filtered=tomllib.loads(lockscreen.strip_visual_overrides(original))
        self.assertFalse(filtered['lockscreen']['allow_empty_password'])
        self.assertEqual(filtered['lockscreen']['grace_period_seconds'],0)
        self.assertTrue(filtered['lockscreen']['lock_before_suspend'])
        self.assertTrue(filtered['shell']['polkit_agent'])
        self.assertNotIn('lockscreen_widgets',filtered)

    def test_visual_snapshot_excludes_authentication_and_other_settings(self):
        snapshot=lockscreen.visual_snapshot('[lockscreen]\nfingerprint = false\ntint_intensity = 0.7\n[shell]\nfont_family = "old"\n[lockscreen_widgets]\nenabled = true\n')
        data=tomllib.loads(snapshot)
        self.assertEqual(data['lockscreen'],{'tint_intensity':.7})
        self.assertNotIn('shell',data)
        self.assertTrue(data['lockscreen_widgets']['enabled'])

    def test_lock_restore_preserves_later_profile_and_auth_choices(self):
        settings=self.state/'settings.toml'
        settings.write_text('[lockscreen]\nfingerprint = true\ntint_intensity = 0.8\n[shell.animation]\nenabled = false\n')
        config=self.state/'config';config.mkdir()
        backup=self.state/'backup';backup.mkdir()
        (backup/'settings.toml').write_text('[lockscreen]\nfingerprint = false\ntint_intensity = 0.3\n[shell.animation]\nenabled = true\n')
        (config/'rice-lock.toml').write_text('candidate')
        (self.state/'lock-enabled').write_text('enabled')
        with patch.object(lockscreen,'SETTINGS',settings),patch.object(lockscreen,'CONFIG',config),patch.object(theme,'command'),patch.object(theme,'reload_components'):
            lockscreen.restore(backup)
        data=tomllib.loads(settings.read_text())
        self.assertTrue(data['lockscreen']['fingerprint'])
        self.assertFalse(data['shell']['animation']['enabled'])
        self.assertEqual(data['lockscreen']['tint_intensity'],.3)
        self.assertFalse((config/'rice-lock.toml').exists())
        self.assertFalse((self.state/'lock-enabled').exists())

    def test_profile_changes_do_not_turn_on_lock_automatically(self):
        result=theme.render({'colors':theme.FALLBACK.copy(),'generator':'test'})
        self.assertIn('lockscreen.toml',result)
        self.assertFalse((self.state/'lock-enabled').exists())
        self.assertIn('rice_active_bg transparent',result['colors.css'])
        self.assertIn('rice_active_border transparent',result['colors.css'])

    def test_main_routes_super_in_same_screen_without_wrapper(self):
        screen=object()
        with patch.object(rice.ui,'setup'), patch.object(rice.ui,'choose',side_effect=[1,None]), patch.object(rice.shortcuts,'selector') as selector, patch.object(rice.curses,'wrapper') as wrapper:
            rice.menu(screen)
        selector.assert_called_once_with(screen)
        wrapper.assert_not_called()

    def test_cli_requires_confirmation_before_lock(self):
        with patch.object(sys,'argv',['rice','lock-trial']), patch.object(lockscreen,'trial') as trial:
            with self.assertRaises(SystemExit): rice.main()
        trial.assert_not_called()

    def test_standalone_theme_entrypoints_resolve_shared_package(self):
        for path,args in [('extras/theme/profiles.py',['current']),('extras/theme/theme.py',['show'])]:
            result=subprocess.run([sys.executable,str(theme.ROOT/path),*args],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_doctor_never_repairs_or_generates(self):
        calls=[]
        def run(args,**kwargs):
            calls.append([str(v) for v in args])
            return type('P',(),{'returncode':0,'stdout':'','stderr':''})()
        with patch.object(doctor.subprocess,'run',side_effect=run),patch.object(lockscreen,'validate',return_value='candidate valid'):
            doctor.inspect()
        joined=' '.join(' '.join(c) for c in calls)
        for forbidden in ('config-set','config-reload','regenerate','session lock','wallpaper-set'):
            self.assertNotIn(forbidden,joined)

    def test_doctor_stream_reports_every_result_in_order(self):
        def run(args,**kwargs):
            return type('P',(),{'returncode':0,'stdout':'','stderr':''})()
        seen=[]
        with patch.object(doctor.subprocess,'run',side_effect=run),patch.object(lockscreen,'validate',return_value='candidate valid'):
            results=doctor.inspect(seen.append)
        self.assertEqual(seen,results)
        self.assertGreater(len(results),20)

if __name__ == '__main__': unittest.main()
