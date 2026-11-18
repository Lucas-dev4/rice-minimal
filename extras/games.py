#!/usr/bin/env python3
"""LW // GAMES data: ~/.local/share/lw/games.json and the scanners that fill it.

  games.py scan                 merge every source into games.json (never drops your data)
  games.py list                 print games.json
  games.py add --exe PATH [--prefix DIR] [--title TEXT] [--args TEXT]
                                a Windows .exe (run with Wine) or a native executable
  games.py set ID KEY=VALUE...  edit status, progress, est_hours, notes, fav, order,
                                gamemode, mangohud, proton, gamescope, fsr, complete (100%), title,
                                prefix (the Wine/Proton prefix; the launch command follows);
                                becoming done/complete stamps done_at/complete_at
  games.py remove ID            drop a game (meant for ones marked missing)
  games.py running              ids whose processes are alive now (see running())
  games.py launch ID            start the game and its watcher; Windows games run with Wine or,
                                when `proton` is on, Proton-GE through umu-run; gamemoderun,
                                mangohud and gamescope (fsr: 75% upscaled) as toggled
  games.py watch ID             (started by launch) records the session: begins when the game's
                                process appears, ends when it is gone, even with LW closed
  games.py stop ID              asks the game's processes to quit (SIGTERM)
  games.py arrange STATUS ID... one backlog column at once: these games get STATUS and
                                order 1..n in this sequence (drag & drop, Shift+arrows)
  games.py installers           Windows installers in the download folders (setup.exe, *.msi)
                                and what LW already did with each
  games.py install SETUP [--name TEXT]
                                runs the installer in a new Wine prefix (~/Games/<name>); a
                                detached worker waits for it and lists the new .exe files
  games.py install-add SETUP EXE   puts the chosen .exe in the library (with that prefix)
  games.py install-forget SETUP    drops LW's record of that installer (the prefix stays)
  games.py add-ready EXE --name TEXT
                                a game that came ready (a Hydra download): library entry with
                                its own prefix in ~/Games/<name> and Proton on when umu exists
  games.py meta [--all] [ID...]  IGDB data for games that have none yet (or these ids, or all):
                                cover and est_hours only where empty; genres, year, the three
                                times to beat and similar games kept in the game's `igdb`

Sources: Steam (every library in libraryfolders.vdf, art from appcache/librarycache in
both the old flat and the newer per-app layout, playtime from userdata localconfig.vdf),
Wine/native executables added by hand, the Hydra Launcher's library when it names an
executable, and ROM folders (~/.local/share/lw/games-config.json). A scan only adds new
games and refreshes what the source knows (title, launch, cover, hours_source); status,
your hours, notes and the rest are never touched. Games a source no longer has are marked
`missing`, not removed. Everything prints one JSON object.
"""
# games.py — o "cérebro" da seção JOGOS do LW. Só ele escreve em ~/.local/share/lw/games.json.
# Partes: scanners (Steam, Hydra, ROMs/emuladores, PS4) → merge sem perder seus dados (status, horas, notas);
# lançar o jogo (Wine/Proton/emulador + gamemode/mangohud/gamescope) e o "vigia" que conta as horas;
# instaladores de Windows; metadados do IGDB (capa, gêneros, duração).
# Toda escrita usa a trava games.lock + gravação atômica, então GUI e linha de comando podem rodar juntas.
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
EDITABLE = {'status': str, 'progress': int, 'est_hours': float, 'notes': str, 'fav': bool, 'igdb_id': int,
            'order': int, 'gamemode': bool, 'mangohud': bool, 'title': str,
            'proton': bool, 'gamescope': bool, 'fsr': bool, 'complete': bool, 'prefix': str,
            'steam_appid': int}
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
    """Pasta pessoal (respeita $HOME, útil nos testes)."""
    return Path(os.environ.get('HOME', str(Path.home())))


def data_dir():
    """Pasta de dados do LW: ~/.local/share/lw."""
    return Path(os.environ.get('XDG_DATA_HOME', home()/'.local'/'share'))/'lw'


def db_path():
    """O arquivo da biblioteca: games.json."""
    return data_dir()/'games.json'


def config():
    """Configuração (games-config.json) por cima dos padrões: pastas de ROMs, prontos, emuladores, RetroArch."""
    path = data_dir()/'games-config.json'
    defaults = {'rom_dirs': ['~/ROMs', '~/Jogos/ROMs'], 'ready_dirs': ['~/Downloads/hydra_Jogos'],
                'emulator_dirs': ['~/Jogos/Emuladores'],
                'retroarch': 'retroarch', 'cores_dir': '/usr/lib/libretro', 'emulators': {}}
    try:
        defaults.update(json.loads(path.read_text()))
    except (OSError, ValueError):
        pass
    return defaults


@contextmanager
def locked():
    """Trava exclusiva do games.json enquanto o bloco "with locked():" roda."""
    data_dir().mkdir(parents=True, exist_ok=True)
    with open(data_dir()/'games.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def load():
    """Lê o games.json (ou uma biblioteca vazia se não existir/estiver quebrado)."""
    try:
        data = json.loads(db_path().read_text())
        return data if isinstance(data, dict) and isinstance(data.get('games'), list) else {'games': []}
    except (OSError, ValueError):
        return {'games': []}


def save(data):
    """Grava o games.json de forma atômica (nunca fica pela metade)."""
    fd, tmp = tempfile.mkstemp(dir=data_dir(), prefix='.games-', suffix='.json')
    with os.fdopen(fd, 'w') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=1)
    os.replace(tmp, db_path())


def short_hash(text):
    """12 caracteres de hash — usado para criar ids estáveis a partir de caminhos."""
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def blank(gid, title, source, launch, cover=None, hours_source=None):
    """Um jogo novo com todos os campos no valor inicial (status "quero jogar", 0 horas...)."""
    return {'id': gid, 'title': title, 'source': source, 'launch': launch, 'cover': cover,
            'status': 'want', 'hours': 0.0, 'hours_source': hours_source, 'est_hours': None,
            'progress': 0, 'fav': False, 'order': 0, 'last_played': None, 'sessions': [],
            'notes': '', 'gamemode': False, 'mangohud': False, 'missing': False}


