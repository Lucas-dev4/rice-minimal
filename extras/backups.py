"""What each backup is and how to restore it. Nothing here restores anything."""
# backups.py — lista os backups em backups/ e diz como restaurar cada um.
# Usado pela tela Backups do LW (lw backups list) e pela TUI. Só lê; quem restaura é scripts/restore.py.
import json
from pathlib import Path
from theme import theme

KINDS = {'full':'Live files and theme state (project code is in git)',
         'files':'Files changed by one install step',
         'lock':'Lock screen visuals',
         'snapshot':'Copies for manual restore'}


def classify(path):
    # Every format with a manifest goes through scripts/restore.py, which previews first.
    """Descobre o tipo do backup (full, files, lock, snapshot) e o comando que o restaura."""
    if path.name.startswith('lock-visual-'):
        return 'lock','python3 extras/rice.py lock-restore'
    try:
        manifest = json.loads((path/'manifest.json').read_text())
    except (OSError,ValueError):
        manifest = None
    if isinstance(manifest,list) and manifest:
        kind = 'full' if (path/'theme').is_dir() else 'files'
        return kind,f'python3 scripts/restore.py {path.relative_to(theme.ROOT)}'
    return 'snapshot',None


def size(path):
    """Tamanho total em bytes dos arquivos do backup (sem seguir links)."""
    return sum(item.stat().st_size for item in path.rglob('*') if item.is_file() and not item.is_symlink())


def listing():
    """Todos os backups, do mais novo ao mais antigo, mais os comandos de recuperação (greeter, bloqueio, completo)."""
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
