"""JSON envelope and launcher behaviour of the GUI command layer."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'extras'))
import cli
from theme import theme


class Envelope(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.state = Path(temp.name)
        (self.state/'palette-a').mkdir()
        (self.state/'current').symlink_to('palette-a')
        patcher = patch.object(theme,'STATE',self.state)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_cli(self, *argv):
        out = StringIO()
        with redirect_stdout(out):
            code = cli.main(list(argv))
        return code, json.loads(out.getvalue())

    def test_status_reports_sync_state_and_lock_flags(self):
        image = self.state/'a.png'
        image.touch()
        (self.state/'lock-tested').touch()
        with patch.object(theme,'selected_wallpaper',return_value=image), patch.object(theme,'current_wallpaper',return_value=image):
            code, result = self.run_cli('status','--json')
        self.assertEqual(code,0)
        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['generation'],'palette-a')
        self.assertTrue(result['data']['wallpaper']['in_sync'])
        self.assertEqual(result['data']['lock'],{'enabled':False,'tested':True})

    def test_missing_wallpaper_is_not_in_sync(self):
        with patch.object(theme,'selected_wallpaper',return_value=None), patch.object(theme,'current_wallpaper',return_value=None):
            self.assertFalse(self.run_cli('status','--json')[1]['data']['wallpaper']['in_sync'])

    def test_failure_keeps_stderr_and_exits_one(self):
        error = subprocess.CalledProcessError(1,'noctalia',stderr=' socket gone\n')
        with patch.object(theme,'current_wallpaper',side_effect=error):
            code, result = self.run_cli('status','--json')
        self.assertEqual(code,1)
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['stderr'],'socket gone')


class Wallpapers(Envelope):
    def setUp(self):
        super().setUp()
        from PIL import Image
        self.folder = self.state/'walls'
        self.folder.mkdir()
        self.image = self.folder/'a b#1.png'
        Image.new('RGB',(1000,500),'red').save(self.image)
        self.other = self.folder/'broken.png'
        self.other.write_text('not an image')
        cache = patch.object(cli,'THUMBS',self.state/'thumbs')
        cache.start()
        self.addCleanup(cache.stop)
        walls = patch.object(theme,'images',return_value=[self.image,self.other])
        walls.start()
        self.addCleanup(walls.stop)

    def thumbs(self):
        out = StringIO()
        with redirect_stdout(out):
            cli.main(['wallpaper','thumbs'])
        return [json.loads(line) for line in out.getvalue().splitlines()]

    def test_list_marks_active_through_symlink(self):
        link = self.state/'link.png'
        link.symlink_to(self.image)
        with patch.object(theme,'current_wallpaper',return_value=link), patch.object(theme,'library',return_value=(self.folder,False)):
            data = self.run_cli('wallpaper','list','--json')[1]['data']
        self.assertEqual([i['active'] for i in data['images']],[True,False])

    def test_thumbs_stream_skip_cached_and_report_broken_image(self):
        from PIL import Image
        first = self.thumbs()
        self.assertEqual(len(first),2)
        self.assertIn('error',first[1])
        with Image.open(first[0]['thumb']) as thumb:
            self.assertEqual(thumb.size,(cli.THUMB_SIZE,200))
        self.assertEqual([line['path'] for line in self.thumbs()],[str(self.other)])
        self.assertEqual(list((self.state/'thumbs').glob('*.tmp')),[])

    def test_changed_image_gets_new_thumb(self):
        before = cli.thumb_path(self.image)
        os.utime(self.image,(1,1))
        self.assertNotEqual(cli.thumb_path(self.image),before)

    def apply(self, result, effective):
        with patch.object(theme,'apply_choice',return_value=result) as choice, patch.object(theme,'current_wallpaper',return_value=effective), \
             patch.object(cli.signal,'signal') as block:
            outcome = self.run_cli('wallpaper','apply',str(self.image),'--json')
        return outcome, choice, block

    def test_apply_survives_gui_closing_and_reports_effective(self):
        (code, result), choice, block = self.apply('matugen',self.image)
        self.assertEqual(code,0)
        self.assertEqual(result['warnings'],[])
        self.assertEqual(result['data']['effective'],str(self.image))
        choice.assert_called_once_with(self.image)
        block.assert_any_call(cli.signal.SIGTERM,cli.signal.SIG_IGN)

    def test_apply_warns_on_kept_palette_and_other_image(self):
        self.assertEqual(len(self.apply('kept-last-palette',self.other)[0][1]['warnings']),2)

    def test_apply_missing_file_fails_before_touching_anything(self):
        with patch.object(theme,'apply_choice') as choice:
            code, result = self.run_cli('wallpaper','apply','/missing.png','--json')
        self.assertEqual((code,result['error']['code']),(1,'not_found'))
        choice.assert_not_called()


class Palette(Envelope):
    def setUp(self):
        super().setUp()
        (self.state/'palette-b').mkdir()
        (self.state/'previous').symlink_to('palette-b')
        self.write('palette-a',{'accent':'#111111'},'/a.png')
        self.write('palette-b',{'accent':'#222222'},'/b.png')

    def write(self, folder, colors, wallpaper):
        (self.state/folder/'palette.json').write_text(json.dumps({'colors':colors,'generator':'matugen','wallpaper':wallpaper}))

    def test_show_includes_previous_and_restore_state(self):
        data = self.run_cli('palette','show','--json')[1]['data']
        self.assertEqual(data['previous']['colors'],{'accent':'#222222'})
        self.assertTrue(data['can_restore'])
        self.assertFalse(data['emergency'])

    def test_identical_previous_cannot_be_restored(self):
        self.write('palette-b',{'accent':'#111111'},'/a.png')
        with patch.object(theme,'restore_previous') as restore:
            code, result = self.run_cli('palette','restore','--json')
        self.assertEqual((code,result['error']['code']),(1,'invalid'))
        restore.assert_not_called()

    def test_restore_syncs_greeter_and_warns_about_other_wallpaper(self):
        with patch.object(theme,'restore_previous',return_value='palette-b'), patch.object(theme,'sync_greeter') as sync, patch.object(cli.signal,'signal'):
            result = self.run_cli('palette','restore','--json')[1]
        sync.assert_called_once()
        self.assertEqual(len(result['warnings']),1)

    def test_regenerate_warns_and_skips_greeter_when_palette_was_kept(self):
        with patch.object(theme,'regenerate',return_value='kept-last-palette'), patch.object(theme,'sync_greeter') as sync, patch.object(cli.signal,'signal'):
            result = self.run_cli('palette','regenerate','--json')[1]
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['warnings']),1)
        sync.assert_not_called()


class Profile(Envelope):
    def set_profile(self, name, previous=None):
        (self.state/'profile').write_text(name+'\n')
        if previous:
            (self.state/'previous-profile').write_text(previous+'\n')

    def test_active_profile_keeps_history(self):
        self.set_profile('refined','minimal')
        with patch.object(cli.profiles,'switch') as switch:
            data = self.run_cli('profile','set','refined','--json')[1]['data']
        switch.assert_not_called()
        self.assertEqual((data['changed'],data['previous']),(False,'minimal'))

    def test_switch_survives_gui_closing(self):
        self.set_profile('refined')
        with patch.object(cli.profiles,'switch') as switch, patch.object(cli.signal,'signal') as block:
            self.assertTrue(self.run_cli('profile','set','minimal','--json')[1]['data']['changed'])
        switch.assert_called_once_with('minimal')
        block.assert_any_call(cli.signal.SIGTERM,cli.signal.SIG_IGN)

    def test_restore_without_history_is_a_clean_error(self):
        self.set_profile('refined')
        code, result = self.run_cli('profile','restore','--json')
        self.assertEqual((code,result['ok']),(1,False))


class Greeter(Envelope):
    def test_auto_toggles_the_flag_used_by_the_restore_script(self):
        self.assertTrue(self.run_cli('greeter','auto','on','--json')[1]['data']['auto_sync'])
        self.assertTrue((self.state/'greeter-sync').exists())
        self.run_cli('greeter','auto','off','--json')
        self.assertFalse((self.state/'greeter-sync').exists())

    def test_manual_sync_failure_is_reported(self):
        with patch.object(theme,'sync_greeter',return_value='failed') as sync, patch.object(cli.signal,'signal'):
            code, result = self.run_cli('greeter','sync','--json')
        sync.assert_called_once_with(force=True)
        self.assertEqual((code,result['ok']),(1,False))

    def test_sync_warnings_list_the_steps_that_were_not_ok(self):
        steps = [{'step':'palette','status':'OK','detail':'x'},{'step':'greeter','status':'WARN','detail':'failed'}]
        with patch.object(theme,'sync_all',return_value=steps), patch.object(cli.signal,'signal'):
            result = self.run_cli('sync','--json')[1]
        self.assertEqual(result['warnings'],['greeter: failed'])

    def test_busy_lock_has_its_own_error_code(self):
        with patch.object(theme,'sync_all',side_effect=TimeoutError('busy')), patch.object(cli.signal,'signal'):
            self.assertEqual(self.run_cli('sync','--json')[1]['error']['code'],'busy')


class Launcher(unittest.TestCase):
    def test_second_press_closes_open_window(self):
        running = subprocess.CompletedProcess([],0,stdout='target rice\n  function close(): void\n')
        with patch.object(cli.subprocess,'run',return_value=running) as run, patch.object(cli.os,'execvp') as launch, patch.object(theme,'STATE',Path(tempfile.gettempdir())):
            self.assertEqual(cli.gui(),0)
        self.assertEqual(run.call_args.args[0][-3:],['call','rice','close'])
        launch.assert_not_called()

    def test_first_press_launches_single_instance(self):
        absent = subprocess.CompletedProcess([],0,stdout='')
        with patch.object(cli.subprocess,'run',return_value=absent), patch.object(cli.os,'execvp') as launch, patch.object(theme,'STATE',Path(tempfile.gettempdir())):
            cli.gui()
        self.assertEqual(launch.call_args.args[1][:3],['qs','-n','-d'])

if __name__ == '__main__':
    unittest.main()