# ---- Steam ----------------------------------------------------------------------------
def vdf(text):
    """Valve KeyValues text -> nested dicts (keys lower-cased)."""
    tokens = re.findall(r'"((?:[^"\\]|\\.)*)"|([{}])', text)
    def block(i):
        """Lê um bloco { ... } do VDF recursivamente."""
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
    """Pastas onde a Steam pode estar instalada (normal, ~/.steam e Flatpak), sem repetir."""
    seen, out = set(), []
    for p in (home()/'.local/share/Steam', home()/'.steam/steam', home()/'.steam/root',
              home()/'.var/app/com.valvesoftware.Steam/.local/share/Steam'):
        if p.is_dir() and p.resolve() not in seen:
            seen.add(p.resolve())
            out.append(p)
    return out


def steam_cover(root, appid):
    """Capa de um jogo da Steam no cache local (vertical primeiro, depois o banner)."""
    cache = root/'appcache'/'librarycache'
    for pattern in (f'{appid}_library_600x900.jpg', f'{appid}/library_600x900.jpg', f'{appid}/*/library_600x900.jpg',
                    f'{appid}_header.jpg', f'{appid}/header.jpg', f'{appid}/*/header.jpg'):
        found = sorted(cache.glob(pattern))
        if found:
            return str(found[0])
    return None


def steam_playtime(root):
    """Minutos jogados de cada jogo, lidos do localconfig.vdf da Steam."""
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
    """Jogos instalados em todas as bibliotecas da Steam, com capa e horas."""
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
    """Jogos do Hydra Launcher que têm executável (lidos do banco de dados dele)."""
    db = home()/'.config'/'hydralauncher'/'hydra-db'
    found = {}
    for part in sorted(db.glob('*.log')) + sorted(db.glob('*.ldb')):
        text = part.read_bytes().decode('utf-8', 'replace')
        for m in re.finditer(r'\{[^{}]*"executablePath":"([^"]+)"[^{}]*\}', text):
            record = m.group(0)
            title = re.search(r'"title":"([^"]+)"', record)
            exe = m.group(1).replace('\\\\', '\\')
            # The .ldb files are Snappy-compressed: a record read raw can come out with
            # compression bytes in the middle of the path. Only a path that exists is real.
            if (title and '"isDeleted":true' not in record and exe.lower().endswith('.exe')
                    and Path(exe).is_file()):
                prefix = re.search(r'"winePrefixPath":"([^"]+)"', record)
                found[exe] = wine_entry(exe, prefix.group(1) if prefix else None, title.group(1), source='hydra')
    return list(found.values())


# ---- Wine / native executables added by hand ------------------------------------------
def wine_entry(exe, prefix=None, title=None, args='', source='wine'):
    """Monta a entrada de um jogo de PC: .exe roda com Wine (prefixo opcional), outro executável roda direto."""
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
    # Windows games run with Proton-GE by default when umu-run is there (a scan never
    # changes this on games already in the library: `proton` is not refreshed).
    from shutil import which
    entry['proton'] = exe.lower().endswith('.exe') and bool(which('umu-run'))
    return entry


# ---- ROMs -------------------------------------------------------------------------------
# A folder per console under a ROM dir (~/Jogos/ROMs/ps2/…) says which emulator runs it:
# extensions alone cannot (an .iso is PS2, PSP, GameCube or Wii). (emulator, core, extensions)
ARCHIVES = {'.zip', '.7z'}
EMU_SYSTEMS = {
    'nes': ('retroarch', 'nestopia', {'.nes'} | ARCHIVES),
    'snes': ('retroarch', 'snes9x', {'.sfc', '.smc'} | ARCHIVES),
    'megadrive': ('retroarch', 'genesis_plus_gx', {'.md', '.gen', '.smd', '.bin'} | ARCHIVES),
    'gba': ('retroarch', 'mgba', {'.gba', '.gb', '.gbc'} | ARCHIVES),
    'n64': ('retroarch', 'mupen64plus_next', {'.n64', '.z64', '.v64'} | ARCHIVES),
    'nds': ('retroarch', 'melonds', {'.nds'} | ARCHIVES),
    'ps1': ('retroarch', 'mednafen_psx_hw', {'.cue', '.chd', '.pbp', '.m3u', '.bin'}),
    'ps2': ('pcsx2', None, {'.iso', '.chd', '.cso', '.gz', '.bin'}),
    'psp': ('ppsspp', None, {'.iso', '.cso', '.pbp', '.chd'}),
    '3ds': ('azahar', None, {'.3ds', '.cci', '.cia', '.cxi', '.3dsx'}),
    'gamecube': ('dolphin', None, {'.iso', '.gcm', '.rvz', '.ciso', '.gcz'}),
    'wii': ('dolphin', None, {'.iso', '.wbfs', '.rvz', '.wad', '.gcz'}),
    'switch': ('ryujinx', None, {'.nsp', '.xci', '.nro'}),
}
SYSTEM_NAMES = {'nes': 'NES', 'snes': 'SNES', 'megadrive': 'Mega Drive', 'gba': 'Game Boy', 'n64': 'Nintendo 64',
                'nds': 'Nintendo DS', 'ps1': 'PlayStation', 'ps2': 'PlayStation 2', 'psp': 'PSP', '3ds': 'Nintendo 3DS',
                'gamecube': 'GameCube', 'wii': 'Wii', 'switch': 'Switch', 'ps4': 'PlayStation 4'}


def appimage(name, cfg):
    """The newest AppImage of an emulator in emulator_dirs (pcsx2-v2.8.2-…AppImage), or None."""
    found = []
    for folder in cfg.get('emulator_dirs', []):
        found += [p for p in Path(folder).expanduser().glob('*.AppImage') if name in p.name.lower()]
    return str(max(found, key=lambda p: p.stat().st_mtime)) if found else None


