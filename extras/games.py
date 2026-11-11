#!/usr/bin/env python3
"""LW // GAMES data: ~/.local/share/lw/games.json and the scanners that fill it.

  games.py scan                 merge every source into games.json (never drops your data)
  games.py list                 print games.json
  games.py add --exe PATH [--prefix DIR] [--title TEXT] [--args TEXT]
                                a Windows .exe (run with Wine) or a native executable
  games.py set ID KEY=VALUE...  edit status, progress, est_hours, notes, fav, order,
                                gamemode, mangohud, title
  games.py remove ID            drop a game (meant for ones marked missing)
  games.py running              ids whose processes are alive now (see running())
  games.py launch ID            start the game (gamemoderun/mangohud as toggled) and its watcher
  games.py watch ID             (started by launch) records the session: begins when the game's
                                process appears, ends when it is gone, even with LW closed
  games.py stop ID              asks the game's processes to quit (SIGTERM)

Sources: Steam (every library in libraryfolders.vdf, art from appcache/librarycache in
both the old flat and the newer per-app layout, playtime from userdata localconfig.vdf),
Wine/native executables added by hand, the Hydra Launcher's library when it names an
executable, and ROM folders (~/.local/share/lw/games-config.json). A scan only adds new
games and refreshes what the source knows (title, launch, cover, hours_source); status,
your hours, notes and the rest are never touched. Games a source no longer has are marked
`missing`, not removed. Everything prints one JSON object.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import shlex
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

STATUSES = ('want', 'playing', 'done', 'dropped')
EDITABLE = {'status': str, 'progress': int, 'est_hours': float, 'notes': str, 'fav': bool,
            'order': int, 'gamemode': bool, 'mangohud': bool, 'title': str}
# Steam "games" that are tools.
STEAM_TOOLS = re.compile(r'^(Proton|Steam Linux Runtime|Steamworks Common|SteamVR)', re.I)
ROM_EXT = {
    '.nes': 'fceumm', '.sfc': 'snes9x', '.smc': 'snes9x', '.gb': 'gambatte', '.gbc': 'gambatte',
    '.gba': 'mgba', '.n64': 'mupen64plus_next', '.z64': 'mupen64plus_next', '.v64': 'mupen64plus_next',
    '.nds': 'melonds', '.md': 'genesis_plus_gx', '.gen': 'genesis_plus_gx', '.sms': 'genesis_plus_gx',
    '.cue': 'swanstation', '.chd': 'swanstation', '.pbp': 'swanstation', '.psp': 'ppsspp', '.cso': 'ppsspp',
}


# ---- paths and storage --------------------------------------------------------------
def home():
    return Path(os.environ.get('HOME', str(Path.home())))


def data_dir():
    return Path(os.environ.get('XDG_DATA_HOME', home()/'.local'/'share'))/'lw'


def db_path():
    return data_dir()/'games.json'


def config():
    path = data_dir()/'games-config.json'
    defaults = {'rom_dirs': ['~/ROMs', '~/Jogos/ROMs'],
                'retroarch': 'retroarch', 'cores_dir': '/usr/lib/libretro', 'emulators': {}}
    try:
        defaults.update(json.loads(path.read_text()))
    except (OSError, ValueError):
        pass
    return defaults


@contextmanager
def locked():
    data_dir().mkdir(parents=True, exist_ok=True)
    with open(data_dir()/'games.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def load():
    try:
        data = json.loads(db_path().read_text())
        return data if isinstance(data, dict) and isinstance(data.get('games'), list) else {'games': []}
    except (OSError, ValueError):
        return {'games': []}


def save(data):
    fd, tmp = tempfile.mkstemp(dir=data_dir(), prefix='.games-', suffix='.json')
    with os.fdopen(fd, 'w') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=1)
    os.replace(tmp, db_path())


def short_hash(text):
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def blank(gid, title, source, launch, cover=None, hours_source=None):
    return {'id': gid, 'title': title, 'source': source, 'launch': launch, 'cover': cover,
            'status': 'want', 'hours': 0.0, 'hours_source': hours_source, 'est_hours': None,
            'progress': 0, 'fav': False, 'order': 0, 'last_played': None, 'sessions': [],
            'notes': '', 'gamemode': False, 'mangohud': False, 'missing': False}


# ---- Steam ----------------------------------------------------------------------------
def vdf(text):
    """Valve KeyValues text -> nested dicts (keys lower-cased)."""
    tokens = re.findall(r'"((?:[^"\\]|\\.)*)"|([{}])', text)
    def block(i):
        out = {}
        while i < len(tokens):
            word, brace = tokens[i]
            if brace == '}':
                return out, i + 1
            key = word.lower()
            value, brace2 = tokens[i + 1]
            if brace2 == '{':
                out[key], i = block(i + 2)
            else:
                out[key] = value.replace('\\\\', '\\')
                i += 2
        return out, i
    return block(0)[0]


def steam_roots():
    seen, out = set(), []
    for p in (home()/'.local/share/Steam', home()/'.steam/steam', home()/'.steam/root',
              home()/'.var/app/com.valvesoftware.Steam/.local/share/Steam'):
        if p.is_dir() and p.resolve() not in seen:
            seen.add(p.resolve())
            out.append(p)
    return out


def steam_cover(root, appid):
    cache = root/'appcache'/'librarycache'
    for pattern in (f'{appid}_library_600x900.jpg', f'{appid}/library_600x900.jpg', f'{appid}/*/library_600x900.jpg',
                    f'{appid}_header.jpg', f'{appid}/header.jpg', f'{appid}/*/header.jpg'):
        found = sorted(cache.glob(pattern))
        if found:
            return str(found[0])
    return None


def steam_playtime(root):
    minutes = {}
    for cfg in (root/'userdata').glob('*/config/localconfig.vdf'):
        try:
            apps = vdf(cfg.read_text(errors='replace'))['userlocalconfigstore']['software']['valve']['steam']['apps']
        except (KeyError, OSError):
            continue
        for appid, values in apps.items():
            if isinstance(values, dict) and values.get('playtime', '').isdigit():
                minutes[appid] = max(minutes.get(appid, 0), int(values['playtime']))
    return minutes


def scan_steam():
    found = []
    for root in steam_roots():
        try:
            folders = vdf((root/'steamapps'/'libraryfolders.vdf').read_text(errors='replace')).get('libraryfolders', {})
        except OSError:
            folders = {}
        libraries = {Path(v['path']) for v in folders.values() if isinstance(v, dict) and v.get('path')} | {root}
        playtime = steam_playtime(root)
        for lib in libraries:
            for acf in (lib/'steamapps').glob('appmanifest_*.acf'):
                try:
                    state = vdf(acf.read_text(errors='replace')).get('appstate', {})
                except OSError:
                    continue
                appid, name = state.get('appid'), state.get('name', '')
                if not appid or STEAM_TOOLS.match(name):
                    continue
                hours = round(playtime[appid] / 60, 1) if appid in playtime else None
                found.append(blank(f'steam:{appid}', name, 'steam', f'steam steam://rungameid/{appid}',
                                   steam_cover(root, appid), hours))
    return found


# ---- Hydra Launcher (best effort: only entries that name an executable) ---------------
def scan_hydra():
    db = home()/'.config'/'hydralauncher'/'hydra-db'
    found = {}
    for part in sorted(db.glob('*.log')) + sorted(db.glob('*.ldb')):
        text = part.read_bytes().decode('utf-8', 'replace')
        for m in re.finditer(r'\{[^{}]*"executablePath":"([^"]+)"[^{}]*\}', text):
            record = m.group(0)
            title = re.search(r'"title":"([^"]+)"', record)
            exe = m.group(1).replace('\\\\', '\\')
            if title and '"isDeleted":true' not in record and exe.lower().endswith('.exe'):
                prefix = re.search(r'"winePrefixPath":"([^"]+)"', record)
                found[exe] = wine_entry(exe, prefix.group(1) if prefix else None, title.group(1), source='hydra')
    return list(found.values())


# ---- Wine / native executables added by hand ------------------------------------------
def wine_entry(exe, prefix=None, title=None, args='', source='wine'):
    exe = str(Path(exe).expanduser())
    title = title or Path(exe).stem
    if exe.lower().endswith('.exe'):
        env = f'WINEPREFIX={shlex.quote(str(Path(prefix).expanduser()))} ' if prefix else ''
        launch = f'env {env}wine {shlex.quote(exe)}'.replace('env  ', 'env ')
    else:
        launch = shlex.quote(exe)
    if args:
        launch += ' ' + args
    entry = blank(f'{source}:{short_hash(exe)}', title, source, launch)
    entry.update(exe=exe, prefix=str(Path(prefix).expanduser()) if prefix else None, workdir=str(Path(exe).parent))
    return entry


# ---- ROMs -------------------------------------------------------------------------------
def scan_roms():
    cfg = config()
    found = []
    for folder in cfg['rom_dirs']:
        base = Path(folder).expanduser()
        if not base.is_dir():
            continue
        for rom in sorted(base.rglob('*')):
            ext = rom.suffix.lower()
            if not rom.is_file() or (ext not in ROM_EXT and ext not in cfg['emulators']):
                continue
            if ext in cfg['emulators']:
                launch = cfg['emulators'][ext].replace('{rom}', shlex.quote(str(rom)))
            else:
                core = Path(cfg['cores_dir'])/f'{ROM_EXT[ext]}_libretro.so'
                launch = f"{cfg['retroarch']} -L {shlex.quote(str(core))} {shlex.quote(str(rom))}"
            title = re.sub(r'\s*[\(\[][^\)\]]*[\)\]]', '', rom.stem).strip() or rom.stem
            entry = blank(f'rom:{short_hash(str(rom))}', title, 'rom', launch)
            entry.update(rom=str(rom), system=ext.lstrip('.'))
            found.append(entry)
    return found


# ---- merge ------------------------------------------------------------------------------
SCANNED = {'steam': scan_steam, 'hydra': scan_hydra, 'rom': scan_roms}
REFRESH = ('title', 'launch', 'cover', 'hours_source', 'exe', 'prefix', 'workdir', 'rom', 'system')


def merge(data, fresh):
    by_id = {g['id']: g for g in data['games']}
    new = 0
    next_order = max([g.get('order', 0) for g in data['games']] + [0]) + 1
    for entry in fresh:
        if entry['id'] in by_id:
            game = by_id[entry['id']]
            for key in REFRESH:
                if key in entry and entry[key] is not None and not (key == 'title' and game.get('title_edited')):
                    game[key] = entry[key]
            game['missing'] = False
        else:
            entry['order'] = next_order
            next_order += 1
            data['games'].append(entry)
            by_id[entry['id']] = entry
            new += 1
    return new


def scan():
    with locked():
        data = load()
        fresh, errors = [], {}
        for source, scanner in SCANNED.items():
            try:
                fresh += scanner()
            except Exception as exc:  # one broken source must not stop the others
                errors[source] = str(exc)
        seen = {g['id'] for g in fresh}
        new = merge(data, fresh)
        for game in data['games']:
            source = game.get('source')
            if source in SCANNED and source not in errors:
                game['missing'] = game['id'] not in seen
            elif source == 'wine':
                game['missing'] = not Path(game.get('exe', '')).exists()
        data['scanned_at'] = int(time.time())
        save(data)
    return {'total': len(data['games']), 'new': new,
            'missing': sum(1 for g in data['games'] if g.get('missing')), 'errors': errors}


def add(exe, prefix=None, title=None, args=''):
    if not Path(exe).expanduser().is_file():
        raise ValueError('executável não encontrado: ' + exe)
    with locked():
        data = load()
        entry = wine_entry(exe, prefix, title, args)
        if any(g['id'] == entry['id'] for g in data['games']):
            raise ValueError('já está na biblioteca: ' + entry['title'])
        merge(data, [entry])
        save(data)
    return {'added': entry}


def set_fields(gid, pairs):
    with locked():
        data = load()
        game = next((g for g in data['games'] if g['id'] == gid), None)
        if not game:
            raise ValueError('jogo não encontrado: ' + gid)
        for pair in pairs:
            key, _, raw = pair.partition('=')
            if key not in EDITABLE:
                raise ValueError('campo não editável: ' + key)
            kind = EDITABLE[key]
            if kind is bool:
                value = raw.lower() in ('1', 'true', 'on', 'sim', 'yes')
            elif key == 'est_hours' and raw in ('', 'null', 'none'):
                value = None
            else:
                value = kind(raw)
            if key == 'status' and value not in STATUSES:
                raise ValueError('status inválido: ' + raw)
            if key == 'progress':
                value = max(0, min(100, value))
            game[key] = value
            if key == 'title':
                game['title_edited'] = True
        save(data)
    return {'game': game}


def remove(gid):
    with locked():
        data = load()
        before = len(data['games'])
        data['games'] = [g for g in data['games'] if g['id'] != gid]
        if len(data['games']) == before:
            raise ValueError('jogo não encontrado: ' + gid)
        save(data)
    return {'removed': gid}


# ---- what is running --------------------------------------------------------------------
# Wine's own helpers inherit LW_GAME_ID too and linger after the game; they are not the game.
WINE_SYSTEM = {'wineserver', 'services.exe', 'winedevice.exe', 'explorer.exe', 'plugplay.exe', 'svchost.exe',
               'rpcss.exe', 'conhost.exe', 'start.exe', 'winemenubuilder', 'winemenubuilder.exe', 'tabtip.exe'}


def is_wine_helper(entry):
    try:
        return (entry/'comm').read_text().strip() in WINE_SYSTEM
    except OSError:
        return False


def running(proc='/proc'):
    """Game ids alive now. LW launches carry LW_GAME_ID (every child inherits it, the .exe
    under Wine too); Steam puts SteamAppId in its games' environment."""
    alive = set()
    for entry in Path(proc).iterdir():
        if not entry.name.isdigit():
            continue
        try:
            env = (entry/'environ').read_bytes().split(b'\0')
        except OSError:
            continue
        if is_wine_helper(entry):
            continue
        for var in env:
            if var.startswith(b'LW_GAME_ID='):
                alive.add(var[11:].decode(errors='replace'))
            elif var.startswith(b'SteamAppId=') and var[11:] not in (b'', b'0'):
                alive.add('steam:' + var[11:].decode(errors='replace'))
    return sorted(alive)


