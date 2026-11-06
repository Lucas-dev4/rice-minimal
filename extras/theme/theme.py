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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'extras'))
STATE = Path(os.environ.get('RICE_THEME_STATE', Path.home()/'.local/state/rice-minimal/theme'))
WAYPAPER = Path.home()/'.config/waypaper/config.ini'
FALLBACK = dict(background='#111612', foreground='#d9dfd5', accent='#a6b898',
                muted='#929b8d', red='#d6aaa1', green='#a9bc9c', yellow='#c9bd98',
                blue='#9eafb9', magenta='#b6a4b6', cyan='#9fbcb6',
                bar_foreground='#e8ede4', bar_accent='#c9dcc0')

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
def locked():
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE/'generation.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield

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

def luminance(color):
    values = [v/12.92 if v <= 0.04045 else ((v+0.055)/1.055)**2.4 for v in rgb(color)]
    return sum(v*w for v, w in zip(values, (.2126, .7152, .0722)))

def ratio(a, b):
    x, y = sorted((luminance(a), luminance(b)))
    return (y+.05)/(x+.05)

def mix(a, b, amount):
    return hexcolor(x*(1-amount)+y*amount for x, y in zip(rgb(a), rgb(b)))

def bar_contrast(path, colors, size=(1920, 1080)):
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
    def choose(scoring):
        foreground = max(candidates, key=scoring)
        accent = subdued(colors['accent'])
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
        fg,ac = choose(regional)
        colors['bar_'+name] = ac if name == 'clock' else fg
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
    return hashlib.sha256(f'{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:neutral-v2'.encode()).hexdigest()

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
    contrast = bar_contrast(path, colors, monitor_size())
    return dict(colors=colors, wallpaper=str(path.resolve()), fingerprint=fingerprint(path),
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
    kitty = '\n'.join(f'{k} {v}' for k,v in {
        'background':c['background'], 'foreground':c['foreground'], 'cursor':c['accent'],
        'cursor_text_color':c['background'], 'selection_background':c['accent'],
        'selection_foreground':c['background'], **{f'color{i}':v for i,v in enumerate(ansi)}}.items())+'\n'
    css = f"@define-color rice_text {c['bar_foreground']};\n@define-color rice_accent {c['bar_accent']};\n"
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
    fish = '\n'.join(f'set -g {key} {value[1:]}' for key,value in {
        'rice_prompt_color': c['accent'], 'rice_error_color': c['red'],
        'fish_color_normal':c['foreground'], 'fish_color_command':c['accent'],
        'fish_color_param':c['foreground'], 'fish_color_quote':c['green'],
        'fish_color_error':c['red'], 'fish_color_comment':c['muted'],
        'fish_color_operator':c['cyan'], 'fish_color_escape':c['yellow'],
        'fish_color_autosuggestion':c['muted'], 'fish_color_search_match':c['yellow']}.items())+'\n'
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
            'nvim.lua':nvim, 'palette.json':json.dumps(palette,indent=2)+'\n'}

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

def wallpaper_hook(path=None):
    # Waypaper starts its hook before finishing its own config save.
    time.sleep(.3)
    with locked():
        latest = selected_wallpaper()
        chosen = latest or (Path(path).expanduser() if path else None)
        if chosen is None:
            raise ValueError('Waypaper has no readable selection')
        set_wallpaper(chosen)
        return regenerate(chosen)

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
