"""JSON envelope and launcher behaviour of the GUI command layer."""
# Testes dos subcomandos "lw ... --json" (o contrato entre a GUI e o Python).
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'extras'))
import cli
import cmd_games
import cmd_music
import cmd_system
from theme import theme


def running(pid):
    """True se o processo existe e não é um zumbi esperando o init."""
    try:
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[0] != 'Z'
    except OSError:
        return False


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
        cache = patch.object(cmd_system,'THUMBS',self.state/'thumbs')
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

    def test_list_reports_resolution_and_size_and_survives_a_broken_image(self):
        with patch.object(theme,'current_wallpaper',return_value=None), patch.object(theme,'library',return_value=(self.folder,False)):
            good, broken = self.run_cli('wallpaper','list','--json')[1]['data']['images']
        from PIL import Image
        with Image.open(self.image) as image:
            self.assertEqual(good['size'],list(image.size))
        self.assertEqual(good['bytes'],self.image.stat().st_size)
        self.assertIsNone(broken['size'])

    def test_thumbs_stream_skip_cached_and_report_broken_image(self):
        from PIL import Image
        first = self.thumbs()
        self.assertEqual(len(first),2)
        self.assertIn('error',first[1])
        with Image.open(first[0]['thumb']) as thumb:
            self.assertEqual(thumb.size,(cmd_system.THUMB_SIZE,200))
        self.assertEqual([line['path'] for line in self.thumbs()],[str(self.other)])
        self.assertEqual(list((self.state/'thumbs').glob('*.tmp')),[])

    def test_changed_image_gets_new_thumb(self):
        before = cmd_system.thumb_path(self.image)
        os.utime(self.image,(1,1))
        self.assertNotEqual(cmd_system.thumb_path(self.image),before)

    def apply(self, result, effective):
        with patch.object(theme,'apply_choice',return_value=result) as choice, patch.object(theme,'current_wallpaper',return_value=effective), \
             patch.object(cmd_system.signal,'signal') as block:
            outcome = self.run_cli('wallpaper','apply',str(self.image),'--json')
        return outcome, choice, block

    def test_apply_survives_gui_closing_and_reports_effective(self):
        (code, result), choice, block = self.apply('matugen',self.image)
        self.assertEqual(code,0)
        self.assertEqual(result['warnings'],[])
        self.assertEqual(result['data']['effective'],str(self.image))
        choice.assert_called_once_with(self.image)
        block.assert_any_call(cmd_system.signal.SIGTERM,cmd_system.signal.SIG_IGN)

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
        with patch.object(theme,'restore_previous',return_value='palette-b'), patch.object(theme,'sync_greeter') as sync, patch.object(cmd_system.signal,'signal'):
            result = self.run_cli('palette','restore','--json')[1]
        sync.assert_called_once()
        self.assertEqual(len(result['warnings']),1)

    def test_regenerate_warns_and_skips_greeter_when_palette_was_kept(self):
        with patch.object(theme,'regenerate',return_value='kept-last-palette'), patch.object(theme,'sync_greeter') as sync, patch.object(cmd_system.signal,'signal'):
            result = self.run_cli('palette','regenerate','--json')[1]
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['warnings']),1)
        sync.assert_not_called()

    def test_scheme_is_kept_and_unknown_ones_are_refused(self):
        self.assertEqual(theme.scheme(),'scheme-neutral')
        theme.set_scheme('scheme-vibrant')
        self.assertEqual(theme.scheme(),'scheme-vibrant')
        with self.assertRaises(ValueError):
            theme.set_scheme('scheme-made-up')
        (self.state/'scheme').write_text('garbage\n')
        self.assertEqual(theme.scheme(),'scheme-neutral')

    def test_default_scheme_keeps_the_old_fingerprint(self):
        import hashlib
        image = self.state/'a.png'
        image.write_bytes(b'x')
        stat = image.stat()
        old = hashlib.sha256(f'{image.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:neutral-v4'.encode()).hexdigest()
        self.assertEqual(theme.fingerprint(image),old)
        theme.set_scheme('scheme-expressive')
        self.assertNotEqual(theme.fingerprint(image),old)

    def test_regenerate_with_scheme_saves_it_or_rolls_it_back(self):
        with patch.object(theme,'regenerate',return_value='matugen 4.2 / scheme-vibrant / dark'), patch.object(theme,'sync_greeter'), patch.object(cmd_system.signal,'signal'):
            self.assertTrue(self.run_cli('palette','regenerate','--scheme','vibrant','--json')[1]['ok'])
        self.assertEqual(theme.scheme(),'scheme-vibrant')
        with patch.object(theme,'regenerate',return_value='kept-last-palette'), patch.object(theme,'sync_greeter'), patch.object(cmd_system.signal,'signal'):
            self.run_cli('palette','regenerate','--scheme','expressive','--json')
        self.assertEqual(theme.scheme(),'scheme-vibrant')


class Profile(Envelope):
    def set_profile(self, name, previous=None):
        (self.state/'profile').write_text(name+'\n')
        if previous:
            (self.state/'previous-profile').write_text(previous+'\n')

    def test_differences_come_from_the_files_that_apply_the_profiles(self):
        rows = {r['setting']:r for r in cmd_system.profile_differences()}
        self.assertEqual(rows['hyprland animations']['refined'],'on')
        self.assertEqual(rows['workspace switch']['minimal'],'instant')
        self.assertRegex(rows['workspace switch']['refined'],r'^slide \d+ ms$')
        self.assertEqual(rows['noctalia shell.animation.enabled']['minimal'],'off')
        self.assertEqual(rows['greeter waits for colors']['refined'],f'{theme.GREETER_SETTLE} s')
        # Settings equal in both profiles never appear.
        self.assertFalse(any('rounding' in name or 'font' in name for name in rows))

    def test_active_profile_keeps_history(self):
        self.set_profile('refined','minimal')
        with patch.object(cmd_system.profiles,'switch') as switch:
            data = self.run_cli('profile','set','refined','--json')[1]['data']
        switch.assert_not_called()
        self.assertEqual((data['changed'],data['previous']),(False,'minimal'))

    def test_switch_survives_gui_closing(self):
        self.set_profile('refined')
        with patch.object(cmd_system.profiles,'switch') as switch, patch.object(cmd_system.signal,'signal') as block:
            self.assertTrue(self.run_cli('profile','set','minimal','--json')[1]['data']['changed'])
        switch.assert_called_once_with('minimal')
        block.assert_any_call(cmd_system.signal.SIGTERM,cmd_system.signal.SIG_IGN)

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
        with patch.object(theme,'sync_greeter',return_value='failed') as sync, patch.object(cmd_system.signal,'signal'):
            code, result = self.run_cli('greeter','sync','--json')
        sync.assert_called_once_with(force=True)
        self.assertEqual((code,result['ok']),(1,False))

    def test_sync_warnings_list_the_steps_that_were_not_ok(self):
        steps = [{'step':'palette','status':'OK','detail':'x'},{'step':'greeter','status':'WARN','detail':'failed'}]
        with patch.object(theme,'sync_all',return_value=steps), patch.object(cmd_system.signal,'signal'):
            result = self.run_cli('sync','--json')[1]
        self.assertEqual(result['warnings'],['greeter: failed'])

    def test_busy_lock_has_its_own_error_code(self):
        with patch.object(theme,'sync_all',side_effect=TimeoutError('busy')), patch.object(cmd_system.signal,'signal'):
            self.assertEqual(self.run_cli('sync','--json')[1]['error']['code'],'busy')


