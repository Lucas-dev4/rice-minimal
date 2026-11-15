#!/usr/bin/env python3
"""Event-driven palette generation and the shared Waypaper/Noctalia bridge."""
# theme.py — o motor de cores do rice. Quando o wallpaper muda (pelo Waypaper, LW ou TUI):
# 1) gera a paleta com o Matugen a partir da imagem;  2) escreve os arquivos de tema de cada programa
# (Kitty, Waybar, Fish, Neovim, Noctalia, yazi, cliamp, bloqueio...) numa pasta "geração" nova;
# 3) troca o link "current" para ela de uma vez e avisa os programas para recarregar.
# A geração anterior fica em "previous" (lw palette restore). Tudo sob a trava generation.lock.
# Estado em ~/.local/state/rice-minimal/theme/.
import argparse
import colorsys
import configparser
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'extras'))
STATE = Path(os.environ.get('RICE_THEME_STATE', Path.home()/'.local/state/rice-minimal/theme'))
WAYPAPER = Path.home()/'.config/waypaper/config.ini'
FALLBACK = dict(background='#111612', foreground='#d9dfd5', accent='#a6b898',
                muted='#929b8d', red='#d6aaa1', green='#a9bc9c', yellow='#c9bd98',
                blue='#9eafb9', magenta='#b6a4b6', cyan='#9fbcb6',
                bar_foreground='#e8ede4', bar_accent='#c9dcc0')

GREETER_SETTLE = 2  # seconds; comfortably longer than Noctalia's palette animation
GREETER_STAGE = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))/'noctalia-greeter-sync'
LOG_LIMIT = 256*1024
TERMINAL_WORST_BACKGROUND = '#3a3a3a'  # dark terminal at 0.85 opacity over a white wallpaper

def command(args, **kwargs):
    """Roda um comando e devolve a saída; lança erro se falhar (limite de 30 s)."""
    return subprocess.run([str(a) for a in args], check=True, capture_output=True,
                          text=True, timeout=30, **kwargs).stdout.strip()

def waypaper_settings():
    """Seção [Settings] do config.ini do Waypaper."""
    cf = configparser.ConfigParser(interpolation=None)
    cf.read(WAYPAPER)
    return cf['Settings'] if cf.has_section('Settings') else {}

def selected_wallpaper():
    """O wallpaper escolhido no Waypaper (se o arquivo existir)."""
    value = waypaper_settings().get('wallpaper', '')
    path = Path(value).expanduser() if value else None
    return path if path and path.is_file() else None

def current_wallpaper():
    """O wallpaper que o Noctalia está mostrando agora (ou o do Waypaper como reserva)."""
    try:
        path = Path(command(['noctalia', 'msg', 'wallpaper-get'])).expanduser()
        if path.is_file():
            return path
    except (subprocess.SubprocessError, OSError):
        pass
    return selected_wallpaper()

def library():
    """Pasta de wallpapers configurada no Waypaper e se a busca é recursiva."""
    settings = waypaper_settings()
    folder = settings.get('folder', '')
    if not folder:
        raise ValueError('Waypaper has no configured wallpaper folder')
    path = Path(folder).expanduser()
    recursive = any(settings.get(k, 'false').lower() == 'true'
                    for k in ('subfolders', 'all_subfolders'))
    return path, recursive

def images():
    """Todas as imagens da pasta de wallpapers, em ordem alfabética."""
    folder, recursive = library()
    extensions = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tif', '.tiff'}
    return sorted((p for p in (folder.rglob('*') if recursive else folder.iterdir())
                   if p.is_file() and p.suffix.lower() in extensions), key=lambda p: p.name.casefold())

