#!/usr/bin/env python3
"""Restore an implementation backup. Saves current files before restoring."""
import argparse
import datetime
import json
from pathlib import Path
import shutil
parser = argparse.ArgumentParser()
parser.add_argument('backup', type=Path)
args = parser.parse_args()
backup = args.backup.expanduser().resolve()
manifest = json.loads((backup/'manifest.json').read_text())
rescue = backup / ('before-restore-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
for item in reversed(manifest):
    target = Path(item['path'])
    if target.exists() or target.is_symlink():
        saved = rescue / target.relative_to(Path.home())
        saved.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            saved.symlink_to(target.readlink())
        else:
            shutil.copy2(target, saved)
    if item['backup']:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item['backup'], target)
    elif target.is_file() or target.is_symlink():
        target.unlink()
print('Restaurado. Estado anterior à restauração:', rescue)
print('Sem reload automático. Confira a sessão antes de executar hyprctl reload.')
