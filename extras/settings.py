"""Escolhas do usuário: ~/.config/lw/config.toml por cima dos padrões dos manifestos."""
# settings.py — lê a config do LW (contrato em docs/modulos.md). Só lê, nunca grava.
# Arquivo ou chave ausente = padrão do manifesto. Arquivo quebrado ou tipo errado também:
# vale o padrão e o problema aparece em problems(), que o "lw doctor" mostra.
import os
from pathlib import Path
import tomllib
import modules


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


def problems():
    """O que está errado nos manifestos e na config (lista vazia se nada)."""
    known, found = modules.load()
    data, error = read()
    if error:
        return found + [f'{path()}: {error}']
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
