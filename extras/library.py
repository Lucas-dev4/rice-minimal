#!/usr/bin/env python3
"""LW // MUSIC library index: the tags of every audio file under ~/Músicas.

  library.py lookup [--root DIR] --out PLAN.json
      Looks every track up online (Deezer first, the iTunes Search API for what Deezer
      misses; only artist and title are sent) and writes a proposal: the genre per artist
      (the majority of that artist's matched tracks, so one artist gets one genre), the
      year per matched track, and a cover only for files without one. Writes nothing to
      the audio files.
  library.py apply --plan PLAN.json
      Writes the proposal: every existing tag is kept (lyrics too); genre, date, title,
      artist, album and album_artist are set when the plan has them,
      covers embedded; the audio is copied untouched and checked by hash before the
      original goes to the trash.
  library.py scan [--root DIR]
      Prints one JSON object: {"ok", "root", "tracks": [{path, title, artist, album,
      genre, year, duration, cover, lyrics}]}. Tags are read with ffprobe only for files
      that are new or changed since the last scan (cache in
      ~/.cache/rice-minimal/music-library.json). Lyrics are cut to 4000 characters, enough
      to search in. Nothing is ever written to the audio files.
"""
# library.py — índice da biblioteca de música (~/Músicas) para a aba BIBLIOTECA do LW.
# "scan" lê as tags (com cache); "lookup" + "apply" organizam gênero/ano/capa buscando na internet,
# sem nunca mexer no áudio (o arquivo novo é conferido por hash e o antigo vai para a lixeira).
import argparse
import collections
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path

AUDIO = {'.mp3', '.m4a', '.flac', '.ogg', '.opus', '.wav', '.aac', '.wv', '.ape', '.aiff', '.alac', '.wma'}
LYRICS_LIMIT = 4000


def cache_path():
    """Onde fica o cache das tags já lidas (~/.cache/rice-minimal/music-library.json)."""
    return Path(os.environ.get('XDG_CACHE_HOME', Path.home()/'.cache'))/'rice-minimal'/'music-library.json'


def clean(value):
    """Tira espaços repetidos e o caractere invisível BOM de um texto de tag."""
    return ' '.join(str(value or '').replace('﻿', '').split())


def read_tags(path):
    """Lê as tags de um arquivo de áudio com ffprobe (título, artista, álbum, gênero, ano, duração, capa, letra)."""
    out = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', str(path)],
                         capture_output=True, text=True, timeout=30).stdout
    data = json.loads(out or '{}')
    fmt = data.get('format') or {}
    tags = {k.lower(): v for k, v in (fmt.get('tags') or {}).items()}
    lyrics = next((v for k, v in tags.items() if k.startswith('lyrics') or k == 'unsyncedlyrics'), '')
    date = clean(tags.get('date') or tags.get('year') or '')
    return {
        'title': clean(tags.get('title')), 'artist': clean(tags.get('artist')), 'album': clean(tags.get('album')),
        'genre': clean(tags.get('genre')), 'year': date[:4] if date[:4].isdigit() else '',
        'duration': round(float(fmt.get('duration') or 0), 1),
        'cover': any((s.get('disposition') or {}).get('attached_pic') for s in data.get('streams', [])),
        'lyrics': str(lyrics).replace('﻿', '')[:LYRICS_LIMIT],
    }


def scan(root):
    """Lista todas as músicas com as tags; só relê arquivos novos ou alterados desde a última vez."""
    root = Path(root).expanduser()
    files = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in AUDIO)
    cache_file = cache_path()
    try:
        cache = json.loads(cache_file.read_text())
    except (OSError, ValueError):
        cache = {}
    fresh, todo = {}, []
    for p in files:
        st = p.stat()
        key = str(p)
        stamp = [st.st_mtime_ns, st.st_size]
        if key in cache and cache[key].get('stamp') == stamp:
            fresh[key] = cache[key]
        else:
            todo.append((key, stamp))
    with ThreadPoolExecutor(6) as pool:
        for (key, stamp), tags in zip(todo, pool.map(lambda job: read_tags(job[0]), todo)):
            fresh[key] = dict(tags, stamp=stamp)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=cache_file.parent, prefix='.music-library-')
    with os.fdopen(fd, 'w') as stream:
        json.dump(fresh, stream, ensure_ascii=False)
    os.replace(tmp, cache_file)
    tracks = []
    for p in files:
        t = dict(fresh[str(p)])
        t.pop('stamp', None)
        t['path'] = str(p)
        t['title'] = t['title'] or p.stem
        tracks.append(t)
    return {'root': str(root), 'tracks': tracks, 'read': len(todo)}


# ---- online lookup -----------------------------------------------------------------
AGENT = 'rice-minimal-lw-music/1.0'


