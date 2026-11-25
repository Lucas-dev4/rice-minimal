#!/usr/bin/env python3
"""LW // MUSIC downloads through yt-dlp. Prints one JSON object per line (stream).

  ytdl.py download URL [--playlist] [--root DIR]
      Audio only, MP3 (best VBR), with title/artist tags and the thumbnail as a square
      cover. One video goes to ROOT/Downloads/ as "Artist - Title.mp3"; with --playlist
      the whole playlist goes to ROOT/Downloads/<playlist>/ as "NN - Title.mp3".
      Already downloaded videos are skipped (archive in ~/.local/share/lw/yt-dlp-archive.txt).

  Events: {"event": "start"|"item"|"progress"|"done"|"skip"|"error"|"end", ...}
  "end" carries ok/done/skipped/errors; exit 0 when nothing failed.
"""
# ytdl.py — baixa músicas e playlists do YouTube pelo yt-dlp para a aba ONLINE do LW.
# Grava em ~/Músicas/Downloads (playlist numa pasta própria) em MP3 com tags e capa,
# e conta o progresso em linhas JSON para a tela (gui/player/OnlineScreen.qml). A busca da tela
# (lw online search) também é daqui.
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import settings

# Linhas que o yt-dlp imprime para este script (o resto da saída é ignorado).
TAG = 'LW\t'
# prctl(PR_SET_PDEATHSIG): o sinal que o kernel manda ao processo quando o pai dele morre.
# Carregado aqui porque entre o fork e o exec não é hora de abrir biblioteca.
PRCTL = ctypes.CDLL(None).prctl
PR_SET_PDEATHSIG = 1
# Segundos que a busca espera pelo YouTube.
SEARCH_LIMIT = 30
# Capa quadrada: corta o centro da miniatura 16:9 do vídeo. O yt-dlp separa os argumentos
# do --ppa como um shell, por isso as aspas duplas em volta (as vírgulas ficam no crop).
SQUARE = 'crop="\'if(gt(ih,iw),iw,ih)\':\'if(gt(iw,ih),ih,iw)\'"'


def archive_path():
    """Lista dos vídeos já baixados (o yt-dlp pula os que estão nela)."""
    base = Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))
    return base/'lw'/'yt-dlp-archive.txt'


def command(url, root, playlist=False):
    """A linha de comando do yt-dlp para uma música (ou, com playlist, a playlist inteira)."""
    dest = Path(root)/'Downloads'
    if playlist:
        template = str(dest/'%(playlist_title,playlist|Playlist)s'/'%(playlist_index|0)02d - %(title).150B.%(ext)s')
    else:
        template = str(dest/'%(artist,creator,uploader|Desconhecido).60B - %(title).150B.%(ext)s')
    return [
        'yt-dlp', '--ignore-config', '--newline', '--no-colors', '--quiet', '--progress', '--no-simulate',
        '--yes-playlist' if playlist else '--no-playlist', '--ignore-errors',
        '-x', '--audio-format', 'mp3', '--audio-quality', '0',
        '--embed-metadata', '--embed-thumbnail', '--convert-thumbnails', 'jpg',
        '--ppa', f'ThumbnailsConvertor+ffmpeg_o:-c:v mjpeg -vf {SQUARE}',
        # O YouTube só põe o artista em músicas oficiais; senão vale o canal (sem o " - Topic").
        '--parse-metadata', '%(artist,creator,uploader|)s:%(meta_artist)s',
        '--replace-in-metadata', 'meta_artist', r' - Topic$', '',
        *(['--parse-metadata', '%(playlist_title,playlist|)s:%(meta_album)s',
           '--parse-metadata', '%(playlist_index|)s:%(meta_track)s'] if playlist else []),
        '--download-archive', str(archive_path()), '--no-overwrites',
        '-o', template,
        '--print', f'before_dl:{TAG}item\t%(playlist_index|1)s\t%(n_entries|1)s\t%(title)s',
        '--print', f'after_move:{TAG}done\t%(filepath)s',
        '--progress-template', f'download:{TAG}progress\t%(progress.downloaded_bytes|0)s\t'
                               '%(progress.total_bytes,progress.total_bytes_estimate|0)s',
        # --print liga o modo silencioso; sem ele o aviso de "já baixado" some.
        '--no-quiet', '--', url,
    ]


def parse(line):
    """Uma linha da saída do yt-dlp vira um evento (ou None se não interessa)."""
    line = line.rstrip('\n')
    if line.startswith(TAG):
        kind, *fields = line[len(TAG):].split('\t')
        if kind == 'item' and len(fields) >= 3:
            return {'event': 'item', 'index': int(fields[0] or 1), 'total': int(fields[1] or 1),
                    'title': '\t'.join(fields[2:])}
        if kind == 'done' and fields:
            return {'event': 'done', 'file': '\t'.join(fields)}
        if kind == 'progress' and len(fields) == 2:
            done, total = (float(x) if x.replace('.', '', 1).isdigit() else 0 for x in fields)
            return {'event': 'progress', 'percent': round(100*done/total, 1) if total else 0}
        return None
    if 'has already been recorded in the archive' in line or 'has already been downloaded' in line:
        return {'event': 'skip', 'message': line.split('] ', 1)[-1]}
    if line.startswith('ERROR:'):
        return {'event': 'error', 'message': line[6:].strip()}
    return None