# ---- launch, watch, sessions --------------------------------------------------------------
import signal
import subprocess

WATCH_APPEAR = 180     # seconds to wait for the game's process (Wine and Steam can be slow)
WATCH_POLL = 2
HEARTBEAT = 30


def tools():
    from shutil import which
    return {'gamemode': bool(which('gamemoderun')), 'mangohud': bool(which('mangohud'))}


def command_for(game):
    """The command LW runs. Steam goes through steam:// (its own launch options decide the
    wrappers); everything else gets gamemoderun/mangohud in front when toggled and installed."""
    cmd = game['launch']
    if game['source'] == 'steam':
        return cmd
    have = tools()
    if game.get('mangohud') and have['mangohud']:
        cmd = 'mangohud ' + cmd
    if game.get('gamemode') and have['gamemode']:
        cmd = 'gamemoderun ' + cmd
    return cmd


def pids_of(gid, proc='/proc'):
    out = []
    want_lw = b'LW_GAME_ID=' + gid.encode()
    want_steam = b'SteamAppId=' + gid.split(':', 1)[1].encode() if gid.startswith('steam:') else None
    for entry in Path(proc).iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            env = (entry/'environ').read_bytes().split(b'\0')
        except OSError:
            continue
        if (want_lw in env or (want_steam and want_steam in env)) and not is_wine_helper(entry):
            out.append(int(entry.name))
    return out