class Shortcuts(Envelope):
    TEXT = """local mainMod = "SUPER"
local noctCall = "noctalia msg "
local launchPrefix = "uwsm app -- "
-- Windows
hl.bind(mainMod .. " + Q",    hl.dsp.window.close())
hl.bind(mainMod .. " + E",    hl.dsp.exec_cmd(launchPrefix .. FILES))
-- Shell
hl.bind(mainMod .. " + Tab",  hl.dsp.exec_cmd(noctCall .. "window-switcher"))
hl.bind(mainMod .. " + Z",    hl.dsp.exec_cmd("hyprctl kill"), { locked = true })
"""

    def setUp(self):
        super().setUp()
        self.file = self.state/'binds.lua'
        self.file.write_text(self.TEXT)
        hypr = patch.object(cmd_system.shortcuts,'live_conflict',return_value=False)
        self.conflict = hypr.start()
        self.addCleanup(hypr.stop)

    def listing(self):
        return self.run_cli('shortcuts','list','--json','--file',str(self.file))[1]['data']

    def change(self, line, *extra):
        data = self.listing()
        return self.run_cli('shortcuts','set','--line',str(line),'--revision',data['revision'],*extra,'--json','--file',str(self.file))

    def test_list_exposes_only_real_commands_and_their_sections(self):
        binds = {b['key']:b for b in self.listing()['binds']}
        self.assertIsNone(binds['SUPER + Q']['command'])
        self.assertIsNone(binds['SUPER + E']['command'])
        self.assertEqual(binds['SUPER + Tab']['command'],'window-switcher')
        self.assertEqual(binds['SUPER + Tab']['section'],'Shell')

    def test_command_edit_keeps_prefix_and_options(self):
        self.change(7,'--command','launcher-toggle')
        self.assertIn('hl.dsp.exec_cmd(noctCall .. "launcher-toggle"))',self.file.read_text())
        self.change(8,'--command','hyprctl reload')
        self.assertIn('hl.dsp.exec_cmd("hyprctl reload"), { locked = true })',self.file.read_text())

    def test_dispatcher_and_variable_commands_are_refused_untouched(self):
        for line in (4,5):
            code, result = self.change(line,'--command','firefox')
            self.assertEqual((code,result['ok']),(1,False))
        self.assertEqual(self.file.read_text(),self.TEXT)

    def test_replace_turns_a_dispatcher_into_a_plain_command(self):
        self.assertEqual(self.change(4,'--command','noctalia msg volume-down','--replace')[0],0)
        self.assertIn('hl.bind(mainMod .. " + Q",    hl.dsp.exec_cmd("noctalia msg volume-down"))',self.file.read_text())
        self.assertEqual(self.file.read_text().count('\n'),self.TEXT.count('\n'))

    def test_delete_removes_only_that_line_and_keeps_a_backup(self):
        code, result = self.run_cli('shortcuts','delete','--line','4','--revision',self.listing()['revision'],'--json','--file',str(self.file))
        self.assertEqual((code,result['ok']),(0,True))
        self.assertEqual(self.file.read_text(),self.TEXT.replace('hl.bind(mainMod .. " + Q",    hl.dsp.window.close())\n',''))
        self.assertEqual(Path(result['data']['backup']).read_text(),self.TEXT)
        # Not a bind line (a comment) and a stale revision are refused.
        self.assertFalse(self.run_cli('shortcuts','delete','--line','3','--revision',self.listing()['revision'],'--json','--file',str(self.file))[1]['ok'])
        self.assertFalse(self.run_cli('shortcuts','delete','--line','4','--revision','x','--json','--file',str(self.file))[1]['ok'])

    def test_key_edit_works_on_a_dispatcher(self):
        self.assertEqual(self.change(4,'--key','SHIFT + Q')[0],0)
        self.assertIn('hl.dsp.window.close()',self.file.read_text())
        self.assertIn('" + SHIFT + Q"',self.file.read_text())

    def test_conflicts_are_refused_in_the_file_and_in_the_running_session(self):
        self.assertFalse(self.change(4,'--key','Tab')[1]['ok'])
        self.conflict.return_value = True
        self.assertFalse(self.change(4,'--key','BackSpace')[1]['ok'])
        self.assertEqual(self.file.read_text(),self.TEXT)

    def test_display_puts_super_first_and_keeps_key_spelling(self):
        self.assertEqual(cmd_system.shortcuts.display_key('mainMod .. " + SHIFT + mouse_up"'),'SUPER + SHIFT + mouse_up')
        self.assertEqual(cmd_system.shortcuts.display_key('mainMod .. " + ALT + BackSpace"'),'SUPER + ALT + BackSpace')

    def test_editing_the_displayed_text_never_doubles_super(self):
        self.change(4,'--key','SHIFT + SUPER + mouse_up')
        self.assertIn('mainMod .. " + SHIFT + mouse_up"',self.file.read_text())

    def test_stale_revision_is_refused(self):
        code, result = self.run_cli('shortcuts','set','--line','4','--revision','old','--key','W','--json','--file',str(self.file))
        self.assertEqual((code,result['error']['code']),(1,'invalid'))

    def test_backup_can_be_listed_and_restored(self):
        self.change(4,'--key','W')
        backups = self.run_cli('shortcuts','backups','--json','--file',str(self.file))[1]['data']['backups']
        self.assertEqual(len(backups),1)
        self.assertTrue(self.run_cli('shortcuts','restore',backups[0]['path'],'--json','--file',str(self.file))[1]['ok'])
        self.assertEqual(self.file.read_text(),self.TEXT)

    def test_restore_refuses_unrelated_file(self):
        self.assertFalse(self.run_cli('shortcuts','restore','/etc/passwd','--json','--file',str(self.file))[1]['ok'])

    def test_check_finds_duplicates_and_bad_lua(self):
        self.file.write_text(self.TEXT+'hl.bind(mainMod .. " + Q", hl.dsp.window.close())\n')
        self.assertEqual(self.run_cli('shortcuts','check','--json','--file',str(self.file))[1]['data']['duplicates'],['SUPER + Q'])
        self.file.write_text('hl.bind(')
        self.assertFalse(self.run_cli('shortcuts','check','--json','--file',str(self.file))[1]['ok'])


class LiveConflict(unittest.TestCase):
    def active(self, *binds):
        return subprocess.CompletedProcess([],0,stdout=json.dumps(list(binds)))

    def test_same_key_needs_same_modifiers(self):
        with patch.object(cmd_system.shortcuts.subprocess,'run',return_value=self.active({'modmask':64,'key':'BackSpace','keycode':0})):
            self.assertTrue(cmd_system.shortcuts.live_conflict(('SUPER','BACKSPACE')))
            self.assertFalse(cmd_system.shortcuts.live_conflict(('ALT','SUPER','BACKSPACE')))

    def test_number_row_binds_are_matched_by_keycode(self):
        with patch.object(cmd_system.shortcuts.subprocess,'run',return_value=self.active({'modmask':64,'key':'','keycode':10})):
            self.assertTrue(cmd_system.shortcuts.live_conflict(('SUPER','1')))

    def test_no_session_means_no_live_conflict(self):
        with patch.object(cmd_system.shortcuts.subprocess,'run',side_effect=FileNotFoundError):
            self.assertFalse(cmd_system.shortcuts.live_conflict(('SUPER','Q')))


