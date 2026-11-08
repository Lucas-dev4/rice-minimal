#!/usr/bin/env python3
"""Install only pending integration files, saving a unique restoration manifest."""
import datetime
import configparser
import json
from pathlib import Path
import io
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()

def hook_installed(command):
    return 'extras/theme/theme.py' in command and command.rstrip().endswith(' wallpaper')

def desired(source, target):
    """New content for target, or None when it already does what the rice needs."""
    if not target.exists():
        return source.read_bytes()
    if source.suffix != '.ini':
        return None if target.read_bytes() == source.read_bytes() else source.read_bytes()
    # Waypaper rewrites its config with the user's wallpaper and many extra keys.
    # Only the hook is the rice's; every other value already there is the user's.
    expected, current = (configparser.ConfigParser(interpolation=None) for _ in range(2))
    for parser in (expected, current):
        parser.optionxform = str
    expected.read(source)
    current.read(target)
    changed = False
    for section in expected.sections():
        if not current.has_section(section):
            current.add_section(section)
        for key, value in expected.items(section):
            actual = current.get(section, key, fallback=None)
            if actual is None or (key == 'post_command' and not hook_installed(actual)):
                current.set(section, key, value)
                changed = True
    if not changed:
        return None
    text = io.StringIO()
    current.write(text)
    return text.getvalue().encode()

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
    changes = [(target, data) for source, target in plan
               if (data := desired(source, target)) is not None]
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