def emulator_command(emulator, core, rom, cfg):
    """O comando que abre a ROM no emulador certo (RetroArch, PCSX2, Azahar, PPSSPP, Dolphin, shadPS4, Ryujinx)."""
    q = shlex.quote(str(rom))
    if emulator == 'retroarch':
        return f"{cfg['retroarch']} -f -L {shlex.quote(str(Path(cfg['cores_dir'])/f'{core}_libretro.so'))} {q}"
    if emulator == 'pcsx2':
        return f"{shlex.quote(appimage('pcsx2', cfg) or 'pcsx2-qt')} -batch -nogui -fullscreen -- {q}"
    if emulator == 'azahar':
        return f"{shlex.quote(appimage('azahar', cfg) or 'azahar')} -f {q}"
    if emulator == 'ppsspp':
        return f'PPSSPPSDL --fullscreen {q}'
    if emulator == 'dolphin':
        return f'dolphin-emu -b -e {q}'
    if emulator == 'shadps4':
        return f"{shlex.quote(appimage('shadps4', cfg) or 'shadps4')} -f true -g {q}"
    return f'ryujinx {q}'


def rom_title(stem):
    """'Super Mario World (USA) [!]' → 'Super Mario World'."""
    return re.sub(r'\s*[\(\[][^\)\]]*[\)\]]', '', stem).strip() or stem


def sfo_fields(path):
    """The text fields of a PS4 param.sfo ({'TITLE': 'Bloodborne', 'TITLE_ID': 'CUSA03173', …})."""
    import struct
    try:
        data = Path(path).read_bytes()
        if data[:4] != b'\0PSF':
            return {}
        keys, values, count = struct.unpack_from('<III', data, 8)
        fields = {}
        for i in range(count):
            key_off, fmt, length, _, data_off = struct.unpack_from('<HHIII', data, 20 + 16*i)
            key = data[keys + key_off:data.index(b'\0', keys + key_off)].decode('utf-8', 'replace')
            if fmt == 0x0204:   # utf-8 text, NUL-terminated
                fields[key] = data[values + data_off:values + data_off + length].rstrip(b'\0').decode('utf-8', 'replace')
        return fields
    except (OSError, ValueError, struct.error):
        return {}


def scan_ps4(base, cfg):
    """PS4 games are dumped folders (CUSA03173/eboot.bin + sce_sys/param.sfo), not one file."""
    found = []
    for eboot in sorted((base/'ps4').glob('*/eboot.bin')):
        sfo = eboot.parent/'sce_sys/param.sfo'
        if not sfo.is_file():
            continue
        info = sfo_fields(sfo)
        icon = eboot.parent/'sce_sys/icon0.png'
        entry = blank(f'rom:{short_hash(str(eboot))}', re.sub(r'[™®©]', '', info.get('TITLE', '')).strip() or eboot.parent.name, 'rom',
                      emulator_command('shadps4', None, eboot, cfg), cover=str(icon) if icon.is_file() else None)
        entry.update(rom=str(eboot), system='ps4', system_name=SYSTEM_NAMES['ps4'])
        found.append(entry)
    return found


def scan_roms():
    """Varre as pastas de ROMs: a subpasta (ps2, snes...) escolhe o emulador; ignora saves e faixas de CD."""
    cfg = config()
    found = []
    for folder in cfg['rom_dirs']:
        base = Path(folder).expanduser()
        if not base.is_dir():
            continue
        found += scan_ps4(base, cfg)
        # A PS4 dump is ~30k files of game data: never walk it file by file.
        files = sorted(p for p in base.rglob('*') if p.is_file() and not p.relative_to(base).parts[0].lower() == 'ps4')
        # Discs a .cue or .m3u already points at are not games by themselves.
        listed = set()
        for f in files:
            if f.suffix.lower() in ('.cue', '.m3u'):
                try:
                    text = f.read_text(errors='replace')
                except OSError:
                    continue
                for line in text.splitlines():
                    name = re.sub(r'^\s*FILE\s+"?([^"]+)"?.*$', r'\1', line).strip() if 'FILE' in line.upper() else line.strip()
                    if name and not name.startswith('#'):
                        listed.add((f.parent/name).resolve())
        for rom in files:
            if rom.resolve() in listed:
                continue
            ext = rom.suffix.lower()
            system = rom.relative_to(base).parts[0].lower() if len(rom.relative_to(base).parts) > 1 else None
            if system in EMU_SYSTEMS:
                emulator, core, exts = EMU_SYSTEMS[system]
                if ext not in exts:
                    continue
                launch = emulator_command(emulator, core, rom, cfg)
            elif ext in cfg['emulators']:
                launch = cfg['emulators'][ext].replace('{rom}', shlex.quote(str(rom)))
                system = ext.lstrip('.')
            elif ext in ROM_EXT:
                core = Path(cfg['cores_dir'])/f'{ROM_EXT[ext]}_libretro.so'
                launch = f"{cfg['retroarch']} -L {shlex.quote(str(core))} {shlex.quote(str(rom))}"
                system = ext.lstrip('.')
            else:
                continue
            entry = blank(f'rom:{short_hash(str(rom))}', rom_title(rom.stem), 'rom', launch)
            entry.update(rom=str(rom), system=system, system_name=SYSTEM_NAMES.get(system, system.upper()))
            found.append(entry)
    return found


# ---- merge ------------------------------------------------------------------------------
SCANNED = {'steam': scan_steam, 'hydra': scan_hydra, 'rom': scan_roms}
REFRESH = ('title', 'launch', 'cover', 'hours_source', 'exe', 'prefix', 'workdir', 'rom', 'system', 'system_name')


def merge(data, fresh):
    """Junta o resultado do scan com a biblioteca: acrescenta novos, atualiza só campos da fonte, marca sumidos."""
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
    """Roda todos os scanners e grava (games.py scan). Nunca apaga seus dados."""
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
            'missing': sum(1 for g in data['games'] if g.get('missing')), 'errors': errors,
            'played_pending': sum(1 for p in played_titles() if p['n'] not in data.get('played', {}))}


