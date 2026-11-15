"""Read-only session diagnostics. Never generates colors, reloads or repairs."""
# doctor.py — o "lw doctor": confere sessão, serviços, programas, tema e arquivos instalados.
# Cada checagem vira {status: OK/WARN/FAIL, name, detail}. Nunca conserta nada, só relata.
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from theme import theme


def inspect(report=None):
    """report, when given, receives each result as soon as it is known (rice doctor --stream)."""
    results=[]
    def add(status,name,detail=''):
        """Guarda um resultado e, no modo --stream, já o envia para quem está ouvindo."""
        results.append({'status':status,'name':name,'detail':str(detail)})
        if report:
            report(results[-1])
    def command(name,args,empty=False):
        """Roda um comando e vira resultado: OK se deu certo. Com empty=True, só é OK se não imprimir nada."""
        try:
            p=subprocess.run([str(x) for x in args],capture_output=True,text=True,timeout=8)
            output=(p.stdout+p.stderr).strip()
            good=p.returncode == 0 and (not output if empty else True)
            add('OK' if good else ('FAIL' if empty and p.returncode == 0 and output else 'WARN'),name,output[:300])
            return good,output
        except (OSError,subprocess.SubprocessError) as exc:
            add('WARN',name,exc)
            return False,''
    command('Hyprland version',['hyprctl','version'])
    command('Hyprland Lua errors',['hyprctl','configerrors'],empty=True)
    hypr=Path.home()/'.config/hypr/hyprland.lua'
    add('OK' if hypr.is_file() and 'rice-appearance' in hypr.read_text() else 'FAIL','Lua appearance include',hypr)
    command('Waybar active',['pgrep','-u',str(theme.os.getuid()),'-x','waybar'])
    command('Noctalia services',['noctalia','msg','status'])
    command('Noctalia config',['noctalia','config','validate'])
    command('Audio / PipeWire',['wpctl','status'])
    command('NetworkManager',['systemctl','is-active','NetworkManager'])
    command('Wayland portals',['systemctl','--user','is-active','xdg-desktop-portal.service','xdg-desktop-portal-hyprland.service'])
    command('UWSM graphical session',['systemctl','--user','is-active','graphical-session.target'])
    command('Native screen locker',['noctalia','msg','config-get','lockscreen'])
    for app in ('matugen','waypaper','kitty','fish','nvim','qs'):
        add('OK' if shutil.which(app) else 'FAIL',app,shutil.which(app) or 'missing executable')
    command('Kitty opacity',['kitty','+runpy','from kitty.config import load_config; o=load_config("'+str(Path.home()/'.config/kitty/kitty.conf')+'"); assert o.background_opacity == 0.85; print(o.background_opacity)'])
    command('Fish syntax',['fish','-n',Path.home()/'.config/fish/config.fish'])
    command('Neovim Lua syntax',['luac','-p',Path.home()/'.config/nvim/init.lua'])
    wal=Path.home()/'.cache/wal/colors-wal.vim'
    add('OK' if wal.is_file() else 'WARN','Neovim colors (pywal.nvim)',wal if wal.is_file() else 'missing; run rice sync')
    command('Super validation',['python3',theme.ROOT/'extras/supers/Supers','--check'])
    palette=theme.read_palette()
    path=Path(palette.get('wallpaper','/missing'))
    add('OK' if path.is_file() else 'FAIL','Wallpaper reference',path)
    try:
        command_ok,current=command('Current wallpaper',['noctalia','msg','wallpaper-get'])
        if command_ok:
            add('OK' if Path(current).resolve() == path.resolve() else 'WARN','Wallpaper / palette synchronization',current)
        hook=theme.waypaper_settings().get('post_command','')
        add('OK' if 'theme.py' in hook and 'wallpaper' in hook else 'FAIL','Waypaper / Matugen hook',hook)
        add('OK' if palette.get('generator','').startswith('matugen') else 'WARN','Palette generator',palette.get('generator'))
        profile_file=theme.STATE/'profile'
        value=profile_file.read_text().strip()
        add('OK' if value in ('minimal','refined') else 'FAIL','Persistent appearance profile',value)
    except Exception as exc:
        add('WARN','Adaptive configuration',exc)
    # GTK and Qt follow the theme only through the files Noctalia regenerates.
    sources={Path.home()/'.config/gtk-3.0/gtk.css':'noctalia.css',Path.home()/'.config/gtk-4.0/gtk.css':'noctalia.css',
             Path.home()/'.config/qt5ct/qt5ct.conf':'colors/noctalia.conf',Path.home()/'.config/qt6ct/qt6ct.conf':'colors/noctalia.conf'}
    imports=lambda text:[line for line in text.splitlines() if line.startswith(('@import','color_scheme_path'))]
    stray=[str(path) for path,expected in sources.items() if path.is_file() and any(expected not in line for line in imports(path.read_text()))]
    add('WARN' if stray else 'OK','GTK / Qt theme source',', '.join(stray) or 'Noctalia')
    try:
        greeter=theme.greeter_status()
        synced=greeter['colors_match'] and greeter['image_match']
        add('OK' if synced or not greeter['staged'] else 'WARN','Greeter sync',
            ('matches the current theme' if synced else 'differs from the current theme') if greeter['staged'] else 'nothing sent since boot')
        add('OK' if greeter['auto_sync'] else 'WARN','Greeter automatic sync','on' if greeter['auto_sync'] else 'off')
    except Exception as exc:
        add('WARN','Greeter sync',exc)
    try:
        import lockscreen
        add('OK','Lock visual candidate',lockscreen.validate())
        enabled=(theme.STATE/'lock-enabled').exists()
        add('OK' if enabled else 'WARN','Lock activation','active' if enabled else 'tested on this layout; not activated yet' if lockscreen.tested() else 'staged; run a lock trial first')
    except Exception as exc:
        add('WARN','Lock visual candidate',exc)
    try:
        # Installed copies that drifted from the repository (scripts/install.py fixes them).
        import importlib.util
        spec=importlib.util.spec_from_file_location('rice_install',theme.ROOT/'scripts/install.py')
        install=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(install)
        pending=[str(path).replace(str(Path.home()),'~') for path in install.plan()]
        add('WARN' if pending else 'OK','Installed files match the repo',', '.join(pending) or 'all installed; run scripts/install.py to see details')
    except Exception as exc:
        add('WARN','Installed files match the repo',exc)
    try:
        hashes=json.loads((theme.ROOT/'config/integrity.json').read_text())
        bad=[name for name,digest in hashes.items() if not (theme.ROOT/name).is_file() or hashlib.sha256((theme.ROOT/name).read_bytes()).hexdigest()!=digest]
        add('FAIL' if bad else 'OK','Managed file integrity',', '.join(bad) or str(len(hashes))+' files match')
    except (OSError,ValueError) as exc:
        add('WARN','Managed file integrity',exc)
    return results


def lines(results):
    """Formata os resultados como texto para o terminal: "[ OK ] nome — detalhe"."""
    return [f"[ {r['status']} ] {r['name']}"+(' — '+r['detail'] if r['detail'] else '') for r in results]
