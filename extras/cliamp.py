"""lw cliamp sync: escreve o initial_directory do cliamp a partir de music.dir."""
# cliamp.py — a pasta das músicas tem uma fonte só: music.dir, em ~/.config/lw/config.toml.
# Daqui ela vai para ~/.config/cliamp/config.toml, nunca o contrário. Muda só essa chave, com
# backup em ~/.local/state/rice-minimal/cliamp/backups e escrita atômica.
# O arquivo ausente não é criado: quem cria é o scripts/install.py.
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
import tomllib
import settings

KEY = 'initial_directory'
LINE = re.compile(r'''^(\s*initial_directory\s*=\s*)("(?:[^"\\\n]|\\.)*"|'[^'\n]*')''', re.M)


def config_path():
    """O arquivo de config do cliamp: ~/.config/cliamp/config.toml."""
    return Path(os.environ.get('XDG_CONFIG_HOME', settings.home()/'.config'))/'cliamp'/'config.toml'


def backup(path):
    """Cópia do arquivo antes de editar."""
    state = Path(os.environ.get('XDG_STATE_HOME', settings.home()/'.local/state'))
    folder = state/'rice-minimal'/'cliamp'/'backups'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder/f'{path.name}.{time.strftime("%Y%m%d-%H%M%S")}.{time.time_ns() % 1000000000:09d}'
    shutil.copy2(path, target)
    return str(target)


def write(path, text):
    """Grava de forma atômica, com a permissão que o arquivo já tinha."""
    mode = path.stat().st_mode & 0o777
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.lw-')
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(text.encode())
            out.flush()
            os.fsync(out.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def replaced(text, folder):
    """O texto do config.toml com o initial_directory novo; o resto tem que ficar igual."""
    home = str(settings.home())
    shown = '~' + folder[len(home):] if folder.startswith(home + '/') else folder
    value = json.dumps(shown, ensure_ascii=False)
    before = tomllib.loads(text)
    if KEY in before:
        # A chave é do nível de cima, então a primeira linha com ela é a certa.
        new = LINE.sub(lambda m: m.group(1) + value, text, count=1)
    else:
        new = f'{KEY} = {value}\n' + text
    if tomllib.loads(new) != dict(before, **{KEY: shown}):
        raise ValueError('não consegui trocar só o ' + KEY)
    return new


def sync():
    """Deixa o initial_directory igual a music.dir; devolve (dados, avisos)."""
    folder = settings.get('music', 'dir')
    data = {'dir': folder, 'exists': Path(folder).is_dir(), 'changed': False, 'backup': None}
    warnings = [] if data['exists'] else ['a pasta das músicas não existe: ' + folder]
    path = config_path()
    if not path.is_file():
        return data, warnings + ['o cliamp ainda não tem config.toml']
    path = path.resolve()      # um link simbólico continua sendo link
    text = path.read_bytes().decode()
    try:
        current = tomllib.loads(text).get(KEY)
        if isinstance(current, str) and settings.expand(current).rstrip('/') == folder.rstrip('/'):
            return data, warnings
        new = replaced(text, folder)
    except ValueError as exc:
        raise ValueError(f'{path}: {exc}') from exc
    data['backup'] = backup(path)
    write(path, new)
    data['changed'] = True
    return data, warnings