def add(exe, prefix=None, title=None, args=''):
    """Adiciona um jogo à mão (executável, prefixo, nome)."""
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
    """Muda campos de um jogo (status, notas, proton...). Mudar o prefixo reescreve o comando junto."""
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
            # When it was finished / completed, for DESEMPENHO; kept if it is undone later.
            if key == 'status' and value == 'done' and game.get('status') != 'done':
                game['done_at'] = int(time.time())
            if key == 'complete' and value and not game.get('complete'):
                game['complete_at'] = int(time.time())
            game[key] = value
            if key == 'title':
                game['title_edited'] = True
            if key == 'prefix':
                value = str(Path(value).expanduser())
                game['prefix'] = value
                # The Wine command carries the prefix too: keep the two the same.
                game['launch'] = re.sub(r'WINEPREFIX=(\'[^\']*\'|\S+)', lambda m: 'WINEPREFIX=' + shlex.quote(value), game['launch'])
        save(data)
    return {'game': game}


def arrange(status, ids):
    """Nova ordem dos jogos de um status (arrastar no BACKLOG)."""
    if status not in STATUSES:
        raise ValueError('status inválido: ' + status)
    with locked():
        data = load()
        by_id = {g['id']: g for g in data['games']}
        unknown = [i for i in ids if i not in by_id]
        if unknown:
            raise ValueError('jogo não encontrado: ' + ', '.join(unknown))
        for n, gid in enumerate(ids, 1):
            game = by_id[gid]
            if game['status'] != status and status == 'done':
                game['progress'] = 100
                game['done_at'] = int(time.time())
            game['status'] = status
            game['order'] = n
        save(data)
    return {'status': status, 'ids': ids}


def remove(gid):
    """Tira um jogo da biblioteca."""
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
               'rpcss.exe', 'conhost.exe', 'start.exe', 'winemenubuilder', 'winemenubuilder.exe', 'tabtip.exe',
               # Proton through umu and the wrappers: alive around the game, not the game.
               'umu-run', 'reaper', 'pv-bwrap', 'srt-bwrap', 'pressure-vessel', 'steam-runtime-l',
               'gamescope', 'gamescopereaper', 'mangoapp', 'gamemoderun'}


def is_wine_helper(entry):
    """True se o processo é um serviço do Wine (wineserver, services.exe...), não o jogo."""
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
    """Quais ferramentas estão instaladas: gamemode, mangohud, umu-run (Proton) e gamescope."""
    from shutil import which
    return {'gamemode': bool(which('gamemoderun')), 'mangohud': bool(which('mangohud')),
            'proton': bool(which('umu-run')), 'gamescope': bool(which('gamescope'))}


def screen_size():
    """The focused monitor's resolution and refresh, for gamescope; 1920x1080@60 without Hyprland."""
    try:
        out = subprocess.run(['hyprctl', 'monitors', '-j'], capture_output=True, text=True, timeout=2).stdout
        mon = next((m for m in json.loads(out) if m.get('focused')), None) or json.loads(out)[0]
        return int(mon['width']), int(mon['height']), round(float(mon.get('refreshRate', 60)))
    except (OSError, ValueError, IndexError, KeyError, subprocess.TimeoutExpired):
        return 1920, 1080, 60


def steam_appid(game):
    """The game's Steam id: set by hand, or from a steam_appid.txt beside the .exe or up to two
    folders above it (Steam-emulator releases ship one, often in steam_settings/). umu uses it
    to apply that game's protonfixes."""
    if game.get('steam_appid'):
        return int(game['steam_appid'])
    exe = Path(game.get('exe') or '')
    for folder in list(exe.parents)[:3]:
        for name in ('steam_appid.txt', 'steam_settings/steam_appid.txt'):
            try:
                text = (folder/name).read_text().strip()
            except OSError:
                continue
            if text.isdigit():
                return int(text)
    return None


def command_for(game):
    """The command LW runs. Steam goes through steam:// (its own launch options decide the
    wrappers). A Windows game runs with Wine, or with Proton-GE through umu-run when `proton`
    is on (umu downloads and updates GE-Proton itself; the game's prefix is kept; with the
    Steam id, GAMEID=umu-<id> turns on that game's protonfixes). Then, when
    toggled and installed: mangohud inside, gamescope around (fullscreen at the monitor's size;
    `fsr` renders at 75% and upscales), gamemoderun outermost."""
    cmd = game['launch']
    if game['source'] == 'steam':
        return cmd
    have = tools()
    exe = game.get('exe') or ''
    if game.get('proton') and have['proton'] and exe.lower().endswith('.exe'):
        prefix = f"WINEPREFIX={shlex.quote(game['prefix'])} " if game.get('prefix') else ''
        args = cmd.split(shlex.quote(exe), 1)[1] if shlex.quote(exe) in cmd else ''
        appid = steam_appid(game)
        gameid = f'umu-{appid}' if appid else 'umu-default'
        cmd = f"env {prefix}GAMEID={gameid} PROTONPATH=GE-Proton umu-run {shlex.quote(exe)}{args}"
    if game.get('mangohud') and have['mangohud']:
        cmd = 'mangohud ' + cmd
    if game.get('gamescope') and have['gamescope']:
        w, h, hz = screen_size()
        size = f'-W {w} -H {h} -r {hz}'
        if game.get('fsr'):
            size += f' -w {w * 3 // 4} -h {h * 3 // 4} -F fsr'
        cmd = f'gamescope -f {size} -- {cmd}'
    if game.get('gamemode') and have['gamemode']:
        cmd = 'gamemoderun ' + cmd
    return cmd


def pids_of(gid, proc='/proc'):
    """Processos do jogo, achados pela variável LW_GAME_ID (ou SteamAppId) no ambiente deles."""
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
    """Lê, aplica uma função que altera os dados e grava — tudo dentro da trava."""
    with locked():
        data = load()
        result = fn(data)
        save(data)
    return result