def fold(text):
    """Normaliza um texto para comparar: minúsculas, sem acentos, sem parênteses e pontuação."""
    text = unicodedata.normalize('NFKD', str(text).lower())
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r'[\(\[].*?[\)\]]', ' ', text)
    return ' '.join(re.sub(r'[^\w\s]', ' ', text).split())


def fetch(url):
    """Baixa e decodifica um JSON de uma URL (com tempo limite)."""
    request = urllib.request.Request(url, headers={'User-Agent': AGENT})
    with urllib.request.urlopen(request, timeout=10) as reply:
        return json.load(reply)


def best_match(track, candidates):
    """Entre os resultados online, o mais parecido com artista+título (mínimo de 80% em cada)."""
    artist, title = fold(track['artist'].split(',')[0]), fold(track['title'])
    found = None
    for c in candidates:
        sa = SequenceMatcher(None, artist, fold(c['artist'])).ratio()
        st = SequenceMatcher(None, title, fold(c['title'])).ratio()
        if sa >= 0.8 and st >= 0.8 and (not found or sa + st > found[0]):
            found = (sa + st, c)
    return found[1] if found else None


class Online:
    """Busca online de uma faixa: Deezer primeiro e iTunes como reserva, respeitando o limite de pedidos."""
    def __init__(self):
        self.albums = {}
        self.last = {'deezer': 0.0, 'itunes': 0.0}

    def pace(self, source, gap):
        """Espera o intervalo mínimo entre pedidos a um mesmo serviço."""
        wait = self.last[source] + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self.last[source] = time.monotonic()

    def deezer(self, track):
        """Procura a faixa no Deezer; gênero e ano vêm do álbum (guardado em cache)."""
        self.pace('deezer', 0.15)
        query = urllib.parse.urlencode({'q': track['artist'].split(',')[0] + ' ' + track['title'], 'limit': 8})
        data = fetch('https://api.deezer.com/search?' + query).get('data', [])
        match = best_match(track, [{'artist': x['artist']['name'], 'title': x['title'], 'album': x['album']['id'],
                                    'cover': x['album'].get('cover_xl', '')} for x in data])
        if not match:
            return None
        if match['album'] not in self.albums:
            self.pace('deezer', 0.15)
            album = fetch('https://api.deezer.com/album/' + str(match['album']))
            self.albums[match['album']] = ((album.get('genres') or {}).get('data') or [{}])[0].get('name', ''), (album.get('release_date') or '')[:4]
        genre, year = self.albums[match['album']]
        return {'source': 'deezer', 'artist': match['artist'], 'title': match['title'], 'genre': genre, 'year': year, 'cover': match['cover']}

    def itunes(self, track):
        """Procura a faixa no iTunes (mais lento: ~20 pedidos por minuto)."""
        self.pace('itunes', 3.2)  # about 20 requests a minute
        query = urllib.parse.urlencode({'term': track['artist'].split(',')[0] + ' ' + track['title'], 'entity': 'song', 'limit': 8, 'country': 'BR'})
        data = fetch('https://itunes.apple.com/search?' + query).get('results', [])
        match = best_match(track, [{'artist': x.get('artistName', ''), 'title': x.get('trackName', ''), 'genre': x.get('primaryGenreName', ''),
                                    'year': (x.get('releaseDate') or '')[:4], 'cover': (x.get('artworkUrl100') or '').replace('100x100', '600x600')} for x in data])
        return dict(match, source='itunes') if match else None


def lookup(root, out):
    """Monta a proposta de mudanças (plano JSON) para todas as faixas; um gênero por artista."""
    tracks = scan(root)['tracks']
    online, found = Online(), {}
    for n, t in enumerate(tracks, 1):
        if 'Gravações' in Path(t['path']).parts:
            continue
        match = None
        for source in (online.deezer, online.itunes):
            try:
                match = source(t)
            except (OSError, ValueError, KeyError):
                match = None
            if match:
                break
        found[t['path']] = match
        print(f'\r{n}/{len(tracks)} encontradas: {sum(1 for m in found.values() if m)}', end='', file=sys.stderr, flush=True)
    print(file=sys.stderr)
    # One genre per artist: the most common among that artist's matches.
    by_artist = collections.defaultdict(collections.Counter)
    for t in tracks:
        m = found.get(t['path'])
        if m and m.get('genre'):
            by_artist[t['artist'].split(',')[0].strip()][m['genre']] += 1
    plan = []
    for t in tracks:
        if t['path'] not in found:
            continue
        m, main = found[t['path']], t['artist'].split(',')[0].strip()
        change = {}
        if not t['genre'] and by_artist.get(main):
            change['genre'] = by_artist[main].most_common(1)[0][0]
        if not t['year'] and m and m.get('year'):
            change['date'] = m['year']
        if not t['cover'] and m and m.get('cover'):
            change['cover'] = m['cover']
        plan.append({'path': t['path'], 'artist': t['artist'], 'title': t['title'], 'match': m, 'set': change})
    Path(out).write_text(json.dumps(plan, ensure_ascii=False, indent=1))
    return {'plan': str(out), 'tracks': len(plan), 'matched': sum(1 for p in plan if p['match']),
            'genre': sum(1 for p in plan if 'genre' in p['set']), 'date': sum(1 for p in plan if 'date' in p['set']),
            'cover': sum(1 for p in plan if 'cover' in p['set']),
            'artist_genres': {a: c.most_common(1)[0][0] for a, c in sorted(by_artist.items())}}