class Lock(Envelope):
    def setUp(self):
        super().setUp()
        (self.state/'palette-a'/'palette.json').write_text('{"colors":{},"generator":"matugen"}')
        (self.state/'palette-a'/'lockscreen.toml').write_text('[lockscreen]\ntint_intensity = 0.6\nwallpaper = "/w.png"\n')
        self.monitors = [{'name':'HDMI-A-1','width':1920,'height':1080,'scale':1}]

    def command(self, args, **kwargs):
        if args[:2] == ['hyprctl','-j']:
            return json.dumps(self.monitors)
        return json.dumps({'locked':False})

    def stamp(self, name, age):
        path = self.state/name
        path.write_text(json.dumps(self.monitors) if name.endswith('.json') else 'x')
        os.utime(path,(1000-age,1000-age))

    def test_real_lock_commands_need_explicit_confirmation(self):
        with patch.object(cmd_system.lockscreen,'run_trial') as trial, patch.object(cmd_system.lockscreen,'activate') as activate:
            self.assertFalse(self.run_cli('lock','trial','--json')[1]['ok'])
            self.assertFalse(self.run_cli('lock','activate','--json')[1]['ok'])
        trial.assert_not_called()
        activate.assert_not_called()

    def test_trial_survives_gui_closing_and_logs_failure(self):
        with patch.object(cmd_system.lockscreen,'run_trial',side_effect=RuntimeError('Lock was not confirmed')), patch.object(cmd_system.signal,'signal') as block:
            code, result = self.run_cli('lock','trial','--confirm','--json')
        self.assertEqual((code,result['ok']),(1,False))
        block.assert_any_call(cmd_system.signal.SIGTERM,cmd_system.signal.SIG_IGN)
        self.assertIn('Lock was not confirmed',(self.state/'actions.jsonl').read_text())

    def test_trial_is_valid_only_for_the_layout_it_saw(self):
        self.stamp('lock-displays.json',20)
        self.stamp('lock-tested',10)
        self.assertTrue(cmd_system.lockscreen.tested())
        self.stamp('lock-displays.json',5)
        self.assertFalse(cmd_system.lockscreen.tested())
        with self.assertRaises(RuntimeError):
            cmd_system.lockscreen.activate()

    def test_same_monitors_keep_the_trial_and_new_ones_invalidate_it(self):
        self.stamp('lock-displays.json',20)
        self.stamp('lock-tested',10)
        with patch.object(theme,'command',side_effect=self.command):
            cmd_system.lockscreen.capture_displays()
            self.assertTrue(cmd_system.lockscreen.tested())
            self.monitors = [{'name':'DP-1','width':2560,'height':1440,'scale':1}]
            cmd_system.lockscreen.capture_displays()
        self.assertFalse(cmd_system.lockscreen.tested())

    def test_status_reads_candidate_and_session(self):
        with patch.object(theme,'command',side_effect=self.command):
            data = self.run_cli('lock','status','--json')[1]['data']
        self.assertEqual((data['effective_dim'],data['session_locked'],data['enabled']),(.6,False,False))

    def test_dim_accepts_the_slider_steps_and_nothing_else(self):
        for level in ('10','50','57','90'):
            with patch.object(sys,'stderr',StringIO()), self.assertRaises(SystemExit):
                cli.main(['lock','dim',level])
        with patch.object(cmd_system.lockscreen,'set_dim',return_value=.65) as set_dim:
            self.assertTrue(self.run_cli('lock','dim','65','--json')[1]['ok'])
        set_dim.assert_called_once_with(.65)

    def test_candidate_is_not_published_from_a_missing_palette(self):
        (self.state/'palette-a'/'palette.json').unlink()
        with patch.object(theme,'activate') as activate:
            self.assertFalse(self.run_cli('lock','update','--json')[1]['ok'])
        activate.assert_not_called()


class Backups(Envelope):
    def setUp(self):
        super().setUp()
        root = patch.object(theme,'ROOT',self.state)
        root.start()
        self.addCleanup(root.stop)
        self.root = self.state/'backups'

    def add(self, name, *files, manifest=None):
        path = self.root/name
        path.mkdir(parents=True)
        for item in files:
            (path/item).mkdir()
        if manifest is not None:
            (path/'manifest.json').write_text(json.dumps(manifest))
        return path

    def listed(self):
        return {b['name']:b for b in self.run_cli('backups','list','--json')[1]['data']['backups']}

    def test_each_format_points_to_its_own_tool(self):
        self.add('rice-final-1','project','theme',manifest=[{'path':'/x'}])
        self.add('phase3-1',manifest=[{'path':'/x','backup':'/y'}])
        self.add('lock-visual-1')
        self.add('gui-fase0-1')
        data = self.listed()
        self.assertIn('scripts/restore.py',data['rice-final-1']['command'])
        self.assertIn('scripts/restore.py',data['phase3-1']['command'])
        self.assertIn('lock-restore',data['lock-visual-1']['command'])
        self.assertEqual((data['gui-fase0-1']['kind'],data['gui-fase0-1']['command']),('snapshot',None))

    def test_empty_manifest_has_nothing_to_restore(self):
        self.add('old',manifest=[])
        self.assertIsNone(self.listed()['old']['command'])

    def test_missing_folder_is_an_empty_list_for_a_fresh_clone(self):
        result = self.run_cli('backups','list','--json')[1]
        self.assertEqual((result['ok'],result['data']['backups'],result['data']['recovery']['full']),(True,[],None))

    def test_newest_full_backup_is_the_recovery_command(self):
        old = self.add('rice-final-old','theme',manifest=[{'path':'/x'}])
        os.utime(old,(1,1))
        self.add('rice-final-new','theme',manifest=[{'path':'/x'}])
        self.assertIn('rice-final-new',self.run_cli('backups','list','--json')[1]['data']['recovery']['full'])


