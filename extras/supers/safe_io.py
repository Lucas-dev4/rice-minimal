"""Validated atomic edits, unique backups, conflict checks and restoration."""
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time


def lua_string(value):
    if any(ord(c) < 32 for c in value):
        raise ValueError('Caracteres de controle não são permitidos')
    return json.dumps(value, ensure_ascii=False)


def normalize_key(expr):
    # Only static expressions are editable. Loops/digitCode remain untouched.
    match = re.fullmatch(r'mainMod\s*\.\.\s*"([^"\\]*)"|"([^"\\]*)"', expr.strip())
    if not match:
        return None
    value = ('SUPER' + match[1]) if match[1] is not None else match[2]
    parts = [x.strip().upper() for x in value.split('+')]
    return tuple(sorted(parts[:-1])) + (parts[-1],)


def safe_write(path, original, replacement):
    target = Path(path).expanduser()
    if target.is_symlink():
        raise ValueError('Recusando editar link simbólico')
    with open(str(target) + '.supers.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if target.read_text() != original:
            raise ValueError('Arquivo mudou durante a edição; reabra o Super')
        fd, name = tempfile.mkstemp(prefix='.supers-', suffix='.lua', dir=target.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                stream.write(replacement)
                stream.flush()
                os.fsync(stream.fileno())
            subprocess.run(['luac', '-p', name], check=True, capture_output=True)
            backup = target.with_name(target.name + '.supers-' + str(time.time_ns()) + '.bak')
            shutil.copy2(target, backup)
            os.chmod(name, target.stat().st_mode & 0o777)
            os.replace(name, target)
            directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            return backup
        finally:
            if os.path.exists(name):
                os.unlink(name)
