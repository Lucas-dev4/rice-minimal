#!/usr/bin/env python3
"""lw compat: o hardware real desta máquina comparado com o requisito mínimo de cada jogo.

scan   CPU, threads, RAM, GPU (a mais forte, se houver várias), VRAM e espaço livre
check  cada jogo da lista e do mistério: ok / lim / no / na, com os motivos

Tudo sem sudo e sem depender do idioma do sistema: lê /proc e /sys direto, usa os códigos
numéricos do lspci e o nvidia-smi em CSV. Os dados (lista, mistério, requisitos e as tabelas
de GPU/CPU) vêm de compat-data.json, extraído de docs/lw-jogos-prototype.html, e a avaliação
é a mesma do evalG daquela página.
"""
# compat.py — compatibilidade dos jogos com o hardware (lw compat scan|check).
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import games  # noqa: E402

DATA = Path(__file__).resolve().parent/'compat-data.json'
# Raiz do sistema de arquivos para /proc e /sys (os testes trocam por uma pasta falsa).
ROOT = Path('/')


def data():
    """Lista, mistério, requisitos e tabelas (compat-data.json)."""
    return json.loads(DATA.read_text())


def run(command):
    """Roda um comando com o idioma neutro; devolve a saída, ou None se falhar ou não existir."""
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=10,
                              env=dict(os.environ, LC_ALL='C', LANG='C'))
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def read(path):
    """Texto de um arquivo dentro de ROOT (ou None)."""
    try:
        return (ROOT/path.lstrip('/')).read_text()
    except OSError:
        return None


def num(x):
    """Número como o JavaScript da página imprime: 24 e não 24.0, 5.7 como 5.7."""
    return f'{x:g}' if isinstance(x, float) else str(x)


# ---- hardware -------------------------------------------------------------------------
def cpu():
    """Nome do processador (primeiro "model name" de /proc/cpuinfo)."""
    m = re.search(r'^model name\s*:\s*(.+)$', read('/proc/cpuinfo') or '', re.M)
    return m.group(1).strip() if m else None


def threads():
    """Threads disponíveis (nproc)."""
    out = run(['nproc'])
    return int(out) if out and out.strip().isdigit() else None


def ram():
    """RAM total em GB (GiB, uma casa), de /proc/meminfo."""
    m = re.search(r'^MemTotal:\s*(\d+)\s*kB', read('/proc/meminfo') or '', re.M)
    return round(int(m.group(1))/1048576, 1) if m else None


def gpu_info(name, table):
    """[índice, VRAM] da primeira linha da tabela cujo trecho aparece no nome (ou None)."""
    n = (name or '').lower()
    for key, score, vram in table:
        if key in n:
            return score, vram
    return None


def gpus():
    """Placas de vídeo pelo lspci (classe 03xx): slot, fabricante, nome."""
    out = run(['lspci', '-D', '-mm', '-nn']) or ''
    found = []
    for line in out.splitlines():
        try:
            f = shlex.split(line)
        except ValueError:
            continue
        if len(f) < 4 or not re.search(r'\[03[0-9a-f]{2}\]$', f[1]):
            continue
        vendor_id = (re.search(r'\[([0-9a-f]{4})\]$', f[2]) or [None, None])[1]
        clean = lambda s: re.sub(r'\s*\[[0-9a-f]{4}\]$', '', s)
        found.append({'slot': f[0], 'vendor_id': vendor_id, 'name': clean(f[2]) + ' ' + clean(f[3])})
    return found


def vram_of(card):
    """VRAM em GB de uma placa: nvidia-smi para NVIDIA, sysfs (amdgpu) para as outras."""
    if card['vendor_id'] == '10de':
        out = run(['nvidia-smi', '--query-gpu=pci.bus_id,memory.total', '--format=csv,noheader,nounits']) or ''
        rows = [r.split(',') for r in out.strip().splitlines() if ',' in r]
        for bus, mib in rows:
            # nvidia-smi escreve o domínio com 8 dígitos (00000000:01:00.0).
            if bus.strip().lower()[-12:] == card['slot'].lower()[-12:] and mib.strip().isdigit():
                return round(int(mib)/1024, 1)
        if len(rows) == 1 and rows[0][1].strip().isdigit():
            return round(int(rows[0][1])/1024, 1)
        return None
    for device in sorted((ROOT/'sys/class/drm').glob('card*/device')):
        uevent = read(str(device.relative_to(ROOT)/'uevent')) or ''
        if f'PCI_SLOT_NAME={card["slot"]}' in uevent:
            total = read(str(device.relative_to(ROOT)/'mem_info_vram_total'))
            if total and total.strip().isdigit():
                return round(int(total)/1073741824, 1)
    return None


def free_gb(path):
    """Espaço livre em GB (o mesmo número do "disponível" do df)."""
    s = os.statvfs(path)
    return round(s.f_bavail*s.f_frsize/1073741824, 1)


def steam_libraries():
    """Pastas das bibliotecas da Steam (libraryfolders.vdf), sem repetir."""
    paths = []
    for root in games.steam_roots():
        try:
            folders = games.vdf((root/'steamapps/libraryfolders.vdf').read_text()).get('libraryfolders', {})
        except OSError:
            continue
        for entry in folders.values():
            path = entry.get('path') if isinstance(entry, dict) else None
            if path and Path(path).is_dir() and path not in paths:
                paths.append(path)
    return paths


