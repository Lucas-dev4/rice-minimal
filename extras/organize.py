#!/usr/bin/env python3
"""LW // MUSIC: sends what is in ~/Músicas/Downloads to the right genre folder.

The library is one folder per genre with files named "Artist - Title.ext". An artist
who already has songs in a folder decides where a new song of theirs goes (the folder
with most of their songs). New artists stay in Downloads until a folder is chosen once;
from then on the artist is known. Prints one JSON object.

  organize.py plan             what would move, and what has no folder yet
  organize.py apply            moves the known ones
  organize.py move FILE FOLDER moves one file to a genre folder (a new artist)

Moves never overwrite: a song that is already in the folder stays in Downloads.
Every move is appended to ~/Músicas/.organizacao-log.json as [from, to].
"""
# organize.py — tira as músicas de ~/Músicas/Downloads e põe na pasta de gênero certa,
# pelo artista (o mesmo artista já tem músicas numa pasta). Artista novo: fica em Downloads
# até você escolher a pasta uma vez (aba ONLINE do LW, tecla g).
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import settings

AUDIO = {'.mp3', '.m4a', '.opus', '.ogg', '.flac', '.wav', '.aac'}
DOWNLOADS = 'Downloads'
LOG = '.organizacao-log.json'
# "A ft. B", "A feat. B", "A x B", "A X B", "A, B", "A & B": o artista principal é o primeiro.
SPLIT = re.compile(r'\s+(?:ft\.?|feat\.?|featuring|part\.?|x|X|&|vs\.?)\s+|\s*,\s*')


def fold(text):
    """Para comparar nomes: sem acento, minúsculo, espaços simples."""
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return ' '.join(text.casefold().split())


def names(artist):
    """O nome completo e o artista principal (antes de ft./x/&...), já dobrados."""
    full = fold(artist)
    main = fold(SPLIT.split(artist or '', maxsplit=1)[0])
    return [n for n in dict.fromkeys([full, main]) if n]


def split_name(stem):
    """'Artista - Título' -> (artista, título); sem ' - ', ('', stem)."""
    if ' - ' in stem:
        artist, title = stem.split(' - ', 1)
        return artist.strip(), title.strip()
    return '', stem.strip()


def folders(root):
    """As pastas de gênero (tudo menos Downloads e pastas ocultas), em ordem alfabética."""
    return sorted((p.name for p in Path(root).iterdir()
                   if p.is_dir() and p.name != DOWNLOADS and not p.name.startswith('.')),
                  key=fold)


def index(root):
    """Artista (dobrado) -> Counter(pasta: quantas músicas dele estão lá)."""
    found = {}
    for folder in folders(root):
        for path in (Path(root)/folder).iterdir():
            if path.suffix.lower() not in AUDIO:
                continue
            artist, _ = split_name(path.stem)
            for name in names(artist):
                found.setdefault(name, Counter())[folder] += 1
    return found


def read_tags(path):
    """Artista e título das tags (ffprobe); vazio se não der para ler."""
    try:
        out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format_tags=artist,title', '-of', 'json', str(path)],
                             capture_output=True, text=True, timeout=15).stdout
        tags = {k.lower(): v for k, v in (json.loads(out).get('format', {}).get('tags') or {}).items()}
    except (OSError, ValueError, subprocess.SubprocessError):
        tags = {}
    return (tags.get('artist') or '').strip(), (tags.get('title') or '').strip()


def safe(text):
    """Nome de arquivo válido: sem '/', sem espaços sobrando."""
    return ' '.join(text.replace('/', '⧸').replace('\0', '').split()).strip(' .') or 'Sem título'


def describe(path):
    """Artista, título e o nome final 'Artista - Título.ext' de um arquivo baixado."""
    file_artist, file_title = split_name(path.stem)
    if re.fullmatch(r'\d+', file_artist):          # "01 - Título" de uma playlist
        file_artist = ''
    tag_artist, tag_title = read_tags(path)
    artist = tag_artist or file_artist
    title = tag_title or file_title
    # O YouTube costuma repetir o artista no título: "WLO - WLO - Música".
    while artist and fold(title).startswith(fold(artist) + ' - '):
        title = title[len(artist) + 3:].strip()
    name = (safe(artist) + ' - ' if artist else '') + safe(title) + path.suffix.lower()
    return artist, title, name


def folder_for(artist, known):
    """A pasta com mais músicas do artista (nome completo antes do principal); None se for novo."""
    for name in names(artist):
        if name in known:
            return known[name].most_common(1)[0][0]
    return None


