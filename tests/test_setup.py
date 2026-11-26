# Testes da TUI do "lw setup" (extras/setup_tui.py): tela de curses falsa, lw falso, nada é instalado.
import curses
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'extras'))
import setup_tui  # noqa: E402
import ui  # noqa: E402

DOWN, TAB, SPACE, ENTER = curses.KEY_DOWN, 9, ord(' '), 10


class Screen:
    """Uma tela de curses na memória: guarda as linhas desenhadas e entrega as teclas da lista."""
    def __init__(self, keys, size=(30, 140)):
        self.keys, self.size = list(keys), size
        self.erase()

    def getmaxyx(self):
        return self.size

    def erase(self):
        self.rows = [' ' * self.size[1] for _ in range(self.size[0])]

    def addnstr(self, y, x, text, n, attr=0):
        text = text[:n]
        self.rows[y] = self.rows[y][:x] + text + self.rows[y][x + len(text):]

    def getch(self):
        return self.keys.pop(0) if self.keys else ord('q')

    def text(self):
        return '\n'.join(row.rstrip() for row in self.rows)


def dep(name, key, optional=False, found='', manual=''):
    return {'name': name, 'key': key, 'optional': optional, 'why': 'para ' + name, 'found': found,
            'package': '' if manual else key, 'aur': '', 'manual': manual}


class FakeLw:
    """Responde como o lw: dois módulos, dependências fixas; anota cada chamada."""
    def __init__(self):
        self.calls = []
        self.modules = [{'id': 'system', 'name': 'SISTEMA', 'description': 'A base.', 'enabled': True, 'required': True},
                        {'id': 'music', 'name': 'MÚSICA', 'description': 'Toca músicas.', 'enabled': True, 'required': False}]
        self.deps = {'system': [dep('kitty', 'kitty', found='/usr/bin/kitty')],
                     'music': [dep('cliamp', '', manual='ver o README'), dep('pactl', 'libpulse'),
                               dep('cava', 'cava', optional=True), dep('gio', 'glib2', optional=True, found='/usr/bin/gio')]}

    def __call__(self, *argv):
        self.calls.append(argv)
        if argv[:2] == ('modules', 'list'):
            return {'ok': True, 'data': self.modules}
        if argv[1] in ('enable', 'disable'):
            return {'ok': True, 'data': {'enabled': argv[1] == 'enable'}}
        picks = [argv[i + 1] for i, a in enumerate(argv) if a == '--pick']
        return {'ok': True, 'data': {'dependencies': self.deps[argv[2]], 'install': {
            'commands': [['sudo', 'pacman', '-S', '--needed', *picks]] if picks else [], 'blocked': []}}}


