#!/usr/bin/env python3
"""Install Phase 4 includes with a full pre-install backup, then activate Refined."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'extras'))
from theme import theme, profiles
HOME = Path.home()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args = parser.parse_args()
    target = HOME/'.config/hypr/hyprland.lua'
    hook = 'require("config.rice-appearance")'
    original = target.read_text()
    palette = HOME/'.config/noctalia/palettes/RiceMinimal.json'
    module = HOME/'.config/hypr/config/rice-appearance.lua'
    print('Include:',target,'\nModule:',module,'\nPalette:',palette)
    if not args.apply:
        return
    backup = Path((ROOT/'.phase4-backup').read_text().strip())
    if (backup/'manifest.json').exists():
        if hook not in original or not palette.is_file():
            raise RuntimeError('Incomplete installation: inspect the saved backup before retrying')
        shutil.copy2(ROOT/'config/hypr/rice-appearance.lua',module)
        theme.cached()
        profiles.switch('refined')
        print('Refined reapplied; original backup preserved:',backup)
        return
    if palette.exists() or palette.is_symlink():
        raise RuntimeError('Custom palette already exists; refusing to replace')
    manifest = []
    for path in (target,module,palette,HOME/'.local/state/noctalia/settings.toml'):
        saved = None
        if path.exists():
            saved = backup/'home'/path.relative_to(HOME)
            saved.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,saved)
        manifest.append({'path':str(path),'backup':str(saved) if saved else None})
    if theme.STATE.exists():
        shutil.copytree(theme.STATE,backup/'theme',symlinks=True)
    (backup/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    module.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'config/hypr/rice-appearance.lua',module)
    theme.cached()
    palette.parent.mkdir(parents=True,exist_ok=True)
    if palette.exists() or palette.is_symlink():
        raise RuntimeError('Custom palette already exists; refusing to replace')
    palette.write_text((theme.STATE/'current/noctalia.json').read_text())
    if hook not in original:
        target.write_text(original.rstrip()+'\n\n'+hook+'\n')
    try:
        profiles.switch('refined')
    except Exception:
        print('Installation failed. Restore with scripts/restore_refined.py',backup,file=sys.stderr)
        raise
    print('Refined active. Backup:',backup)

if __name__ == '__main__':
    main()
