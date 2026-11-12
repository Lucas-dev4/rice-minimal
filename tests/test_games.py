import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'extras'))
import games  # noqa: E402

LIBRARY_FOLDERS = '''"libraryfolders"
{
	"0"
	{
		"path"		"%s"
		"apps" { "620" "123" }
	}
	"1"
	{
		"path"		"%s"
	}
}
'''
MANIFEST = '''"AppState"
{
	"appid"		"%s"
	"name"		"%s"
	"installdir"		"%s"
}
'''
LOCALCONFIG = '''"UserLocalConfigStore"
{
	"Software" { "Valve" { "Steam" { "apps" {
		"620" { "LastPlayed" "1700000000" "Playtime" "125" }
		"999" { "Playtime" "0" }
	} } } }
}
'''


class Games(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        env = patch.dict(os.environ, {'HOME': str(self.home), 'XDG_DATA_HOME': str(self.home/'data')})
        env.start()
        self.addCleanup(env.stop)

    def cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = games.main(list(argv))
        return code, json.loads(out.getvalue())

    def steam(self):
        root = self.home/'.local/share/Steam'
        extra = self.home/'Disco2/SteamLibrary'
        for lib in (root, extra):
            (lib/'steamapps').mkdir(parents=True)
        (root/'steamapps/libraryfolders.vdf').write_text(LIBRARY_FOLDERS % (root, extra))
        (root/'steamapps/appmanifest_620.acf').write_text(MANIFEST % ('620', 'Portal 2', 'Portal 2'))
        (root/'steamapps/appmanifest_1493710.acf').write_text(MANIFEST % ('1493710', 'Proton Experimental', 'Proton - Experimental'))
        (extra/'steamapps/appmanifest_999.acf').write_text(MANIFEST % ('999', 'Hollow Knight', 'Hollow Knight'))
        cache = root/'appcache/librarycache'
        cache.mkdir(parents=True)
        (cache/'620_library_600x900.jpg').write_bytes(b'old layout')
        (cache/'999/abc123').mkdir(parents=True)
        (cache/'999/abc123/library_600x900.jpg').write_bytes(b'new layout')
        (root/'userdata/42/config').mkdir(parents=True)
        (root/'userdata/42/config/localconfig.vdf').write_text(LOCALCONFIG)
        return root, extra

    def test_steam_reads_every_library_both_art_layouts_and_playtime(self):
        root, extra = self.steam()
        found = {g['id']: g for g in games.scan_steam()}
        self.assertEqual(set(found), {'steam:620', 'steam:999'})       # Proton is a tool, not a game
        self.assertTrue(found['steam:620']['cover'].endswith('620_library_600x900.jpg'))
        self.assertTrue(found['steam:999']['cover'].endswith('999/abc123/library_600x900.jpg'))
        self.assertEqual(found['steam:620']['hours_source'], 2.1)     # 125 minutes
        self.assertEqual(found['steam:620']['launch'], 'steam steam://rungameid/620')

    def test_rescan_keeps_your_data_and_marks_missing_instead_of_deleting(self):
        root, extra = self.steam()
        self.assertEqual(self.cli('scan')[1]['new'], 2)
        self.cli('set', 'steam:620', 'status=playing', 'notes=fase 3', 'progress=40', 'est_hours=12')
        (extra/'steamapps/appmanifest_999.acf').unlink()
        code, result = self.cli('scan')
        self.assertEqual((result['new'], result['missing']), (0, 1))
        db = {g['id']: g for g in games.load()['games']}
        self.assertEqual((db['steam:620']['status'], db['steam:620']['notes'], db['steam:620']['progress'], db['steam:620']['est_hours']),
                         ('playing', 'fase 3', 40, 12.0))
        self.assertTrue(db['steam:999']['missing'])
        self.assertEqual(self.cli('remove', 'steam:999')[0], 0)
        self.assertEqual(len(games.load()['games']), 1)

    def test_roms_pick_the_core_by_extension_and_clean_the_title(self):
        roms = self.home/'ROMs/gba'
        roms.mkdir(parents=True)
        (roms/'Pokemon Emerald (USA) [!].gba').write_bytes(b'rom')
        (roms/'leia-me.txt').write_text('x')
        found = games.scan_roms()
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0]['title'], found[0]['system']), ('Pokemon Emerald', 'gba'))
        self.assertIn('mgba_libretro.so', found[0]['launch'])

    def test_wine_games_are_added_by_hand_once_and_validated(self):
        exe = self.home/'Jogos/NFS/NFS11.exe'
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b'MZ')
        code, result = self.cli('add', '--exe', str(exe), '--prefix', str(self.home/'.wine_dodi'), '--title', 'NFS Hot Pursuit')
        self.assertEqual(code, 0)
        launch = result['added']['launch']
        self.assertIn('WINEPREFIX=', launch)
        self.assertIn('wine ', launch)
        self.assertEqual(self.cli('add', '--exe', str(exe))[0], 1)            # no duplicates
        self.assertEqual(self.cli('add', '--exe', str(self.home/'nada.exe'))[0], 1)
        gid = result['added']['id']
        self.assertEqual(self.cli('set', gid, 'status=zerado')[0], 1)       # only want|playing|done|dropped
        self.assertEqual(self.cli('set', gid, 'hours=99')[0], 1)            # hours come from sessions only
        exe.unlink()
        self.cli('scan')
        self.assertTrue(games.load()['games'][0]['missing'])

    def test_hydra_entries_with_an_executable_are_imported(self):
        db = self.home/'.config/hydralauncher/hydra-db'
        db.mkdir(parents=True)
        (db/'000008.log').write_bytes(
            b'\x00junk{"title":"Need For Speed: Hot Pursuit","shop":"steam","objectId":"47870",'
            b'"executablePath":"/home/x/Games/NFS/NFS11.exe","winePrefixPath":"/home/x/.wine_dodi","isDeleted":false}'
            b'{"title":"Sem exe","objectId":"1","isDeleted":false}')
        found = games.scan_hydra()
        self.assertEqual([g['title'] for g in found], ['Need For Speed: Hot Pursuit'])
        self.assertEqual(found[0]['source'], 'hydra')

    def test_running_finds_lw_launches_and_steam_games(self):
        proc = self.home/'proc'
        for pid, env in (('10', b'PATH=/usr/bin\0LW_GAME_ID=wine:abc\0'), ('11', b'SteamAppId=620\0'),
                         ('12', b'SteamAppId=0\0'), ('self', b'LW_GAME_ID=nope\0')):
            (proc/pid).mkdir(parents=True)
            (proc/pid/'environ').write_bytes(env)
        self.assertEqual(games.running(proc), ['steam:620', 'wine:abc'])

    def test_wine_helpers_are_not_the_game(self):
        proc = self.home/'proc'
        for pid, comm in (('20', 'NFS11.exe'), ('21', 'wineserver'), ('22', 'explorer.exe')):
            (proc/pid).mkdir(parents=True)
            (proc/pid/'environ').write_bytes(b'LW_GAME_ID=wine:nfs\0')
            (proc/pid/'comm').write_text(comm + '\n')
        self.assertEqual(games.pids_of('wine:nfs', proc), [20])
        (proc/'20/environ').write_bytes(b'')
        self.assertEqual(games.running(proc), [])     # only Wine helpers left: the game is over

    def test_wrappers_only_when_toggled_and_installed_and_never_for_steam(self):
        game = {'source': 'wine', 'launch': 'wine x.exe', 'gamemode': True, 'mangohud': True}
        with patch.object(games, 'tools', return_value={'gamemode': True, 'mangohud': False}):
            self.assertEqual(games.command_for(game), 'gamemoderun wine x.exe')
            self.assertEqual(games.command_for(dict(game, source='steam', launch='steam steam://rungameid/1')), 'steam steam://rungameid/1')

    def test_a_session_adds_hours_moves_want_to_playing_and_recover_closes_at_the_heartbeat(self):
        exe = self.home/'g.exe'
        exe.write_bytes(b'MZ')
        gid = self.cli('add', '--exe', str(exe))[1]['added']['id']
        def opened(d):
            d['open_session'] = {'id': gid, 'start': 1000, 'seen': 1000 + 5400}
        games.update(opened)
        with patch.object(games, 'pids_of', return_value=[]):
            result = games.recover()
        self.assertEqual((result['session'], result['added_hours']), ('closed', 1.5))
        db = games.load()
        game = db['games'][0]
        self.assertEqual((game['hours'], game['status'], game['last_played'], len(game['sessions'])), (1.5, 'playing', 6400, 1))
        self.assertNotIn('open_session', db)
        self.assertEqual(db['last_session']['hours'], 1.5)

    def test_arrange_sets_a_whole_column_in_one_write(self):
        ids = []
        for name in ('a', 'b', 'c'):
            exe = self.home/f'{name}.exe'
            exe.write_bytes(b'MZ')
            ids.append(self.cli('add', '--exe', str(exe))[1]['added']['id'])
        self.assertEqual(self.cli('arrange', 'done', ids[2], ids[0])[0], 0)
        db = {g['id']: g for g in games.load()['games']}
        self.assertEqual([(db[i]['status'], db[i]['order'], db[i]['progress']) for i in (ids[2], ids[0])], [('done', 1, 100), ('done', 2, 100)])
        self.assertEqual(db[ids[1]]['status'], 'want')
        self.assertEqual(self.cli('arrange', 'zerado', ids[1])[0], 1)

    # ---- installers ------------------------------------------------------------------
    def test_clean_name_drops_tags_and_brackets(self):
        self.assertEqual(games.clean_name('Need For Speed Hot Pursuit - [DODI Repack]'), 'Need For Speed Hot Pursuit')
        self.assertEqual(games.clean_name('Hollow_Knight (GOG)'), 'Hollow Knight')

    def test_installers_one_per_folder_without_redistributables(self):
        down = self.home/'Downloads'
        game = down/'hydra/Jogo Bom - [Repack]'
        (game/'_Redist').mkdir(parents=True)
        for f in ('Setup.exe', 'setup-a.bin', 'Install_Helper.exe'):
            (game/f).write_bytes(b'x')
        (game/'_Redist/vcredist_x64.exe').write_bytes(b'x')
        (down/'GOG_installer.exe').write_bytes(b'x')
        (down/'deep/a/b/c').mkdir(parents=True)
        (down/'deep/a/b/c/setup.exe').write_bytes(b'x')   # four levels down: not looked at
        found = {i['name']: i for i in self.cli('installers')[1]['installers']}
        self.assertEqual(sorted(found), ['GOG installer', 'Jogo Bom'])
        self.assertTrue(found['Jogo Bom']['setup'].endswith('Setup.exe'))
        self.assertIsNone(found['Jogo Bom']['install'])

    def test_candidates_prefer_the_game_over_tools(self):
        prefix = self.home/'Games/jogo-bom'
        root = prefix/'drive_c/Games/Jogo Bom'
        (root/'bin').mkdir(parents=True)
        (prefix/'drive_c/windows/system32').mkdir(parents=True)
        (root/'bin/JogoBom.exe').write_bytes(b'x' * 50)
        (root/'Launcher.exe').write_bytes(b'x' * 500)
        (root/'unins000.exe').write_bytes(b'x' * 900)
        (prefix/'drive_c/windows/system32/notepad.exe').write_bytes(b'x' * 900)
        found = [Path(c['exe']).name for c in games.candidates(prefix, time.time() - 30, 'Jogo Bom')]
        self.assertEqual(found, ['JogoBom.exe', 'Launcher.exe'])

    def test_install_flow_records_and_adds_with_its_prefix(self):
        setup = self.home/'Downloads/Jogo/setup.exe'
        setup.parent.mkdir(parents=True)
        setup.write_bytes(b'x')
        with patch('shutil.which', return_value='/usr/bin/wine'), patch.object(games.subprocess, 'Popen') as worker:
            record = self.cli('install', str(setup))[1]['install']
        self.assertEqual((record['state'], record['prefix']), ('running', str(self.home/'Games/jogo')))
        self.assertEqual(worker.call_args.args[0][-2:], ['install-run', str(setup)])
        self.assertFalse(self.cli('install', str(setup))[1]['ok'])   # one at a time
        exe = self.home/'Games/jogo/drive_c/Games/Jogo/Jogo.exe'
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b'x')
        with patch.object(games.subprocess, 'run') as run:
            run.return_value.returncode = 0
            self.assertEqual([Path(c['exe']).name for c in self.cli('install-run', str(setup))[1]['candidates']], ['Jogo.exe'])
        self.assertEqual(games.load()['installs'][str(setup)]['state'], 'done')
        added = self.cli('install-add', str(setup), str(exe))[1]['added']
        self.assertEqual((added['title'], added['prefix']), ('Jogo', str(self.home/'Games/jogo')))
        self.assertEqual(games.load()['installs'][str(setup)]['state'], 'added')
        self.assertTrue(self.cli('install-forget', str(setup))[1]['ok'])
        self.assertNotIn(str(setup), games.load().get('installs', {}))

    # ---- Proton and wrappers ----------------------------------------------------------
    def wrapped(self, have, **flags):
        game = games.wine_entry('/g/pfx/drive_c/Jogo/Jogo.exe', '/g/pfx', 'Jogo', args='-dx11')
        game.update(flags)
        with patch.object(games, 'tools', return_value=dict({'gamemode': False, 'mangohud': False, 'proton': False, 'gamescope': False}, **have)), \
             patch.object(games, 'screen_size', return_value=(1920, 1080, 75)):
            return games.command_for(game)

    def test_wine_by_default_proton_when_on(self):
        self.assertEqual(self.wrapped({}), 'env WINEPREFIX=/g/pfx wine /g/pfx/drive_c/Jogo/Jogo.exe -dx11')
        self.assertEqual(self.wrapped({'proton': True}, proton=True),
                         'env WINEPREFIX=/g/pfx GAMEID=umu-default PROTONPATH=GE-Proton umu-run /g/pfx/drive_c/Jogo/Jogo.exe -dx11')
        # Toggled but umu-run missing: plain Wine, never a broken command.
        self.assertTrue(self.wrapped({}, proton=True).startswith('env WINEPREFIX=/g/pfx wine '))

    def test_wrapper_order_and_fsr(self):
        cmd = self.wrapped({'proton': True, 'gamescope': True, 'mangohud': True, 'gamemode': True},
                           proton=True, gamescope=True, fsr=True, mangohud=True, gamemode=True)
        self.assertTrue(cmd.startswith('gamemoderun gamescope -f -W 1920 -H 1080 -r 75 -w 1440 -h 810 -F fsr -- mangohud env '))
        self.assertNotIn('-F fsr', self.wrapped({'gamescope': True}, gamescope=True))

    def test_proton_helpers_do_not_keep_a_session_open(self):
        for name in ('umu-run', 'reaper', 'gamescope', 'wineserver'):
            self.assertIn(name, games.WINE_SYSTEM)

    # ---- IGDB --------------------------------------------------------------------------
    def test_best_match_wants_the_main_entry_and_refuses_guesses(self):
        results = [{'id': 1, 'name': 'Need for Speed: Hot Pursuit - Remastered'},
                   {'id': 2, 'name': 'Need for Speed: Hot Pursuit', 'parent_game': 9},
                   {'id': 9, 'name': 'Need for Speed: Hot Pursuit', 'total_rating_count': 411},
                   {'id': 3, 'name': 'Need for Speed: Hot Pursuit 2'}]
        self.assertEqual(games.best_match('Need For Speed Hot Pursuit', results)['id'], 9)
        self.assertIsNone(games.best_match('Jogo Inventado', results))

    def test_meta_fills_only_empty_fields(self):
        mine = self.home/'mine.jpg'
        mine.write_bytes(b'x')
        for title, cover in (('Hollow Knight', None), ('Celeste', str(mine)), ('Nada Disso', None)):
            exe = self.home/(title + '.exe')
            exe.write_bytes(b'x')
            self.cli('add', '--exe', str(exe), '--title', title)
        def setup(d):
            for g in d['games']:
                if g['title'] == 'Celeste':
                    g.update(cover=str(mine), est_hours=40.0)
        games.update(setup)
        answers = {'Hollow Knight': [{'id': 11, 'name': 'Hollow Knight', 'genres': [{'name': 'Platform'}], 'cover': {'image_id': 'hk'}, 'similar_games': [21]}],
                   'Celeste': [{'id': 12, 'name': 'Celeste', 'cover': {'image_id': 'ce'}}],
                   'Nada Disso': [{'id': 13, 'name': 'Outra Coisa'}]}
        class Fake:
            def query(self, endpoint, body):
                if endpoint == 'game_time_to_beats':
                    return [{'normally': 27 * 3600, 'completely': 60 * 3600}]
                if body.startswith('search'):
                    return answers[body.split('"')[1]]
                return [{'id': 21, 'name': 'Hollow Knight: Silksong', 'genres': [], 'cover': {'image_id': 'sk'}}]
        with patch.object(games, 'Igdb', Fake), patch.object(games, 'fetch_cover', side_effect=lambda image, gid: f'/covers/{image}.jpg'):
            result = self.cli('meta')[1]
        self.assertEqual((sorted(result['matched']), result['missed']), (['Celeste', 'Hollow Knight'], ['Nada Disso']))
        by = {g['title']: g for g in games.load()['games']}
        self.assertEqual((by['Hollow Knight']['cover'], by['Hollow Knight']['est_hours']), ('/covers/hk.jpg', 27.0))
        self.assertEqual((by['Celeste']['cover'], by['Celeste']['est_hours']), (str(mine), 40.0))   # mine stay
        self.assertEqual(by['Hollow Knight']['igdb']['ttb'], {'normally': 27.0, 'completely': 60.0})
        self.assertNotIn('name', by['Nada Disso']['igdb'])
        self.assertEqual(games.load()['igdb_similar']['21']['name'], 'Hollow Knight: Silksong')
        # Already looked up: a second run does not even ask Twitch for a token.
        with patch.object(games, 'Igdb', side_effect=AssertionError('queried again')):
            self.assertEqual(self.cli('meta')[1], {'ok': True, 'matched': [], 'missed': []})


if __name__ == '__main__':
    unittest.main()