@contextmanager
def locked(timeout=None):
    # Not reentrant: flock on a second descriptor deadlocks the same process.
    """Trava exclusiva do tema (uma mudança por vez). Não chame dentro de outro "with locked()"."""
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE/'generation.lock').open('a') as stream:
        if timeout is None:
            fcntl.flock(stream, fcntl.LOCK_EX)
        else:
            deadline = time.monotonic()+timeout
            while True:
                try:
                    fcntl.flock(stream, fcntl.LOCK_EX|fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() > deadline:
                        raise TimeoutError('Another theme change is still running') from None
                    time.sleep(.1)
        yield

def log_action(action, status, detail=''):
    # Shared history for the GUI; losing a line must never fail the change itself.
    """Acrescenta uma linha ao histórico actions.jsonl (o painel LOG do LW lê dali)."""
    path = STATE/'actions.jsonl'
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        with path.open('a') as stream:
            stream.write(json.dumps({'time_ns':time.time_ns(),'action':action,'status':status,'detail':str(detail)},ensure_ascii=False)+'\n')
        if path.stat().st_size > LOG_LIMIT:
            temporary = path.with_name('.actions.tmp')
            temporary.write_text('\n'.join(path.read_text().splitlines()[-500:])+'\n')
            os.replace(temporary, path)
    except OSError:
        pass

def read_palette():
    """A paleta publicada atual, ou cores de emergência se não houver."""
    try:
        return json.loads((STATE/'current/palette.json').read_text())
    except (OSError, ValueError):
        return {'colors': FALLBACK.copy(), 'generator': 'static-emergency'}

def rgb(color):
    """"#rrggbb" → (r, g, b) entre 0 e 1; valida o formato."""
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        raise ValueError(f'Invalid color: {color!r}')
    return tuple(int(color[i:i+2], 16)/255 for i in (1, 3, 5))

def hexcolor(values):
    """(r, g, b) entre 0 e 1 → "#rrggbb"."""
    return '#'+''.join(f'{max(0, min(255, round(v*255))):02x}' for v in values)

def subdued(color, cap=0.23):
    """Mesma cor com saturação limitada (o visual "pouco saturado" do rice)."""
    h, l, s = colorsys.rgb_to_hls(*rgb(color))
    return hexcolor(colorsys.hls_to_rgb(h, l, min(s, cap)))

def vivid(color, saturation=.7, lightness=.72):
    # Keeps the wallpaper's hue but makes it readable as a color in terminal text.
    """Mesma tonalidade, mas viva e clara o bastante para texto colorido no terminal."""
    h, _, s = colorsys.rgb_to_hls(*rgb(color))
    if s < .02:
        return color
    # Blues are darker at equal lightness, so each hue rises only as far as it needs.
    while True:
        candidate = hexcolor(colorsys.hls_to_rgb(h, lightness, saturation))
        if ratio(candidate, TERMINAL_WORST_BACKGROUND) >= 4.5 or lightness >= .9:
            return candidate
        lightness += .01

def image_hue(path):
    # Matugen picks its most suitable color, not the most present one, which can be
    # the opposite of what the image looks like. Weight each pixel by how colorful it is.
    """Tonalidade dominante da imagem, dando mais peso aos pixels mais coloridos."""
    from PIL import Image
    with Image.open(path) as image:
        image = image.convert('RGB')
        image.thumbnail((160, 160))
        data = image.convert('HSV').tobytes()
    bins = [0]*36
    colorful = 0
    for hue, saturation, value in zip(data[0::3], data[1::3], data[2::3]):
        if saturation > 64 and value > 51:
            colorful += 1
            bins[hue*36//256] += saturation*value
    top = max(range(36), key=lambda i: bins[i-1]+bins[i]+bins[(i+1)%36])
    return {'hue':top*10+5, 'colorful':round(colorful/(len(data)//3), 3)}

def terminal_accent(palette):
    """A cor de destaque viva (terminal, LW, Waybar, Noctalia) a partir da tonalidade do wallpaper."""
    info = palette.get('terminal') or {}
    hue = info.get('hue')
    if hue is None:
        hue = colorsys.rgb_to_hls(*rgb(palette['colors']['accent']))[0]*360
    hue = float(hue)%360
    # Commands must not read as errors, so hues next to red move to the closest side.
    if hue >= 345 or hue < 3:
        hue = 340
    elif hue < 25:
        hue = 25
    # A nearly gray image has no real hue to amplify.
    saturation = .4 if info.get('colorful', 1) < .08 else .7
    return vivid(hexcolor(colorsys.hls_to_rgb(hue/360, .6, .6)), saturation)

def terminal_colors(palette):
    # The vivid set: terminal text, LW, Waybar tints and Noctalia's accents.
    """O conjunto de cores vivas usadas no texto do terminal e nos destaques."""
    c = palette['colors']
    return {**{k:vivid(c[k]) for k in ('green','yellow','blue','magenta','cyan')},
            'accent':terminal_accent(palette), 'red':vivid('#ff4040', .95, .68)}

def sgr(color):
    """Cor → código de escape ANSI de 24 bits (para o fish/fzf)."""
    return '38;2;'+';'.join(str(round(x*255)) for x in rgb(color))

def luminance(color):
    """Luminância relativa (fórmula do WCAG) — base do cálculo de contraste."""
    values = [v/12.92 if v <= 0.04045 else ((v+0.055)/1.055)**2.4 for v in rgb(color)]
    return sum(v*w for v, w in zip(values, (.2126, .7152, .0722)))

def ratio(a, b):
    """Contraste entre duas cores (1 a 21; 4.5 é o mínimo bom para texto)."""
    x, y = sorted((luminance(a), luminance(b)))
    return (y+.05)/(x+.05)

def mix(a, b, amount):
    """Mistura duas cores (amount 0 = só a primeira, 1 = só a segunda)."""
    return hexcolor(x*(1-amount)+y*amount for x, y in zip(rgb(a), rgb(b)))

def bar_contrast(path, colors, size=(1920, 1080), tints=None):
    """Sample the visible top strip after cover scaling; never poll the screen."""
    from PIL import Image, ImageOps
    with Image.open(path) as image:
        # Small target preserves the same crop and avoids a full desktop-sized allocation.
        width = 384
        height = max(1, round(width*size[1]/size[0]))
        cover = ImageOps.fit(image.convert('RGB'), (width, height))
        strip = cover.crop((0, 0, width, max(1, round(height*28/size[1]))))
        samples = [hexcolor(v/255 for v in pixel) for pixel in strip.get_flattened_data()]
    values = [luminance(sample) for sample in samples]
    def scorer(region):
        """Cria a função que mede o contraste de uma cor contra a faixa amostrada."""
        def score(color):
            lum = luminance(color)
            contrasts = sorted((max(lum,v)+.05)/(min(lum,v)+.05) for v in region)
            return contrasts[len(contrasts)//10]
        return score
    score = scorer(values)
    light = subdued(colors['foreground'])
    dark = colors['background']
    # Intermediate neutral tones also help images containing both bright and dark areas.
    h, _, _ = colorsys.rgb_to_hls(*rgb(colors['accent']))
    candidates = [light,dark,'#f2f4ee','#101510'] + [
        hexcolor(colorsys.hls_to_rgb(h,l/100,.08)) for l in range(0,101,4)]
    tints = tints or {}
    def choose(scoring, tint=None):
        """Escolhe a cor de texto da barra mais legível, mantendo a tonalidade do wallpaper se der."""
        foreground = max(candidates, key=scoring)
        accent = tint or subdued(colors['accent'])
        # Retain the wallpaper hue as far as the sampled background allows.
        for amount in (0,.2,.4,.6,.8,1):
            candidate = mix(accent,foreground,amount)
            if scoring(candidate) >= min(4.5, scoring(foreground)):
                return foreground,candidate
        return foreground,foreground
    foreground,accent = choose(score)
    colors.update(bar_foreground=foreground, bar_accent=accent)
    # Estimate module positions from the preserved layout and 13px monospace font.
    # This avoids choosing dark text for the bright left side and losing it on a dark right side.
    screen_width = size[0]
    edge = screen_width
    regions = {}
    metrics = {}
    for name,module_width in (('clock',50),('volume',80),('memory',80),('cpu',72)):
        regions[name] = (max(0,edge-module_width),edge)
        edge -= module_width+8
    workspace_width = 100
    try:
        workspaces = json.loads(command(['hyprctl','-j','workspaces']))
        workspace_width = max(37,min(400,len(workspaces)*37))
    except (OSError,ValueError,subprocess.SubprocessError):
        pass
    regions['workspace'] = (0,workspace_width)
    regions['window'] = (workspace_width+8,min(workspace_width+400,screen_width))
    for name,(left,right) in regions.items():
        x0 = max(0,min(width-1,round(left*width/screen_width)))
        x1 = max(x0+1,min(width,round(right*width/screen_width)))
        pixels = [luminance(hexcolor(v/255 for v in p)) for p in strip.crop((x0,0,x1,strip.height)).get_flattened_data()]
        regional = scorer(pixels)
        fg,ac = choose(regional, tints.get(name))
        # Each module keeps its own hue, darkened or lightened only as far as legibility needs.
        colors['bar_'+name] = ac if name == 'clock' or (name in tints and name != 'workspace') else fg
        if name == 'workspace':
            colors['bar_accent'] = ac
        metrics[name] = round(regional(colors['bar_'+name]),2)
    return {'text_contrast_p10': round(score(foreground), 2),
            'accent_contrast_p10': round(score(accent), 2), 'modules_p10':metrics,
            'sample': 'top 28px, cover, estimated module bounds, focused monitor'}

def monitor_size():
    """Tamanho lógico do monitor em foco (para recortar a faixa da barra igual à tela)."""
    try:
        monitors = json.loads(command(['hyprctl', '-j', 'monitors']))
        monitor = next((m for m in monitors if m.get('focused')), monitors[0])
        scale = monitor.get('scale', 1)
        return round(monitor['width']/scale), round(monitor['height']/scale)
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
        return 1920, 1080

# Matugen schemes offered by the GUI; the choice is kept in STATE/scheme.
SCHEMES = ('scheme-neutral', 'scheme-tonal-spot', 'scheme-vibrant', 'scheme-expressive')

def scheme():
    """Esquema do Matugen escolhido (neutral, tonal-spot, vibrant, expressive)."""
    try:
        value = (STATE/'scheme').read_text().strip()
        return value if value in SCHEMES else SCHEMES[0]
    except OSError:
        return SCHEMES[0]

def set_scheme(value):
    """Grava o esquema do Matugen escolhido."""
    if value not in SCHEMES:
        raise ValueError('Unknown scheme: '+value)
    temporary = STATE/'.scheme.tmp'
    temporary.write_text(value+'\n')
    temporary.replace(STATE/'scheme')

def fingerprint(path):
    """Identidade de wallpaper+esquema: se não mudou, a paleta em cache é reaproveitada."""
    stat = path.stat()
    # The default keeps its old tag, so palettes made before schemes existed stay cached.
    tag = 'neutral-v4' if scheme() == SCHEMES[0] else scheme()+'-v4'
    return hashlib.sha256(f'{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:{tag}'.encode()).hexdigest()

def generate(path):
    """Roda o Matugen na imagem e monta a paleta escura do rice."""
    raw = command(['matugen', 'image', path, '--config', ROOT/'extras/theme/matugen.toml',
                   '--dry-run', '--json', 'hex', '--mode', 'dark',
                   '--type', scheme(), '--source-color-index', '0', '--quiet'])
    data = json.loads(raw)['colors']
    def color(name):
        """Uma cor do Matugen, já com a saturação limitada."""
        return subdued(data[name]['dark']['color'])
    colors = dict(background=color('background'), foreground=color('on_surface'),
                  accent=color('primary'), muted=color('outline'), red=color('error'),
                  green=color('secondary'), yellow=color('tertiary'),
                  blue=color('primary'), magenta=color('tertiary'), cyan=color('secondary'))
    # ANSI hues stay distinguishable, with a subtle bias toward the wallpaper accent.
    for key in ('red', 'green', 'yellow', 'blue', 'magenta', 'cyan'):
        colors[key] = subdued(mix(FALLBACK[key], colors['accent'], .18), .25)
    if ratio(colors['foreground'], colors['background']) < 7:
        colors['foreground'] = '#e5e9df'
    terminal = image_hue(path)
    accent = terminal_accent({'colors':colors,'terminal':terminal})
    tints = {'workspace':accent, 'clock':accent, 'cpu':vivid(colors['green']),
             'memory':vivid(colors['yellow']), 'volume':vivid(colors['cyan'])}
    contrast = bar_contrast(path, colors, monitor_size(), tints)
    return dict(colors=colors, terminal=terminal, wallpaper=str(path.resolve()), fingerprint=fingerprint(path),
                generator=f'matugen 4.2 / {scheme()} / dark', contrast=contrast,
                created_ns=time.time_ns())

def current_profile():
    """Perfil atual: minimal ou refined."""
    try:
        profile = (STATE/'profile').read_text().strip()
        return profile if profile in ('minimal', 'refined') else 'minimal'
    except OSError:
        return 'minimal'

def render(palette):
    """Escreve o conteúdo de todos os arquivos de tema (Kitty, Waybar, Hyprland, fish, nvim, Noctalia...)."""
    c = palette['colors']
    for value in c.values():
        rgb(value)
    ansi = [c['background'], c['red'], c['green'], c['yellow'], c['blue'], c['magenta'], c['cyan'], c['foreground'],
            c['muted']] + [mix(c[k], c['foreground'], .2) for k in ('red','green','yellow','blue','magenta','cyan')] + [c['foreground']]
    v = terminal_colors(palette)
    terminal = [c['background'], v['red'], v['green'], v['yellow'], v['blue'], v['magenta'], v['cyan'], c['foreground'],
                c['muted']] + [mix(v[k], '#ffffff', .2) for k in ('red','green','yellow','blue','magenta','cyan')] + [c['foreground']]
    # Same colors as Kitty, in the format pywal.nvim sources from ~/.cache/wal.
    wal = '" LW: terminal colors for pywal.nvim.\n' + ''.join(
        f"let g:{key} = '{value}'\n" for key,value in
        [('background',c['background']),('foreground',c['foreground']),('cursor',v['accent'])]
        + [(f'color{i}',value) for i,value in enumerate(terminal)])
    # cliamp theme: same vivid terminal colors; no bg keeps Kitty's transparency.
    cliamp = '# LW: generated on every palette change.\n' + ''.join(
        f'{key} = "{value}"\n' for key,value in (('accent',v['accent']),('bright_fg',c['foreground']),
        ('fg',c['muted']),('green',v['green']),('yellow',v['yellow']),('red',v['red'])))
    # yazi: its default theme already uses ANSI colors; only the fixed blues change.
    a, bg, muted = v['accent'], c['background'], c['muted']
    yazi = f'''# LW: generated on every palette change; edits are overwritten.
[mgr]
cwd = {{ fg = "{a}" }}
border_style = {{ fg = "{muted}" }}

[tabs]
active = {{ fg = "{a}", bold = true }}
inactive = {{ fg = "{muted}" }}

[mode]
normal_main = {{ fg = "{bg}", bg = "{a}", bold = true }}
normal_alt = {{ fg = "{a}" }}

[indicator]
current = {{ fg = "{bg}", bg = "{a}" }}
parent = {{ fg = "{a}", bold = true }}

# filetype has no prepend: the full preset list (yazi 26.9.1), only the folder color changes.
[filetype]
rules = [
\t{{ mime = "**/image/*", fg = "yellow" }},
\t{{ mime = "**/{{audio,video}}/*", fg = "magenta" }},
\t{{ mime = "**/application/{{zip,rar,7z*,tar,gzip,xz,zstd,bzip*,lzma,compress,archive,cpio,arj,xar,ms-cab*}}", fg = "red" }},
\t{{ mime = "**/application/{{pdf,doc,rtf}}", fg = "cyan" }},
\t{{ mime = "vfs/{{absent,stale}}", fg = "gray" }},
\t{{ url = "*", is = "orphan", bg = "red" }},
\t{{ url = "*", is = "exec", fg = "green" }},
\t{{ url = "*", is = "dummy", bg = "red" }},
\t{{ url = "*/", is = "dummy", bg = "red" }},
\t{{ url = "*/", fg = "{a}" }},
]

[icon]
prepend_conds = [
\t{{ if = "dir & hovered", text = "\ue5fe", fg = "{bg}" }},
\t{{ if = "dir", text = "\ue5ff", fg = "{a}" }},
]
'''
    kitty = '\n'.join(f'{k} {v}' for k,v in {
        'background':c['background'], 'foreground':c['foreground'], 'cursor':c['accent'],
        'cursor_text_color':c['background'], 'selection_background':c['accent'],
        'selection_foreground':c['background'], **{f'color{i}':value for i,value in enumerate(terminal)}}.items())+'\n'
    css = f"@define-color rice_text {c['bar_foreground']};\n@define-color rice_accent {c['bar_accent']};\n"
    # No single color can stay readable on a mixed strip, so a halo steps in only then.
    measured = (palette.get('contrast') or {}).get('modules_p10',{})
    for name in ('workspace','cpu','memory','volume','clock'):
        halo = '#000000' if luminance(c.get('bar_'+name,c['foreground'])) > .4 else '#ffffff'
        css += f"@define-color rice_{name}_halo {'transparent' if measured.get(name,99) >= 4.5 else halo};\n"
    for name in ('workspace','window','cpu','memory','volume','clock'):
        css += f"@define-color rice_{name} {c.get('bar_'+name,c['bar_foreground'])};\n"
    css += f"@define-color rice_urgent {c['red']};\n"
    refined = current_profile() == 'refined'
    accent = c['accent']
    ink = max((c['background'], c['foreground']), key=lambda v: ratio(v, accent))
    css += '@define-color rice_active_bg transparent;\n'
    css += f"@define-color rice_active_fg {c['bar_accent']};\n"
    css += '@define-color rice_active_border transparent;\n'
    duration = '150ms' if refined else '0ms'
    profile_css = '#workspaces button { transition: background-color '+duration+' ease, color '+duration+' ease, border-color '+duration+' ease; }\n'
    hypr = ('hl.config({ general = { border_size = 1, col = { active_border = "rgba('+c['accent'][1:]+'ff)", '
            'inactive_border = "rgba('+c['muted'][1:]+'ff)" } } })\n')
    types = {'di':'1;'+sgr(v['accent']), 'ln':sgr(v['cyan']), 'ex':'1;'+sgr(v['green']), 'or':sgr(v['red']),
              'so':sgr(v['magenta']), 'pi':sgr(v['yellow']), 'bd':sgr(v['yellow']), 'cd':sgr(v['yellow'])}
    kinds = {'im':sgr(v['magenta']), 'vi':sgr(v['magenta']), 'mu':sgr(v['cyan']), 'lo':sgr(v['cyan']),
             'do':sgr(v['yellow']), 'co':sgr(v['red']), 'sc':sgr(v['blue'])}
    listing = lambda values: ':'.join(f'{key}={value}' for key,value in values.items())
    fish = '\n'.join(f"set -g {key} {value.lstrip('#')}" for key,value in {
        'rice_prompt_color':v['accent'], 'rice_error_color':v['red'],
        'fish_color_normal':c['foreground'], 'fish_color_command':v['accent'], 'fish_color_keyword':v['magenta'],
        'fish_color_param':c['foreground'], 'fish_color_option':v['cyan'], 'fish_color_quote':v['green'],
        'fish_color_error':v['red']+' --bold --underline', 'fish_color_comment':c['muted'],
        'fish_color_operator':v['cyan'], 'fish_color_redirection':v['magenta'], 'fish_color_end':v['magenta'],
        'fish_color_escape':v['yellow'], 'fish_color_autosuggestion':c['muted'],
        'fish_color_search_match':v['yellow']}.items())+'\n'
    fish += f"set -gx LS_COLORS '{listing(types)}'\nset -gx EZA_COLORS '{listing({**types,**kinds})}'\n"
    # bat (and man, through MANPAGER) uses the terminal ANSI colors; fzf gets the same
    # palette, a transparent background and plain ASCII marks.
    fzf = (f"--color=bg:-1,bg+:-1,gutter:-1,fg:{c['foreground']},fg+:{c['foreground']},hl:{v['accent']},hl+:{v['accent']},"
           f"info:{c['muted']},prompt:{v['accent']},pointer:{v['accent']},marker:{v['green']},spinner:{v['accent']},"
           f"header:{c['muted']},border:{c['muted']},separator:{c['muted']},scrollbar:{c['muted']} "
           # Quoted: an unquoted > breaks how fzf reads the options after it.
           "--pointer='>' --marker='*' --prompt='> ' --gutter=' ' --separator=- --no-scrollbar")
    fish += f'set -gx BAT_THEME ansi\nset -gx FZF_DEFAULT_OPTS "{fzf}"\nset -g rice_accent_sgr \'{sgr(v["accent"])}\'\n'
    # Noctalia's panels, launcher and widgets use the same vivid accent as LW, Kitty and the
    # Waybar (the subdued Matugen colors made them look grey next to everything else).
    noctalia = {'dark': {
        'mPrimary':v['accent'], 'mOnPrimary':c['background'],
        'mSecondary':v['accent'], 'mOnSecondary':c['background'],
        'mTertiary':v['cyan'], 'mOnTertiary':c['background'],
        'mError':v['red'], 'mOnError':c['background'],
        'mSurface':c['background'], 'mOnSurface':c['foreground'],
        'mSurfaceVariant':mix(c['background'], c['foreground'], .07),
        'mOnSurfaceVariant':c['muted'], 'mOutline':c['muted'],
        'mShadow':c['background'], 'mHover':v['accent'], 'mOnHover':c['background'],
    }}
    names = ('black','red','green','yellow','blue','magenta','cyan','white')
    noctalia['dark']['terminal'] = {
        'normal':dict(zip(names,ansi[:8])), 'bright':dict(zip(names,ansi[8:])),
        'background':c['background'], 'foreground':c['foreground'],
        'cursor':c['accent'], 'cursorText':c['background'],
        'selectionBg':c['accent'], 'selectionFg':c['background'],
    }
    import lockscreen
    lock_theme = lockscreen.render(palette, current_profile())
    return {'lockscreen.toml':lock_theme, 'noctalia.json':json.dumps(noctalia,indent=2)+'\n', 'kitty.conf':kitty, 'colors.css':css, 'profile.css':profile_css, 'hyprland.lua':hypr, 'colors.fish':fish,
            'colors-wal.vim':wal, 'cliamp.toml':cliamp, 'yazi-theme.toml':yazi, 'palette.json':json.dumps(palette,indent=2)+'\n'}

def link(name, target):
    """Troca um link simbólico (current/previous) de forma atômica."""
    temporary = STATE/f'.{name}-{time.time_ns()}'
    temporary.symlink_to(target)
    os.replace(temporary, STATE/name)

def prune(keep, limit=20):
    # Generations are cheap to rebuild; keep the newest ones and whatever is in use.
    """Apaga gerações antigas (mantém as 20 mais novas e as que estão em uso)."""
    keep = {path for path in keep if path} | {(STATE/'previous').resolve()}
    folders = [p for p in STATE.glob('palette-*') if p.is_dir()]
    # Empty folders are failed publishes; they must not take one of the kept places.
    empty = [p for p in folders if not any(p.iterdir())]
    generations = sorted((p for p in folders if p not in empty), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in generations[limit:] + empty:
        if path.resolve() not in keep:
            shutil.rmtree(path, ignore_errors=True)

def publish(palette):
    """Cria uma geração nova com os arquivos, valida e aponta "current" para ela."""
    folder = Path(tempfile.mkdtemp(prefix='palette-', dir=STATE))
    for name, content in render(palette).items():
        (folder/name).write_text(content)
    command(['luac', '-p', folder/'hyprland.lua'])
    command(['fish', '-n', folder/'colors.fish'])
    # GTK's real CSS parser validates before any running bar can read the file.
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    Gtk.CssProvider().load_from_data((folder/'colors.css').read_bytes())
    previous = (STATE/'current').resolve() if (STATE/'current').exists() else None
    prune(keep={folder.resolve(), previous})
    if previous:
        # Profile and lock changes republish the same colors; keep the real previous palette.
        try:
            same = json.loads((previous/'palette.json').read_text()).get('colors') == palette.get('colors')
        except (OSError, ValueError):
            same = False
        if not same:
            link('previous', previous.name)
    link('current', folder.name)
    return previous

def reload_components():
    """Avisa os programas para recarregar as cores (kitty, waybar, Noctalia, hyprland...)."""
    warnings = []
    if (STATE/'lock-enabled').exists():
        import lockscreen
        lockscreen.validate()
        lockscreen.atomic(Path.home()/'.config/noctalia/rice-lock.toml', (STATE/'current/lockscreen.toml').read_text())
    if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
        command(['hyprctl', 'eval', (STATE/'current/hyprland.lua').read_text()])
    if (Path.home()/'.config/noctalia/palettes/RiceMinimal.json').exists():
        target = Path.home()/'.config/noctalia/palettes/RiceMinimal.json'
        temporary = target.with_name('.RiceMinimal.json.tmp')
        temporary.write_text((STATE/'current/noctalia.json').read_text())
        os.replace(temporary, target)
        command(['noctalia', 'msg', 'config-reload'])
    # Terminal apps that read a theme file: Neovim (pywal.nvim), cliamp and yazi.
    for name, target in (('colors-wal.vim', Path.home()/'.cache/wal/colors-wal.vim'),
                         ('cliamp.toml', Path.home()/'.config/cliamp/themes/rice.toml'),
                         ('yazi-theme.toml', Path.home()/'.config/yazi/theme.toml')):
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name('.'+target.name+'.tmp')
        temporary.write_text((STATE/'current'/name).read_text())
        os.replace(temporary, target)
    for app, sig in (('kitty', signal.SIGUSR1), ('waybar', signal.SIGUSR2)):
        try:
            pids = command(['pgrep', '-u', str(os.getuid()), '-x', app]).split()
        except subprocess.CalledProcessError:
            continue
        for pid in pids:
            try:
                os.kill(int(pid), sig)
            except ProcessLookupError:
                pass
            except OSError as exc:
                warnings.append(f'{app}: {exc}')
    # Noctalia reload restores its configured bar; keep the supervisor's fallback hidden.
    try:
        command(['pgrep', '-u', str(os.getuid()), '-x', 'waybar'])
    except subprocess.CalledProcessError:
        pass
    else:
        command(['noctalia', 'msg', 'bar-hide'])
    return warnings

def activate(palette, reload=True):
    """Publica a paleta e recarrega; se a recarga falhar, volta para a geração anterior."""
    previous = publish(palette)
    if reload:
        try:
            warnings = reload_components()
        except Exception:
            if previous:
                link('current', previous.name)
                reload_components()
            raise
        return warnings
    return []

def save_status(**values):
    """Grava o status.json (resultado da última mudança)."""
    temporary = STATE/f'.status-{time.time_ns()}'
    temporary.write_text(json.dumps(values, indent=2)+'\n')
    os.replace(temporary, STATE/'status.json')

def regenerate(path=None, force=False, reload=True):
    """Gera a paleta para o wallpaper (usa o cache se nada mudou, a não ser com force)."""
    path = path or current_wallpaper()
    if path is None:
        raise ValueError('No readable wallpaper was found')
    if not force and read_palette().get('fingerprint') == fingerprint(path):
        save_status(result='cached', wallpaper=str(path), time_ns=time.time_ns())
        return 'cached'
    try:
        palette = generate(path)
    except Exception as exc:
        error = getattr(exc, 'stderr', None) or str(exc)
        if (STATE/'current/palette.json').is_file():
            save_status(result='kept-last-palette', error=error, wallpaper=str(path), time_ns=time.time_ns())
            return 'kept-last-palette'
        palette = {'colors':FALLBACK.copy(), 'generator':'static-emergency', 'error':error}
        try:
            palette['contrast'] = bar_contrast(path, palette['colors'], monitor_size())
        except Exception:
            pass
    warnings = activate(palette, reload=reload)
    save_status(result=palette['generator'], wallpaper=str(path), warnings=warnings, time_ns=time.time_ns())
    return palette['generator']

def set_wallpaper(path):
    """Pede ao Noctalia para mostrar um wallpaper."""
    path = Path(path).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError('Wallpaper is not a file')
    command(['noctalia','msg','wallpaper-set',path])
    # IPC acknowledgement is asynchronous. Confirm the effective selection.
    for _ in range(40):
        current = current_wallpaper()
        if current and current.resolve() == path:
            return
        time.sleep(.1)
    raise RuntimeError('Noctalia did not confirm the selected wallpaper')

def sync_greeter(force=False):
    # scripts/restore_greeter.sh removes this flag to stop automatic syncing.
    """Envia wallpaper e cores para a tela de login (se o envio automático estiver ligado)."""
    if not force and not (STATE/'greeter-sync').exists():
        log_action('greeter','SKIP','automatic sync is off')
        return 'disabled'
    # With animations on (Refined), Noctalia fades between palettes and greeter-sync
    # would snapshot a blend; Minimal switches instantly, so it can sync right away.
    # The login screen is cosmetic here: a failure must not fail the wallpaper change.
    time.sleep(GREETER_SETTLE if current_profile() == 'refined' else 0)
    try:
        command(['noctalia','msg','greeter-sync'])
    except (OSError, subprocess.SubprocessError) as exc:
        log_action('greeter','FAIL',getattr(exc,'stderr',None) or exc)
        return 'failed'
    log_action('greeter','OK','sent to the login screen')
    return 'sent'

def greeter_status():
    # greeter-sync only acknowledges the request; the staged copy shows what was really sent.
    """O que foi enviado para a tela de login e se ainda bate com o tema atual."""
    status = {'auto_sync':(STATE/'greeter-sync').exists(),'staged':False,'last_sync_ns':None,
              'image':None,'colors_match':None,'image_match':None}
    staged = GREETER_STAGE/'sync.toml'
    if not staged.is_file():
        return status
    sent = tomllib.loads(staged.read_text())['appearance']['palette']
    colors = json.loads((STATE/'current/noctalia.json').read_text())['dark']
    pairs = {'primary':'mPrimary','surface':'mSurface','on_surface':'mOnSurface','outline':'mOutline'}
    image = next(GREETER_STAGE.glob('wallpaper.*'), None)
    wallpaper = current_wallpaper()
    status.update(staged=True, last_sync_ns=staged.stat().st_mtime_ns, image=str(image) if image else None,
                  colors_match=all(sent.get(a,'').lower() == colors[b].lower() for a,b in pairs.items()),
                  image_match=bool(image and wallpaper and image.read_bytes() == wallpaper.read_bytes()))
    return status

REVEAL = ROOT/'gui/reveal'

def reveal(path):
    # Builds the new wallpaper in ASCII on screen (gui/reveal) and waits, briefly, until the
    # screen is covered so the swap underneath is unseen. Cosmetic: never fails the change.
    # Touch STATE/reveal-off to disable it.
    """Animação ASCII ao trocar de wallpaper (só enfeite; nunca impede a troca)."""
    try:
        if (STATE/'reveal-off').exists() or not os.environ.get('WAYLAND_DISPLAY'):
            return
        target = Path(path).expanduser().resolve()
        shown = subprocess.run(['noctalia','msg','wallpaper-get'], capture_output=True, text=True, timeout=2).stdout.strip()
        if shown and Path(shown).expanduser().resolve() == target:
            return  # duplicate Waypaper event or the same image again
        ready = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp'))/'rice-reveal.ready'
        ready.unlink(missing_ok=True)
        env = dict(os.environ, RICE_REVEAL_IMAGE=str(target), RICE_REVEAL_READY=str(ready))
        # The GUI runs on the software renderer and its children inherit it; the reveal is a
        # GPU shader and draws nothing there, leaving only the black cover.
        env.pop('QT_QUICK_BACKEND', None)
        subprocess.Popen(['qs','-n','-p',str(REVEAL)], env=env, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        for _ in range(15):
            if ready.exists():
                return
            time.sleep(.1)
    except Exception:
        pass

def wallpaper_hook(path=None, wait=True):
    # Waypaper starts its hook before finishing its own config save.
    """O gancho do Waypaper: aplica o wallpaper, gera a paleta e sincroniza o resto."""
    if wait:
        time.sleep(.3)
    with locked():
        latest = selected_wallpaper()
        chosen = latest or (Path(path).expanduser() if path else None)
        if chosen is None:
            raise ValueError('Waypaper has no readable selection')
        reveal(chosen)
        set_wallpaper(chosen)
        result = regenerate(chosen)
        # Duplicate Waypaper events land here as 'cached'; nothing new to send.
        if result != 'cached':
            log_action('wallpaper','OK',Path(chosen).name)
            log_action('palette','WARN' if result == 'kept-last-palette' else 'OK',result)
            sync_greeter()
        return result

def sync_all():
    # One lock for the whole flow; every step below must stay unlocked.
    """SYNC ALL: wallpaper, paleta, bloqueio e greeter em ordem, sob uma única trava."""
    steps = []
    def step(name, status, detail=''):
        """Registra o resultado de um passo (e no LOG)."""
        steps.append({'step':name,'status':status,'detail':str(detail)})
        log_action(name,status,detail)
    try:
        with locked(timeout=30):
            chosen = selected_wallpaper() or current_wallpaper()
            if chosen is None:
                raise ValueError('No readable wallpaper was found')
            active = current_wallpaper()
            if not active or active.resolve() != chosen.resolve():
                set_wallpaper(chosen)
            step('wallpaper','OK',chosen.name)
            result = regenerate(chosen)
            # Nothing was published, so the running components still need refreshing.
            if result in ('cached','kept-last-palette'):
                reload_components()
            step('palette','WARN' if result == 'kept-last-palette' else 'OK',result)
            import lockscreen
            try:
                lockscreen.validate()
                step('lock','OK','active' if (STATE/'lock-enabled').exists() else 'candidate updated')
            except Exception as exc:
                step('lock','WARN',exc)
            result = sync_greeter(force=True)
            steps.append({'step':'greeter','status':'OK' if result == 'sent' else 'WARN','detail':result})
    except Exception as exc:
        log_action('sync','FAIL',exc)
        raise
    return steps

def apply_choice(path):
    # Persist through Waypaper, then execute the very same hook synchronously.
    """Aplica um wallpaper pelo Waypaper e roda o gancho na hora."""
    command(['waypaper','--wallpaper',path,'--no-post-command'])
    # Waypaper has already exited and saved, so there is nothing to wait for.
    return wallpaper_hook(path, wait=False)

def restore_previous(reload=True):
    """Volta para a geração de cores anterior."""
    with locked():
        previous = (STATE/'previous').resolve()
        current = (STATE/'current').resolve()
        palette = json.loads((previous/'palette.json').read_text())
        expected = render(palette)  # Reject corrupt or untrusted color values.
        # Palette history may belong to a different appearance profile.
        if any(not (previous/name).is_file() or (previous/name).read_text() != value
               for name,value in expected.items()):
            publish(palette)
        else:
            link('current', previous.name)
        try:
            if reload:
                reload_components()
        except Exception:
            link('current', current.name)
            link('previous', previous.name)
            raise
        link('previous', current.name)
        save_status(result='restored', palette=previous.name, time_ns=time.time_ns())
        return previous.name

def cached(restore_wallpaper=False):
    """Republica a paleta atual sem rodar o Matugen (usado no login e na instalação)."""
    with locked():
        # Never execute Matugen during startup.
        try:
            palette = json.loads((STATE/'current/palette.json').read_text())
            expected = render(palette)
            if any(not (STATE/'current'/name).is_file() or (STATE/'current'/name).read_text() != value for name,value in expected.items()):
                activate(palette, reload=False)
        except (OSError, ValueError, KeyError):
            activate({'colors':FALLBACK.copy(), 'generator':'static-emergency'}, reload=False)
        if restore_wallpaper:
            selected = selected_wallpaper()
            if selected:
                set_wallpaper(selected)
        return read_palette()['generator']

def main():
    """Linha de comando: wallpaper | regenerate | cached | restore | show | apply."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['wallpaper','regenerate','cached','restore','show','apply'])
    parser.add_argument('path', nargs='?')
    parser.add_argument('--restore-wallpaper', action='store_true')
    parser.add_argument('--no-reload', action='store_true')
    args = parser.parse_args()
    if args.action == 'wallpaper':
        result = wallpaper_hook(args.path)
    elif args.action == 'apply':
        if not args.path:
            parser.error('apply requires a path')
        result = apply_choice(Path(args.path).expanduser())
    elif args.action == 'regenerate':
        with locked():
            result = regenerate(Path(args.path).expanduser() if args.path else None, force=True, reload=not args.no_reload)
    elif args.action == 'restore':
        result = restore_previous(reload=not args.no_reload)
    elif args.action == 'cached':
        result = cached(args.restore_wallpaper)
    else:
        result = json.dumps(read_palette(), indent=2)
    print(result)

if __name__ == '__main__':
    try:
        directory = Path(__file__).resolve().parent
        sys.path[:] = [p for p in sys.path if Path(p or '.').resolve() != directory]
        sys.path.insert(0,str(directory.parent))
        from theme import theme as api
        api.main()
    except Exception as exc:
        print(f'rice-theme: {exc}', file=sys.stderr)
        sys.exit(1)
