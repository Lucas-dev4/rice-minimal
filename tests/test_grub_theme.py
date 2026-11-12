import importlib.util
import re
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('grub_theme', Path(__file__).resolve().parent.parent/'scripts'/'grub_theme.py')
grub_theme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grub_theme)


class GrubThemeTest(unittest.TestCase):
    def test_theme_uses_only_built_fonts_and_palette(self):
        colors = {'bg': '#151311', 'fg': '#e8e1dd', 'dim': '#888888', 'faint': '#555555', 'accent': '#eaaf86', 'wallpaper': ''}
        fonts = {(style, size): f'LW Mono {style} {size}' for style in ('Regular', 'Bold') for size in (16, 20, 34)}
        text = grub_theme.theme(colors, fonts)
        used = set(re.findall(r'font(?:\s*=|:)\s*"([^"]+)"', text))
        self.assertTrue(used)
        self.assertTrue(used <= set(fonts.values()), used - set(fonts.values()))
        self.assertIn('id = "__timeout__"', text)
        self.assertIn('selected_item_pixmap_style = "select_*.png"', text)
        self.assertIn('selected_item_color = "#eaaf86"', text)

    def test_mix(self):
        self.assertEqual(grub_theme.mix('#000000', '#ffffff', 0.5), '#808080')


if __name__ == '__main__':
    unittest.main()
