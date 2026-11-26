"""Read-only session diagnostics. Never generates colors, reloads or repairs."""
# doctor.py — o "lw doctor": confere sessão, serviços, programas, tema e arquivos instalados.
# Cada checagem vira {status: OK/WARN/FAIL, name, detail}. Nunca conserta nada, só relata.
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
from theme import theme
import modules
import settings


def located(dep):
    """Onde está a dependência de um manifesto, ou '' se falta."""
    if 'python' in dep:
        spec=importlib.util.find_spec(dep['python'])
        return (spec.origin or dep['python']) if spec else ''
    if 'font' in dep:
        try:
            return subprocess.run(['fc-list',dep['font'],'file'],capture_output=True,text=True,timeout=8).stdout.split('\n')[0].strip(' :')
        except (OSError,subprocess.SubprocessError):
            return ''
    # cliamp and other user tools live in ~/.local/bin, not always on the PATH.
    path=os.environ.get('PATH','')+':'+str(Path.home()/'.local/bin')
    names=dep['command'] if isinstance(dep['command'],list) else [dep['command']]
    return next((found for found in (shutil.which(name,path=path) for name in names) if found),'')


def module_dependencies(module):
    """As dependências de um módulo (ligado ou não), obrigatórias antes, cada uma com onde está ('' = falta).
    key é o pacote (pacman ou AUR) que a resolve, ou '' quando ela é manual."""
    m=modules.load()[0][module]
    found=[]
    for dep in sorted(m.get('dependency',[]),key=lambda d: d.get('optional',False)):
        name=dep.get('command') or dep.get('python') or dep.get('font')
        found.append({'name':' / '.join(name) if isinstance(name,list) else name,'key':dep.get('package') or dep.get('aur') or '',
                      'optional':dep.get('optional',False),'why':dep.get('why',''),'found':located(dep),
                      'package':dep.get('package',''),'aur':dep.get('aur',''),'manual':dep.get('manual','')})
    return found


def helper():
    """O instalador do AUR que existir (paru antes de yay), ou None."""
    return next((name for name in ('paru','yay') if shutil.which(name)),None)


def install_plan(deps,picks=None,optional=False):
    """Os comandos exatos para instalar o que falta. picks: só esses pacotes; sem picks, as obrigatórias
    (e as opcionais com optional=True). AUR sem paru/yay e o que é manual ficam em blocked, sem comando."""
    missing=[d for d in deps if not d['found']]
    if picks is None:
        chosen=[d for d in missing if optional or not d['optional']]
    else:
        known={d['key'] for d in deps if d['key']}
        unknown=[p for p in picks if p not in known]
        if unknown:
            raise ValueError('pacote que não é dependência deste módulo: '+', '.join(unknown))
        chosen=[d for d in missing if d['key'] in picks]
    pacman=list(dict.fromkeys(d['package'] for d in chosen if d['package']))
    aur=list(dict.fromkeys(d['aur'] for d in chosen if d['aur']))
    tool=helper()
    commands=[['sudo','pacman','-S','--needed',*pacman]] if pacman else []
    blocked=[]
    if aur and tool:
        commands.append([tool,'-S','--needed',*aur])
    elif aur:
        blocked.append('AUR, sem paru nem yay: instale '+' '.join(aur)+' com um deles')
    blocked+=[d['name']+': '+d['manual'] for d in chosen if d['manual']]
    return {'pacman':pacman,'aur':aur,'helper':tool,'commands':commands,'blocked':blocked}


def module_deps(name,picks=None,optional=False):
    """lw modules deps NOME: as dependências do módulo e o plano para o que falta."""
    m=modules.find(name)
    deps=module_dependencies(m['id'])
    return {'module':m['id'],'name':m['name'],'dependencies':deps,'install':install_plan(deps,picks,optional)}


def module_install(name,picks=None,optional=False,yes=False):
    """lw modules install NOME --yes: roda o plano em primeiro plano (o sudo pede a senha no terminal)."""
    if not yes:
        raise ValueError('nada foi instalado: confira antes com lw modules deps '+name+' e repita com --yes')
    data=module_deps(name,picks,optional)
    data['ran']=[]
    for argv in data['install']['commands']:
        code=subprocess.run(argv).returncode
        data['ran'].append({'command':argv,'code':code})
        if code:
            raise RuntimeError(' '.join(argv)+f' saiu com {code}')
    return data


def deps_text(data):
    """As dependências de um módulo e o plano, para o terminal."""
    out=[data['name']]
    for d in data['dependencies']:
        out.append(f"[ {'OK' if d['found'] else '--'} ] {d['name']}"+(' (opcional)' if d['optional'] else '')
                   +' — '+(d['found'] or 'falta · '+d['why']))
    plan=data['install']
    out+=['']+[' '.join(c) for c in plan['commands']]+plan['blocked']
    if not plan['commands'] and not plan['blocked']:
        out.append('nada a instalar')
    return '\n'.join(out)


def install_text(data):
    """O resultado da instalação, para o terminal."""
    return '\n'.join([f"[ {'OK' if r['code'] == 0 else 'FAIL'} ] "+' '.join(r['command']) for r in data['ran']]
                     +data['install']['blocked']) or 'nada a instalar'


def dependencies(add):
    """As dependências de cada módulo ativo, obrigatórias antes, e o pacman do que falta."""
    on=settings.switches()
    missing={False:[],True:[]}
    for m in modules.load()[0].values():
        if not on[m['id']]:
            continue
        for dep in module_dependencies(m['id']):
            optional=dep['optional']
            detail=place=dep['found']
            if not place:
                # Pacote entra na linha do pacman; AUR e manual dizem o caminho aqui.
                way='AUR: '+dep['aur'] if dep['aur'] else dep['manual']
                detail='falta · '+dep['why']+(' · '+way if way else '')
                if dep['package'] and dep['package'] not in missing[optional]:
                    missing[optional].append(dep['package'])
            add('OK' if place else 'INFO' if optional else 'FAIL',dep['name'],detail,
                module=m['id'],optional=optional)
    extra=[p for p in missing[True] if p not in missing[False]]
    if missing[False]:
        add('WARN','Pacotes obrigatórios','sudo pacman -S --needed '+' '.join(missing[False]))
    if extra:
        add('INFO','Pacotes opcionais','sudo pacman -S --needed '+' '.join(extra))


def inspect(report=None):
    """report, when given, receives each result as soon as it is known (rice doctor --stream)."""
    results=[]
    def add(status,name,detail='',**extra):
        """Guarda um resultado e, no modo --stream, já o envia para quem está ouvindo."""
        results.append({'status':status,'name':name,'detail':str(detail),**extra})
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
    # Manifestos dos módulos e ~/.config/lw/config.toml: com erro vale o padrão.
    bad=settings.problems()
    add('FAIL' if bad else 'OK','LW config','; '.join(bad) or (settings.path() if settings.path().exists() else 'defaults'))
    try:
        # Installed copies that drifted from the repository (scripts/install.py fixes them).
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
    dependencies(add)
    return results


def lines(results):
    """Formata os resultados como texto para o terminal: "[ OK ] nome — detalhe", com um título por módulo."""
    found=modules.load()[0]
    out,title=[],None
    for r in results:
        # As checagens da sessão vêm antes dos módulos, sem título; depois deles só o que instalar.
        block=(found[r['module']]['name']+(' — opcionais' if r['optional'] else ' — obrigatórias') if 'module' in r
               else 'INSTALAR' if title else None)
        if block != title:
            out+=['',block]
            title=block
        out.append(f"[ {r['status']} ] {r['name']}"+(' — '+r['detail'] if r['detail'] else ''))
    return out
