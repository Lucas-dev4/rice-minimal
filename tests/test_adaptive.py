"""Failure, cache, rollback, file-name safety and contrast tests."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'extras'))
from theme import theme
from wallpapers.wallpaper_tui import filtered

class Adaptive(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)
        self.old = theme.STATE
        theme.STATE = self.state
        self.addCleanup(setattr, theme, 'STATE', self.old)

    def publish(self, accent):
        colors = dict(theme.FALLBACK, accent=accent)
        return theme.publish({'colors':colors,'generator':'test'})

    def test_failed_generation_keeps_last_and_empty_state_has_emergency(self):
        with patch.object(theme,'generate', side_effect=RuntimeError('generator unavailable')):
            with patch.object(theme,'bar_contrast', return_value={}):
                theme.regenerate(Path('/missing'), force=True, reload=False)
            self.assertEqual(theme.read_palette()['generator'],'static-emergency')
            before = (self.state/'current').resolve()
            theme.regenerate(Path('/missing'), force=True, reload=False)
            self.assertEqual((self.state/'current').resolve(),before)
            self.assertEqual(json.loads((self.state/'status.json').read_text())['result'],'kept-last-palette')

    def test_invalid_palette_does_not_replace_working_generation(self):
        self.publish('#abcdef')
        before = (self.state/'current').resolve()
        with self.assertRaises(ValueError):
            self.publish('#abcd\"; os.execute("bad")')
        self.assertEqual((self.state/'current').resolve(),before)

    def test_restore_previous_and_reload_failure_rollback(self):
        self.publish('#abcabc')
        first = (self.state/'current').resolve()
        self.publish('#bcabca')
        second = (self.state/'current').resolve()
        theme.restore_previous(reload=False)
        self.assertEqual((self.state/'current').resolve(),first)
        self.assertEqual((self.state/'previous').resolve(),second)
        with patch.object(theme,'reload_components',side_effect=RuntimeError('reload failed')):
            with self.assertRaises(RuntimeError):
                theme.restore_previous()
        self.assertEqual((self.state/'current').resolve(),first)

    def test_cached_startup_never_generates_and_duplicate_event_reuses_cache(self):
        image = self.state/'wallpaper with spaces.png'
        image.write_bytes(b'fingerprint only')
        palette = {'colors':theme.FALLBACK.copy(),'generator':'test','fingerprint':theme.fingerprint(image)}
        theme.publish(palette)
        before = (self.state/'current').resolve()
        with patch.object(theme,'generate',side_effect=AssertionError('must not generate')):
            theme.cached()
            self.assertEqual(theme.regenerate(image,reload=False),'cached')
        self.assertEqual((self.state/'current').resolve(),before)

    def test_special_file_names_are_arguments_and_share_waypaper_state(self):
        chosen = Path('/tmp/space \' ; $monitor $(touch DO-NOT-CREATE).png')
        with patch.object(theme,'command') as command, patch.object(theme,'wallpaper_hook',return_value='ok') as hook:
            self.assertEqual(theme.apply_choice(chosen),'ok')
            command.assert_called_once_with(['waypaper','--wallpaper',chosen,'--no-post-command'])
            hook.assert_called_once_with(chosen)
        self.assertEqual(filtered([chosen], 'SPACE'),[chosen])

    def test_bar_text_flips_for_light_and_dark_background(self):
        from PIL import Image
        for background, expect_light in (('white',False),('black',True)):
            image = self.state/(background+'.png')
            Image.new('RGB',(300,180),background).save(image)
            colors = theme.FALLBACK.copy()
            metadata = theme.bar_contrast(image,colors)
            self.assertEqual(theme.luminance(colors['bar_foreground'])>.5,expect_light)
            self.assertGreaterEqual(metadata['text_contrast_p10'], 7)

    def test_lock_excludes_other_processes(self):
        with theme.locked():
            code = 'import fcntl,sys; f=open(sys.argv[1],"a"); fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)'
            p = subprocess.run([sys.executable,'-c',code,str(self.state/'generation.lock')],capture_output=True)
            self.assertNotEqual(p.returncode,0)
            self.assertIn(b'BlockingIOError',p.stderr)

    def test_mixed_wallpaper_uses_different_text_on_each_side(self):
        from PIL import Image
        image = self.state/'mixed.png'
        canvas = Image.new('RGB',(1920,1080),'white')
        canvas.paste('black',(960,0,1920,1080))
        canvas.save(image)
        colors = theme.FALLBACK.copy()
        metadata = theme.bar_contrast(image,colors)
        self.assertLess(theme.luminance(colors['bar_workspace']),.3)
        self.assertGreater(theme.luminance(colors['bar_cpu']),.5)
        self.assertGreaterEqual(metadata['modules_p10']['cpu'],4.5)

    def test_corrupt_cache_starts_with_static_emergency_without_matugen(self):
        self.publish('#abcdef')
        (self.state/'current/palette.json').write_text('{broken')
        with patch.object(theme,'generate',side_effect=AssertionError('must not generate')):
            theme.cached()
        self.assertEqual(theme.read_palette()['generator'],'static-emergency')

if __name__ == '__main__':
    unittest.main()