def update(fn):
    with locked():
        data = load()
        result = fn(data)
        save(data)
    return result


def launch(gid):
    data = load()
    game = next((g for g in data['games'] if g['id'] == gid), None)
    if not game:
        raise ValueError('jogo não encontrado: ' + gid)
    if game.get('missing'):
        raise ValueError(game['title'] + ' sumiu da fonte')
    live = data.get('open_session')
    if live and pids_of(live['id']):
        other = next((g['title'] for g in data['games'] if g['id'] == live['id']), live['id'])
        raise ValueError('já há uma sessão: ' + other)
    cmd = command_for(game)
    env = dict(os.environ, LW_GAME_ID=gid)
    if game.get('prefix'):
        env['WINEPREFIX'] = game['prefix']
    cwd = game.get('workdir') if game.get('workdir') and Path(game['workdir']).is_dir() else str(home())
    log = data_dir()/'last-launch.log'
    with open(log, 'w') as out:
        subprocess.Popen(['sh', '-c', cmd], env=env, cwd=cwd, stdin=subprocess.DEVNULL, stdout=out,
                         stderr=subprocess.STDOUT, start_new_session=True)
    # The watcher is its own session too: closing LW never stops the count.
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'watch', gid], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                     env={k: v for k, v in os.environ.items() if k != 'LW_GAME_ID'})
    def pending(d):
        d['launching'] = {'id': gid, 'at': int(time.time()), 'command': cmd}
    update(pending)
    return {'command': cmd, 'tools': tools(), 'log': str(log)}