class Launcher(unittest.TestCase):
    """lw gui|music|games against a fake running window (qs ipc answers)."""
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.config = Path(temp.name)/'lw/config.toml'
        self.config.parent.mkdir()
        # A escolha de módulos de quem roda os testes não entra aqui.
        env = patch.dict(os.environ,{'XDG_CONFIG_HOME':temp.name})
        env.start()
        self.addCleanup(env.stop)

    def press(self, section, shown='', hidden='no', go='ok', code=None):
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            if args[:2] == ['qs','list']:
                return subprocess.CompletedProcess(args,0,stdout='')
            op = args[-1] if args[-2] == 'lw' else args[-2]
            answers = {'section': shown, 'hidden': hidden, 'go': go}
            if op in answers:
                return subprocess.CompletedProcess(args,0 if shown else 1,stdout=answers[op]+'\n' if shown else '')
            return subprocess.CompletedProcess(args,0,stdout='')
        self.started = None
        def execvp(*args):
            self.started = cli.os.environ.get('LW_START_GROUP')
            self.given = json.loads(cli.os.environ['LW_MODULES'])
        with patch.object(cli.subprocess,'run',side_effect=run), patch.object(cli.os,'execvp',side_effect=execvp) as launch, \
             patch.object(theme,'STATE',Path(tempfile.gettempdir())), patch.dict(cli.os.environ,{'XDG_RUNTIME_DIR':tempfile.mkdtemp()}):
            self.assertEqual(cli.gui(section),code if code is not None else 0 if shown else None)
        ops = [c[c.index('lw')+1:] for c in calls if 'lw' in c]
        self.notified = [c[-1] for c in calls if c[:3] == ['noctalia','msg','notification-show']]
        return ops, launch

    def test_closed_window_opens_on_the_section(self):
        ops, launch = self.press('music')
        self.assertEqual(launch.call_args.args[1][:3],['qs','-n','-d'])
        self.assertEqual(self.started,'music')

    def test_same_section_closes(self):
        ops, launch = self.press('games', shown='games')
        self.assertIn(['close'],ops)
        launch.assert_not_called()

    def test_other_section_switches(self):
        ops, launch = self.press('music', shown='system')
        self.assertIn(['go','music'],ops)
        self.assertNotIn(['close'],ops)

    def test_hidden_window_comes_back_on_the_section(self):
        ops, launch = self.press('system', shown='system', hidden='yes')
        self.assertIn(['reveal'],ops)
        self.assertIn(['go','system'],ops)
        self.assertNotIn(['close'],ops)

    def test_the_shortcut_of_a_module_turned_off_says_so(self):
        self.config.write_text('[modules]\nmusic = false\n')
        text = 'módulo MÚSICA desligado · lw modules enable musica'
        for shown, hidden in (('',''),('system','no'),('music','yes'),('music','no')):
            with self.subTest(shown=shown,hidden=hidden), redirect_stderr(StringIO()) as err:
                ops, launch = self.press('music', shown=shown, hidden=hidden, code=1)
                self.assertEqual((ops,self.notified),([['notice',text]],[text]))
                launch.assert_not_called()
                self.assertIn(text,err.getvalue())

    def test_the_notice_does_not_need_noctalia_nor_an_open_window(self):
        for failure in (FileNotFoundError('noctalia'),subprocess.TimeoutExpired('qs',3)):
            with patch.object(cli.subprocess,'run',side_effect=failure), redirect_stderr(StringIO()) as err:
                self.assertEqual(cli.warn('x'),1)
            self.assertEqual(err.getvalue(),'lw: x\n')

    def test_the_other_modules_still_open(self):
        self.config.write_text('[modules]\nmusic = false\n')
        ops, launch = self.press('games')
        launch.assert_called_once()
        self.assertEqual({m['id']:m['enabled'] for m in self.given},
                         {'system':True,'music':False,'games':True})

    def test_a_module_turned_on_with_the_window_open_asks_to_reopen(self):
        for hidden in ('no','yes'):
            with self.subTest(hidden=hidden), redirect_stderr(StringIO()):
                ops, launch = self.press('music', shown='system', hidden=hidden, go='unknown', code=1)
                self.assertEqual(self.notified,['módulo MÚSICA ligado · feche e abra o LW'])
                launch.assert_not_called()

    def test_the_window_gets_the_same_module_list_as_the_command(self):
        with patch.object(cli.os,'execvp'), patch.object(cli.subprocess,'run',return_value=subprocess.CompletedProcess([],1,stdout='')), \
             patch.object(theme,'STATE',Path(tempfile.gettempdir())), patch.dict(cli.os.environ,{'XDG_RUNTIME_DIR':tempfile.mkdtemp()}):
            cli.gui('system')
            given = json.loads(cli.os.environ['LW_MODULES'])
        out = StringIO()
        with redirect_stdout(out):
            self.assertEqual(cli.main(['modules','list','--json']),0)
        result = json.loads(out.getvalue())
        self.assertEqual((result['ok'],result['action'],result['data']),(True,'modules list',given))
        self.assertEqual([m['id'] for m in given],['system','music','games'])
        self.assertEqual(given[0]['screens'][0],{'name':'WALLPAPERS','file':'WallpaperScreen.qml'})
        self.assertIn('dir',given[1]['config'])


class Modules(unittest.TestCase):
    """lw modules list|enable|disable e os comandos de um módulo desligado."""
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        env = patch.dict(os.environ,{'HOME':str(self.home),'XDG_CONFIG_HOME':str(self.home/'.config'),'XDG_STATE_HOME':str(self.home/'state')})
        env.start()
        self.addCleanup(env.stop)

    def run_cli(self, *argv):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def call(self, *argv):
        code, out, _ = self.run_cli(*argv,'--json')
        return code, json.loads(out)

    def test_list_shows_every_module_and_what_is_on(self):
        self.call('modules','disable','games')
        data = self.call('modules','list')[1]['data']
        self.assertEqual([(m['id'],m['enabled'],m['required']) for m in data],
                         [('system',True,True),('music',True,False),('games',False,False)])
        out = self.run_cli('modules','list')[1].splitlines()
        self.assertEqual([line.split() for line in out],[['ligado','sistema','SISTEMA','(obrigatório)'],
                                                         ['ligado','musica','MÚSICA'],['desligado','jogos','JOGOS']])

    def test_disable_and_enable_by_id_or_name(self):
        code, result = self.call('modules','disable','MÚSICA')
        self.assertEqual((code,result['ok'],result['action']),(0,True,'modules disable'))
        self.assertEqual(result['data'],{'id':'music','name':'MÚSICA','enabled':False,'changed':True,'backup':None})
        self.assertFalse(self.call('modules','disable','music')[1]['data']['changed'])
        result = self.call('modules','enable','musica')[1]
        self.assertEqual((result['data']['enabled'],result['data']['changed']),(True,True))
        self.assertIn('music = false',Path(result['data']['backup']).read_text())
        self.assertEqual(self.run_cli('modules','enable','musica')[1].strip(),'módulo MÚSICA já está ligado')
        self.assertEqual(self.run_cli('modules','disable','musica')[1].strip(),'módulo MÚSICA desligado · vale na próxima abertura do LW')

    def test_the_system_and_unknown_names_are_refused(self):
        for argv, text in ((('disable','system'),'SISTEMA é obrigatório'),(('enable','nada'),'módulo desconhecido: nada')):
            code, result = self.call('modules',*argv)
            self.assertEqual((code,result['ok'],result['error']['code']),(1,False,'invalid'))
            self.assertIn(text,result['error']['message'])
        self.assertFalse((self.home/'.config').exists())

    def test_the_commands_of_a_module_turned_off_are_refused_before_its_handler(self):
        for module in ('music','games'):
            self.call('modules','disable',module)
        text = {'music':'módulo MÚSICA desligado · lw modules enable musica','games':'módulo JOGOS desligado · lw modules enable jogos'}
        with patch.object(cli.importlib,'import_module') as load:
            for command, owner in cli.modules.owners().items():
                if owner == 'system':
                    continue
                with self.subTest(command=command):
                    code, result = self.call(command,'x')
                    self.assertEqual((code,result['ok'],result['action'],result['error']['code'],result['error']['message']),
                                     (1,False,command,'invalid',text[owner]))
                    code, out, err = self.run_cli(command,'x')
                    self.assertEqual((code,out,err),(1,'','lw: '+text[owner]+'\n'))
            load.assert_not_called()

    def test_the_system_commands_go_on(self):
        self.call('modules','disable','music')
        with patch.object(cmd_system,'profile_get',return_value={'profile':'x'}):
            self.assertEqual(self.call('profile','get')[1]['data'],{'profile':'x'})

    def test_list_brings_the_description(self):
        data = self.call('modules','list')[1]['data']
        self.assertTrue(all(m['description'] for m in data))
        self.assertEqual(data[1]['description'],cli.modules.load()[0]['music']['description'])