def controller_mappings():
    """SDL GameController mappings, one per line, in ~/.local/share/lw/controllers.txt
    (lines starting with # are comments)."""
    try:
        lines = (data_dir()/'controllers.txt').read_text().splitlines()
    except OSError:
        return []
    return [l.strip() for l in lines if l.strip() and not l.lstrip().startswith('#') and l.count(',') >= 3]


def launch(gid):
    """Inicia o jogo e o vigia que conta a sessão."""
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
    # Controllers SDL does not know (generic HID pads): mappings from controllers.txt, so
    # Wine/Proton present them as an Xbox pad (XInput) to the game.
    mappings = controller_mappings()
    if mappings:
        env['SDL_GAMECONTROLLERCONFIG'] = '\n'.join(filter(None, [os.environ.get('SDL_GAMECONTROLLERCONFIG', '')] + mappings))
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
        """Marca o jogo como "iniciando" no games.json."""
        d['launching'] = {'id': gid, 'at': int(time.time()), 'command': cmd}
    update(pending)
    return {'command': cmd, 'tools': tools(), 'log': str(log)}


def watch(gid):
    # One watcher per game.
    """O vigia: abre a sessão quando o jogo aparece e fecha quando some (funciona com o LW fechado)."""
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
    """Fecha a sessão aberta: soma as horas, guarda a sessão e a data em que jogou."""
    def finish(d):
        """A parte que altera os dados (rodada dentro da trava)."""
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
    """Pede para o jogo fechar (SIGTERM)."""
    pids = pids_of(gid)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    return {'signalled': len(pids)}


# ---- installers: setup.exe → Wine prefix → library ------------------------------------
# An installer is a setup/install executable (or .msi); redistributables are not.
SETUP_NAME = re.compile(r'(^|[\W_])(setup|install(er)?)([\W_]|$)', re.I)
NOT_SETUP = re.compile(r'unins|uninstall|redist|vc_?redist|directx|dxsetup|dotnet|physx|oalinst|xnafx|prereq', re.I)
# .exe files an installer leaves that are not the game.
NOT_GAME = re.compile(r'unins|setup|install|redist|crash|report|dxsetup|vc_?redist|dotnet|physx|helper|update|'
                      r'7z|unarc|quickbms|cleanup|activat|regist|config(urator)?$', re.I)
# Parts of drive_c the game is never in.
PREFIX_SKIP = {'windows', 'programdata', 'users', 'common files', 'internet explorer',
               'windows media player', 'windows nt', 'microsoft.net', 'windowspowershell'}


def download_dirs():
    """Pastas onde procurar instaladores (padrão: ~/Downloads)."""
    return [Path(d).expanduser() for d in config().get('download_dirs', ['~/Downloads'])]


def clean_name(text):
    """'Need For Speed Hot Pursuit - [DODI Repack]' → 'Need For Speed Hot Pursuit'."""
    text = re.sub(r'[\[({][^\])}]*[\])}]', ' ', text)
    # Site names and release tags: Dark.Souls.Remastered.SteamGG.net → Dark Souls Remastered.
    text = re.sub(r'[.\s_-]*\b[\w-]+\.(net|com|org|ru|io|to|cc)\b', ' ', text, flags=re.I)
    text = re.sub(r'\b(repack|dodi|fitgirl|elamigos|steamrip|gog|portable|multi\d*|v\d+(\.\d+)*)\b', ' ', text, flags=re.I)
    text = re.sub(r'[_.]+', ' ', text)
    text = re.sub(r'\s+-\s*$|^\s*-\s+', ' ', re.sub(r'\s+', ' ', text)).strip(' -')
    return re.sub(r'\s+', ' ', text).strip() or 'Jogo'


def slug(text):
    """Nome → nome de pasta (minúsculas e hífens): "Dark Souls" → "dark-souls"."""
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-') or 'jogo'


def installers():
    """Installers under the download folders (three levels deep), one per folder:
    setup.exe first, then the shortest name. Each carries LW's record, if any."""
    found = {}
    for root in download_dirs():
        if not root.is_dir():
            continue
        base = len(root.parts)
        for dirpath, dirs, files in os.walk(root):
            if len(Path(dirpath).parts) - base >= 3:
                dirs[:] = []
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in files:
                stem, ext = os.path.splitext(f)
                if ext.lower() not in ('.exe', '.msi') or not SETUP_NAME.search(stem) or NOT_SETUP.search(stem):
                    continue
                folder = Path(dirpath)
                key = str(folder) if folder != root else os.path.join(dirpath, f)
                rank = (f.lower() != 'setup.exe', len(f))
                if key not in found or rank < found[key][0]:
                    name = clean_name(folder.name if folder != root else stem)
                    found[key] = (rank, {'setup': str(folder/f), 'name': name, 'folder': str(folder)})
    data = load()
    records = data.get('installs', {})
    # An install whose worker is gone (reboot, killed) is not running any more.
    stale = [k for k, v in records.items() if v.get('state') == 'running' and not worker_alive(k)]
    if stale:
        def unstick(d):
            for k in stale:
                d['installs'][k].update(state='failed', error='o instalador foi interrompido')
        update(unstick)
        records = load().get('installs', {})
    out = [dict(item, install=records.get(item['setup'])) for _, item in found.values()]
    # Records whose installer is gone (moved, deleted) still show, so they can be finished.
    listed = {i['setup'] for i in out}
    out += [{'setup': k, 'name': v.get('name', ''), 'folder': str(Path(k).parent), 'install': v}
            for k, v in records.items() if k not in listed]
    library = [g.get('exe') or '' for g in data['games']]
    return {'installers': sorted(out, key=lambda i: i['name'].lower()), 'ready': ready_games(library)}