def watch(gid):
    # One watcher per game.
    with open(data_dir()/f'watch-{short_hash(gid)}.lock', 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return {'watch': 'already watching'}
        deadline = time.time() + WATCH_APPEAR
        while not pids_of(gid):
            if time.time() > deadline:
                def failed(d):
                    d.pop('launching', None)
                    d['launch_error'] = {'id': gid, 'at': int(time.time()), 'error': 'o processo do jogo não apareceu em %d s' % WATCH_APPEAR}
                update(failed)
                return {'watch': 'not started'}
            time.sleep(0.5)
        start = time.time()
        def begin(d):
            d.pop('launching', None)
            prior = d.get('open_session')
            # LW reopened during a session that is still running: keep its start.
            d['open_session'] = prior if prior and prior.get('id') == gid else {'id': gid, 'start': int(start), 'seen': int(start)}
        update(begin)
        misses, beat = 0, time.time()
        while misses < 2:
            time.sleep(WATCH_POLL)
            misses = 0 if pids_of(gid) else misses + 1
            if misses == 0 and time.time() - beat >= HEARTBEAT:
                beat = time.time()
                update(lambda d: d.get('open_session') and d['open_session'].update(seen=int(beat)))
        return {'added_hours': close_session(gid, time.time() - WATCH_POLL * 2)}


def close_session(gid, end):
    def finish(d):
        live = d.get('open_session')
        if not live or live.get('id') != gid:
            return 0
        game = next((g for g in d['games'] if g['id'] == gid), None)
        d.pop('open_session', None)
        if not game:
            return 0
        start = live['start']
        end_at = max(start, int(end))
        hours = round((end_at - start) / 3600, 3)
        game.setdefault('sessions', []).append({'start': start, 'end': end_at})
        game['hours'] = round(game.get('hours', 0) + hours, 3)
        game['last_played'] = end_at
        if game.get('status') == 'want':
            game['status'] = 'playing'
        d['last_session'] = {'id': gid, 'title': game['title'], 'hours': hours, 'end': end_at}
        return hours
    return update(finish)


def recover():
    """LW (re)opened: a session whose game is gone (crash, reboot, killed watcher) ends at its
    last heartbeat; one whose game still runs gets a watcher again."""
    data = load()
    live = data.get('open_session')
    if not live:
        return {'session': None}
    if pids_of(live['id']):
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'watch', live['id']], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return {'session': 'running', 'id': live['id']}
    return {'session': 'closed', 'id': live['id'], 'added_hours': close_session(live['id'], live.get('seen', live['start']))}


