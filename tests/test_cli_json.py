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
        with patch.object(theme,'regenerate',return_value='matugen 4.2 / scheme-vibrant / dark'), patch.object(theme,'sync_greeter'), patch.object(cli.signal,'signal'):
            self.assertTrue(self.run_cli('palette','regenerate','--scheme','vibrant','--json')[1]['ok'])
        self.assertEqual(theme.scheme(),'scheme-vibrant')
        with patch.object(theme,'regenerate',return_value='kept-last-palette'), patch.object(theme,'sync_greeter'), patch.object(cli.signal,'signal'):
            self.run_cli('palette','regenerate','--scheme','expressive','--json')
        self.assertEqual(theme.scheme(),'scheme-vibrant')


class Profile(Envelope):
    def set_profile(self, name, previous=None):
        (self.state/'profile').write_text(name+'\n')
        if previous:
            (self.state/'previous-profile').write_text(previous+'\n')

    def test_differences_come_from_the_files_that_apply_the_profiles(self):
        rows = {r['setting']:r for r in cli.profile_differences()}
        self.assertEqual(rows['hyprland animations']['refined'],'on')
        self.assertEqual(rows['workspace switch']['minimal'],'instant')
        self.assertRegex(rows['workspace switch']['refined'],r'^slide \d+ ms$')
        self.assertEqual(rows['noctalia shell.animation.enabled']['minimal'],'off')
        self.assertEqual(rows['greeter waits for colors']['refined'],f'{theme.GREETER_SETTLE} s')
        # Settings equal in both profiles never appear.
        self.assertFalse(any('rounding' in name or 'font' in name for name in rows))

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
        hypr = patch.object(cli.shortcuts,'live_conflict',return_value=False)
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
        self.assertEqual(cli.shortcuts.display_key('mainMod .. " + SHIFT + mouse_up"'),'SUPER + SHIFT + mouse_up')
        self.assertEqual(cli.shortcuts.display_key('mainMod .. " + ALT + BackSpace"'),'SUPER + ALT + BackSpace')

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
        with patch.object(cli.shortcuts.subprocess,'run',return_value=self.active({'modmask':64,'key':'BackSpace','keycode':0})):
            self.assertTrue(cli.shortcuts.live_conflict(('SUPER','BACKSPACE')))
            self.assertFalse(cli.shortcuts.live_conflict(('ALT','SUPER','BACKSPACE')))

    def test_number_row_binds_are_matched_by_keycode(self):
        with patch.object(cli.shortcuts.subprocess,'run',return_value=self.active({'modmask':64,'key':'','keycode':10})):
            self.assertTrue(cli.shortcuts.live_conflict(('SUPER','1')))

    def test_no_session_means_no_live_conflict(self):
        with patch.object(cli.shortcuts.subprocess,'run',side_effect=FileNotFoundError):
            self.assertFalse(cli.shortcuts.live_conflict(('SUPER','Q')))


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
        with patch.object(cli.lockscreen,'run_trial') as trial, patch.object(cli.lockscreen,'activate') as activate:
            self.assertFalse(self.run_cli('lock','trial','--json')[1]['ok'])
            self.assertFalse(self.run_cli('lock','activate','--json')[1]['ok'])
        trial.assert_not_called()
        activate.assert_not_called()

    def test_trial_survives_gui_closing_and_logs_failure(self):
        with patch.object(cli.lockscreen,'run_trial',side_effect=RuntimeError('Lock was not confirmed')), patch.object(cli.signal,'signal') as block:
            code, result = self.run_cli('lock','trial','--confirm','--json')
        self.assertEqual((code,result['ok']),(1,False))
        block.assert_any_call(cli.signal.SIGTERM,cli.signal.SIG_IGN)
        self.assertIn('Lock was not confirmed',(self.state/'actions.jsonl').read_text())

    def test_trial_is_valid_only_for_the_layout_it_saw(self):
        self.stamp('lock-displays.json',20)
        self.stamp('lock-tested',10)
        self.assertTrue(cli.lockscreen.tested())
        self.stamp('lock-displays.json',5)
        self.assertFalse(cli.lockscreen.tested())
        with self.assertRaises(RuntimeError):
            cli.lockscreen.activate()

    def test_same_monitors_keep_the_trial_and_new_ones_invalidate_it(self):
        self.stamp('lock-displays.json',20)
        self.stamp('lock-tested',10)
        with patch.object(theme,'command',side_effect=self.command):
            cli.lockscreen.capture_displays()
            self.assertTrue(cli.lockscreen.tested())
            self.monitors = [{'name':'DP-1','width':2560,'height':1440,'scale':1}]
            cli.lockscreen.capture_displays()
        self.assertFalse(cli.lockscreen.tested())

    def test_status_reads_candidate_and_session(self):
        with patch.object(theme,'command',side_effect=self.command):
            data = self.run_cli('lock','status','--json')[1]['data']
        self.assertEqual((data['effective_dim'],data['session_locked'],data['enabled']),(.6,False,False))

    def test_dim_accepts_the_slider_steps_and_nothing_else(self):
        for level in ('10','50','57','90'):
            with patch.object(sys,'stderr',StringIO()), self.assertRaises(SystemExit):
                cli.main(['lock','dim',level])
        with patch.object(cli.lockscreen,'set_dim',return_value=.65) as set_dim:
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
    def press(self, section, shown='', hidden='no'):
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            if args[:2] == ['qs','list']:
                return subprocess.CompletedProcess(args,0,stdout='')
            op = args[-1] if args[-2] == 'lw' else args[-2]
            answers = {'section': shown, 'hidden': hidden}
            if op in answers:
                return subprocess.CompletedProcess(args,0 if shown else 1,stdout=answers[op]+'\n' if shown else '')
            return subprocess.CompletedProcess(args,0,stdout='')
        self.started = None
        def execvp(*args):
            self.started = cli.os.environ.get('LW_START_GROUP')
        with patch.object(cli.subprocess,'run',side_effect=run), patch.object(cli.os,'execvp',side_effect=execvp) as launch, \
             patch.object(theme,'STATE',Path(tempfile.gettempdir())), patch.dict(cli.os.environ,{'XDG_RUNTIME_DIR':tempfile.mkdtemp()}):
            self.assertEqual(cli.gui(section),0 if shown else None)
        ops = [c[c.index('lw')+1:] for c in calls if 'lw' in c]
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

if __name__ == '__main__':
    unittest.main()