def rank_exes(found, name, top=8):
    """(path, size) pairs, the likely game first: words of its name in the path, an .exe named
    after the game (JogoBom.exe for "Jogo Bom") above a launcher beside it, then size."""
    words = set(re.findall(r'[a-z0-9]{3,}', name.lower()))
    joined = ''.join(sorted(words, key=name.lower().find))
    out = []
    for path, size in found:
        hits = len(words & set(re.findall(r'[a-z0-9]{3,}', str(path).lower())))
        own = re.sub(r'[^a-z0-9]', '', Path(path).stem.lower())
        if own and (own in joined or any(w in own for w in words)):
            hits += 5
        out.append((hits, size, {'exe': str(path), 'size': size}))
    out.sort(key=lambda c: (-c[0], -c[1]))
    return [c[2] for c in out[:top]]


# Folders of a ready game that hold no game: installers, redistributables, uninstallers.
NOT_GAME_DIR = re.compile(r'redist|uninstall|directx|support|prereq|^_|vcredist|dotnet|tools?$', re.I)


def ready_games(library_exes):
    """Games that came ready to play (no installer): every folder in `ready_dirs`
    (~/Downloads/hydra_Jogos) not already in the library, with its likely .exe files."""
    out = []
    for root in [Path(d).expanduser() for d in config().get('ready_dirs', [])]:
        if not root.is_dir():
            continue
        for folder in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith('.')):
            if any(e.startswith(str(folder) + os.sep) for e in library_exes):
                continue
            found, has_setup = [], False
            base = len(folder.parts)
            for dirpath, dirs, files in os.walk(folder):
                if len(Path(dirpath).parts) - base >= 4:
                    dirs[:] = []
                dirs[:] = [d for d in dirs if not NOT_GAME_DIR.search(d)]
                for f in files:
                    stem, ext = os.path.splitext(f)
                    if ext.lower() not in ('.exe', '.msi'):
                        continue
                    if SETUP_NAME.search(stem) and not NOT_SETUP.search(stem):
                        has_setup = True
                    elif ext.lower() == '.exe' and not NOT_GAME.search(stem):
                        try:
                            found.append((Path(dirpath)/f, (Path(dirpath)/f).stat().st_size))
                        except OSError:
                            pass
            name = clean_name(folder.name)
            # A folder with an installer is listed as an installer, not as a ready game.
            if found and not has_setup:
                out.append({'folder': str(folder), 'name': name, 'candidates': rank_exes(found, name)})
    return out


def worker_alive(setup):
    """True se o processo que acompanha a instalação ainda está rodando."""
    for entry in Path('/proc').iterdir():
        if entry.name.isdigit():
            try:
                cmd = (entry/'cmdline').read_bytes().split(b'\0')
            except OSError:
                continue
            if b'install-run' in cmd and setup.encode() in cmd:
                return True
    return False


def add_ready(exe, name):
    """Adiciona um jogo "pronto para jogar" com prefixo próprio em ~/Games e Proton ligado."""
    from shutil import which
    added = add(exe, home()/'Games'/slug(name), name)['added']
    if which('umu-run'):
        set_fields(added['id'], ['proton=true'])
        added['proton'] = True
    return {'added': added}


def candidates(prefix, since, name, top=8):
    """New .exe files in the prefix (changed after the install began), the likely game first:
    words of its name in the path, then size."""
    drive = Path(prefix)/'drive_c'
    out = []
    for dirpath, dirs, files in os.walk(drive):
        dirs[:] = [d for d in dirs if d.lower() not in PREFIX_SKIP]
        for f in files:
            stem, ext = os.path.splitext(f)
            if ext.lower() != '.exe' or NOT_GAME.search(stem):
                continue
            path = Path(dirpath)/f
            try:
                st = path.stat()
            except OSError:
                continue
            if max(st.st_mtime, st.st_ctime) < since - 60:
                continue
            out.append((path, st.st_size))
    # Ranked on the path inside drive_c: the prefix's own folder name says nothing.
    ranked = rank_exes([(p.relative_to(drive), size) for p, size in out], name, top)
    return [dict(c, exe=str(drive/c['exe'])) for c in ranked]


def install(setup, name=None):
    """Começa a instalar um setup.exe num prefixo Wine novo e registra a instalação."""
    from shutil import which
    setup = str(Path(setup).expanduser())
    if not Path(setup).is_file():
        raise ValueError('instalador não encontrado: ' + setup)
    if not which('wine'):
        raise ValueError('wine não encontrado')
    name = name or clean_name(Path(setup).parent.name)
    prefix = home()/'Games'/slug(name)
    def start(d):
        """Registra a instalação como "rodando" (recusa se já estiver instalando)."""
        live = d.setdefault('installs', {}).get(setup)
        if live and live.get('state') == 'running':
            raise ValueError('já está instalando: ' + name)
        d['installs'][setup] = {'name': name, 'setup': setup, 'prefix': str(prefix), 'state': 'running',
                                'started': int(time.time())}
        return dict(d['installs'][setup])
    record = update(start)
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'install-run', setup], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {'install': record}


def install_run(setup):
    """The detached worker: makes the prefix, runs the installer, waits for every process it
    started (wineserver -w), then records the new .exe files."""
    record = load().get('installs', {}).get(setup)
    if not record:
        raise ValueError('instalação não registrada: ' + setup)
    prefix = Path(record['prefix'])
    prefix.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, WINEPREFIX=str(prefix), WINEDEBUG='-all')
    env.pop('LW_GAME_ID', None)
    code = None
    with open(prefix/'lw-install.log', 'w') as out:
        subprocess.run(['wineboot', '-u'], env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT)
        cmd = ['wine', 'msiexec', '/i', setup] if setup.lower().endswith('.msi') else ['wine', setup]
        code = subprocess.run(cmd, env=env, cwd=str(Path(setup).parent), stdin=subprocess.DEVNULL,
                              stdout=out, stderr=subprocess.STDOUT).returncode
        subprocess.run(['wineserver', '-w'], env=env, stdout=out, stderr=subprocess.STDOUT)
    found = candidates(prefix, record['started'], record['name'])
    def finish(d):
        """Grava o resultado: concluída (com os .exe encontrados) ou falhou."""
        r = d.setdefault('installs', {}).setdefault(setup, record)
        r.update(state='done' if found else 'failed', ended=int(time.time()), code=code, candidates=found,
                 error=None if found else 'nenhum .exe novo no prefixo (instalação cancelada ou falhou)')
    update(finish)
    return {'candidates': found}


