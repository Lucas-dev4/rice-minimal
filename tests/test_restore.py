"""restore.py checks first, keeps a restorable rescue and rolls back on failure."""
# Testes do scripts/restore.py: restauração com resgate e volta automática.
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rice_restore', ROOT/'scripts/restore.py')
restore = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore)


class Restore(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        self.home, self.backup = base/'home', base/'backup'
        self.live = self.home/'.config/hypr/hyprland.lua'
        self.live.parent.mkdir(parents=True)
        self.live.write_text('current')
        self.extra = self.home/'.config/noctalia/rice-lock.toml'
        self.extra.parent.mkdir(parents=True)
        self.extra.write_text('overlay')
        saved = self.backup/'home/hyprland.lua'
        saved.parent.mkdir(parents=True)
        saved.write_text('original')
        self.manifest([{'path':str(self.live),'backup':str(saved)},{'path':str(self.extra),'backup':None}])
        self.state = self.home/'.local/state/rice-minimal/theme'
        self.state.mkdir(parents=True)
        (self.state/'profile').write_text('refined')
        (self.backup/'theme/palette-old').mkdir(parents=True)
        (self.backup/'theme/profile').write_text('minimal')
        (self.backup/'theme/current').symlink_to('palette-old')

    def manifest(self, entries):
        (self.backup/'manifest.json').write_text(json.dumps(entries))

    def test_restores_files_theme_and_the_rescue_undoes_it(self):
        rescue = restore.restore(self.backup, home=self.home, reload=False)
        self.assertEqual(self.live.read_text(), 'original')
        self.assertFalse(self.extra.exists())
        self.assertEqual((self.state/'profile').read_text(), 'minimal')
        self.assertTrue((self.state/'current').is_symlink())
        restore.restore(rescue, home=self.home, reload=False)
        self.assertEqual((self.live.read_text(), self.extra.read_text()), ('current', 'overlay'))
        self.assertEqual((self.state/'profile').read_text(), 'refined')

    def test_missing_backup_copy_changes_nothing(self):
        self.manifest([{'path':str(self.live),'backup':str(self.backup/'gone.lua')}])
        with self.assertRaises(restore.BackupError):
            restore.restore(self.backup, home=self.home, reload=False)
        self.assertEqual(self.live.read_text(), 'current')
        self.assertEqual(list(self.backup.glob('before-restore-*')), [])

    def test_paths_outside_home_are_refused(self):
        self.manifest([{'path':'/etc/greetd/config.toml','backup':None}])
        with self.assertRaises(restore.BackupError):
            restore.restore(self.backup, home=self.home, reload=False)

    def test_failure_halfway_puts_everything_back(self):
        real = restore.put
        calls = []
        def flaky(target, source):
            calls.append(target)
            if len(calls) == 2:
                raise OSError('disk full')
            return real(target, source)
        with patch.object(restore, 'put', side_effect=flaky), self.assertRaises(OSError):
            restore.restore(self.backup, home=self.home, reload=False)
        self.assertEqual((self.live.read_text(), self.extra.read_text()), ('current', 'overlay'))
        self.assertEqual((self.state/'profile').read_text(), 'refined')

    def test_preview_changes_nothing(self):
        from contextlib import redirect_stdout
        from io import StringIO
        with patch('sys.argv', ['restore.py', str(self.backup)]), patch.object(restore.Path, 'home', return_value=self.home), redirect_stdout(StringIO()):
            self.assertEqual(restore.main(), 0)
        self.assertEqual(self.live.read_text(), 'current')


if __name__ == '__main__':
    unittest.main()