def stop(gid):
    pids = pids_of(gid)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    return {'signalled': len(pids)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('scan')
    sub.add_parser('list')
    sub.add_parser('running')
    a = sub.add_parser('add')
    a.add_argument('--exe', required=True)
    a.add_argument('--prefix')
    a.add_argument('--title')
    a.add_argument('--args', default='')
    s = sub.add_parser('set')
    s.add_argument('id')
    s.add_argument('pairs', nargs='+')
    r = sub.add_parser('remove')
    r.add_argument('id')
    for name in ('launch', 'watch', 'stop'):
        sub.add_parser(name).add_argument('id')
    sub.add_parser('recover')
    args = parser.parse_args(argv)
    try:
        if args.action == 'scan':
            data = scan()
        elif args.action == 'list':
            data = load()
        elif args.action == 'running':
            data = {'running': running()}
        elif args.action == 'add':
            data = add(args.exe, args.prefix, args.title, args.args)
        elif args.action == 'set':
            data = set_fields(args.id, args.pairs)
        elif args.action == 'launch':
            data = launch(args.id)
        elif args.action == 'watch':
            data = watch(args.id)
        elif args.action == 'stop':
            data = stop(args.id)
        elif args.action == 'recover':
            data = recover()
        else:
            data = remove(args.id)
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(dict(ok=True, **data), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
