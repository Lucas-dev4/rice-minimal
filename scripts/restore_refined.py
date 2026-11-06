#!/usr/bin/env python3
"""Restore Phase 3 project and live files, retaining a rescue snapshot."""
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
def restore(backup, *, root=ROOT, home=None, reload=True):
    home = home or Path.home()
    manifest = json.loads((backup/'manifest.json').read_text())
    # Finalization may create an overlay after this snapshot was taken.
    overlay = home/'.config/noctalia/rice-lock.toml'
    if not any(Path(item['path']) == overlay for item in manifest):
        manifest.append({'path':str(overlay),'backup':None})
    rescue = backup/('before-restore-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    rescue.mkdir(parents=True)
    state = home/'.local/state/rice-minimal/theme'
    if state.exists():
        shutil.copytree(state,rescue/'theme',symlinks=True)
    for item in manifest:
        target = Path(item['path'])
        if target.exists() or target.is_symlink():
            saved = rescue/'home'/target.relative_to(home)
            saved.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(target,saved)
            if target.is_symlink():
                target.unlink()
        if item['backup']:
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(item['backup'],target)
        elif target.exists():
            target.unlink()
    # Move rather than delete generations; retain all current state in rescue.
    if state.exists():
        shutil.move(str(state),str(rescue/'theme-live'))
    if (backup/'theme').exists():
        shutil.copytree(backup/'theme',state,symlinks=True)
    for path in (backup/'project').iterdir():
        current = root/path.name
        if current.is_dir():
            shutil.copytree(current,rescue/'project'/path.name,symlinks=True)
            shutil.copytree(path,current,dirs_exist_ok=True)
        else:
            (rescue/'project').mkdir(parents=True,exist_ok=True)
            shutil.copy2(current,rescue/'project'/path.name)
            shutil.copy2(path,current)
    if reload:
        subprocess.run(['hyprctl','reload','config-only'],check=True)
        subprocess.run(['noctalia','msg','config-reload'],check=True)
        subprocess.run(['python3',str(root/'extras/theme/theme.py'),'cached'],check=True)
        subprocess.run(['python3','-c','import sys; sys.path.insert(0,"extras"); from theme import theme; theme.reload_components()'],cwd=root,check=True)
        if subprocess.run(['pgrep','-u',str(os.getuid()),'-x','waybar'],capture_output=True).returncode == 0:
            subprocess.run(['noctalia','msg','bar-hide'],check=True)
    return rescue


if __name__ == '__main__':
    backup = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv)>1 else Path((ROOT/'.phase4-backup').read_text().strip())
    print('Fase 3 restored. Rescue:',restore(backup))
