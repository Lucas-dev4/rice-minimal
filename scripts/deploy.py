#!/usr/bin/env python3
"""Install only pending integration files, saving a unique restoration manifest."""
import datetime
import configparser
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()

def matches(source, target):
    if not target.exists():
        return False
    if source.suffix != '.ini':
        return target.read_bytes() == source.read_bytes()
    # Waypaper adds defaults and abbreviates HOME after its first GUI run.
    # Preserve that valid generated configuration instead of reinstalling it.
    expected, current = configparser.ConfigParser(), configparser.ConfigParser()
    expected.read(source)
    current.read(target)
    for section in expected.sections():
        for key, value in expected.items(section):
            actual = current.get(section, key, fallback=None)
            if actual is None:
                return False
            if key in {'folder', 'wallpaper'}:
                actual, value = str(Path(actual).expanduser()), str(Path(value).expanduser())
            if actual != value:
                return False
    return True

def main():
    hypr = HOME/'.config/hypr/hyprland.lua'
    original = hypr.read_text()
    binds = json.loads(subprocess.check_output(['hyprctl', '-j', 'binds']))
    for bind in binds:
        if ('require("config.rice-integration")' not in original
                and bind.get('modmask') == 76
                and str(bind.get('key', '')).upper() in {'W','B','S','N'}):
            raise RuntimeError(f'Binding conflict: {bind}')
    plan = [(ROOT/'config/waypaper/config.ini', HOME/'.config/waypaper/config.ini'),
            (ROOT/'config/hypr/rice-integration.lua', HOME/'.config/hypr/config/rice-integration.lua'),
            (ROOT/'config/autostart/rice-minimal.desktop', HOME/'.config/autostart/rice-minimal.desktop')]
    changes = [(target, source.read_bytes()) for source, target in plan
               if not matches(source, target)]
    if 'require("config.rice-integration")' not in original:
        changes.append((hypr, (original+'\nrequire("config.rice-integration")\n').encode()))
    if not changes:
        print('Integration already installed; no files changed')
        return
    backup = ROOT/'backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True, exist_ok=False)
    manifest = []
    for target, _ in changes:
        saved = None
        if target.exists():
            saved = backup/target.relative_to(HOME)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
        manifest.append({'path': str(target), 'backup': str(saved) if saved else None})
    (backup/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    for target, data in changes:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    print('New backup:', backup)
    print('Files installed:', len(changes))

if __name__ == '__main__':
    main()
