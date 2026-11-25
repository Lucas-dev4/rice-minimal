"""Escolhas do usuário: ~/.config/lw/config.toml por cima dos padrões dos manifestos."""
# settings.py — lê a config do LW (contrato em docs/modulos.md). Só grava a escolha dos módulos ligados
# (set_module), uma linha de [modules], com backup em ~/.local/state/rice-minimal/lw/backups.
# Arquivo ou chave ausente = padrão do manifesto. Arquivo quebrado ou tipo errado também:
# vale o padrão e o problema aparece em problems(), que o "lw doctor" mostra.
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
import tomllib
import modules

HEADER = re.compile(r'\s*\[\s*modules\s*\]\s*(#.*)?$')


def home():
    """Pasta pessoal (respeita $HOME, útil nos testes)."""
    return Path(os.environ.get('HOME', str(Path.home())))


def path():
    """O arquivo de config: ~/.config/lw/config.toml."""
    return Path(os.environ.get('XDG_CONFIG_HOME', home()/'.config'))/'lw'/'config.toml'


def read():
    """(conteúdo do arquivo, erro ou None). Arquivo ausente não é erro."""
    try:
        return tomllib.loads(path().read_text()), None
    except FileNotFoundError:
        return {}, None
    except (OSError, ValueError) as exc:
        return {}, str(exc)


def expand(value):
    """"~/" no começo vira a pasta pessoal (também em listas)."""
    if isinstance(value, list):
        return [expand(item) for item in value]
    if isinstance(value, str) and (value == '~' or value.startswith('~/')):
        return str(home()) + value[1:]
    return value


def wrong(value, default):
    """Por que o valor não serve no lugar do padrão (None se serve)."""
    if type(value) is not type(default):
        kinds = {str: 'um texto', bool: 'true ou false', int: 'um número inteiro', float: 'um número com ponto',
                 list: 'uma lista de textos', dict: 'uma tabela de textos'}
        return 'esperava ' + kinds[type(default)]
    if not modules.default_ok(value):
        return 'esperava só textos dentro'
    if isinstance(value, str) and default and not value.strip():
        return 'texto vazio'
    return None


def manifest(module):
    """As chaves de config declaradas pelo módulo."""
    known, errors = modules.load()
    if module not in known:
        raise ValueError(f'módulo desconhecido: {module}' + (f' ({"; ".join(errors)})' if errors else ''))
    return known[module].get('config', {})


def chosen(module):
    """Só o que o usuário escolheu (e é válido) para o módulo."""
    table = read()[0].get(module, {})
    if not isinstance(table, dict):
        return {}
    return {key: expand(table[key]) for key, spec in manifest(module).items()
            if key in table and wrong(table[key], spec['default']) is None}


def section(module):
    """Todas as chaves do módulo: padrão do manifesto, com a escolha do usuário por cima."""
    values = {key: expand(spec['default']) for key, spec in manifest(module).items()}
    return dict(values, **chosen(module))


def get(module, key):
    """Valor de uma chave: settings.get('music', 'dir')."""
    return section(module)[key]


def switches():
    """{id: ligado} de todos os módulos: o `default` do manifesto, com a escolha do usuário por cima."""
    table = read()[0].get('modules', {})
    table = table if isinstance(table, dict) else {}
    found = {}
    for module, spec in modules.load()[0].items():
        value = table.get(module)
        found[module] = bool(spec.get('required')) or (value if isinstance(value, bool) else spec.get('default', True))
    return found


def module_problems(table, known):
    """O que está errado em [modules]."""
    if not isinstance(table, dict):
        return ['modules: esperava uma tabela']
    found = []
    for module, value in table.items():
        if module not in known:
            # O de manifesto inválido já aparece com o erro dele.
            if not (modules.FOLDER/module/'module.toml').is_file():
                found.append(f'modules.{module}: módulo desconhecido')
        elif not isinstance(value, bool):
            found.append(f'modules.{module}: esperava true ou false')
        elif not value and known[module].get('required'):
            found.append(f'modules.{module}: {known[module]["name"]} é obrigatório')
    return found


