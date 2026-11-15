#!/usr/bin/env python3
"""Restore a rice backup safely.

Works with every backup that has a manifest.json (install, deploy, phase and
full backups). Without --apply it only lists what would happen. With --apply it:

1. checks the whole backup first and changes nothing if any piece is missing;
2. saves the current files and theme state as a rescue backup, itself restorable;
3. restores, and puts everything back from the rescue if anything fails.

Project code is never touched: it lives in git (git log, git checkout).
The login screen has its own restorer: sudo sh /var/backups/rice-greeter/restore.sh
"""
# restore.py — restaura um backup feito pelo install.py (python3 scripts/restore.py backups/<nome> [--apply]).
# Confere o backup inteiro antes, salva o estado atual num backup de resgate e desfaz se algo falhar.
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


class BackupError(Exception):
    """Erro de backup inválido ou incompleto."""
    pass


def load(backup, home):
    """The manifest entries, after checking every piece the restore will need."""
    try:
        manifest = json.loads((backup/'manifest.json').read_text())
    except (OSError, ValueError) as exc:
        raise BackupError(f'no readable manifest.json in {backup}: {exc}') from None
    if not isinstance(manifest, list):
        raise BackupError('manifest.json is not a list of files')
    entries = []
    for item in manifest:
        target = Path(item['path'])
        source = Path(item['backup']) if item.get('backup') else None
        # Only files of this user; system files (the login screen) need their own restorer.
        if not target.is_relative_to(home):
            raise BackupError(f'refusing a path outside your home: {target}')
        if source is not None and not (source.is_file() or source.is_symlink()):
            raise BackupError(f'backup copy missing: {source}')
        entries.append((target, source))
    return entries


def snapshot(entries, state, rescue, home):
    """Copy everything that is about to change into a restorable rescue backup."""
    rescue.mkdir(parents=True)
    manifest = []
    for target, _ in entries:
        saved = None
        if target.exists() or target.is_symlink():
            saved = rescue/'home'/target.relative_to(home)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved, follow_symlinks=False)
        manifest.append({'path': str(target), 'backup': str(saved) if saved else None})
    if state.exists():
        shutil.copytree(state, rescue/'theme', symlinks=True)
    (rescue/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


def put(target, source):
    """Coloca no lugar o arquivo do backup (ou apaga, se no backup ele não existia)."""
    if target.is_symlink() or target.exists():
        target.unlink()
    if source is not None:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)


def restore(backup, *, home=None, reload=True):
    """Restaura todos os arquivos do backup, com resgate e volta automática em caso de erro."""
    home = home or Path.home()
    backup = Path(backup).resolve()
    state = home/'.local/state/rice-minimal/theme'
    entries = load(backup, home)
    theme = backup/'theme' if (backup/'theme').is_dir() else None
    rescue = backup/('before-restore-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    snapshot(entries, state, rescue, home)
    staged = state.with_name(state.name+'.restoring')
    try:
        for target, source in entries:
            put(target, source)
        if theme:
            # Build the new state beside the live one, then swap.
            shutil.rmtree(staged, ignore_errors=True)
            shutil.copytree(theme, staged, symlinks=True)
            if state.exists():
                shutil.rmtree(state)
            staged.rename(state)
    except Exception:
        for target, _ in entries:
            saved = rescue/'home'/target.relative_to(home)
            put(target, saved if (saved.exists() or saved.is_symlink()) else None)
        if theme:
            shutil.rmtree(staged, ignore_errors=True)
            if not state.exists() and (rescue/'theme').exists():
                shutil.copytree(rescue/'theme', state, symlinks=True)
        raise
    if reload:
        reload_session()
    return rescue


def reload_session():
    """Bring the running session up to date; never fails the restore."""
    commands = [['hyprctl', 'reload', 'config-only'], ['noctalia', 'msg', 'config-reload'],
                [sys.executable, str(ROOT/'extras/theme/theme.py'), 'cached'],
                [sys.executable, str(ROOT/'extras/rice.py'), 'sync', '--json']]
    for command in commands:
        subprocess.run(command, capture_output=True, cwd=ROOT)


def main():
    """Sem --apply mostra o que mudaria; com --apply restaura."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('backup', type=Path)
    parser.add_argument('--apply', action='store_true', help='restore (otherwise only list what would change)')
    parser.add_argument('--no-reload', action='store_true')
    args = parser.parse_args()
    backup = args.backup.expanduser().resolve()
    try:
        entries = load(backup, Path.home())
    except BackupError as exc:
        print('restore: nothing was changed:', exc, file=sys.stderr)
        return 1
    for target, source in entries:
        print(('restore  ' if source else 'remove   ')+str(target).replace(str(Path.home()), '~'))
    if (backup/'theme').is_dir():
        print('restore  theme state (palettes, profile, lock flags)')
    if (backup/'project').is_dir():
        print('skip     project code: use git instead (git log, git checkout)')
    if not args.apply:
        print('\nRun again with --apply to restore. Current files are saved first.')
        return 0
    rescue = restore(backup, reload=not args.no_reload)
    print('\nRestored. To undo: python3 scripts/restore.py', rescue.relative_to(ROOT) if rescue.is_relative_to(ROOT) else rescue, '--apply')
    return 0


if __name__ == '__main__':
    sys.exit(main())
