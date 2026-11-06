"""Restore real file/symlink trees in a disposable HOME, keeping rescue data."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from restore_refined import restore


class Restore(unittest.TestCase):
    def test_files_palette_generations_and_rescue(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            home, root, backup = (base/name for name in ('home','project','backup'))
            root.mkdir()
            live = home/'.config/hypr/hyprland.lua'
            live.parent.mkdir(parents=True)
            live.write_text('refined include')
            saved = backup/'original.lua'
            saved.parent.mkdir(parents=True)
            saved.write_text('phase3 includes')
            palette = home/'.config/noctalia/palettes/RiceMinimal.json'
            palette.parent.mkdir(parents=True)
            palette.write_text('phase4 palette')
            (backup/'manifest.json').write_text(json.dumps([
                {'path':str(live),'backup':str(saved)},
                {'path':str(palette),'backup':None}]))
            old = backup/'theme/old-generation'
            old.mkdir(parents=True)
            (old/'palette.json').write_text('old palette')
            (backup/'theme/current').symlink_to('old-generation')
            state = home/'.local/state/rice-minimal/theme'
            state.mkdir(parents=True)
            (state/'profile').write_text('refined')
            (backup/'project/config').mkdir(parents=True)
            (backup/'project/config/original').write_text('phase3')
            (root/'config').mkdir()
            (root/'config/original').write_text('phase4')
            rescue = restore(backup,root=root,home=home,reload=False)
            self.assertEqual(live.read_text(),'phase3 includes')
            self.assertFalse(palette.exists())
            self.assertEqual((state/'current/palette.json').read_text(),'old palette')
            self.assertEqual((root/'config/original').read_text(),'phase3')
            self.assertEqual((rescue/'theme-live/profile').read_text(),'refined')
            self.assertEqual((rescue/'home/.config/hypr/hyprland.lua').read_text(),'refined include')

if __name__ == '__main__':
    unittest.main()