# Programas falsos: cada um anota os argumentos em calls.txt e sai com o código de exit-<nome>, se houver.
FAKE = """#!/bin/sh
echo "${{0##*/}} $*" >> {log}
test -f {folder}/exit-${{0##*/}} && read code < {folder}/exit-${{0##*/}} && exit $code
exit 0
"""


class ModuleInstall(unittest.TestCase):
    """lw modules deps|install, com sudo, pacman, paru e yay falsos; o PATH só tem a pasta deles."""
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.bin = self.home/'bin'
        self.bin.mkdir()
        self.log = self.home/'calls.txt'
        self.fake('sudo','pacman')

    def fake(self, *names):
        for name in names:
            (self.bin/name).write_text(FAKE.format(log=self.log,folder=self.bin))
            (self.bin/name).chmod(0o755)

    def env(self):
        return {'HOME':str(self.home),'XDG_CONFIG_HOME':str(self.home/'.config'),'XDG_STATE_HOME':str(self.home/'state'),
                'PATH':str(self.bin)}

    def lw(self, *argv, json_out=True):
        p = subprocess.run([sys.executable,str(ROOT/'extras/rice.py'),*argv,*(['--json'] if json_out else [])],
                           capture_output=True,text=True,env=self.env(),timeout=60)
        return p.returncode, json.loads(p.stdout) if json_out else p.stdout

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_deps_lists_every_dependency_and_the_exact_command(self):
        code, result = self.lw('modules','deps','musica')
        self.assertEqual((code,result['ok'],result['action']),(0,True,'modules deps'))
        data = result['data']
        self.assertEqual((data['module'],data['name']),('music','MÚSICA'))
        self.assertEqual([d['name'] for d in data['dependencies'] if not d['optional']],['cliamp','wpctl','pactl'])
        self.assertTrue(all(d['found'] == '' for d in data['dependencies']))
        plan = data['install']
        self.assertEqual(plan['commands'],[['sudo','pacman','-S','--needed','wireplumber','libpulse']])
        self.assertEqual(plan['blocked'],['cliamp: fora dos repositórios; ver modules/music/README.md'])
        self.assertEqual(self.calls(),[])

    def test_optional_and_picks_choose_what_enters(self):
        everything = self.lw('modules','deps','musica','--optional')[1]['data']['install']['pacman']
        self.assertEqual(everything,['wireplumber','libpulse','cava','ffmpeg','yt-dlp','playerctl','zenity','glib2'])
        picked = self.lw('modules','deps','musica','--pick','cava','--pick','ffmpeg')[1]['data']['install']
        self.assertEqual(picked['commands'],[['sudo','pacman','-S','--needed','cava','ffmpeg']])
        code, result = self.lw('modules','deps','musica','--pick','nada')
        self.assertEqual((code,result['error']['code']),(1,'invalid'))

    def test_nothing_missing_means_no_command(self):
        self.fake('wpctl','pactl','cliamp')
        plan = self.lw('modules','deps','music')[1]['data']['install']
        self.assertEqual((plan['commands'],plan['blocked']),([],[]))
        self.assertEqual(self.lw('modules','install','music','--yes')[1]['data']['ran'],[])

    def test_install_without_yes_runs_nothing(self):
        code, result = self.lw('modules','install','music')
        self.assertEqual((code,result['ok'],result['error']['code']),(1,False,'invalid'))
        self.assertIn('--yes',result['error']['message'])
        self.assertEqual(self.calls(),[])

    def test_install_runs_exactly_the_plan(self):
        code, result = self.lw('modules','install','music','--pick','libpulse','--yes')
        self.assertEqual((code,result['ok']),(0,True))
        self.assertEqual(result['data']['ran'],[{'command':['sudo','pacman','-S','--needed','libpulse'],'code':0}])
        self.assertEqual(self.calls(),['sudo pacman -S --needed libpulse'])
        code, out = self.lw('modules','install','jogos','--pick','wine','--yes',json_out=False)
        self.assertEqual(out.strip(),'[ OK ] sudo pacman -S --needed wine')

    def test_a_failed_install_says_so(self):
        (self.bin/'exit-sudo').write_text('1\n')
        code, result = self.lw('modules','install','music','--yes')
        self.assertEqual((code,result['ok']),(1,False))
        self.assertIn('saiu com 1',result['error']['message'])

    def test_aur_uses_paru_then_yay_and_otherwise_only_says_it(self):
        import doctor
        deps = [{'name':'x','key':'x-bin','optional':False,'why':'','found':'','package':'','aur':'x-bin','manual':''},
                {'name':'y','key':'y','optional':False,'why':'','found':'','package':'y','aur':'','manual':''}]
        with patch.dict(os.environ,{'PATH':str(self.bin)}):
            plan = doctor.install_plan(deps)
            self.assertEqual((plan['helper'],plan['commands']),(None,[['sudo','pacman','-S','--needed','y']]))
            self.assertEqual(plan['blocked'],['AUR, sem paru nem yay: instale x-bin com um deles'])
            self.fake('yay')
            self.assertEqual(doctor.install_plan(deps)['commands'][1],['yay','-S','--needed','x-bin'])
            self.fake('paru')
            plan = doctor.install_plan(deps)
            self.assertEqual((plan['helper'],plan['commands'][1],plan['blocked']),('paru',['paru','-S','--needed','x-bin'],[]))

    def pacman_with(self, *packages):
        """O pacman falso responde ao -Qq com estes pacotes instalados (e anota as instalações)."""
        names = ' '.join(packages)
        (self.bin/'pacman').write_text(f'''#!/bin/sh
if [ "$1" = "-Qq" ]; then
  shift; for a in "$@"; do for p in {names}; do [ "$a" = "$p" ] && echo "$p"; done; done; exit 0
fi
echo "pacman $*" >> {self.log}
''')

    def test_a_conflicting_package_installed_is_never_asked(self):
        # Máquina com o noctalia-shell: noctalia-qs no lugar do quickshell.
        self.pacman_with('noctalia-qs','noctalia-shell')
        data = self.lw('modules','deps','sistema')[1]['data']
        deps = {d['name']: d for d in data['dependencies']}
        self.assertIn('noctalia-qs instalado, que conflita com quickshell',deps['qs']['conflict'])
        self.assertIn('noctalia-shell instalado',deps['noctalia']['conflict'])
        command = data['install']['commands'][0]
        self.assertNotIn('quickshell',command)
        self.assertNotIn('noctalia',command)
        self.assertIn('hyprland',command)
        self.assertEqual([b.split(':')[0] for b in data['install']['blocked'][:2]],['quickshell','noctalia'])
        picked = self.lw('modules','deps','sistema','--pick','quickshell')[1]['data']['install']
        self.assertEqual(picked['commands'],[])
        self.lw('modules','install','sistema','--yes')
        self.assertFalse([c for c in self.calls() if 'quickshell' in c or ' noctalia' in c])
        out = self.lw('modules','deps','sistema',json_out=False)[1]
        self.assertIn('[ !! ] qs — conflito · noctalia-qs instalado',out)

    def test_without_the_conflict_quickshell_and_noctalia_are_asked(self):
        self.pacman_with()
        command = self.lw('modules','deps','sistema')[1]['data']['install']['commands'][0]
        self.assertEqual(command[:6],['sudo','pacman','-S','--needed','quickshell','hyprland'])
        self.assertIn('noctalia',command)

    def test_the_terminal_text(self):
        out = self.lw('modules','deps','music',json_out=False)[1].splitlines()
        self.assertEqual(out[:2],['MÚSICA','[ -- ] cliamp — falta · é o player'])
        self.assertIn('sudo pacman -S --needed wireplumber libpulse',out)


