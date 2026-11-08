#!/usr/bin/env python3
"""Event-driven palette generation and the shared Waypaper/Noctalia bridge."""
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
    return subprocess.run([str(a) for a in args], check=True, capture_output=True,
                          text=True, timeout=30, **kwargs).stdout.strip()

def waypaper_settings():
    cf = configparser.ConfigParser(interpolation=None)
    cf.read(WAYPAPER)
    return cf['Settings'] if cf.has_section('Settings') else {}

def selected_wallpaper():
    value = waypaper_settings().get('wallpaper', '')
    path = Path(value).expanduser() if value else None
    return path if path and path.is_file() else None

def current_wallpaper():
    try:
        path = Path(command(['noctalia', 'msg', 'wallpaper-get'])).expanduser()
        if path.is_file():
            return path
    except (subprocess.SubprocessError, OSError):
        pass
    return selected_wallpaper()

def library():
    settings = waypaper_settings()
    folder = settings.get('folder', '')
    if not folder:
        raise ValueError('Waypaper has no configured wallpaper folder')
    path = Path(folder).expanduser()
    recursive = any(settings.get(k, 'false').lower() == 'true'
                    for k in ('subfolders', 'all_subfolders'))
    return path, recursive

def images():
    folder, recursive = library()
    extensions = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tif', '.tiff'}
    return sorted((p for p in (folder.rglob('*') if recursive else folder.iterdir())
                   if p.is_file() and p.suffix.lower() in extensions), key=lambda p: p.name.casefold())

@contextmanager
def locked(timeout=None):
    # Not reentrant: flock on a second descriptor deadlocks the same process.
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
    try:
        return json.loads((STATE/'current/palette.json').read_text())
    except (OSError, ValueError):
        return {'colors': FALLBACK.copy(), 'generator': 'static-emergency'}

def rgb(color):
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        raise ValueError(f'Invalid color: {color!r}')
    return tuple(int(color[i:i+2], 16)/255 for i in (1, 3, 5))

def hexcolor(values):
    return '#'+''.join(f'{max(0, min(255, round(v*255))):02x}' for v in values)

def subdued(color, cap=0.23):
    h, l, s = colorsys.rgb_to_hls(*rgb(color))
    return hexcolor(colorsys.hls_to_rgb(h, l, min(s, cap)))

def vivid(color, saturation=.7, lightness=.72):
    # Keeps the wallpaper's hue but makes it readable as a color in terminal text.
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
    # Only terminal text is vivid; bars and Noctalia keep the subdued palette.
    c = palette['colors']
    return {**{k:vivid(c[k]) for k in ('green','yellow','blue','magenta','cyan')},
            'accent':terminal_accent(palette), 'red':vivid('#ff4040', .95, .68)}

def sgr(color):
    return '38;2;'+';'.join(str(round(x*255)) for x in rgb(color))

def luminance(color):
    values = [v/12.92 if v <= 0.04045 else ((v+0.055)/1.055)**2.4 for v in rgb(color)]
    return sum(v*w for v, w in zip(values, (.2126, .7152, .0722)))

def ratio(a, b):
    x, y = sorted((luminance(a), luminance(b)))
    return (y+.05)/(x+.05)

def mix(a, b, amount):
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
    try:
        monitors = json.loads(command(['hyprctl', '-j', 'monitors']))
        monitor = next((m for m in monitors if m.get('focused')), monitors[0])
        scale = monitor.get('scale', 1)
        return round(monitor['width']/scale), round(monitor['height']/scale)
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
        return 1920, 1080

def fingerprint(path):
    stat = path.stat()
    return hashlib.sha256(f'{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:neutral-v4'.encode()).hexdigest()

def generate(path):
    raw = command(['matugen', 'image', path, '--config', ROOT/'extras/theme/matugen.toml',
                   '--dry-run', '--json', 'hex', '--mode', 'dark',
                   '--type', 'scheme-neutral', '--source-color-index', '0', '--quiet'])
    data = json.loads(raw)['colors']
    def color(name):
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
                generator='matugen 4.2 / scheme-neutral / dark', contrast=contrast,
                created_ns=time.time_ns())

def current_profile():
    try:
        profile = (STATE/'profile').read_text().strip()
        return profile if profile in ('minimal', 'refined') else 'minimal'
    except OSError:
        return 'minimal'