def installed():
    """True se o yt-dlp está no PATH."""
    return shutil.which('yt-dlp') is not None


def tied():
    """O preexec_fn do yt-dlp: ele recebe SIGTERM se este processo morrer, até por SIGKILL."""
    parent = os.getpid()

    def prepare():
        PRCTL(PR_SET_PDEATHSIG, signal.SIGTERM, 0, 0, 0)
        # O pai pode ter morrido entre o fork e o prctl: aí o sinal não viria mais.
        if os.getppid() != parent:
            os._exit(143)
    return prepare


def search(query):
    """Busca no YouTube, ou lista o que tem num link (música ou playlist), sem baixar nada."""
    query = query.strip()
    if not query:
        raise ValueError('busca vazia')
    link = re.fullmatch(r'https?://\S+', query) is not None
    if not installed():
        raise FileNotFoundError('yt-dlp não está instalado: sudo pacman -S yt-dlp')
    # Cancelada pela tela: sair por exceção faz o subprocess.run matar o yt-dlp junto.
    before = signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    try:
        out = subprocess.run(['yt-dlp', '--flat-playlist', '--no-warnings', '-J', query if link else 'ytsearch25:' + query],
                             capture_output=True, text=True, timeout=SEARCH_LIMIT, preexec_fn=tied())
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f'o YouTube não respondeu em {SEARCH_LIMIT} s') from exc
    finally:
        signal.signal(signal.SIGTERM, before)
    try:
        data = json.loads(out.stdout) if out.returncode == 0 else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise RuntimeError(out.stderr.strip().split('\n')[-1] or f'yt-dlp falhou ({out.returncode})')
    entries = data.get('entries')
    many = entries is not None
    # A playlist (ou busca) traz entries; o link de uma música só, o próprio vídeo.
    if not many:
        entries = [dict(data, url=data.get('webpage_url') or query)] if link else []
    results = [{'title': e.get('title') or e['url'], 'artist': e.get('artist') or e.get('channel') or e.get('uploader') or '',
                'path': e['url'], 'duration_secs': e.get('duration') or 0, 'stream': True}
               for e in entries if e and e.get('url')]
    playlist = {'title': data.get('title') or 'Playlist', 'url': data.get('webpage_url') or query} if link and many else None
    return {'link': link, 'results': results, 'playlist': playlist}


def emit(event):
    """Manda um evento para a tela (uma linha JSON)."""
    print(json.dumps(event, ensure_ascii=False), flush=True)


def download(url, root, playlist=False):
    """Roda o yt-dlp e transforma a saída dele em eventos; devolve o código de saída."""
    if not shutil.which('yt-dlp'):
        emit({'event': 'end', 'ok': False, 'done': 0, 'skipped': 0, 'errors': 1,
              'message': 'yt-dlp não está instalado: sudo pacman -S yt-dlp'})
        return 1
    if not shutil.which('ffmpeg'):
        emit({'event': 'end', 'ok': False, 'done': 0, 'skipped': 0, 'errors': 1,
              'message': 'ffmpeg não está instalado: sudo pacman -S ffmpeg'})
        return 1
    archive_path().parent.mkdir(parents=True, exist_ok=True)
    emit({'event': 'start', 'url': url, 'playlist': playlist, 'dest': str(Path(root)/'Downloads')})
    child = subprocess.Popen(command(url, root, playlist), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, bufsize=1, start_new_session=True, preexec_fn=tied())

    def stop(*_):
        # Cancelado pela tela: para o yt-dlp e o ffmpeg dele junto.
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    counts = {'done': 0, 'skip': 0, 'error': 0}
    last = None
    for line in child.stdout:
        event = parse(line)
        if not event:
            continue
        if event['event'] in counts:
            counts[event['event']] += 1
        if event['event'] == 'error':
            last = event['message']
        emit(event)
    code = child.wait()
    cancelled = code < 0
    ok = not cancelled and counts['error'] == 0 and code == 0
    end = {'event': 'end', 'ok': ok, 'cancelled': cancelled, 'done': counts['done'],
           'skipped': counts['skip'], 'errors': counts['error']}
    if not ok:
        end['message'] = 'cancelado' if cancelled else (last or f'yt-dlp saiu com {code}')
    emit(end)
    return 0 if ok else 1


def main(argv=None):
    """Linha de comando: ytdl.py download URL [--playlist] [--root DIR]."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    d = sub.add_parser('download')
    d.add_argument('url')
    d.add_argument('--playlist', action='store_true')
    d.add_argument('--root', default=settings.get('music', 'dir'))
    args = parser.parse_args(argv)
    if not args.url.startswith(('http://', 'https://')):
        emit({'event': 'end', 'ok': False, 'done': 0, 'skipped': 0, 'errors': 1, 'message': 'link inválido'})
        return 1
    return download(args.url, args.root, args.playlist)


if __name__ == '__main__':
    sys.exit(main())
