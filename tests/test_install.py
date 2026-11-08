"""The installer renders paths, never clobbers user files and is transactional."""
import configparser
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
install = load('rice_install', ROOT/'scripts/install.py')
restore = load('rice_restore', ROOT/'scripts/restore.py')


class Install(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)/'bob'
        self.home.mkdir()
        for name, value in (('HOME', self.home), ('STATE', self.home/'.local/state/rice-minimal/theme')):
            patcher = patch.object(install, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_fresh_home_gets_every_file_with_its_own_paths(self):
        changes = install.plan()
        targets = {str(p.relative_to(self.home)) for p in changes}
        for _, target in install.FILES + install.SEEDS:
            self.assertIn(target, targets)
        self.assertIn('.local/bin/rice', targets)
        integration = changes[self.home/'.config/hypr/config/rice-integration.lua'][0]
        self.assertIn(f'{self.home}/.local/bin/rice gui', integration)
        self.assertNotIn('/home/lucas/.local', integration)
        self.assertIn(str(ROOT), changes[self.home/'.local/bin/rice'][0])
        self.assertTrue(changes[self.home/'.config/kitty/kitty.conf'][0].rstrip().endswith('/current/kitty.conf'))

    def test_checkout_path_is_not_rewritten_twice(self):
        with patch.object(install, 'ROOT', Path('/home/lucas/Projetos/rice-minimal')):
            self.assertEqual(install.render('/home/lucas/Projetos/rice-minimal/x /home/lucas/y'),
                             f'/home/lucas/Projetos/rice-minimal/x {self.home}/y')

    def test_apply_is_idempotent_and_keeps_user_seeds(self):
        install.apply(install.plan(), backups=self.home/'backups')
        seed = self.home/'.config/cliamp/config.toml'
        seed.write_text('theme = "mine"\n')
        self.assertEqual(install.plan(), {})
        self.assertEqual(seed.read_text(), 'theme = "mine"\n')

    def test_theme_names_change_only_their_own_lines(self):
        env = self.home/'.config/uwsm/env'
        env.parent.mkdir(parents=True)
        env.write_text('export EDITOR=nvim\nexport XCURSOR_THEME="Bibata"\nexport XCURSOR_SIZE=24\n')
        env.chmod(0o600)
        qt = self.home/'.config/qt6ct/qt6ct.conf'
        qt.parent.mkdir(parents=True)
        qt.write_text('[Appearance]\ncolor_scheme_path=/x/noctalia.conf\nicon_theme=breeze\nstyle=Fusion\n')
        changes = install.plan()
        self.assertEqual(changes[env], ('export EDITOR=nvim\nexport XCURSOR_THEME="Adwaita"\nexport XCURSOR_SIZE=24\n', 0o600))
        self.assertIn('icon_theme=Adwaita\nstyle=Fusion', changes[qt][0])
        self.assertNotIn(self.home/'.config/gtk-3.0/settings.ini', changes)  # absent files are not created

    def test_hyprland_requires_are_added_once(self):
        hypr = self.home/'.config/hypr/hyprland.lua'
        hypr.parent.mkdir(parents=True)
        hypr.write_text('require("config.binds")\nrequire("config.rice-minimal")\n')
        text = install.plan()[hypr][0]
        self.assertEqual(text.count('require("config.rice-minimal")'), 1)
        for module in install.HYPR_MODULES:
            self.assertIn(f'require("config.{module}")', text)

    def test_waypaper_keeps_the_user_settings_and_only_fixes_the_hook(self):
        config = self.home/'.config/waypaper/config.ini'
        config.parent.mkdir(parents=True)
        config.write_text('[Settings]\nfolder = ~/Imagens\nwallpaper = ~/mine.png\nnumber_of_columns = 3\npost_command = swww img $wallpaper\n'
                          'backend = none\nfill = fill\nsort = name\ncolor = #111111\nshow_hidden = False\nshow_gifs_only = False\n')
        result = configparser.ConfigParser(interpolation=None)
        result.read_string(install.waypaper(config))
        self.assertTrue(install.hook_installed(result['Settings']['post_command']))
        self.assertEqual((result['Settings']['wallpaper'], result['Settings']['number_of_columns']), ('~/mine.png', '3'))
        config.write_text(config.read_text().replace('swww img $wallpaper', f'/usr/bin/python3 {ROOT}/extras/theme/theme.py wallpaper'))
        self.assertIsNone(install.waypaper(config))

    def test_invalid_file_stops_everything_before_any_write(self):
        broken = {self.home/'.config/nvim/init.lua': ('if then end end', 0o644),
                  self.home/'.config/yazi/yazi.toml': ('[ok]\n', 0o644)}
        with self.assertRaises(Exception):
            install.apply(broken, backups=self.home/'backups')
        self.assertFalse((self.home/'.config/yazi/yazi.toml').exists())
        self.assertFalse((self.home/'backups').exists())

    def test_failed_write_rolls_back_and_backup_restores(self):
        kitty = self.home/'.config/kitty/kitty.conf'
        kitty.parent.mkdir(parents=True)
        kitty.write_text('mine\n')
        changes = {kitty: ('new kitty\n', 0o644), self.home/'.config/yazi/yazi.toml': ('[mgr]\n', 0o644)}
        real = os.replace
        calls = []
        def flaky(src, dst):
            calls.append(dst)
            if len(calls) == 2:
                raise OSError('disk full')
            return real(src, dst)
        with patch.object(install.os, 'replace', side_effect=flaky), self.assertRaises(OSError):
            install.apply(changes, backups=self.home/'backups')
        self.assertEqual(kitty.read_text(), 'mine\n')
        self.assertFalse((self.home/'.config/yazi/yazi.toml').exists())
        backup = install.apply(changes, backups=self.home/'backups')
        self.assertEqual(kitty.read_text(), 'new kitty\n')
        restore.restore(backup, home=self.home, reload=False)
        self.assertEqual(kitty.read_text(), 'mine\n')
        self.assertFalse((self.home/'.config/yazi/yazi.toml').exists())

    def test_live_system_has_nothing_pending(self):
        real = Path.home()/'.config/hypr/hyprland.lua'
        if not real.exists():
            self.skipTest('no live installation')
        with patch.object(install, 'HOME', Path.home()), patch.object(install, 'STATE', Path.home()/'.local/state/rice-minimal/theme'):
            self.assertEqual(install.plan(), {})


if __name__ == '__main__':
    unittest.main()