def disk():
    """Espaço livre em cada biblioteca da Steam; sem Steam, a pasta pessoal (onde caem os do Hydra)."""
    libraries = [{'path': p, 'free_gb': free_gb(p)} for p in steam_libraries()]
    source = 'steam'
    if not libraries:
        source = 'home'
        libraries = [{'path': str(games.home()), 'free_gb': free_gb(games.home())}]
    best = max(libraries, key=lambda x: x['free_gb'])
    return {'free_gb': best['free_gb'], 'path': best['path'], 'source': source, 'libraries': libraries}


def scan():
    """O hardware desta máquina, com a GPU mais forte pela tabela quando há mais de uma."""
    table = data()['gpu_table']
    cards = gpus()
    for card in cards:
        info = gpu_info(card['name'], table)
        card['score'] = info[0] if info else None
    known = [c for c in cards if c['score'] is not None]
    chosen = max(known, key=lambda c: c['score']) if known else (cards[0] if cards else None)
    return {'cpu': cpu(), 'threads': threads(), 'ram_gb': ram(),
            'gpu': chosen['name'] if chosen else None,
            'vram_gb': vram_of(chosen) if chosen else None,
            'gpus': cards, 'disk': disk()}


# ---- avaliação (a mesma do evalG da página) ------------------------------------------
def cpu_score(name, thr, table):
    """Índice da CPU pela tabela; fora dela, uma estimativa pelas threads (até 110)."""
    n = (name or '').lower()
    for key, score in table:
        if key in n:
            return score
    return min(110, thr*8) if thr else None


def evaluate(name, machine, d):
    """ok / lim / no / na de um jogo, com os motivos."""
    q = d['req'].get(name)
    if not q:
        return {'k': 'na', 'reasons': [], 'w': 'sem dados', 's': None, 'd': None}
    if q.get('ps4'):
        return {'k': 'na', 'reasons': [], 'w': 'sem versão PC (PS4/PS5); no PC só por emulação, e pesada', 's': 0, 'd': None}
    r = dict(d['req_default'], **q)
    issues, level = [], 0
    gi = gpu_info(machine.get('gpu'), d['gpu_table'])
    cs = cpu_score(machine.get('cpu'), machine.get('threads'), d['cpu_table'])
    vram = machine.get('vram_gb') or (gi[1] if gi else 0)
    if gi:
        x = gi[0]/r['g']
        if x < .8:
            level = 2
            issues.append(f'GPU fraca ({gi[0]} vs {r["g"]} mín)')
        elif x < 1.2:
            level = max(level, 1)
            issues.append(f'GPU no limite ({gi[0]} vs {r["g"]})')
    else:
        issues.append('GPU desconhecida')
    mem = machine.get('ram_gb')
    if mem is not None:
        if mem < r['r'] - 1:
            level = 2
            issues.append(f'RAM {num(mem)}/{num(r["r"])} GB')
        elif mem < r['r']*.97:
            level = max(level, 1)
            issues.append(f'RAM {num(mem)}/{num(r["r"])} GB')
    if r['v'] and vram:
        if vram < r['v'] - 1:
            level = 2
            issues.append(f'VRAM {num(vram)}/{num(r["v"])} GB')
        elif vram < r['v']:
            level = max(level, 1)
            issues.append(f'VRAM {num(vram)}/{num(r["v"])} GB')
    if cs is not None:
        x = cs/r['c']
        if x < .7:
            level = 2
            issues.append('CPU fraca')
        elif x < 1:
            level = max(level, 1)
            issues.append('CPU no limite')
    free = (machine.get('disk') or {}).get('free_gb')
    if free is not None and free < r['d']:
        level = 2
        issues.append(f'falta disco ({num(free)}/{num(r["d"])} GB)')
    if q.get('emu'):
        issues.append('via emulador (Switch)')
    w = ' · '.join(issues) if issues else (f'folga: GPU ×{gi[0]/r["g"]:.1f}'.replace('.', ',') if gi else 'ok')
    return {'k': ('ok', 'lim', 'no')[level], 'reasons': issues, 'w': w, 's': r['s'], 'd': r['d']}


def installed_titles():
    """Títulos normalizados dos jogos que estão na biblioteca do LW e não sumiram da fonte."""
    return {games.norm_title(g.get('title', '')): g['id'] for g in games.load()['games'] if not g.get('missing')}


def check(machine=None):
    """Avalia cada jogo da lista e do mistério contra o hardware (lido agora, se não vier)."""
    d = data()
    machine = machine or scan()
    have = installed_titles()
    out, counts = [], {'ok': 0, 'lim': 0, 'no': 0, 'na': 0}
    for src, items in (('list', d['list']), ('mystery', d['mystery'])):
        for g in items:
            e = evaluate(g['n'], machine, d)
            gid = have.get(games.norm_title(g['n']))
            out.append(dict(n=g['n'], src=src, installed=gid is not None, game_id=gid, **e))
            counts[e['k']] += 1
    return {'machine': machine, 'counts': counts, 'games': out}
