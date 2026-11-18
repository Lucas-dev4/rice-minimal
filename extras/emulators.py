#!/usr/bin/env python3
"""lw emu: ajustes rápidos dos emuladores e do controle (tela EMULADORES de JOGOS).

list               emuladores, se estão instalados e os ajustes atuais
set EMU KEY VALUE  muda um ajuste (res, fullscreen, vsync, fps) na configuração do emulador
apply-pad EMU      põe o controle como player 1 no emulador (PCSX2, Dolphin)
pads               controles conectados, GUID SDL, mapeamento em controllers.txt, bateria
pad-watch EVENT    eventos ao vivo do controle (uma linha JSON por evento) para o teste
pad-save ...       grava o mapeamento SDL de um controle em controllers.txt

Cada gravação guarda antes uma cópia do arquivo em ~/.local/state/rice-minimal/emulators/
e escreve de forma atômica. Só mexe nas chaves que mudam: o resto do arquivo fica igual.
Emulador cuja configuração ainda não existe (nunca foi aberto) não é editado.
"""
# emulators.py — configurações rápidas de emuladores e controle, sem sudo.
import fcntl
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import games  # noqa: E402

# Raiz de /proc, /sys e /dev (os testes trocam por uma pasta falsa).
ROOT = Path('/')


def home():
    return games.home()


def state_dir():
    """~/.local/state/rice-minimal/emulators (backups dos arquivos editados)."""
    return Path(os.environ.get('XDG_STATE_HOME', home()/'.local/state'))/'rice-minimal'/'emulators'


# ---- arquivos: INI linha a linha, cfg do RetroArch e JSON ------------------------------
def ini_get(text, section, key):
    """Valor de key em [section] (section None: arquivo sem seções, como o retroarch.cfg)."""
    inside = section is None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('[') and s.endswith(']'):
            inside = s[1:-1] == section
            continue
        if inside and '=' in s and s.split('=', 1)[0].strip() == key:
            return s.split('=', 1)[1].strip().strip('"')
    return None


def ini_set(text, section, key, value, quote=False):
    """Troca (ou cria) key em [section] sem mexer no resto do arquivo."""
    shown = f'"{value}"' if quote else value
    lines = text.splitlines()
    inside, start, last, found = section is None, None, None, None
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith('[') and s.endswith(']'):
            if inside and section is not None:
                break
            inside = s[1:-1] == section
            if inside:
                start = last = i
            continue
        if inside:
            if s:
                last = i
            if '=' in s and s.split('=', 1)[0].strip() == key:
                found = i
                break
    if found is not None:
        lines[found] = f'{key} = {shown}'
    elif section is None:
        lines.append(f'{key} = {shown}')
    elif start is not None:
        lines.insert(last + 1, f'{key} = {shown}')
    else:
        if lines and lines[-1].strip():
            lines.append('')
        lines += [f'[{section}]', f'{key} = {shown}']
    return '\n'.join(lines) + '\n'


def backup(path):
    """Cópia do arquivo antes de editar (até 20 por emulador)."""
    if not path.exists():
        return None
    folder = state_dir()/'backups'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder/f'{path.name}.{time.strftime("%Y%m%d-%H%M%S")}.{time.time_ns() % 1000000:06d}'
    shutil.copy2(path, target)
    for old in sorted(folder.glob(path.name + '.*'))[:-20]:
        old.unlink()
    return str(target)


