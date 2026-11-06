"""Profile persistence, palette reuse and transactional rollback."""
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extras'))
from theme import theme, profiles


class Profiles(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.state = Path(temp.name)
        self.old = theme.STATE
        theme.STATE = self.state
        self.addCleanup(setattr,theme,'STATE',self.old)
        theme.publish({'colors':theme.FALLBACK.copy(),'generator':'test','wallpaper':'/test.png'})

    def test_profile_switch_reuses_palette_and_persists_without_generator(self):
        with patch.object(theme,'command',return_value='false'), patch.object(profiles,'apply_hypr'), patch.object(theme,'reload_components'), patch.object(theme,'generate',side_effect=AssertionError('regeneration')):
            profiles.switch('refined')
            self.assertEqual(theme.current_profile(),'refined')
            self.assertEqual(theme.read_palette()['wallpaper'],'/test.png')
            self.assertIn('150ms',(self.state/'current/profile.css').read_text())
            theme.cached()
            self.assertEqual(theme.current_profile(),'refined')
            profiles.switch('minimal')
            self.assertIn('0ms',(self.state/'current/profile.css').read_text())
            profiles.previous()
            self.assertEqual(theme.current_profile(),'refined')

    def test_partial_ipc_failure_restores_actual_keys_and_generation(self):
        generation = (self.state/'current').resolve()
        calls = []
        failed = False
        def command(args):
            nonlocal failed
            calls.append(args)
            if 'config-get' in args:
                return '"original"'
            if args[-2] == 'shell.font_family' and args[-1] == '"monospace"' and not failed:
                failed = True
                raise RuntimeError('simulated IPC failure')
            return ''
        with patch.object(theme,'command',side_effect=command), patch.object(profiles,'apply_hypr'), patch.object(theme,'reload_components'):
            with self.assertRaisesRegex(RuntimeError,'simulated IPC failure'):
                profiles.switch('refined')
        self.assertEqual(theme.current_profile(),'minimal')
        self.assertEqual((self.state/'current').resolve(),generation)
        self.assertTrue(any(args[-2:] == ['theme.source','"original"'] for args in calls))

    def test_cache_upgrade_keeps_existing_wallpaper_and_palette(self):
        # Simulate an old generation, before Phase 4 added these outputs.
        for name in ('profile.css','noctalia.json'):
            (self.state/'current'/name).unlink()
        theme.cached()
        self.assertEqual(theme.read_palette()['generator'],'test')
        self.assertEqual(theme.read_palette()['wallpaper'],'/test.png')
        self.assertTrue((self.state/'current/noctalia.json').is_file())

    def test_palette_restore_preserves_current_appearance(self):
        theme.publish({'colors':dict(theme.FALLBACK,accent='#ccbbaa'),'generator':'second'})
        (self.state/'profile').write_text('refined\n')
        theme.restore_previous(reload=False)
        self.assertEqual(theme.current_profile(),'refined')
        self.assertIn('150ms',(self.state/'current/profile.css').read_text())
        self.assertEqual(theme.read_palette()['wallpaper'],'/test.png')

    def test_unknown_profile_cannot_modify_state(self):
        with self.assertRaises(ValueError):
            profiles.switch('../../bad')
        self.assertFalse((self.state/'profile').exists())

if __name__ == '__main__':
    unittest.main()
