"""The installer must never take over files the user already customized."""
import configparser
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('deploy', ROOT/'scripts/deploy.py')
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)
SOURCE = ROOT/'config/waypaper/config.ini'


class Waypaper(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.target = Path(temp.name)/'config.ini'

    def write(self, post_command):
        self.target.write_text(f"""[Settings]
folder = ~/Imagens/Wallpapers
wallpaper = ~/Imagens/Wallpapers/mine.png
post_command = {post_command}
number_of_columns = 3
stylesheet = /home/lucas/.config/waypaper/style.css
backend = none
fill = fill
sort = name
color = #111111
show_hidden = False
show_gifs_only = False
""")

    def test_same_hook_with_full_python_path_changes_nothing(self):
        self.write('/usr/bin/python3 /home/lucas/Projetos/rice-minimal/extras/theme/theme.py wallpaper')
        self.assertIsNone(deploy.desired(SOURCE,self.target))

    def test_missing_hook_is_added_without_touching_the_rest(self):
        self.write('swww img $wallpaper')
        result = configparser.ConfigParser(interpolation=None)
        result.read_string(deploy.desired(SOURCE,self.target).decode())
        self.assertTrue(deploy.hook_installed(result['Settings']['post_command']))
        self.assertEqual(result['Settings']['wallpaper'],'~/Imagens/Wallpapers/mine.png')
        self.assertEqual(result['Settings']['number_of_columns'],'3')

    def test_absent_file_gets_the_project_copy(self):
        self.assertEqual(deploy.desired(SOURCE,self.target),SOURCE.read_bytes())

    def test_live_config_needs_no_change(self):
        live = Path.home()/'.config/waypaper/config.ini'
        if not live.exists():
            self.skipTest('no live Waypaper config')
        self.assertIsNone(deploy.desired(SOURCE,live))


if __name__ == '__main__':
    unittest.main()