def install_add(setup, exe):
    """Põe na biblioteca o .exe escolhido de uma instalação concluída."""
    record = load().get('installs', {}).get(setup)
    if not record:
        raise ValueError('instalação não registrada: ' + setup)
    added = add(exe, record['prefix'], record['name'])['added']
    def mark(d):
        """Marca a instalação como adicionada."""
        d['installs'][setup].update(state='added', game=added['id'])
    update(mark)
    return {'added': added}


def install_forget(setup):
    """Apaga o registro de uma instalação (o prefixo fica no disco)."""
    def drop(d):
        """Remove o registro de dentro dos dados."""
        if not d.get('installs', {}).pop(setup, None):
            raise ValueError('instalação não registrada: ' + setup)
    update(drop)
    return {'forgot': setup}


# ---- IGDB: covers, times to beat, genres, similar games -----------------------------------
# Credentials: ~/.config/lw/igdb.json {"client_id", "client_secret"} (a free Twitch app).
# Only the game's title goes out. A match must be close to the title or nothing is filled:
# no data beats wrong data. Existing covers and est_hours are never replaced.
IGDB_IMAGE = 'https://images.igdb.com/igdb/image/upload/t_cover_big/{}.jpg'


def igdb_credentials():
    """Lê client_id e client_secret do IGDB em ~/.config/lw/igdb.json."""
    path = Path(os.environ.get('XDG_CONFIG_HOME', home()/'.config'))/'lw'/'igdb.json'
    try:
        cred = json.loads(path.read_text())
    except (OSError, ValueError):
        raise ValueError('sem chave do IGDB: crie ~/.config/lw/igdb.json (client_id, client_secret)')
    if not cred.get('client_id') or not cred.get('client_secret'):
        raise ValueError('~/.config/lw/igdb.json sem client_id ou client_secret')
    return cred


