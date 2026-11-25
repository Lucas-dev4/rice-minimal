# Testes da config do LW (extras/settings.py) e de quem a usa: os padrões são os valores de antes,
# config ausente, parcial e quebrada, e a lista de jogos trocada pelo usuário.
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'extras'))
import compat  # noqa: E402
import games  # noqa: E402
import library  # noqa: E402
import organize  # noqa: E402
import settings  # noqa: E402
import ytdl  # noqa: E402


class Config(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        env = patch.dict(os.environ, {'HOME': str(self.home), 'XDG_CONFIG_HOME': str(self.home/'.config'),
                                      'XDG_DATA_HOME': str(self.home/'data'), 'XDG_STATE_HOME': str(self.home/'.local/state'), 'XDG_CACHE_HOME': str(self.home/'cache')})
        env.start()
        self.addCleanup(env.stop)

    def config(self, text):
        path = self.home/'.config/lw/config.toml'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def legacy(self, data):
        (self.home/'data/lw').mkdir(parents=True, exist_ok=True)
        (self.home/'data/lw/games-config.json').write_text(json.dumps(data))

    def test_without_a_file_the_defaults_are_the_old_values(self):
        h = str(self.home)
        self.assertEqual(settings.get('music', 'dir'), h + '/Músicas')
        self.assertEqual(games.config(), {
            'rom_dirs': [h + '/ROMs', h + '/Jogos/ROMs'], 'ready_dirs': [h + '/Downloads/hydra_Jogos'],
            'emulator_dirs': [h + '/Jogos/Emuladores'], 'download_dirs': [h + '/Downloads'], 'prefix_dir': h + '/Games',
            'retroarch': 'retroarch', 'cores_dir': '/usr/lib/libretro', 'emulators': {},
            'compat_list': 'extras/games-list.json'})
        self.assertEqual(settings.problems(), [])

    def test_partial_file_keeps_the_other_defaults(self):
        self.config('[music]\ndir = "~/Áudio"\n[games]\nrom_dirs = ["~/a", "/b"]\n[games.emulators]\n".xyz" = "emu {rom}"\n')
        self.assertEqual(settings.get('music', 'dir'), str(self.home/'Áudio'))
        cfg = games.config()
        self.assertEqual(cfg['rom_dirs'], [str(self.home/'a'), '/b'])
        self.assertEqual(cfg['emulators'], {'.xyz': 'emu {rom}'})
        self.assertEqual(cfg['retroarch'], 'retroarch')

    def test_broken_file_uses_the_defaults_and_is_reported(self):
        self.config('[music\ndir = 1')
        self.assertEqual(settings.get('music', 'dir'), str(self.home/'Músicas'))
        self.assertIn('config.toml', settings.problems()[0])

    def test_wrong_types_use_the_default_and_are_reported(self):
        self.config('games = 3\n[music]\ndir = ["~/x"]\n')
        self.assertEqual(settings.get('music', 'dir'), str(self.home/'Músicas'))
        self.assertEqual(games.config()['retroarch'], 'retroarch')
        self.assertEqual(sorted(p.split(':')[0] for p in settings.problems()), ['games', 'music.dir'])
        self.config('[music]\ndir = " "\n[games]\nrom_dirs = [1]\nretroarch = "ra"\n')
        self.assertEqual(games.config()['rom_dirs'][0], str(self.home/'ROMs'))
        self.assertEqual(games.config()['retroarch'], 'ra')
        self.assertEqual(sorted(p.split(':')[0] for p in settings.problems()), ['games.rom_dirs', 'music.dir'])

    def test_unknown_module_is_an_error(self):
        with self.assertRaises(ValueError):
            settings.get('nada', 'dir')

    def test_config_toml_wins_over_games_config_json(self):
        self.legacy({'rom_dirs': ['/json'], 'retroarch': 'ra-json'})
        self.config('[games]\nrom_dirs = ["/toml"]\n')
        self.assertEqual((games.config()['rom_dirs'], games.config()['retroarch']), (['/toml'], 'ra-json'))
        self.config('[games]\nrom_dirs = 5\n')       # inválido não passa por cima do JSON
        self.assertEqual(games.config()['rom_dirs'], ['/json'])

    def test_music_commands_use_music_dir_and_root_still_wins(self):
        self.config('[music]\ndir = "~/Áudio"\n')
        for module, argv, target in ((library, ['scan'], 'scan'), (organize, ['plan'], 'plan')):
            (self.home/'Áudio').mkdir(exist_ok=True)
            with patch.object(module, target, return_value={'ok': True} if module is organize else {}) as call, \
                    redirect_stdout(io.StringIO()):
                module.main(argv)
            self.assertEqual(call.call_args.args[0], str(self.home/'Áudio'))
        with patch.object(ytdl, 'download', return_value=0) as call:
            ytdl.main(['download', 'https://x'])
            self.assertEqual(call.call_args.args[1], str(self.home/'Áudio'))
            ytdl.main(['download', 'https://x', '--root', '/r'])
            self.assertEqual(call.call_args.args[1], '/r')

    def test_rom_and_download_folders_come_from_the_config(self):
        rom = self.home/'meus/snes/Jogo (USA).sfc'
        rom.parent.mkdir(parents=True)
        rom.touch()
        self.config('[games]\nrom_dirs = ["~/meus"]\ndownload_dirs = ["~/baixados"]\n')
        self.assertEqual([g['title'] for g in games.scan_roms()], ['Jogo'])
        self.assertEqual(games.download_dirs(), [self.home/'baixados'])

    def test_game_list_can_be_replaced(self):
        self.assertEqual(len(games.played_titles()), 35)
        (self.home/'lista.json').write_text(json.dumps({'list': [{'n': 'Meu Jogo', 'hrs': 3, 'plat': 1}]}))
        self.config('[games]\ncompat_list = "~/lista.json"\n')
        self.assertEqual(games.played_titles(), [{'n': 'Meu Jogo', 'hrs': 3, 'plat': True}])
        self.assertEqual(compat.data()['mystery'], [])
        self.assertEqual(compat.evaluate('Meu Jogo', {}, compat.data())['k'], 'na')

    def test_bad_game_list_is_explained(self):
        self.config('[games]\ncompat_list = "~/lista.json"\n')
        for text in (None, '{', '[]', '{"list": 1}', '{"list": [{"x": 1}]}'):
            if text is not None:
                (self.home/'lista.json').write_text(text)
            self.assertEqual(games.played_titles(), [])
            with self.assertRaisesRegex(ValueError, 'lista de jogos'):
                compat.data()

    # ---- [modules]: ligar e desligar ----
    def text(self):
        return (self.home/'.config/lw/config.toml').read_bytes().decode()

    def backups(self):
        return sorted((self.home/'.local/state/rice-minimal/lw/backups').glob('*'))

    def test_the_first_choice_creates_the_file_and_needs_no_backup(self):
        data = settings.set_module('games', False)
        self.assertEqual(self.text(), '[modules]\ngames = false\n')
        self.assertEqual((data['changed'], data['backup'], self.backups()), (True, None, []))
        self.assertEqual(settings.switches(), {'system': True, 'music': True, 'games': False})

    def test_only_the_line_of_the_module_changes(self):
        for before, after in (
                ('# meu\n[music]\ndir = "~/x" # aqui\n', '# meu\n[music]\ndir = "~/x" # aqui\n\n[modules]\ngames = false\n'),
                ('[music]\ndir = "~/x"', '[music]\ndir = "~/x"\n\n[modules]\ngames = false\n'),
                ('[modules] # eu\nmusic = false\n\n[music]\ndir = "~/x"\n', '[modules] # eu\ngames = false\nmusic = false\n\n[music]\ndir = "~/x"\n'),
                ('[modules]\n  "games"  =  true  # jogos\n[games]\nretroarch = "ra"\n', '[modules]\n  "games"  =  false  # jogos\n[games]\nretroarch = "ra"\n'),
                ('[modules]\ngames = "não"\n', '[modules]\ngames = false\n'),
                ('[modules]', '[modules]\ngames = false'),
                ('[modules]\r\nmusic = false\r\n', '[modules]\r\ngames = false\r\nmusic = false\r\n')):
            with self.subTest(before=before):
                path = self.home/'.config/lw/config.toml'
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(before.encode())
                path.chmod(0o600)
                data = settings.set_module('games', False)
                self.assertEqual(self.text(), after)
                self.assertEqual(Path(data['backup']).read_bytes().decode(), before)
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertFalse(list(path.parent.glob('.lw-*')))
                self.assertIs(settings.switches()['games'], False)

    def test_a_choice_already_made_writes_nothing(self):
        self.assertFalse(settings.set_module('games', True)['changed'])
        self.assertFalse((self.home/'.config/lw/config.toml').exists())
        self.config('[modules]\ngames = false\n')
        self.assertFalse(settings.set_module('games', False)['changed'])
        self.assertEqual(self.backups(), [])

    def test_what_cannot_be_changed_safely_is_refused_untouched(self):
        for text in ('[modules\ngames = true\n', 'modules = { music = false }\n', 'modules.music = false\n', 'modules = 3\n',
                     'x = """\n[modules]\ngames = true\n"""\n'):
            with self.subTest(text=text):
                self.config(text)
                with self.assertRaisesRegex(ValueError, 'config.toml'):
                    settings.set_module('games', False)
                self.assertEqual(self.text(), text)
        self.assertEqual(self.backups(), [])

    def test_a_linked_config_stays_a_link(self):
        real = self.home/'dotfiles.toml'
        real.write_text('[modules]\n')
        path = self.home/'.config/lw/config.toml'
        path.parent.mkdir(parents=True)
        path.symlink_to(real)
        settings.set_module('games', False)
        self.assertTrue(path.is_symlink())
        self.assertEqual(real.read_text(), '[modules]\ngames = false\n')

    def test_system_is_always_on(self):
        with self.assertRaisesRegex(ValueError, 'SISTEMA é obrigatório'):
            settings.set_module('sistema', False)
        self.assertFalse(settings.set_module('system', True)['changed'])
        self.config('[modules]\nsystem = false\n')
        self.assertIs(settings.switches()['system'], True)
        self.assertEqual(settings.problems(), ['modules.system: SISTEMA é obrigatório'])

    def test_bad_choices_use_the_default_and_are_reported(self):
        self.config('[modules]\ngames = "não"\nmusica = false\n')
        self.assertEqual(settings.switches(), {'system': True, 'music': True, 'games': True})
        self.assertEqual(sorted(p.split(':')[0] for p in settings.problems()), ['modules.games', 'modules.musica'])
        self.config('modules = 1\n')
        self.assertEqual((all(settings.switches().values()), settings.problems()), (True, ['modules: esperava uma tabela']))
        self.config('[modules\n')
        self.assertTrue(all(settings.switches().values()))


if __name__ == '__main__':
    unittest.main()
