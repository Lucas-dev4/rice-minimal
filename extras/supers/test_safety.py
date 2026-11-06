import importlib.machinery
from pathlib import Path
import tempfile
import unittest
from safe_io import safe_write, lua_string, normalize_key
supers = importlib.machinery.SourceFileLoader('supers_app', str(Path(__file__).with_name('Supers'))).load_module()

class Safety(unittest.TestCase):
    def test_atomic_backup_validation_and_concurrency(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'binds.lua'
            original = 'local mainMod = "SUPER"\n'
            p.write_text(original)
            with self.assertRaises(Exception):
                safe_write(p, original, 'this is invalid Lua !')
            self.assertEqual(p.read_text(), original)
            changed = original + 'local command = ' + lua_string('code "a\\b"') + '\n'
            backup = safe_write(p, original, changed)
            self.assertEqual(backup.read_text(), original)
            with self.assertRaises(ValueError):
                safe_write(p, original, original)
            safe_write(p, changed, backup.read_text())
            self.assertEqual(p.read_text(), original)
    def test_parser_preserves_options_and_excludes_dynamic_keys(self):
        lines = ['hl.bind(mainMod .. " + A", hl.dsp.exec_cmd("echo \\"x\\""), { locked = true })\n',
                 'hl.bind(mainMod .. " + " .. digitCode(1), hl.dsp.focus({ monitor = MONITOR1 }))\n']
        parsed = supers.parse_binds(lines)
        self.assertEqual(len(parsed), 1)
        self.assertIn('echo', parsed[0]['action_clean'])
        self.assertNotIn('locked', parsed[0]['action_clean'])
    def test_normalization_and_injection(self):
        self.assertEqual(normalize_key('mainMod .. " + SHIFT + A"'), normalize_key('"SHIFT + SUPER + a"'))
        with self.assertRaises(ValueError):
            supers.format_lua_key('A"); os.execute("bad")')

if __name__ == '__main__':
    unittest.main()
