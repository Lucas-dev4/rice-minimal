"""What each backup is and how to restore it. Nothing here restores anything."""
import json
from pathlib import Path
from theme import theme

KINDS = {'full':'Project, live files and theme state',
         'files':'Files changed by one install step',
         'lock':'Lock screen visuals',
         'snapshot':'Copies for manual restore'}


def classify(path):
    # Each format has its own tool; the wrong one fails or restores only part of it.
    if path.name.startswith('lock-visual-'):
        return 'lock','python3 extras/rice.py lock-restore'
    relative = path.relative_to(theme.ROOT)
    if (path/'project').is_dir():
        return 'full',f'python3 scripts/restore_refined.py {relative}'
    try:
        manifest = json.loads((path/'manifest.json').read_text())
    except (OSError,ValueError):
        manifest = None
    if isinstance(manifest,list) and manifest:
        return 'files',f'python3 restore.py {relative}'
    return 'snapshot',None


def size(path):
    return sum(item.stat().st_size for item in path.rglob('*') if item.is_file() and not item.is_symlink())


def listing():
    root = theme.ROOT/'backups'
    found = []
    if root.is_dir():
        for path in root.iterdir():
            if path.is_dir():
                kind,command = classify(path)
                found.append({'name':path.name,'path':str(path),'kind':kind,'description':KINDS[kind],'command':command,
                              'time_ns':path.stat().st_mtime_ns,'size':size(path)})
    found.sort(key=lambda item:item['time_ns'],reverse=True)
    return {'backups':found,'recovery':{
        'greeter':'sudo sh /var/backups/rice-greeter/restore.sh',
        'lock':'python3 extras/rice.py lock-restore',
        'full':next((item['command'] for item in found if item['kind'] == 'full'),None)}}
