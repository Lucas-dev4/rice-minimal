#!/usr/bin/env python3
"""Rice Minimal: transient curses menu, no background process."""
import curses
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from theme import theme
from wallpapers.wallpaper_tui import selector
import ui

def menu(screen):
    ui.setup(screen)
    message = ''
    while True:
        height, _ = ui.frame(screen, 'RICE MINIMAL / ADAPTIVE')
        entries = ['[1] Wallpapers', '[2] Super shortcuts', '[3] Current palette',
                   '[4] Regenerate colors', '[5] Restore previous theme', '[Q] Exit']
        for row, value in enumerate(entries, 2):
            ui.text(screen, row, 3, value)
        ui.text(screen, height-4, 2, message)
        ui.text(screen, height-2, 2, 'UNIX workstation | no blur | no animation')
        screen.refresh()
        key = screen.getch()
        try:
            if key in (ord('q'),ord('Q'),27):
                return
            if key == ord('1'):
                selector(screen)
            elif key == ord('2'):
                ui.external(screen, [sys.executable, theme.ROOT/'extras/supers/Supers'])
            elif key == ord('3'):
                palette = theme.read_palette()
                lines = [palette.get('generator','unknown'), '', 'Wallpaper: '+palette.get('wallpaper','(emergency)'), '']
                lines += [f'{name:18} {color}' for name,color in palette['colors'].items()]
                lines += ['', 'Sample contrast: '+str(palette.get('contrast',{}))]
                ui.page(screen, 'CURRENT PALETTE', lines)
            elif key == ord('4'):
                ui.text(screen, height-4, 2, 'Generating colors...')
                screen.refresh()
                with theme.locked():
                    message = theme.regenerate(force=True)
            elif key == ord('5'):
                message = 'Restored: '+theme.restore_previous()
        except Exception as exc:
            message = 'Error: '+str(exc)

if __name__ == '__main__':
    curses.wrapper(menu)
