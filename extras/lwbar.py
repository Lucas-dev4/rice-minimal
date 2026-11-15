#!/usr/bin/env python3
"""LW in Waybar: the game in session or what cliamp plays, one JSON line per change.

  lwbar.py          stream for a Waybar custom module ("return-type": "json")
  lwbar.py click    open LW on what the module shows (JOGOS during a session, else MÚSICA)

A game session wins over music, as in LW itself. Nothing running → empty text, and
Waybar hides the module. Reads only: games.json (written by extras/games.py) and
`cliamp remote state`; never starts cliamp.
"""
# lwbar.py — módulo "custom/lw" da Waybar (config/waybar/config.jsonc).
# A cada segundo calcula o texto (jogo em sessão > música tocando > vazio) e só imprime quando muda.
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get('HOME', str(Path.home())))
GAMES = Path(os.environ.get('XDG_DATA_HOME', HOME/'.local'/'share'))/'lw'/'games.json'
CLIAMP = str(HOME/'.local'/'bin'/'cliamp')
WIDTH = 42


def session():
    """(title, seconds) of the open game session, or None."""
    try:
        data = json.loads(GAMES.read_text())
    except (OSError, ValueError):
        return None
    live = data.get('open_session')
    if not live:
        return None
    game = next((g for g in data.get('games', []) if g.get('id') == live.get('id')), {})
    return game.get('title') or live.get('id', ''), max(0, int(time.time() - live.get('start', time.time())))


def find_state(node):
    """Procura, no JSON do cliamp, o objeto que tem "state" e "track" (o formato pode vir aninhado)."""
    if isinstance(node, dict):
        if 'state' in node and 'track' in node:
            return node
        for value in node.values():
            found = find_state(value)
            if found:
                return found
    return None


def music():
    """(state, title, artist) from cliamp, or None when it is off or stopped."""
    try:
        out = subprocess.run([CLIAMP, 'remote', 'state'], capture_output=True, text=True, timeout=2)
        snap = find_state(json.loads(out.stdout)) if out.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    if not snap or snap.get('state') not in ('playing', 'paused'):
        return None
    track = snap.get('track') or {}
    title = (track.get('title') or Path(track.get('path') or '').stem).replace('﻿', '').strip()
    return snap['state'], title, (track.get('artist') or '').strip()


def clock(seconds):
    """Segundos → "m:ss" ou "h:mm:ss"."""
    h, rest = divmod(seconds, 3600)
    return f'{h}:{rest // 60:02d}:{rest % 60:02d}' if h else f'{rest // 60}:{rest % 60:02d}'


def cut(text):
    """Corta o texto em WIDTH caracteres, com reticências."""
    return text if len(text) <= WIDTH else text[:WIDTH - 1] + '…'


def line():
    """O que a Waybar mostra agora: texto, classe CSS (game/playing/paused/idle) e dica do mouse."""
    game = session()
    if game:
        title, seconds = game
        return {'text': f'● {clock(seconds)} {cut(title)} |', 'class': 'game',
                'tooltip': f'{title} — sessão de {clock(seconds)}\nclique: abrir JOGOS'}
    song = music()
    if song:
        state, title, artist = song
        mark = '▶' if state == 'playing' else '❚❚'
        label = f'{title} — {artist}' if artist else title
        return {'text': f'{mark} {cut(label)} |', 'class': state,
                'tooltip': f'{label}\nclique: abrir MÚSICA · direito: play/pause'}
    return {'text': '', 'class': 'idle'}


def stream():
    """Laço infinito: imprime uma linha JSON sempre que o conteúdo muda (a Waybar lê o stdout)."""
    last = None
    while True:
        now = json.dumps(line(), ensure_ascii=False)
        if now != last:
            print(now, flush=True)
            last = now
        time.sleep(1)


def click():
    """Clique no módulo: abre o LW em JOGOS se houver sessão de jogo, senão em MÚSICA."""
    lw = str(HOME/'.local'/'bin'/'lw')
    os.execv(lw, [lw, 'games' if session() else 'music'])


if __name__ == '__main__':
    if sys.argv[1:] == ['click']:
        click()
    elif sys.argv[1:]:
        sys.exit(__doc__)
    else:
        stream()