def switched(text, module, on):
    """O texto do config.toml com o módulo ligado ou desligado; o resto tem que ficar igual."""
    line = f'{module} = {str(on).lower()}'
    before = tomllib.loads(text)
    end = '\r\n' if '\r\n' in text else '\n'
    rows = text.split('\n')
    start = next((i for i, row in enumerate(rows) if HEADER.match(row)), None)
    if start is None:
        gap = '' if not text else end if text.endswith('\n') else end + end
        new = f'{text}{gap}[modules]{end}{line}{end}'
    else:
        stop = next((i for i in range(start + 1, len(rows)) if re.match(r'\s*\[', rows[i])), len(rows))
        key = re.compile(rf"""(\s*(?:{module}|"{module}"|'{module}')\s*=\s*)("[^"]*"|'[^']*'|[^\s#]+)""")
        at = next((i for i in range(start + 1, stop) if key.match(rows[i])), None)
        if at is not None:
            rows[at] = key.sub(lambda m: m.group(1) + str(on).lower(), rows[at], count=1)
        elif start + 1 == len(rows):      # o cabeçalho é a última linha, sem quebra no fim
            rows.append(line)
        else:
            rows.insert(start + 1, line + end[:-1])
        new = '\n'.join(rows)
    try:
        good = tomllib.loads(new) == dict(before, modules=dict(before.get('modules', {}), **{module: on}))
    except (TypeError, ValueError):
        good = False
    if not good:
        raise ValueError(f'não consegui mudar só essa linha; ponha à mão, em [modules]: {line}')
    return new


def backup(target):
    """Cópia do arquivo antes de editar."""
    state = Path(os.environ.get('XDG_STATE_HOME', home()/'.local/state'))
    folder = state/'rice-minimal'/'lw'/'backups'
    folder.mkdir(parents=True, exist_ok=True)
    copy = folder/f'{target.name}.{time.strftime("%Y%m%d-%H%M%S")}.{time.time_ns() % 1000000000:09d}'
    shutil.copy2(target, copy)
    return str(copy)


def write(target, text):
    """Grava de forma atômica, com a permissão que o arquivo já tinha."""
    mode = target.stat().st_mode & 0o777 if target.exists() else 0o644
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix='.lw-')
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(text.encode())
            out.flush()
            os.fsync(out.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, target)
    finally:
        Path(tmp).unlink(missing_ok=True)


def set_module(name, on):
    """Liga ou desliga um módulo (lw modules enable|disable)."""
    m = modules.find(name)
    module = m['id']
    data = {'id': module, 'name': m['name'], 'enabled': on, 'changed': False, 'backup': None}
    if m.get('required'):
        if not on:
            raise ValueError(f'{m["name"]} é obrigatório e não pode ser desligado')
        return data
    target = path().resolve()      # um link simbólico continua sendo link
    try:
        text = target.read_bytes().decode() if target.exists() else ''
        table = tomllib.loads(text).get('modules', {})
        if isinstance(table, dict) and table.get(module, m.get('default', True)) is on:
            return data
        new = switched(text, module, on)
    except ValueError as exc:
        raise ValueError(f'{path()}: {exc}') from exc
    if target.exists():
        data['backup'] = backup(target)
    write(target, new)
    data['changed'] = True
    return data


def problems():
    """O que está errado nos manifestos e na config (lista vazia se nada)."""
    known, found = modules.load()
    data, error = read()
    if error:
        return found + [f'{path()}: {error}']
    found = found + module_problems(data.get('modules', {}), known)
    for module, spec in known.items():
        table = data.get(module, {})
        if not isinstance(table, dict):
            found.append(f'{module}: esperava uma tabela')
            continue
        for key, item in spec.get('config', {}).items():
            reason = wrong(table[key], item['default']) if key in table else None
            if reason:
                found.append(f'{module}.{key}: {reason}')
    return found