def render(palette):
    c = palette['colors']
    for value in c.values():
        rgb(value)
    ansi = [c['background'], c['red'], c['green'], c['yellow'], c['blue'], c['magenta'], c['cyan'], c['foreground'],
            c['muted']] + [mix(c[k], c['foreground'], .2) for k in ('red','green','yellow','blue','magenta','cyan')] + [c['foreground']]
    v = terminal_colors(palette)
    terminal = [c['background'], v['red'], v['green'], v['yellow'], v['blue'], v['magenta'], v['cyan'], c['foreground'],
                c['muted']] + [mix(v[k], '#ffffff', .2) for k in ('red','green','yellow','blue','magenta','cyan')] + [c['foreground']]
    # Same colors as Kitty, in the format pywal.nvim sources from ~/.cache/wal.
    wal = '" RICE // minimal: terminal colors for pywal.nvim.\n' + ''.join(
        f"let g:{key} = '{value}'\n" for key,value in
        [('background',c['background']),('foreground',c['foreground']),('cursor',v['accent'])]
        + [(f'color{i}',value) for i,value in enumerate(terminal)])
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
    highlights = {
        'Normal': {'fg':c['foreground'], 'bg':'NONE'}, 'NormalFloat': {'fg':c['foreground'],'bg':c['background']},
        'Comment': {'fg':c['muted']}, 'Constant': {'fg':c['yellow']}, 'String': {'fg':c['green']},
        'Identifier': {'fg':c['foreground']}, 'Function': {'fg':c['accent']}, 'Statement': {'fg':c['accent']},
        'PreProc': {'fg':c['cyan']}, 'Type': {'fg':c['cyan']}, 'Special': {'fg':c['magenta']},
        'LineNr': {'fg':c['muted']}, 'CursorLineNr': {'fg':c['accent'],'bold':True},
        'StatusLine': {'fg':c['foreground'],'bg':c['background']}, 'StatusLineNC': {'fg':c['muted'],'bg':c['background']},
        'Search': {'fg':c['background'],'bg':c['yellow']}, 'Visual': {'fg':c['background'],'bg':c['accent']},
        'ErrorMsg': {'fg':c['red']}, 'DiagnosticError': {'fg':c['red']}, 'DiagnosticWarn': {'fg':c['yellow']},
        'FloatBorder': {'fg':c['muted'],'bg':c['background']},
        'WinSeparator': {'fg':c['muted']},
        'Cursor': {'fg':c['background'],'bg':c['accent']},
        'DiagnosticInfo': {'fg':c['cyan']},
        'DiagnosticHint': {'fg':c['muted']},
        'Pmenu': {'fg':c['foreground'],'bg':c['background']}, 'PmenuSel': {'fg':c['background'],'bg':c['accent']},
    }
    nvim = 'vim.opt.termguicolors = true\nvim.opt.background = "dark"\n'
    for name, attrs in highlights.items():
        fields = ', '.join(f'{k} = {str(v).lower() if isinstance(v,bool) else json.dumps(v)}' for k,v in attrs.items())
        nvim += f'vim.api.nvim_set_hl(0, "{name}", {{ {fields} }})\n'
    noctalia = {'dark': {
        'mPrimary':c['accent'], 'mOnPrimary':ink,
        'mSecondary':c['green'], 'mOnSecondary':c['background'],
        'mTertiary':c['yellow'], 'mOnTertiary':c['background'],
        'mError':c['red'], 'mOnError':c['background'],
        'mSurface':c['background'], 'mOnSurface':c['foreground'],
        'mSurfaceVariant':mix(c['background'], c['foreground'], .07),
        'mOnSurfaceVariant':c['muted'], 'mOutline':c['muted'],
        'mShadow':c['background'], 'mHover':c['accent'], 'mOnHover':ink,
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
            'nvim.lua':nvim, 'colors-wal.vim':wal, 'palette.json':json.dumps(palette,indent=2)+'\n'}

def link(name, target):
    temporary = STATE/f'.{name}-{time.time_ns()}'
    temporary.symlink_to(target)
    os.replace(temporary, STATE/name)

def publish(palette):
    folder = Path(tempfile.mkdtemp(prefix='palette-', dir=STATE))
    for name, content in render(palette).items():
        (folder/name).write_text(content)
    for name in ('hyprland.lua', 'nvim.lua'):
        command(['luac', '-p', folder/name])
    command(['fish', '-n', folder/'colors.fish'])
    # GTK's real CSS parser validates before any running bar can read the file.
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    Gtk.CssProvider().load_from_data((folder/'colors.css').read_bytes())
    previous = (STATE/'current').resolve() if (STATE/'current').exists() else None
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
    wal = Path.home()/'.cache/wal/colors-wal.vim'
    wal.parent.mkdir(parents=True, exist_ok=True)
    temporary = wal.with_name('.colors-wal.vim.tmp')
    temporary.write_text((STATE/'current/colors-wal.vim').read_text())
    os.replace(temporary, wal)
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
    temporary = STATE/f'.status-{time.time_ns()}'
    temporary.write_text(json.dumps(values, indent=2)+'\n')
    os.replace(temporary, STATE/'status.json')

def regenerate(path=None, force=False, reload=True):
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
    if not force and not (STATE/'greeter-sync').exists():
        log_action('greeter','SKIP','automatic sync is off')
        return 'disabled'
    # Noctalia animates palette changes and greeter-sync snapshots the live colors,
    # so syncing right after config-reload would send a mid-animation blend.
    # The login screen is cosmetic here: a failure must not fail the wallpaper change.
    time.sleep(GREETER_SETTLE)
    try:
        command(['noctalia','msg','greeter-sync'])
    except (OSError, subprocess.SubprocessError) as exc:
        log_action('greeter','FAIL',getattr(exc,'stderr',None) or exc)
        return 'failed'
    log_action('greeter','OK','sent to the login screen')
    return 'sent'

def greeter_status():
    # greeter-sync only acknowledges the request; the staged copy shows what was really sent.
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

def wallpaper_hook(path=None):
    # Waypaper starts its hook before finishing its own config save.
    time.sleep(.3)
    with locked():
        latest = selected_wallpaper()
        chosen = latest or (Path(path).expanduser() if path else None)
        if chosen is None:
            raise ValueError('Waypaper has no readable selection')
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
    steps = []
    def step(name, status, detail=''):
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
    command(['waypaper','--wallpaper',path,'--no-post-command'])
    return wallpaper_hook(path)

def restore_previous(reload=True):
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