class Music(unittest.TestCase):
    """library, organize, radio, online e download: a lógica dos scripts no envelope do lw."""
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.music = self.home/'Áudio'
        (self.music/'Rap').mkdir(parents=True)
        (self.music/'Downloads').mkdir()
        (self.home/'.config/lw').mkdir(parents=True)
        (self.home/'.config/lw/config.toml').write_text('[music]\ndir = "~/Áudio"\n')
        env = patch.dict(os.environ,{'HOME':str(self.home),'XDG_CONFIG_HOME':str(self.home/'.config'),
                                     'XDG_CACHE_HOME':str(self.home/'cache'),'XDG_DATA_HOME':str(self.home/'data')})
        env.start()
        self.addCleanup(env.stop)

    def run_cli(self, *argv):
        out = StringIO()
        with redirect_stdout(out):
            code = cli.main(list(argv))
        return code, json.loads(out.getvalue())

    def ytdlp(self, body):
        """Um yt-dlp falso na frente do PATH."""
        folder = self.home/'bin'
        folder.mkdir()
        (folder/'yt-dlp').write_text('#!/bin/sh\n'+body)
        (folder/'yt-dlp').chmod(0o755)
        path = patch.dict(os.environ,{'PATH':f'{folder}:{os.environ["PATH"]}'})
        path.start()
        self.addCleanup(path.stop)

    def test_library_scan_reads_music_dir_and_root_wins(self):
        code, result = self.run_cli('library','scan','--json')
        self.assertEqual((code,result['action'],result['data']),(0,'library scan',{'root':str(self.music),'tracks':[],'read':0}))
        self.assertEqual(self.run_cli('library','scan','--root',str(self.home),'--json')[1]['data']['root'],str(self.home))

    def test_library_lookup_and_apply_pass_their_files(self):
        with patch.object(cmd_music.library,'lookup',return_value={'plan':'p'}) as lookup:
            self.assertEqual(self.run_cli('library','lookup','--out','p','--json')[1]['data'],{'plan':'p'})
        lookup.assert_called_once_with(str(self.music),'p')
        code, result = self.run_cli('library','apply','--plan',str(self.home/'nada'),'--json')
        self.assertEqual((code,result['ok'],result['error']['code']),(1,False,'not_found'))

    def test_organize_gives_the_plan_moves_and_explains_refusals(self):
        with patch.object(cmd_music.organize,'read_tags',return_value=('','')):
            for name in ('Rap/WLO - Um.mp3','Downloads/WLO - Dois.mp3','Downloads/Novo - Três.mp3'):
                (self.music/name).write_text('')
            plan = self.run_cli('organize','plan','--json')[1]
            self.assertEqual((plan['action'],sorted(plan['data'])),('organize plan',['folders','moves','unknown']))
            done = self.run_cli('organize','apply','--json')[1]['data']
            self.assertEqual(([m['folder'] for m in done['moved']],done['skipped'],[u['artist'] for u in done['unknown']]),(['Rap'],[],['Novo']))
            new = self.music/'Downloads/Novo - Três.mp3'
            code, result = self.run_cli('organize','move',str(new),'Nada','--json')
            self.assertEqual((code,result['error']['code'],result['error']['message']),(1,'invalid','pasta desconhecida: Nada'))
            self.assertEqual(self.run_cli('organize','move','--json','--',str(new),'Rap')[1]['data']['moved'][0]['folder'],'Rap')
        self.assertTrue((self.music/'Rap/Novo - Três.mp3').is_file())

    def test_organize_without_the_folder_says_so(self):
        code, result = self.run_cli('organize','apply','--root',str(self.home/'x'),'--json')
        self.assertEqual((code,result['error']['code'],result['error']['message']),
                         (1,'not_found','pasta de música não existe: '+str(self.home/'x')))

    def test_radio_saved_add_and_search(self):
        self.assertEqual(self.run_cli('radio','saved','--json')[1]['data']['stations'],[])
        self.assertEqual(self.run_cli('radio','add','--name=-A-','--url=http://a/b','--json')[1]['data']['added'],{'name':'-A-','url':'http://a/b'})
        code, result = self.run_cli('radio','add','--name','A','--url','http://a/b','--json')
        self.assertEqual((code,result['error']['message']),(1,'já está salva: A'))
        with patch.object(cmd_music.radio,'search',return_value={'server':'s','stations':[]}) as search:
            self.run_cli('radio','search','--tag','jazz','--limit','9999','--json')
        search.assert_called_once_with('','jazz',500)

    def test_online_search_by_text_link_and_playlist(self):
        self.ytdlp('for a; do q=$a; done; case "$q" in ytsearch25:*) echo \'{"entries":[{"title":"T","channel":"C","url":"u","duration":61},{"title":"sem url"},null]}\' ;;'
                   ' *list*) echo \'{"title":"L","entries":[{"url":"p1"}]}\' ;; *) echo \'{"title":"V","artist":"A","webpage_url":"w","url":"cdn"}\' ;; esac\n')
        self.assertEqual(self.run_cli('online','status','--json')[1]['data'],{'ytdlp':True})
        self.assertEqual(self.run_cli('online','search','--json','--','-oi')[1]['data'],{'link':False,'playlist':None,
                         'results':[{'title':'T','artist':'C','path':'u','duration_secs':61,'stream':True}]})
        one = self.run_cli('online','search','https://y/v','--json')[1]['data']
        self.assertEqual((one['link'],one['playlist'],one['results'][0]['path'],one['results'][0]['artist']),(True,None,'w','A'))
        many = self.run_cli('online','search','https://y/?list=1','--json')[1]['data']
        self.assertEqual((many['playlist'],many['results'][0]['title']),({'title':'L','url':'https://y/?list=1'},'p1'))

    def test_online_search_says_why_it_failed(self):
        self.ytdlp('echo "aviso" >&2; echo "ERROR: quebrou" >&2; exit 1\n')
        code, result = self.run_cli('online','search','x','--json')
        self.assertEqual((code,result['error']['code'],result['error']['message']),(1,'failed','ERROR: quebrou'))
        self.assertEqual(self.run_cli('online','search',' ','--json')[1]['error']['code'],'invalid')
        (self.home/'bin/yt-dlp').write_text('#!/bin/sh\nexec sleep 5\n')
        with patch.object(cmd_music.ytdl,'SEARCH_LIMIT',0.2):
            self.assertEqual(self.run_cli('online','search','x','--json')[1]['error']['code'],'busy')
        with patch.object(cmd_music.ytdl,'installed',return_value=False):
            self.assertEqual(self.run_cli('online','status','--json')[1]['data'],{'ytdlp':False})
            self.assertEqual(self.run_cli('online','search','x','--json')[1]['error']['code'],'not_found')

    def test_a_cancelled_online_search_stops_yt_dlp(self):
        self.ytdlp(f'echo $$ > {self.home}/pid; exec sleep 20\n')
        search = subprocess.Popen([sys.executable,str(ROOT/'extras/rice.py'),'online','search','x','--json'],
                                  stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.addCleanup(search.kill)
        pid = self.home/'pid'
        for _ in range(100):
            if pid.is_file() and pid.read_text().strip():
                break
            time.sleep(0.05)
        child = int(pid.read_text())
        search.terminate()
        self.assertEqual(search.wait(timeout=5),143)
        with self.assertRaises(ProcessLookupError):
            os.kill(child,0)

    def test_yt_dlp_dies_when_lw_is_killed(self):
        # SIGKILL: o lw não tem chance de limpar nada; quem avisa o yt-dlp é o kernel.
        self.ytdlp(f'echo $$ > {self.home}/pid; exec sleep 20\n')
        (self.home/'bin/ffmpeg').write_text('#!/bin/sh\n')
        (self.home/'bin/ffmpeg').chmod(0o755)
        pid = self.home/'pid'
        for command in (['online','search','x','--json'],['download','https://y/v','--root',str(self.music)]):
            with self.subTest(command=command[0]):
                pid.unlink(missing_ok=True)
                lw = subprocess.Popen([sys.executable,str(ROOT/'extras/rice.py'),*command],
                                      stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                self.addCleanup(lw.kill)
                for _ in range(100):
                    if pid.is_file() and pid.read_text().strip():
                        break
                    time.sleep(0.05)
                child = int(pid.read_text())
                lw.kill()
                lw.wait(timeout=5)
                for _ in range(40):
                    if not running(child):
                        break
                    time.sleep(0.05)
                alive = running(child)
                if alive:
                    os.kill(child,signal.SIGKILL)
                self.assertFalse(alive)

    def test_download_streams_events_without_envelope(self):
        with patch.object(cmd_music.ytdl,'download',return_value=0) as download:
            self.assertEqual(cli.main(['download','https://y/v','--playlist']),0)
        download.assert_called_once_with('https://y/v',str(self.music),True)
        out = StringIO()
        with redirect_stdout(out):
            self.assertEqual(cli.main(['download','naoelink']),1)
        self.assertEqual([json.loads(l)['event'] for l in out.getvalue().splitlines()],['end'])

    def test_lw_music_opens_the_window_on_music(self):
        with patch.object(cli,'gui',return_value=0) as gui:
            self.assertEqual(cli.main(['music']),0)
        gui.assert_called_once_with('music')


class Games(unittest.TestCase):
    """game, compat e emu: a lógica do games.py, compat.py e emulators.py no envelope do lw."""
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        env = patch.dict(os.environ,{'HOME':str(self.home),'XDG_CONFIG_HOME':str(self.home/'.config'),'XDG_STATE_HOME':str(self.home/'state'),
                                     'XDG_CACHE_HOME':str(self.home/'cache'),'XDG_DATA_HOME':str(self.home/'data')})
        env.start()
        self.addCleanup(env.stop)
        self.exe = self.home/'jogo.sh'
        self.exe.write_text('#!/bin/sh\n')

    def run_cli(self, *argv):
        out = StringIO()
        with redirect_stdout(out):
            code = cli.main([*argv,'--json'])
        return code, json.loads(out.getvalue())

    def data(self, *argv):
        code, result = self.run_cli(*argv)
        self.assertEqual((code,result['ok'],result['action'],result['warnings']),(0,True,' '.join(argv[:2]),[]),result)
        return result['data']

    def refused(self, *argv):
        code, result = self.run_cli(*argv)
        self.assertEqual((code,result['ok'],result['error']['code']),(1,False,'invalid'))
        return result['error']['message']

    def test_the_library_goes_through_the_envelope(self):
        self.assertEqual(self.data('game','list'),{'games':[]})
        gid = self.data('game','add','--exe',str(self.exe),'--title','Um','--args=-x')['added']['id']
        self.assertEqual(self.data('game','scan')['total'],1)
        self.assertEqual(self.data('game','set',gid,'notes=--json não é opção','status=playing')['game']['notes'],'--json não é opção')
        self.assertEqual(self.data('game','arrange','done',gid),{'status':'done','ids':[gid]})
        self.assertEqual(self.data('game','arrange','want'),{'status':'want','ids':[]})
        self.assertEqual(self.data('game','running'),{'running':cmd_games.games.running()})
        self.assertEqual(self.data('game','recover'),{'session':None})
        self.assertEqual(self.data('game','seen','7'),{'notified':7})
        self.assertEqual(self.data('game','stop',gid),{'signalled':0})
        self.assertEqual(self.data('game','installers'),{'installers':[],'ready':[]})
        self.assertEqual(sorted(self.data('game','tools')),['gamemode','gamescope','mangohud','proton'])
        self.assertEqual(self.data('game','prefixes'),{'prefixes':[]})
        self.assertEqual(self.data('game','rec-hide','7'),{'hidden':1})
        self.assertEqual(self.data('game','rec-hide','--clear'),{'hidden':0})
        self.assertEqual(self.data('game','remove',gid),{'removed':gid})

    def test_the_same_data_as_the_script(self):
        self.data('game','add','--exe',str(self.exe))
        for name in ('list','installers','running','recover'):
            out = StringIO()
            with redirect_stdout(out):
                cmd_games.games.main([name])
            plain = json.loads(out.getvalue())
            self.assertIs(plain.pop('ok'),True)
            self.assertEqual(self.data('game',name),plain)

    def test_refusals_keep_their_message(self):
        self.assertEqual(self.refused('game','launch','x'),'jogo não encontrado: x')
        self.assertEqual(self.refused('game','remove','x'),'jogo não encontrado: x')
        self.assertEqual(self.refused('game','set','x','status=done'),'jogo não encontrado: x')
        self.assertEqual(self.refused('game','arrange','nada'),'status inválido: nada')
        self.assertEqual(self.refused('game','add','--exe','/nada'),'executável não encontrado: /nada')
        self.assertEqual(self.refused('game','install','/nada'),'instalador não encontrado: /nada')
        self.assertEqual(self.refused('game','install-add','/nada','/x'),'instalação não registrada: /nada')
        self.assertEqual(self.refused('game','install-forget','/nada'),'instalação não registrada: /nada')
        self.assertEqual(self.refused('game','played-add','7'),'sugestão não encontrada: 7')
        self.assertEqual(self.refused('emu','set','nada','res','1'),'emulador desconhecido: nada')

    def test_the_rest_passes_its_arguments(self):
        with patch.object(cmd_games.games,'meta',return_value={'matched':[],'missed':[]}) as meta:
            self.data('game','meta','a','b')
            self.data('game','meta','--all')
        self.assertEqual([c.args for c in meta.call_args_list],[(['a','b'],False),([],True)])
        with patch.object(cmd_games.games,'install',return_value={}) as install, patch.object(cmd_games.games,'add_ready',return_value={}) as ready:
            self.data('game','install','/s','--name','N')
            self.data('game','add-ready','/e','--name','N')
        install.assert_called_once_with('/s','N')
        ready.assert_called_once_with('/e','N')
        with patch.object(cmd_games.compat,'check',return_value={'games':[]}), patch.object(cmd_games.compat,'scan',return_value={'cpu':'x'}):
            self.assertEqual((self.data('compat','check'),self.data('compat','scan')),({'games':[]},{'cpu':'x'}))
        with patch.object(cmd_games.emulators,'pads',return_value={'pads':[]}), patch.object(cmd_games.emulators,'apply_pad',return_value={'applied':'x'}), \
             patch.object(cmd_games.emulators,'pad_save',return_value={'saved':'n'}) as save:
            self.assertEqual((self.data('emu','pads'),self.data('emu','apply-pad','pcsx2')),({'pads':[]},{'applied':'x'}))
            self.data('emu','pad-save','g','n','a=b0','b=b1')
        save.assert_called_once_with('g','n',['a=b0','b=b1'])
        self.assertIn('pcsx2',[e['id'] for e in self.data('emu','list')['emulators']])

    def test_the_watchers_are_not_commands(self):
        # O vigia da sessão e o da instalação rodam direto: desligar JOGOS não pode pará-los.
        for name in ('watch','install-run'):
            with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
                cli.main(['game',name,'x'])

    def test_pad_watch_streams_without_envelope(self):
        with patch.object(cmd_games.emulators,'watch',side_effect=lambda event: print('{"ready": true}')) as watch:
            out = StringIO()
            with redirect_stdout(out):
                self.assertEqual(cli.main(['emu','pad-watch','event3']),0)
        watch.assert_called_once_with('event3')
        self.assertEqual(out.getvalue(),'{"ready": true}\n')
        for error, code in ((KeyboardInterrupt(),0),(BrokenPipeError(),0),(OSError('sumiu'),1)):
            out = StringIO()
            with redirect_stdout(out), patch.object(cmd_games.emulators,'watch',side_effect=error):
                self.assertEqual(cli.main(['emu','pad-watch','event3']),code)
            self.assertEqual(out.getvalue(),'{"error": "sumiu"}\n' if code else '')

    def test_lw_games_opens_the_window_on_games(self):
        with patch.object(cli,'gui',return_value=0) as gui:
            self.assertEqual(cli.main(['games']),0)
        gui.assert_called_once_with('games')


class CliampSync(unittest.TestCase):
    """lw cliamp sync: music.dir manda no initial_directory do cliamp."""
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        env = patch.dict(os.environ,{'HOME':str(self.home),'XDG_CONFIG_HOME':str(self.home/'.config'),
                                     'XDG_STATE_HOME':str(self.home/'state')})
        env.start()
        self.addCleanup(env.stop)
        self.conf = self.home/'.config/cliamp/config.toml'
        self.conf.parent.mkdir(parents=True)

    def sync(self):
        out = StringIO()
        with redirect_stdout(out):
            code = cli.main(['cliamp','sync','--json'])
        return code, json.loads(out.getvalue())

    def music_dir(self, value):
        path = self.home/'.config/lw/config.toml'
        path.parent.mkdir(exist_ok=True)
        path.write_text(f'[music]\ndir = "{value}"\n')

    def backups(self):
        return sorted((self.home/'state/rice-minimal/cliamp/backups').glob('*'))

    def test_only_that_value_changes_with_backup_and_mode(self):
        text = '# meu\ntheme = "rice"\ninitial_directory = "~/Músicas" # pasta\neq = [\n  0,\n]\n[x]\ninitial_directory = "fica"\n'
        self.conf.write_text(text)
        self.conf.chmod(0o600)
        (self.home/'Áudio').mkdir()
        self.music_dir('~/Áudio')
        code, result = self.sync()
        self.assertEqual((code,result['ok'],result['action'],result['warnings']),(0,True,'cliamp sync',[]))
        self.assertEqual((result['data']['dir'],result['data']['exists'],result['data']['changed']),(str(self.home/'Áudio'),True,True))
        self.assertEqual(self.conf.read_text(),text.replace('"~/Músicas"','"~/Áudio"'))
        self.assertEqual(self.conf.stat().st_mode & 0o777,0o600)
        self.assertEqual([p.read_text() for p in self.backups()],[text])
        self.assertEqual(result['data']['backup'],str(self.backups()[0]))
        self.assertEqual([p.name for p in self.conf.parent.iterdir()],['config.toml'])
        self.assertFalse(self.sync()[1]['data']['changed'])       # de novo: nada a fazer
        self.assertEqual(len(self.backups()),1)

    def test_same_folder_written_in_full_is_not_touched(self):
        self.conf.write_text(f'initial_directory = "{self.home}/Músicas/"\n')
        self.assertFalse(self.sync()[1]['data']['changed'])
        self.assertEqual(self.backups(),[])

    def test_default_wins_over_a_folder_edited_in_cliamp(self):
        self.conf.write_text('initial_directory = "/outra"\n')
        code, result = self.sync()
        self.assertTrue(result['data']['changed'])
        self.assertEqual(self.conf.read_text(),'initial_directory = "~/Músicas"\n')
        self.assertFalse((self.home/'.config/lw/config.toml').exists())   # nunca o contrário

    def test_missing_key_is_added_at_the_top_level(self):
        self.conf.write_text('[soundcloud]\nenabled = true\n')
        self.sync()
        self.assertEqual(self.conf.read_text(),'initial_directory = "~/Músicas"\n[soundcloud]\nenabled = true\n')

    def test_special_characters_are_escaped_and_links_stay_links(self):
        real = self.home/'dotfiles.toml'
        real.write_text('initial_directory = "~/Músicas"\n')
        self.conf.symlink_to(real)
        (self.home/'.config/lw').mkdir()
        (self.home/'.config/lw/config.toml').write_text("[music]\ndir = '/m/a\"b\\1'\n")
        self.assertTrue(self.sync()[1]['data']['changed'])
        self.assertTrue(self.conf.is_symlink())
        import tomllib
        self.assertEqual(tomllib.loads(real.read_text())['initial_directory'],'/m/a"b\\1')

    def test_broken_or_missing_file_is_not_written(self):
        code, result = self.sync()
        self.assertEqual((code,result['data']['changed'],len(result['warnings'])),(0,False,2))
        self.assertFalse(self.conf.exists())
        self.conf.write_text('initial_directory = \n')
        code, result = self.sync()
        self.assertEqual((code,result['ok'],result['error']['code']),(1,False,'invalid'))
        self.assertEqual((self.conf.read_text(),self.backups()),('initial_directory = \n',[]))


if __name__ == '__main__':
    unittest.main()