def pending(root):
    """Os arquivos de áudio dentro de Downloads (subpastas de playlist inclusive)."""
    base = Path(root)/DOWNLOADS
    if not base.is_dir():
        return []
    return sorted((p for p in base.rglob('*') if p.is_file() and p.suffix.lower() in AUDIO), key=lambda p: fold(str(p)))


def plan(root):
    """O que vai para onde (moves) e o que ainda não tem pasta (unknown)."""
    known = index(root)
    moves, unknown = [], []
    for path in pending(root):
        artist, title, name = describe(path)
        folder = folder_for(artist, known) if artist else None
        entry = {'file': str(path), 'artist': artist, 'title': title, 'name': name}
        if folder:
            moves.append(dict(entry, folder=folder, dest=str(Path(root)/folder/name)))
        else:
            unknown.append(entry)
    return {'ok': True, 'moves': moves, 'unknown': unknown, 'folders': folders(root)}


def write_log(root, pairs):
    """Acrescenta [de, para] ao log de organização (escrita atômica)."""
    path = Path(root)/LOG
    try:
        log = json.loads(path.read_text())
        if not isinstance(log, list):
            log = []
    except (OSError, ValueError):
        log = []
    log.extend([str(a), str(b)] for a, b in pairs)
    handle, temporary = tempfile.mkstemp(prefix='.organizacao-', dir=root)
    try:
        with os.fdopen(handle, 'w') as stream:
            json.dump(log, stream, ensure_ascii=False, indent=1)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def move_file(source, dest):
    """Move sem sobrescrever; devolve None ou o motivo de não ter movido."""
    source, dest = Path(source), Path(dest)
    if not source.is_file():
        return 'o arquivo não existe mais'
    if dest.exists():
        return 'já existe em ' + dest.parent.name
    try:
        os.link(source, dest)                      # nunca sobrescreve: falha se o destino existir
    except FileExistsError:
        return 'já existe em ' + dest.parent.name
    except OSError:
        shutil.move(source, dest)                  # sistema de arquivos sem link: move normal
        return None
    source.unlink()
    return None


def tidy(root):
    """Apaga as pastas de playlist que ficaram vazias dentro de Downloads."""
    base = Path(root)/DOWNLOADS
    for path in sorted((p for p in base.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        try:
            path.rmdir()
        except OSError:
            pass


def apply(root):
    """Move tudo o que tem pasta conhecida; o resto fica em Downloads."""
    result = plan(root)
    moved, skipped = [], []
    for entry in result['moves']:
        reason = move_file(entry['file'], entry['dest'])
        (skipped.append(dict(entry, reason=reason)) if reason else moved.append(entry))
    if moved:
        write_log(root, [(e['file'], e['dest']) for e in moved])
    tidy(root)
    return {'ok': True, 'moved': moved, 'skipped': skipped, 'unknown': result['unknown'], 'folders': result['folders']}


def move_one(root, file, folder):
    """Move um arquivo de Downloads para uma pasta de gênero escolhida (artista novo)."""
    path = Path(file)
    base = (Path(root)/DOWNLOADS).resolve()
    if base not in path.resolve().parents:
        return {'ok': False, 'error': 'só arquivos de Downloads'}
    if folder not in folders(root):
        return {'ok': False, 'error': 'pasta desconhecida: ' + folder}
    artist, title, name = describe(path)
    dest = Path(root)/folder/name
    reason = move_file(path, dest)
    if reason:
        return {'ok': False, 'error': reason}
    write_log(root, [(path, dest)])
    tidy(root)
    return {'ok': True, 'moved': [{'file': str(path), 'artist': artist, 'title': title, 'name': name,
                                   'folder': folder, 'dest': str(dest)}]}


def main(argv=None):
    """Linha de comando (plan | apply | move FILE FOLDER); imprime um JSON."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', default=settings.get('music', 'dir'))
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('plan')
    sub.add_parser('apply')
    one = sub.add_parser('move')
    one.add_argument('file')
    one.add_argument('folder')
    args = parser.parse_args(argv)
    if not Path(args.root).is_dir():
        result = {'ok': False, 'error': 'pasta de música não existe: ' + args.root}
    elif args.cmd == 'plan':
        result = plan(args.root)
    elif args.cmd == 'apply':
        result = apply(args.root)
    else:
        result = move_one(args.root, args.file, args.folder)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
