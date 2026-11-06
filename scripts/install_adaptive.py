#!/usr/bin/env python3
"""Apply small include hooks after reviewing the prepared Phase 3 backup."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()

def append_once(text, line):
    return text if line in text else text.rstrip()+'\n\n'+line+'\n'

def plan():
    files = {}
    for source, target in [
        ('rice-adaptive.fish','.config/fish/conf.d/rice-adaptive.fish'),
        ('rice-adaptive-nvim.lua','.config/nvim/rice-adaptive.lua'),
        ('rice-adaptive-hypr.lua','.config/hypr/config/rice-adaptive.lua'),
    ]:
        files[HOME/target] = ((ROOT/'extras/theme'/source).read_text(), 0o644)
    path = HOME/'.config/kitty/kitty.conf'
    files[path] = (append_once(path.read_text(), 'include '+str(HOME/'.local/state/rice-minimal/theme/current/kitty.conf')), 0o644)
    path = HOME/'.config/nvim/init.lua'
    files[path] = (append_once(path.read_text(), 'dofile(vim.fn.expand("~/.config/nvim/rice-adaptive.lua"))'), 0o644)
    path = HOME/'.config/hypr/hyprland.lua'
    files[path] = (append_once(path.read_text(), 'require("config.rice-adaptive")'), 0o644)
    path = HOME/'.config/fish/config.fish'
    text = path.read_text()
    if '    rice_theme_refresh\n' not in text:
        text = text.replace('    set_color normal\n    printf', '    rice_theme_refresh\n    set_color $rice_prompt_color\n    printf', 1)
        text = text.replace('        printf \' [%s]\' $last_status',
                            '        set_color $rice_error_color\n        printf \' [%s]\' $last_status\n        set_color $rice_prompt_color', 1)
        text = text.replace("    printf ' > '\nend", "    printf ' > '\n    set_color normal\nend", 1)
    if 'rice_theme_refresh' not in text:
        raise RuntimeError('Fish prompt changed; refusing an unexpected replacement')
    files[path] = (text, 0o644)
    path = HOME/'.config/waypaper/config.ini'
    text = path.read_text()
    if not re.search(r'^backend\s*=\s*none\s*$', text, re.M):
        raise RuntimeError('Waypaper backend changed; refusing to start another renderer')
    hook = 'post_command = /usr/bin/python3 '+shlex.quote(str(ROOT/'extras/theme/theme.py'))+' wallpaper'
    text, count = re.subn(r'^post_command\s*=.*$', lambda _:hook, text, flags=re.M)
    if count != 1:
        raise RuntimeError('Expected exactly one Waypaper post_command')
    files[path] = (text, 0o644)
    for name, entry in [('supers','extras/supers/Supers'),('rice','extras/rice.py'),('wallpapers','extras/wallpapers/wallpaper_tui.py')]:
        files[HOME/'.local/bin'/name] = ('#!/bin/sh\nexec /usr/bin/python3 '+shlex.quote(str(ROOT/entry))+' "$@"\n', 0o755)
    return {p:(text,mode) for p,(text,mode) in files.items() if not p.exists() or p.read_text() != text}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    files = plan()
    print('\n'.join(str(p) for p in files) or 'Already installed; no configuration changes')
    if not args.apply or not files:
        return
    backup = Path((ROOT/'.phase3-backup').read_text().strip())
    manifest = {Path(item['path']):item for item in json.loads((backup/'manifest.json').read_text())}
    for path in files:
        if path not in manifest:
            raise RuntimeError(f'No prepared backup entry: {path}')
        saved = manifest[path]['backup']
        if saved and path.read_bytes() != Path(saved).read_bytes():
            raise RuntimeError(f'File changed since backup: {path}; no files written')
        if not saved and path.exists():
            raise RuntimeError(f'New file appeared since backup: {path}; no files written')
    subprocess.run(['python3',str(ROOT/'extras/theme/theme.py'),'cached'], check=True)
    for path, (text, mode) in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.rice-', dir=path.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, mode)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    print('Installed with prepared backup:', backup)

if __name__ == '__main__':
    main()