def meta_escape(value):
    """Escapa caracteres especiais para o arquivo de metadados do ffmpeg."""
    return re.sub(r'([=;#\\\n])', r'\\\1', str(value))


def audio_md5(path):
    """Hash só do áudio (sem as tags) — prova que o som não mudou."""
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a', '-c', 'copy', '-f', 'md5', '-'], capture_output=True, text=True)
    return r.stdout.strip()


def apply_one(entry):
    """Regrava as tags de um arquivo: copia o áudio sem recodificar, confere o hash e manda o original para a lixeira."""
    src = Path(entry['path'])
    change = entry['set']
    if not change or not src.is_file():
        return {'path': str(src), 'ok': True, 'skipped': True}
    out = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', str(src)], capture_output=True, text=True).stdout
    tags = {k: v.replace('\ufeff', '') for k, v in ((json.loads(out).get('format') or {}).get('tags') or {}).items()}
    for key in ('genre', 'date', 'title', 'artist', 'album', 'album_artist'):
        if key in change:
            tags[key] = change[key]
    work = src.with_name('.lw-tags-' + src.stem)
    meta, cover, tmp = work.with_suffix('.txt'), work.with_suffix('.jpg'), src.with_name('.lw-tmp-' + src.name)
    meta.write_text(';FFMETADATA1\n' + ''.join(f'{meta_escape(k)}={meta_escape(v)}\n' for k, v in tags.items()))
    args = ['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-i', str(meta)]
    if 'cover' in change:
        request = urllib.request.Request(change['cover'], headers={'User-Agent': AGENT})
        with urllib.request.urlopen(request, timeout=15) as reply:
            cover.write_bytes(reply.read())
        args += ['-i', str(cover), '-map', '0:a', '-map', '2', '-disposition:v', 'attached_pic', '-metadata:s:v', 'comment=Cover (front)']
    else:
        args += ['-map', '0']
    args += ['-c', 'copy', '-map_metadata', '1']
    if src.suffix.lower() == '.mp3':
        args += ['-id3v2_version', '3']
    try:
        r = subprocess.run(args + [str(tmp)], capture_output=True, text=True)
        if r.returncode or not audio_md5(tmp) or audio_md5(src) != audio_md5(tmp):
            tmp.unlink(missing_ok=True)
            return {'path': str(src), 'ok': False, 'error': r.stderr.strip()[-300:] or 'áudio diferente'}
        trashed = src.with_name('.lw-old-' + src.name)
        os.replace(src, trashed)
        os.replace(tmp, src)
        if subprocess.run(['gio', 'trash', str(trashed)], capture_output=True).returncode:
            return {'path': str(src), 'ok': True, 'note': 'original antigo ficou como ' + trashed.name}
        return {'path': str(src), 'ok': True}
    finally:
        meta.unlink(missing_ok=True)
        cover.unlink(missing_ok=True)


def apply(plan_file):
    """Aplica o plano inteiro, 4 arquivos por vez."""
    plan = json.loads(Path(plan_file).read_text())
    with ThreadPoolExecutor(4) as pool:
        done = list(pool.map(apply_one, plan))
    bad = [d for d in done if not d['ok']]
    return {'written': sum(1 for d in done if d['ok'] and not d.get('skipped')), 'failed': bad}


def main(argv=None):
    """Linha de comando: scan | lookup | apply."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='action', required=True)
    s = sub.add_parser('scan')
    s.add_argument('--root', default=str(Path.home()/'Músicas'))
    look = sub.add_parser('lookup')
    look.add_argument('--root', default=str(Path.home()/'Músicas'))
    look.add_argument('--out', required=True)
    write = sub.add_parser('apply')
    write.add_argument('--plan', required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == 'lookup':
            data = lookup(args.root, args.out)
        elif args.action == 'apply':
            data = apply(args.plan)
        else:
            data = scan(args.root)
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(dict(ok=True, **data), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