class Tui(unittest.TestCase):
    def setUp(self):
        for target in (patch.object(curses, 'has_colors', return_value=False), patch.object(ui, 'present'),
                       patch.dict(os.environ, {'RICE_NO_ANIMATIONS': '1'})):
            target.start()
            self.addCleanup(target.stop)
        self.lw = FakeLw()
        self.launched = []

    def run_keys(self, *keys, code=0):
        self.screen = Screen(keys)
        def launch(screen, argv):
            self.launched.append(argv)
            return code
        self.setup = setup_tui.Setup(self.screen, run=self.lw, launch=launch)
        self.setup.loop()
        return self.screen.text()

    def test_the_main_panel_shows_the_modules_and_the_key_map(self):
        text = self.run_keys()
        self.assertIn('+-- LW SETUP', text)
        self.assertIn('> [x] SISTEMA   fixo', text)
        self.assertIn('[x] MÚSICA', text)
        self.assertIn('SISTEMA — A base.', text)
        self.assertIn('OK    kitty', text)
        self.assertIn(setup_tui.KEYS['modules'], text)

    def test_space_turns_a_module_off_but_the_system_is_fixed(self):
        text = self.run_keys(SPACE)
        self.assertIn('SISTEMA é fixo', text)
        self.assertFalse([c for c in self.lw.calls if c[1] in ('enable', 'disable')])
        text = self.run_keys(DOWN, SPACE)
        self.assertIn(('modules', 'disable', 'music'), self.lw.calls)
        self.assertIn('[ ] MÚSICA', text)

    def test_the_mini_panel_marks_what_is_missing_required_first(self):
        text = self.run_keys(DOWN, TAB)
        self.assertIn('[x] falta pactl', text)
        self.assertIn('[ ] falta cava · opcional', text)
        self.assertIn('    OK    gio', text)              # instalada: sem caixa
        self.assertIn('falta cliamp · para cliamp · ver o README', text)
        self.assertIn('Comando: sudo pacman -S --needed libpulse', text)
        self.assertIn(setup_tui.KEYS['deps'], text)
        text = self.run_keys(DOWN, TAB, DOWN, DOWN, SPACE)
        self.assertIn('[x] falta cava', text)
        self.assertIn('Comando: sudo pacman -S --needed cava libpulse', text)

    def test_what_has_no_package_or_is_installed_is_not_marked(self):
        self.assertIn('cliamp: ver o README', self.run_keys(DOWN, TAB, SPACE))
        self.assertIn('gio já está instalada', self.run_keys(DOWN, TAB, DOWN, DOWN, DOWN, SPACE))
        self.assertEqual(self.setup.marks['music'], {'libpulse'})

    def test_install_shows_the_command_and_cancel_is_the_default(self):
        self.run_keys(DOWN, ord('i'), ENTER)
        self.assertEqual(self.launched, [])
        self.assertIn('instalação cancelada', self.screen.text())
        self.run_keys(DOWN, ord('i'), ord('q'))
        self.assertEqual(self.launched, [])

    def test_confirm_runs_lw_modules_install_with_the_marks(self):
        screens = []
        original = setup_tui.Setup.confirm
        def seen(this, plan):
            answer = original(this, plan)
            screens.append(this.screen.text())
            return answer
        with patch.object(setup_tui.Setup, 'confirm', seen):
            self.run_keys(DOWN, ord('i'), DOWN, ENTER)
        self.assertIn('sudo pacman -S --needed libpulse', screens[0])
        self.assertIn('O sudo pede a sua senha', screens[0])
        self.assertEqual(self.launched, [[sys.executable, str(setup_tui.RICE), 'modules', 'install', 'music',
                                          '--pick', 'libpulse', '--yes']])
        self.assertIn('[ OK ] instalado', self.screen.text())
        # Depois de instalar, as dependências são lidas de novo.
        self.assertEqual(sum(c[:3] == ('modules', 'deps', 'music') and '--pick' not in c for c in self.lw.calls), 2)

    def test_nothing_marked_installs_nothing(self):
        text = self.run_keys(ord('i'))
        self.assertIn('nada marcado', text)
        self.assertEqual(self.launched, [])

    def test_a_failed_install_says_so(self):
        self.run_keys(DOWN, ord('i'), DOWN, ENTER, code=1)
        self.assertIn('[ FAIL ] a instalação saiu com 1', self.screen.text())

    def test_a_small_terminal_scrolls_the_mini_panel(self):
        self.lw.deps['music'] = [dep(f'p{i}', f'p{i}') for i in range(30)]
        self.screen = Screen([DOWN, TAB] + [DOWN] * 25, size=(24, 100))
        setup_tui.Setup(self.screen, run=self.lw, launch=None).loop()
        text = self.screen.text()
        self.assertIn('> [x] falta p25', text)
        self.assertIn('de 30', text)


class RealLw(unittest.TestCase):
    """A TUI com o lw de verdade (PATH vazio: nada encontrado, nada rodado)."""
    def test_it_draws_from_lw_modules(self):
        with tempfile.TemporaryDirectory() as home, \
                patch.dict(os.environ, {'HOME': home, 'XDG_CONFIG_HOME': home + '/.config', 'PATH': home,
                                        'RICE_NO_ANIMATIONS': '1'}), \
                patch.object(curses, 'has_colors', return_value=False), patch.object(ui, 'present'):
            screen = Screen([DOWN, SPACE])
            setup_tui.Setup(screen, launch=None).loop()
            text = screen.text()
            self.assertIn('[ ] MÚSICA', text)
            self.assertIn('Comando: sudo pacman -S --needed wireplumber libpulse', text)
            self.assertIn('music = false', Path(home, '.config/lw/config.toml').read_text())

    def test_lw_setup_is_a_core_command(self):
        import cli
        self.assertIn('setup', cli.COMMANDS)
        self.assertNotIn('setup', cli.modules.owners())


if __name__ == '__main__':
    unittest.main()