def write(path, text):
    """Grava de forma atômica (nunca fica um arquivo pela metade)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name + '.')
    with os.fdopen(fd, 'w') as out:
        out.write(text)
    os.replace(tmp, path)


# ---- os emuladores ---------------------------------------------------------------------
def cfg_path(*parts):
    return Path(os.environ.get('XDG_CONFIG_HOME', home()/'.config')).joinpath(*parts)


def data_path(*parts):
    return Path(os.environ.get('XDG_DATA_HOME', home()/'.local/share')).joinpath(*parts)


RES = {
    'pcsx2': [(1, '1x nativo'), (2, '2x 720p'), (3, '3x 1080p'), (4, '4x 1440p'), (6, '6x 4K')],
    'dolphin': [(1, '1x nativo'), (2, '2x 720p'), (3, '3x 1080p'), (4, '4x 1440p'), (6, '6x 4K')],
    'ppsspp': [(1, '1x nativo'), (2, '2x'), (3, '3x 720p'), (4, '4x'), (5, '5x 1080p')],
    'ryujinx': [(1, '1x nativo'), (2, '2x'), (3, '3x'), (4, '4x')],
}


def emulators():
    """Cada emulador: onde está a configuração e como cada ajuste é gravado nela.
    setting: (arquivo, seção, chave, verdadeiro, falso) para liga/desliga; (arquivo, seção, chave) para escolha."""
    cfg = games.config()
    pcsx2 = cfg_path('PCSX2', 'inis', 'PCSX2.ini')
    dolphin, gfx = cfg_path('dolphin-emu', 'Dolphin.ini'), cfg_path('dolphin-emu', 'GFX.ini')
    ppsspp = cfg_path('ppsspp', 'PSP', 'SYSTEM', 'ppsspp.ini')
    retro = cfg_path('retroarch', 'retroarch.cfg')
    ryu = cfg_path('Ryujinx', 'Config.json')
    return {
        'pcsx2': {'name': 'PCSX2', 'system': 'PS2', 'installed': bool(games.appimage('pcsx2', cfg) or shutil.which('pcsx2-qt')),
                  'config': pcsx2, 'pad': 'apply',
                  'res': (pcsx2, 'EmuCore/GS', 'upscale_multiplier'),
                  'fullscreen': (pcsx2, 'UI', 'StartFullscreen', 'true', 'false'),
                  'vsync': (pcsx2, 'EmuCore/GS', 'VsyncEnable', 'true', 'false'),
                  'fps': (pcsx2, 'EmuCore/GS', 'OsdShowFPS', 'true', 'false')},
        'dolphin': {'name': 'Dolphin', 'system': 'GameCube / Wii', 'installed': bool(shutil.which('dolphin-emu')),
                    'config': dolphin, 'pad': 'apply',
                    'res': (gfx, 'Settings', 'InternalResolution'),
                    'fullscreen': (dolphin, 'Display', 'Fullscreen', 'True', 'False'),
                    'vsync': (gfx, 'Hardware', 'VSync', 'True', 'False'),
                    'fps': (gfx, 'Settings', 'ShowFPS', 'True', 'False')},
        'ppsspp': {'name': 'PPSSPP', 'system': 'PSP', 'installed': bool(shutil.which('ppsspp') or shutil.which('PPSSPPSDL')),
                   'config': ppsspp, 'pad': 'auto',
                   'res': (ppsspp, 'Graphics', 'InternalResolution'),
                   'fullscreen': (ppsspp, 'Graphics', 'FullScreen', 'True', 'False')},
        'retroarch': {'name': 'RetroArch', 'system': 'NES, SNES, GBA, N64, PS1…', 'installed': bool(shutil.which(cfg['retroarch'])),
                      'config': retro, 'pad': 'auto',
                      'fullscreen': (retro, None, 'video_fullscreen', 'true', 'false'),
                      'vsync': (retro, None, 'video_vsync', 'true', 'false'),
                      'fps': (retro, None, 'fps_show', 'true', 'false')},
        'ryujinx': {'name': 'Ryujinx', 'system': 'Switch', 'installed': bool(shutil.which('ryujinx')),
                    'config': ryu, 'pad': 'manual', 'json': True,
                    'res': (ryu, None, 'res_scale'),
                    'fullscreen': (ryu, None, 'start_fullscreen', True, False),
                    'vsync': (ryu, None, 'vsync_mode', 0, 1)},
        'shadps4': {'name': 'shadPS4', 'system': 'PS4', 'installed': bool(games.appimage('shadps4', cfg)),
                    'config': data_path('shadPS4', 'config.toml'), 'pad': 'auto'},
        'azahar': {'name': 'Azahar', 'system': '3DS', 'installed': bool(games.appimage('azahar', cfg)),
                   'config': cfg_path('azahar-emu', 'qt-config.ini'), 'pad': 'manual'},
    }


SETTINGS = ('res', 'fullscreen', 'vsync', 'fps')
# What the emulator does when the key is not in its file (only where it is not "off").
DEFAULTS = {('retroarch', 'vsync'): True}
LABELS = {'res': 'resolução', 'fullscreen': 'tela cheia', 'vsync': 'vsync', 'fps': 'mostrar FPS'}
PAD_NOTE = {'apply': 'aplica o controle como player 1',
            'auto': 'usa o controle sozinho (SDL)',
            'manual': 'configure o controle uma vez no próprio emulador'}


def read_value(emu, spec):
    """Valor atual de um ajuste (texto do arquivo, ou o do JSON)."""
    path, section, key = spec[:3]
    try:
        if emu.get('json'):
            return json.loads(path.read_text()).get(key)
        return ini_get(path.read_text(), section, key)
    except (OSError, ValueError):
        return None


def describe(eid, emu):
    """Um emulador para a tela: instalado, configuração e os ajustes com o valor atual."""
    has_config = emu['config'].exists()
    out = {'id': eid, 'name': emu['name'], 'system': emu['system'], 'installed': emu['installed'],
           'config': str(emu['config']), 'has_config': has_config, 'pad': emu['pad'], 'pad_note': PAD_NOTE[emu['pad']],
           'settings': []}
    for key in SETTINGS:
        spec = emu.get(key)
        if not spec:
            continue
        raw = read_value(emu, spec) if has_config else None
        if key == 'res':
            try:
                value = int(float(raw)) if raw is not None else 1
            except ValueError:
                value = 1
            out['settings'].append({'key': key, 'label': LABELS[key], 'kind': 'choice', 'value': value,
                                    'choices': [{'v': v, 'label': lab} for v, lab in RES[eid]]})
        else:
            on = DEFAULTS.get((eid, key), False) if raw is None else str(raw).lower() == str(spec[3]).lower()
            out['settings'].append({'key': key, 'label': LABELS[key], 'kind': 'bool', 'value': on})
    return out


def listing():
    """Todos os emuladores conhecidos."""
    return {'emulators': [describe(eid, emu) for eid, emu in emulators().items()]}


def set_value(eid, key, value):
    """Grava um ajuste na configuração do emulador (com backup)."""
    emus = emulators()
    if eid not in emus:
        raise ValueError('emulador desconhecido: ' + eid)
    emu = emus[eid]
    spec = emu.get(key)
    if not spec:
        raise ValueError(f'{emu["name"]} não tem o ajuste {key}')
    if not emu['config'].exists():
        raise ValueError(f'abra o {emu["name"]} uma vez para ele criar a configuração')
    path, section, name = spec[:3]
    if key == 'res':
        allowed = [v for v, _ in RES[eid]]
        if int(value) not in allowed:
            raise ValueError(f'resolução fora das opções: {value}')
        new = int(value)
    else:
        if str(value).lower() not in ('true', 'false', '1', '0', 'on', 'off'):
            raise ValueError('use true ou false')
        new = spec[3] if str(value).lower() in ('true', '1', 'on') else spec[4]
    saved = backup(path)
    if emu.get('json'):
        doc = json.loads(path.read_text())
        doc[name] = new
        if eid == 'ryujinx' and key == 'vsync':
            doc['enable_vsync'] = new == 0     # older builds read this one
        write(path, json.dumps(doc, indent=2, ensure_ascii=False) + '\n')
    else:
        text = path.read_text() if path.exists() else ''
        write(path, ini_set(text, section, name, str(new), quote=section is None))
    return {'emulator': describe(eid, emu), 'backup': saved}


# Player 1 com o controle SDL 0, nos nomes que cada emulador usa.
PCSX2_PAD = {'Type': 'DualShock2', 'Up': 'DPadUp', 'Right': 'DPadRight', 'Down': 'DPadDown', 'Left': 'DPadLeft',
             'Triangle': 'FaceNorth', 'Circle': 'FaceEast', 'Cross': 'FaceSouth', 'Square': 'FaceWest',
             'Select': 'Back', 'Start': 'Start', 'L1': 'LeftShoulder', 'L2': '+LeftTrigger', 'R1': 'RightShoulder',
             'R2': '+RightTrigger', 'L3': 'LeftStick', 'R3': 'RightStick', 'LUp': '-LeftY', 'LRight': '+LeftX',
             'LDown': '+LeftY', 'LLeft': '-LeftX', 'RUp': '-RightY', 'RRight': '+RightX', 'RDown': '+RightY',
             'RLeft': '-RightX', 'Analog': 'Guide'}
DOLPHIN_PAD = {'Buttons/A': '`Button S`', 'Buttons/B': '`Button W`', 'Buttons/X': '`Button E`', 'Buttons/Y': '`Button N`',
               'Buttons/Z': '`Shoulder R`', 'Buttons/Start': 'Start', 'Main Stick/Up': '`Left Y-`',
               'Main Stick/Down': '`Left Y+`', 'Main Stick/Left': '`Left X-`', 'Main Stick/Right': '`Left X+`',
               'C-Stick/Up': '`Right Y-`', 'C-Stick/Down': '`Right Y+`', 'C-Stick/Left': '`Right X-`',
               'C-Stick/Right': '`Right X+`', 'Triggers/L': '`Trigger L`', 'Triggers/R': '`Trigger R`',
               'Triggers/L-Analog': '`Trigger L`', 'Triggers/R-Analog': '`Trigger R`', 'D-Pad/Up': '`Pad N`',
               'D-Pad/Down': '`Pad S`', 'D-Pad/Left': '`Pad W`', 'D-Pad/Right': '`Pad E`'}


def apply_pad(eid, pad_name=None):
    """Põe o primeiro controle SDL como player 1 (PCSX2 e Dolphin)."""
    emus = emulators()
    if eid not in emus or emus[eid]['pad'] != 'apply':
        raise ValueError('esse emulador não precisa (ou não deixa) aplicar o controle daqui')
    emu = emus[eid]
    if not emu['config'].exists():
        raise ValueError(f'abra o {emu["name"]} uma vez para ele criar a configuração')
    backups = []
    if eid == 'pcsx2':
        text = emu['config'].read_text()
        backups.append(backup(emu['config']))
        text = ini_set(text, 'InputSources', 'SDL', 'true')
        for key, value in PCSX2_PAD.items():
            text = ini_set(text, 'Pad1', key, value if key == 'Type' else 'SDL-0/' + value)
        write(emu['config'], text)
    else:
        name = pad_name or next((p['name'] for p in pads()['pads']), None)
        if not name:
            raise ValueError('nenhum controle conectado')
        pad = cfg_path('dolphin-emu', 'GCPadNew.ini')
        text = pad.read_text() if pad.exists() else ''
        backups.append(backup(pad))
        text = ini_set(text, 'GCPad1', 'Device', f'SDL/0/{name}')
        for key, value in DOLPHIN_PAD.items():
            text = ini_set(text, 'GCPad1', key, value)
        write(pad, text)
        main = emu['config']
        backups.append(backup(main))
        write(main, ini_set(main.read_text(), 'Core', 'SIDevice0', '6'))   # 6 = controle padrão
    return {'applied': emu['name'], 'backups': [b for b in backups if b]}


# ---- controles -------------------------------------------------------------------------
def sdl_guid(bus, vendor, product, version):
    """GUID SDL de um controle no Linux (cada campo de 16 bits em little-endian, com zeros entre eles)."""
    le = lambda x: f'{x & 0xff:02x}{x >> 8:02x}'
    return f'{le(bus)}0000{le(vendor)}0000{le(product)}0000{le(version)}0000'


def mappings():
    """Linhas de controllers.txt por GUID (sem comentários)."""
    out = {}
    for line in games.controller_mappings():
        out[line.split(',', 1)[0].lower()] = line
    return out


def battery(event):
    """Bateria do controle (%), se o driver informar."""
    base = ROOT/'sys/class/input'/event/'device'/'device'/'power_supply'
    for cap in sorted(base.glob('*/capacity')):
        try:
            return int(cap.read_text().strip())
        except (OSError, ValueError):
            pass
    return None


def pads():
    """Controles conectados (os que o kernel trata como joystick)."""
    try:
        text = (ROOT/'proc/bus/input/devices').read_text()
    except OSError:
        text = ''
    known = mappings()
    out = []
    for block in text.split('\n\n'):
        ident = re.search(r'Bus=([0-9a-f]+) Vendor=([0-9a-f]+) Product=([0-9a-f]+) Version=([0-9a-f]+)', block)
        name = re.search(r'^N: Name="(.*)"$', block, re.M)
        handlers = re.search(r'^H: Handlers=(.*)$', block, re.M)
        if not (ident and name and handlers) or not re.search(r'\bjs\d+', handlers.group(1)):
            continue
        event = re.search(r'\b(event\d+)\b', handlers.group(1))
        bus, vendor, product, version = (int(x, 16) for x in ident.groups())
        guid = sdl_guid(bus, vendor, product, version)
        # The version is often zeroed in mappings (any firmware): both count.
        line = known.get(guid) or known.get(guid[:24] + '00000000')
        out.append({'name': name.group(1), 'event': event.group(1) if event else None,
                    'id': f'{vendor:04x}:{product:04x}', 'guid': guid, 'mapped': bool(line),
                    'mapping': line, 'battery': battery(event.group(1)) if event else None})
    return {'pads': out}


# ---- teste ao vivo: os índices que o SDL dá a cada botão e eixo ------------------------
BTN_MISC, BTN_JOYSTICK, KEY_MAX, ABS_MAX = 0x100, 0x120, 0x2ff, 0x3f
HATS = range(0x10, 0x18)


def bitmap(text):
    """Bitmap de capacidades do sysfs ("1f 0 ff…", palavra mais alta primeiro) → conjunto de códigos."""
    codes = set()
    words = text.split()
    bits = 64 if any(len(w) > 8 for w in words) or struct.calcsize('l') == 8 else 32
    for i, word in enumerate(reversed(words)):
        value = int(word, 16)
        for b in range(bits):
            if value >> b & 1:
                codes.add(i*bits + b)
    return codes


def layout(event):
    """Índices SDL: botões de BTN_JOYSTICK até KEY_MAX e depois de BTN_MISC; eixos sem os de hat."""
    caps = ROOT/'sys/class/input'/event/'device'/'capabilities'
    keys = bitmap((caps/'key').read_text()) if (caps/'key').exists() else set()
    axes = bitmap((caps/'abs').read_text()) if (caps/'abs').exists() else set()
    order = [c for c in range(BTN_JOYSTICK, KEY_MAX + 1) if c in keys] + [c for c in range(BTN_MISC, BTN_JOYSTICK) if c in keys]
    return ({c: i for i, c in enumerate(order)},
            {c: i for i, c in enumerate(c for c in range(ABS_MAX + 1) if c in axes and c not in HATS)})


def absinfo(fd, code):
    """(mínimo, máximo) de um eixo pelo ioctl EVIOCGABS."""
    request = (2 << 30) | (24 << 16) | (ord('E') << 8) | (0x40 + code)
    try:
        _, lo, hi, *_ = struct.unpack('6i', fcntl.ioctl(fd, request, bytes(24)))
        return lo, hi
    except OSError:
        return -32768, 32767


def watch(event, out=sys.stdout):
    """Uma linha JSON por evento: botão (b), eixo (a, de -1 a 1) ou direcional digital (h)."""
    if not re.fullmatch(r'event\d+', event):
        raise ValueError('evento inválido: ' + event)
    buttons, axes = layout(event)
    fmt = 'llHHi'
    size = struct.calcsize(fmt)
    hat = {}
    with open(ROOT/'dev/input'/event, 'rb', buffering=0) as dev:
        ranges = {c: absinfo(dev.fileno(), c) for c in axes}
        print(json.dumps({'ready': True, 'buttons': len(buttons), 'axes': len(axes)}), file=out, flush=True)
        while True:
            chunk = dev.read(size)
            if len(chunk) < size:
                return
            _, _, kind, code, value = struct.unpack(fmt, chunk)
            if kind == 1 and code in buttons:
                print(json.dumps({'t': 'b', 'i': buttons[code], 'v': 1 if value else 0}), file=out, flush=True)
            elif kind == 3 and code in HATS[:2]:
                hat[code] = value
                x, y = hat.get(0x10, 0), hat.get(0x11, 0)
                mask = (1 if y < 0 else 0) | (2 if x > 0 else 0) | (4 if y > 0 else 0) | (8 if x < 0 else 0)
                print(json.dumps({'t': 'h', 'i': 0, 'v': mask}), file=out, flush=True)
            elif kind == 3 and code in axes:
                lo, hi = ranges[code]
                v = (2*(value - lo)/(hi - lo) - 1) if hi > lo else 0
                print(json.dumps({'t': 'a', 'i': axes[code], 'v': round(v, 3)}), file=out, flush=True)


TARGETS = ['a', 'b', 'x', 'y', 'back', 'guide', 'start', 'leftstick', 'rightstick', 'leftshoulder', 'rightshoulder',
           'dpup', 'dpdown', 'dpleft', 'dpright', 'leftx', 'lefty', 'rightx', 'righty', 'lefttrigger', 'righttrigger']


def pad_save(guid, name, pairs):
    """Grava (ou troca) a linha SDL deste controle em controllers.txt, com backup."""
    if not re.fullmatch(r'[0-9a-f]{32}', guid):
        raise ValueError('GUID inválido')
    name = re.sub(r'[,\n]', ' ', name).strip() or 'Controle'
    binds = []
    for pair in pairs:
        target, _, value = pair.partition('=')
        if target not in TARGETS or not re.fullmatch(r'b\d+|a\d+|[+-]a\d+|a\d+~|h0\.(1|2|4|8)', value):
            raise ValueError('mapeamento inválido: ' + pair)
        binds.append(f'{target}:{value}')
    if not binds:
        raise ValueError('nenhum botão mapeado')
    line = f'{guid},{name},{",".join(binds)},platform:Linux,'
    path = games.data_dir()/'controllers.txt'
    old = path.read_text().splitlines() if path.exists() else [
        '# Mapeamentos SDL de controles que o Proton/Wine não reconhecem sozinhos (um por linha).',
        '# O LW passa estas linhas aos jogos em SDL_GAMECONTROLLERCONFIG.']
    saved = backup(path)
    kept = [l for l in old if l.split(',', 1)[0].strip().lower() != guid]
    write(path, '\n'.join(kept + [line]) + '\n')
    return {'saved': name, 'line': line, 'backup': saved}
