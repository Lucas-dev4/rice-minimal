#!/usr/bin/env python3
"""Refresh config/integrity.json, the SHA-256 list that `rice doctor` checks
("Managed file integrity"). Run it after editing any managed file, before committing.

  scripts/integrity.py           rewrite the list (same files, plus every gui/**/*.qml|js and modules/*/module.toml)
  scripts/integrity.py --check   only report files whose hash changed; exit 1 if any
"""
# integrity.py — atualiza config/integrity.json (hash SHA-256 de cada arquivo gerenciado).
# O "lw doctor" e os testes usam essa lista para saber se algo mudou sem passar por aqui.
# Rode depois de editar qualquer arquivo do projeto; --check só mostra o que mudou.
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIST = ROOT/'config'/'integrity.json'


def wanted(current):
    """Arquivos que entram na lista: os já listados que existem + todos os .qml/.js da GUI + os manifestos."""
    names = {n for n in current if (ROOT/n).is_file()}
    names |= {str(p.relative_to(ROOT)) for p in ROOT.glob('gui/**/*') if p.suffix in ('.qml', '.js')}
    names |= {str(p.relative_to(ROOT)) for p in ROOT.glob('modules/*/module.toml')}
    return sorted(names)


def main(argv):
    """Recalcula os hashes; grava (ou, com --check, só lista as diferenças)."""
    current = json.loads(LIST.read_text())
    fresh = {n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in wanted(current)}
    changed = sorted(n for n in fresh if current.get(n) != fresh[n]) + sorted(n for n in current if n not in fresh)
    if '--check' in argv:
        for n in changed:
            print('changed', n)
        return 1 if changed else 0
    LIST.write_text(json.dumps(fresh, indent=2) + '\n')
    print(len(fresh), 'files,', len(changed), 'updated')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
