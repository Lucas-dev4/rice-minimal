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

    def run_hook(self, result, sync_error=None):
        (self.state/'greeter-sync').touch()
        calls = []
        def command(args, **kwargs):
            calls.append(args)
            if sync_error:
                raise sync_error
        with patch.object(theme,'time') as clock, patch.object(theme,'selected_wallpaper',return_value=Path('/tmp/a.png')), \
             patch.object(theme,'set_wallpaper'), patch.object(theme,'regenerate',return_value=result), \
             patch.object(theme,'command',side_effect=command):
            clock.time_ns.return_value = 0
            clock.sleep.side_effect = lambda seconds: calls.append('settle') if seconds == theme.GREETER_SETTLE else None
            return theme.wallpaper_hook(), calls

    def test_new_palette_syncs_greeter_and_cached_event_does_not(self):
        sync = ['noctalia','msg','greeter-sync']
        self.assertEqual(self.run_hook('matugen'),('matugen',['settle',sync]))
        self.assertEqual(self.run_hook('cached'),('cached',[]))

    def test_greeter_sync_failure_keeps_wallpaper_change(self):
        for error in (subprocess.CalledProcessError(1,'noctalia'),subprocess.TimeoutExpired('noctalia',30),FileNotFoundError('noctalia')):
            self.assertEqual(self.run_hook('matugen',error)[0],'matugen')

    def test_removed_flag_stops_automatic_sync_but_not_a_manual_one(self):
        with patch.object(theme,'command') as command, patch.object(theme.time,'sleep'):
            self.assertEqual(theme.sync_greeter(),'disabled')
            command.assert_not_called()
            self.assertEqual(theme.sync_greeter(force=True),'sent')
            command.assert_called_once_with(['noctalia','msg','greeter-sync'])

    def sync_all(self, regenerate='matugen', greeter='sent'):
        image = self.state/'a.png'
        image.touch()
        import lockscreen
        with patch.object(theme,'selected_wallpaper',return_value=image), patch.object(theme,'current_wallpaper',return_value=image), \
             patch.object(theme,'regenerate',return_value=regenerate), patch.object(theme,'reload_components') as reload, \
             patch.object(lockscreen,'validate'), patch.object(theme,'sync_greeter',return_value=greeter) as sync, \
             patch.object(theme,'set_wallpaper') as wallpaper:
            return theme.sync_all(), reload, sync, wallpaper

    def test_sync_all_runs_every_step_in_order_under_one_lock(self):
        steps, reload, sync, wallpaper = self.sync_all()
        self.assertEqual([s['step'] for s in steps],['wallpaper','palette','lock','greeter'])
        self.assertTrue(all(s['status'] == 'OK' for s in steps))
        reload.assert_not_called()
        wallpaper.assert_not_called()
        sync.assert_called_once_with(force=True)

    def test_sync_all_refreshes_components_when_palette_was_cached(self):
        self.assertEqual(self.sync_all('cached')[1].call_count,1)

    def test_sync_all_reports_failed_greeter_as_warning(self):
        self.assertEqual(self.sync_all(greeter='failed')[0][-1]['status'],'WARN')

    def test_busy_lock_times_out_and_is_logged(self):
        with theme.locked():
            with self.assertRaises(TimeoutError):
                with theme.locked(timeout=.2):
                    self.fail('lock must stay exclusive')
        with patch.object(theme,'locked',side_effect=TimeoutError('busy')):
            with self.assertRaises(TimeoutError):
                theme.sync_all()
        self.assertEqual(json.loads((self.state/'actions.jsonl').read_text().splitlines()[-1])['status'],'FAIL')

    def test_log_is_trimmed(self):
        with patch.object(theme,'LOG_LIMIT',200):
            for index in range(600):
                theme.log_action('step','OK',index)
        lines = (self.state/'actions.jsonl').read_text().splitlines()
        self.assertLessEqual(len(lines),501)
        self.assertEqual(json.loads(lines[-1])['detail'],'599')

    def stage_greeter(self, primary):
        stage = self.state/'stage'
        stage.mkdir()
        (stage/'sync.toml').write_text(f"""[appearance.palette]
primary = "{primary}"
surface = "#000000"
on_surface = "#ffffff"
outline = "#888888"
""")
        (stage/'wallpaper.png').write_bytes(b'image')
        generation = self.state/'palette-z'
        generation.mkdir(exist_ok=True)
        (generation/'noctalia.json').write_text(json.dumps({'dark':{'mPrimary':'#ABCDEF','mSurface':'#000000','mOnSurface':'#FFFFFF','mOutline':'#888888'}}))
        (self.state/'current').unlink(missing_ok=True)
        (self.state/'current').symlink_to('palette-z')
        wallpaper = self.state/'w.png'
        wallpaper.write_bytes(b'image')
        return stage, wallpaper

    def test_greeter_status_compares_what_was_really_sent(self):
        for primary, expected in (('#abcdef',True),('#123456',False)):
            with self.subTest(primary):
                stage, wallpaper = self.stage_greeter(primary)
                with patch.object(theme,'GREETER_STAGE',stage), patch.object(theme,'current_wallpaper',return_value=wallpaper):
                    status = theme.greeter_status()
                self.assertEqual((status['colors_match'],status['image_match']),(expected,True))
                import shutil
                shutil.rmtree(stage)

    def test_greeter_status_without_sync_since_boot(self):
        with patch.object(theme,'GREETER_STAGE',self.state/'missing'):
            self.assertFalse(theme.greeter_status()['staged'])

    def test_vivid_terminal_text_stays_readable_over_a_white_wallpaper(self):
        background = theme.mix(theme.FALLBACK['background'],'#ffffff',.15)  # Kitty opacity 0.85
        for hue in range(0,360,15):
            color = theme.hexcolor(theme.colorsys.hls_to_rgb(hue/360,.75,.15))
            self.assertGreaterEqual(theme.ratio(theme.vivid(color),background),4.5,color)

    def test_vivid_keeps_hue_and_leaves_pure_gray_alone(self):
        before = theme.colorsys.rgb_to_hls(*theme.rgb('#bcc8d3'))
        after = theme.colorsys.rgb_to_hls(*theme.rgb(theme.vivid('#bcc8d3')))
        self.assertAlmostEqual(before[0],after[0],delta=.01)
        self.assertGreater(after[2],.6)
        self.assertEqual(theme.vivid('#808080'),'#808080')

    def test_image_hue_follows_the_area_not_a_small_bright_spot(self):
        from PIL import Image
        image = self.state/'blue.png'
        picture = Image.new('RGB',(200,100),(30,70,200))
        picture.paste((230,120,60),(0,0,30,30))
        picture.save(image)
        result = theme.image_hue(image)
        self.assertLess(abs(result['hue']-225),15)
        self.assertGreater(result['colorful'],.9)

    def test_gray_image_is_reported_as_colorless(self):
        from PIL import Image
        image = self.state/'gray.png'
        Image.new('RGB',(50,50),(128,128,128)).save(image)
        self.assertEqual(theme.image_hue(image)['colorful'],0)

    def hue_of(self, color):
        return theme.colorsys.rgb_to_hls(*theme.rgb(color))[0]*360

    def test_commands_never_share_the_error_hue(self):
        for hue in range(0,360,5):
            result = self.hue_of(theme.terminal_accent({'colors':theme.FALLBACK,'terminal':{'hue':hue,'colorful':.5}}))
            self.assertFalse(result >= 345 or result < 24,hue)

    def test_gray_image_gets_a_softer_accent(self):
        palette = {'colors':theme.FALLBACK,'terminal':{'hue':210,'colorful':.5}}
        gray = {'colors':theme.FALLBACK,'terminal':{'hue':210,'colorful':.01}}
        saturation = lambda color: theme.colorsys.rgb_to_hls(*theme.rgb(color))[2]
        self.assertLess(saturation(theme.terminal_accent(gray)),saturation(theme.terminal_accent(palette)))

    def test_old_palette_without_image_data_still_renders(self):
        self.assertTrue(theme.terminal_accent({'colors':theme.FALLBACK}).startswith('#'))

    def test_error_color_stays_readable(self):
        self.assertGreaterEqual(theme.ratio(theme.vivid('#ff4040',.95,.68),theme.TERMINAL_WORST_BACKGROUND),4.5)

    def test_workspace_halo_appears_only_when_contrast_is_low(self):
        colors = dict(theme.FALLBACK, **{key:'#ffffff' for key in ('bar_clock','bar_volume','bar_memory','bar_cpu','bar_workspace','bar_window')})
        low = theme.render({'colors':colors,'generator':'test','contrast':{'modules_p10':{'workspace':3.7}}})['colors.css']
        high = theme.render({'colors':colors,'generator':'test','contrast':{'modules_p10':{'workspace':8}}})['colors.css']
        old = theme.render({'colors':colors,'generator':'test'})['colors.css']
        self.assertIn('rice_workspace_halo #000000',low)
        self.assertIn('rice_workspace_halo transparent',high)
        self.assertIn('rice_workspace_halo transparent',old)

    def test_bar_modules_keep_their_hue_on_dark_and_turn_readable_on_white(self):
        from PIL import Image
        tints = {'cpu':'#86ea93','memory':'#eadc86','volume':'#86dbea','clock':'#ea86a7','workspace':'#ea86a7'}
        hue = lambda color: theme.colorsys.rgb_to_hls(*theme.rgb(color))[0]
        for background in ('#000000','#ffffff'):
            image = self.state/'bar.png'
            Image.new('RGB',(400,225),background).save(image)
            colors = theme.FALLBACK.copy()
            with patch.object(theme,'command',side_effect=OSError):
                metrics = theme.bar_contrast(image,colors,(1920,1080),tints)['modules_p10']
            for name in ('cpu','memory','volume','clock'):
                self.assertGreaterEqual(metrics[name],4.5,(background,name))
            if background == '#000000':
                self.assertEqual(colors['bar_cpu'],tints['cpu'])
                self.assertNotEqual(colors['bar_cpu'],colors['bar_memory'])
            else:
                self.assertAlmostEqual(hue(colors['bar_cpu']),hue(tints['cpu']),delta=.05)

    def test_republishing_the_same_colors_keeps_the_real_previous_palette(self):
        self.publish('#111111')
        older = (self.state/'current').resolve()
        self.publish('#222222')
        self.assertEqual((self.state/'previous').resolve(),older)
        self.publish('#222222')
        self.assertEqual((self.state/'previous').resolve(),older)
        self.publish('#333333')
        self.assertNotEqual((self.state/'previous').resolve(),older)

    def test_only_the_terminal_gets_vivid_colors(self):
        colors = dict(theme.FALLBACK, **{key:'#777777' for key in ('bar_clock','bar_volume','bar_memory','bar_cpu','bar_workspace','bar_window')})
        files = theme.render({'colors':colors,'generator':'test'})
        accent = theme.terminal_accent({'colors':colors})
        self.assertIn('fish_color_command '+accent[1:],files['colors.fish'])
        self.assertIn('LS_COLORS',files['colors.fish'])
        self.assertIn('color2 '+theme.vivid(colors['green']),files['kitty.conf'])
        self.assertNotIn(theme.vivid(colors['green']).lower(),files['noctalia.json'].lower())

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
