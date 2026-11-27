"""Manifestos dos módulos do LW: modules/<id>/module.toml, lidos e conferidos."""
# modules.py — lê os manifestos (contrato em docs/modulos.md). O conjunto de campos é fechado:
# campo desconhecido é erro. Manifesto inválido fica de fora e o resto do LW abre.
from pathlib import Path
import tomllib
import unicodedata

FOLDER = Path(__file__).resolve().parents[1]/'modules'
FIELDS = {'id': str, 'name': str, 'description': str, 'order': int, 'default': bool, 'required': bool,
          'gui': dict, 'commands': dict, 'dependency': list, 'config': dict, 'shortcut': list}
# Campos de cada tabela; a config tem uma tabela por chave.
TABLES = {'gui': {'folder': str, 'hook': str, 'screens': list},
          'commands': {'handler': str, 'names': list, 'open': str}}
ITEMS = {'dependency': {'command': (str, list), 'python': str, 'font': str, 'package': str, 'aur': str,
                        'manual': str, 'optional': bool, 'why': str, 'conflicts': list},
         'shortcut': {'keys': str, 'command': str, 'description': str}}
SCREEN = {'name': str, 'file': str}


def fields(table, known, where):
    """Confere que a tabela só tem campos conhecidos, cada um do tipo certo."""
    if not isinstance(table, dict):
        raise ValueError(f'{where}: esperava uma tabela')
    for key, value in table.items():
        if key not in known:
            raise ValueError(f'{where}: campo desconhecido "{key}"')
        kinds = known[key] if isinstance(known[key], tuple) else (known[key],)
        if type(value) not in kinds:
            raise ValueError(f'{where}: "{key}" tem o tipo errado')


def default_ok(value):
    """Um padrão de config é texto, número, verdadeiro/falso, lista de textos ou tabela de textos."""
    if isinstance(value, (list, dict)):
        items = value.values() if isinstance(value, dict) else value
        return all(isinstance(item, str) for item in items)
    return isinstance(value, (str, bool, int, float))


def validate(data, folder):
    """Confere um manifesto; devolve os dados ou explica o que está errado."""
    fields(data, FIELDS, folder)
    for key in ('id', 'name'):
        if not data.get(key):
            raise ValueError(f'{folder}: falta "{key}"')
    if data['id'] != folder:
        raise ValueError(f'{folder}: o id "{data["id"]}" não é o nome da pasta')
    for name, known in TABLES.items():
        fields(data.get(name, {}), known, f'{folder}: {name}')
    for screen in data.get('gui', {}).get('screens', []):
        fields(screen, SCREEN, f'{folder}: screens')
    for name, known in ITEMS.items():
        for item in data.get(name, []):
            fields(item, known, f'{folder}: {name}')
    for key, spec in data.get('config', {}).items():
        where = f'{folder}: config.{key}'
        if not isinstance(spec, dict) or set(spec) - {'default', 'description'}:
            raise ValueError(f'{where}: só aceita default e description')
        if 'default' not in spec or not default_ok(spec['default']):
            raise ValueError(f'{where}: falta um default válido')
    return data


def load(base=None):
    """Todos os manifestos: ({id: dados}, [erros]), na ordem da barra lateral."""
    found, errors = [], []
    for path in sorted((base or FOLDER).glob('*/module.toml')):
        try:
            found.append(validate(tomllib.loads(path.read_text()), path.parent.name))
        except (OSError, ValueError) as exc:
            text = str(exc)
            errors.append(text if text.startswith(path.parent.name + ':') else f'{path.parent.name}: {text}')
    found.sort(key=lambda m: (m.get('order', 0), m['id']))
    return {m['id']: m for m in found}, errors


def openers():
    """{comando: id} dos módulos que abrem a janela pelo nome (lw music = LW em MÚSICA)."""
    return {m['commands']['open']: m['id'] for m in load()[0].values() if m.get('commands', {}).get('open')}


def plain(text):
    """O texto em minúsculas e sem acento: MÚSICA → musica."""
    return ''.join(c for c in unicodedata.normalize('NFKD', text.strip().lower()) if not unicodedata.combining(c))


def find(name):
    """O manifesto pelo id ou pelo nome da seção (music, musica, MÚSICA)."""
    found = load()[0]
    for m in found.values():
        if plain(name) in (m['id'], plain(m['name'])):
            return m
    raise ValueError(f'módulo desconhecido: {name} (existem: {", ".join(plain(m["name"]) for m in found.values())})')


def off_text(module):
    """O aviso de módulo desligado, igual no atalho e nos comandos recusados."""
    m = load()[0][module]
    return f'módulo {m["name"]} desligado · lw modules enable {plain(m["name"])}'


def owners():
    """{comando: id} dos comandos de cada módulo."""
    return {name: m['id'] for m in load()[0].values() for name in m.get('commands', {}).get('names', [])}


def handlers():
    """{comando: handler} dos módulos que têm comandos (extras/<handler>.py)."""
    return {name: m['commands']['handler'] for m in load()[0].values() if m.get('commands', {}).get('handler')
            for name in m['commands'].get('names', [])}
