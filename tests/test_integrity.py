# Confere que config/integrity.json está em dia (rode scripts/integrity.py depois de editar).
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Integrity(unittest.TestCase):
    def test_integrity_list_matches_the_files(self):
        # `rice doctor` reports FAIL when config/integrity.json is stale; refresh it with
        # scripts/integrity.py after editing a managed file.
        result = subprocess.run([sys.executable, str(ROOT/'scripts'/'integrity.py'), '--check'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, 'run scripts/integrity.py:\n' + result.stdout)


if __name__ == '__main__':
    unittest.main()
