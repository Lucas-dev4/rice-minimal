#!/usr/bin/env python3
"""Navigate Waypaper's existing image library; apply only on Enter."""
import argparse
import curses
import json
from pathlib import Path
import random
import sys

EXTRAS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXTRAS))
from theme import theme
import ui

def filtered(paths, query):
    return [p for p in paths if query.casefold() in p.name.casefold()]

def selector(screen):
    ui.setup(screen)
    paths = theme.images()
    current = theme.current_wallpaper()
    query, message, index, editing = '', '', 0, False
    while True:
        matches = filtered(paths, query)
        index = min(index, max(0,len(matches)-1))
        height, _ = ui.frame(screen, f'WALLPAPERS [{len(matches):02d}]')
        visible = max(1,height-7)
        start = max(0, index-visible+1)
        for row, path in enumerate(matches[start:start+visible], 2):
            position = row-2+start
            active = bool(current and path.resolve() == current.resolve())
            ui.text(screen, row, 2, f'{">" if position == index else " "} {path.name} {"*" if active else ""}',
                    ui.selected() if position == index else 0)
        if not matches:
            ui.text(screen, 2, 2, '(no matching images)')
        ui.text(screen, height-4, 2, '/'+query if editing or query else message)
        ui.text(screen, height-2, 2, 'j/k: move | Enter: apply | /: search | r: random | q: quit')
        ui.present(screen)
        key = screen.get_wch()
        if editing:
            if key in ('\n','\r'):
                editing = False
            elif key == '\x1b':
                editing, query = False, ''
            elif key in ('\x7f','\b',curses.KEY_BACKSPACE):
                query = query[:-1]
            elif isinstance(key, str) and key.isprintable():
                query += key
            index = 0
            continue
        if key in ('q','\x1b'):
            return
        if key in ('j',curses.KEY_DOWN):
            index = min(index+1,max(0,len(matches)-1))
        elif key in ('k',curses.KEY_UP):
            index = max(0,index-1)
        elif key == '/':
            editing = True
        elif key == 'r' and matches:
            index = random.randrange(len(matches))
        elif key in ('\n','\r') and matches:
            chosen = matches[index]
            try:
                ui.text(screen, height-4, 2, 'Applying wallpaper + colors...')
                ui.present(screen)
                result = theme.apply_choice(chosen)
                current = theme.current_wallpaper()
                message = 'Applied: '+chosen.name+' / '+result
                query = ''
            except Exception as exc:
                message = 'Error: '+str(exc)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true', help='List without starting curses or changing wallpaper')
    parser.add_argument('--apply', type=Path, help='Apply through the same Waypaper hook used by Enter')
    args = parser.parse_args()
    if args.list:
        current = theme.current_wallpaper()
        print(json.dumps({'folder':str(theme.library()[0]), 'current':str(current) if current else None,
                          'images':[str(p) for p in theme.images()]}, ensure_ascii=False, indent=2))
    elif args.apply:
        print(theme.apply_choice(args.apply.expanduser()))
    else:
        curses.wrapper(selector)

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'wallpapers: {exc}', file=sys.stderr)
        sys.exit(1)
