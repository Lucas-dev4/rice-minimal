"""Legacy click requests retain workspace identity without injecting Lua."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from waybar_ipc import translate


class WaybarIPC(unittest.TestCase):
    def test_workspace_number_is_lua_number(self):
        self.assertEqual(translate(b'dispatch workspace 3'),b'eval hl.dispatch(hl.dsp.focus({workspace=3}))')

    def test_relative_workspace_and_queries(self):
        self.assertIn(b'workspace="e+1"',translate(b'dispatch workspace e+1'))
        self.assertEqual(translate(b'j/workspaces'),b'j/workspaces')
        self.assertEqual(translate(b'eval return 1'),b'eval return 1')

    def test_names_are_quoted_as_data(self):
        self.assertIn(b'\\"',translate(b'dispatch workspace name:a"b'))

if __name__ == '__main__':
    unittest.main()