def http(url, data=None, headers=None, timeout=20):
    """Pedido HTTP simples (POST se houver dados) com tempo limite."""
    import urllib.request
    request = urllib.request.Request(url, data=data, headers=headers or {}, method='POST' if data is not None else 'GET')
    request.add_header('User-Agent', 'LW-games/1.0')
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def igdb_token(cred):
    """App token from Twitch, cached until a day before it expires."""
    import urllib.parse
    cache = data_dir()/'igdb-token.json'
    try:
        saved = json.loads(cache.read_text())
        if saved.get('client_id') == cred['client_id'] and saved.get('expires', 0) > time.time() + 86400:
            return saved['token']
    except (OSError, ValueError):
        pass
    body = urllib.parse.urlencode({'client_id': cred['client_id'], 'client_secret': cred['client_secret'],
                                   'grant_type': 'client_credentials'}).encode()
    got = json.loads(http('https://id.twitch.tv/oauth2/token', body))
    data_dir().mkdir(parents=True, exist_ok=True)
    fd = os.open(cache, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump({'client_id': cred['client_id'], 'token': got['access_token'],
                   'expires': int(time.time()) + int(got['expires_in'])}, out)
    return got['access_token']


class Igdb:
    """Cliente da API do IGDB (Twitch): guarda o token e respeita 4 pedidos por segundo."""
    def __init__(self):
        self.cred = igdb_credentials()
        self.token = igdb_token(self.cred)
        self.last = 0.0

    def query(self, endpoint, body):
        # IGDB allows 4 requests a second.
        """Faz uma consulta a um endpoint do IGDB (games, covers...)."""
        time.sleep(max(0.0, self.last + 0.26 - time.time()))
        self.last = time.time()
        return json.loads(http('https://api.igdb.com/v4/' + endpoint, body.encode(),
                               {'Client-ID': self.cred['client_id'], 'Authorization': 'Bearer ' + self.token}))


def norm_title(text):
    """Título normalizado para comparar (minúsculas, sem artigos, sem pontuação)."""
    text = re.sub(r'[\[({][^\])}]*[\])}]', ' ', text.lower())
    text = re.sub(r'\b(the|of|a|an)\b', ' ', text)
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()


def best_match(title, results):
    """The result whose name is closest to the title, if close enough (or None)."""
    from difflib import SequenceMatcher
    want = norm_title(title)
    scored = []
    for r in results:
        name = norm_title(r.get('name', ''))
        ratio = SequenceMatcher(None, want, name).ratio()
        # Exact names first; among equals the main entry (not a port or edition of another)
        # with the most votes, then the shorter name (the original over remasters).
        main = not r.get('parent_game') and not r.get('version_parent')
        scored.append((name == want, ratio, main, r.get('total_rating_count') or 0, -len(name), r))
    scored.sort(key=lambda s: s[:5], reverse=True)
    if scored and (scored[0][0] or scored[0][1] >= 0.82):
        return scored[0][5]
    return None


def year_of(stamp):
    """Data (timestamp) → ano."""
    return time.gmtime(stamp).tm_year if stamp else None


def fetch_cover(image_id, gid):
    """Baixa a capa do IGDB para ~/.local/share/lw/covers."""
    folder = data_dir()/'covers'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/(re.sub(r'[^A-Za-z0-9_-]', '_', gid) + '.jpg')
    path.write_bytes(http(IGDB_IMAGE.format(image_id)))
    return str(path)


def played_titles():
    """Jogos que já joguei (a lista de compat-data.json): nome, horas e platina."""
    try:
        items = json.loads((Path(__file__).resolve().parent/'compat-data.json').read_text())['list']
    except (OSError, ValueError, KeyError):
        return []
    return [{'n': g['n'], 'hrs': g.get('hrs'), 'plat': bool(g.get('plat'))} for g in items]


def meta(ids=None, everything=False):
    """Busca metadados no IGDB e preenche só os campos vazios (capa, gêneros, duração estimada...).
    Também consulta, uma vez, os jogos que já joguei e estão fora da biblioteca: gêneros e
    parecidos deles entram nas recomendações (campo "played" do games.json)."""
    doc = load()
    games_now = doc['games']
    todo = [g for g in games_now if (ids and g['id'] in ids) or (not ids and (everything or 'igdb' not in g))]
    known = doc.get('played', {})
    played_todo = [] if ids else [p for p in played_titles() if everything or p['n'] not in known]
    if not todo and not played_todo:
        return {'matched': [], 'missed': []}
    api = Igdb()
    found = {}
    for game in todo:
        title = game.get('title', '')
        fields = 'id,name,url,first_release_date,cover.image_id,genres.name,similar_games,parent_game,version_parent,total_rating_count'
        if game.get('igdb_id'):
            results = api.query('games', f'fields {fields}; where id = {int(game["igdb_id"])};')
        else:
            safe = title.replace('"', ' ')
            results = api.query('games', f'search "{safe}"; fields {fields}; limit 15;')
        hit = best_match(title, results) if not game.get('igdb_id') else (results[0] if results else None)
        if not hit:
            found[game['id']] = {'match': None, 'checked': int(time.time())}
            continue
        ttb = api.query('game_time_to_beats', f'fields hastily,normally,completely; where game_id = {hit["id"]};')
        times = {k: round(ttb[0][k] / 3600, 1) for k in ('hastily', 'normally', 'completely') if ttb and ttb[0].get(k)}
        info = {'match': {'id': hit['id'], 'name': hit.get('name'), 'url': hit.get('url'),
                          'year': year_of(hit.get('first_release_date')),
                          'genres': [x['name'] for x in hit.get('genres', [])],
                          'ttb': times, 'similar': hit.get('similar_games', [])[:10]},
                'checked': int(time.time())}
        image = (hit.get('cover') or {}).get('image_id')
        if image and not (game.get('cover') and Path(game['cover']).is_file()):
            try:
                info['cover'] = fetch_cover(image, game['id'])
            except OSError:
                pass
        found[game['id']] = info
    # Played before, outside the library: only what the recommendations use.
    played = {}
    fields = 'id,name,genres.name,similar_games,parent_game,version_parent,total_rating_count'
    for p in played_todo:
        hit = best_match(p['n'], api.query('games', f'search "{p["n"].replace(chr(34), " ")}"; fields {fields}; limit 15;'))
        played[p['n']] = dict(p, checked=int(time.time()), **({'igdb': {
            'id': hit['id'], 'name': hit.get('name'), 'genres': [x['name'] for x in hit.get('genres', [])],
            'similar': hit.get('similar_games', [])[:10]}} if hit else {}))
    # Similar games: one query for all, names and covers for the recommendations.
    similar_ids = sorted({i for v in found.values() if v['match'] for i in v['match']['similar']}
                         | {i for v in played.values() if 'igdb' in v for i in v['igdb']['similar']})
    similar = {}
    for start in range(0, len(similar_ids), 100):
        chunk = similar_ids[start:start + 100]
        for s in api.query('games', 'fields id,name,url,first_release_date,cover.image_id,genres.name,total_rating; '
                                    f'where id = ({",".join(map(str, chunk))}); limit 100;'):
            similar[str(s['id'])] = {'name': s.get('name'), 'url': s.get('url'), 'year': year_of(s.get('first_release_date')),
                                     'genres': [x['name'] for x in s.get('genres', [])], 'rating': round(s['total_rating']) if s.get('total_rating') else None,
                                     'image': (s.get('cover') or {}).get('image_id')}
    def write(d):
        """Grava o que foi encontrado, dentro da trava."""
        matched, missed = [], []
        for g in d['games']:
            info = found.get(g['id'])
            if info is None:
                continue
            m = info['match']
            g['igdb'] = dict(m, checked=info['checked']) if m else {'checked': info['checked']}
            if m:
                matched.append(g['title'])
                if info.get('cover') and not (g.get('cover') and Path(g['cover']).is_file()):
                    g['cover'] = info['cover']
                if g.get('est_hours') is None and m['ttb'].get('normally'):
                    g['est_hours'] = m['ttb']['normally']
            else:
                missed.append(g['title'])
        d.setdefault('igdb_similar', {}).update(similar)
        d.setdefault('played', {}).update(played)
        return {'matched': matched, 'missed': missed,
                'played': {'matched': sum(1 for v in played.values() if 'igdb' in v),
                           'missed': [k for k, v in played.items() if 'igdb' not in v]}}
    return update(write)


def main(argv=None):
    """Linha de comando: games.py scan | list | add | set | launch | watch | install | meta ..."""
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
    ar = sub.add_parser('arrange')
    ar.add_argument('status')
    ar.add_argument('ids', nargs='*')
    sub.add_parser('installers')
    i = sub.add_parser('install')
    i.add_argument('setup')
    i.add_argument('--name')
    for name in ('install-run', 'install-forget'):
        sub.add_parser(name).add_argument('setup')
    me = sub.add_parser('meta')
    me.add_argument('ids', nargs='*')
    me.add_argument('--all', action='store_true')
    ar2 = sub.add_parser('add-ready')
    ar2.add_argument('exe')
    ar2.add_argument('--name', required=True)
    ia = sub.add_parser('install-add')
    ia.add_argument('setup')
    ia.add_argument('exe')
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
        elif args.action == 'arrange':
            data = arrange(args.status, args.ids)
        elif args.action == 'meta':
            data = meta(args.ids, args.all)
        elif args.action == 'installers':
            data = installers()
        elif args.action == 'install':
            data = install(args.setup, args.name)
        elif args.action == 'install-run':
            data = install_run(args.setup)
        elif args.action == 'add-ready':
            data = add_ready(args.exe, args.name)
        elif args.action == 'install-add':
            data = install_add(args.setup, args.exe)
        elif args.action == 'install-forget':
            data = install_forget(args.setup)
        else:
            data = remove(args.id)
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(dict(ok=True, **data), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
