"""Subcomandos do módulo SISTEMA: wallpaper, paleta, atalhos, perfil, bloqueio, greeter…"""
# cmd_system.py — os comandos declarados em modules/system/module.toml (contrato em docs/modulos.md).
# Cada função devolve os dados (ou dados e avisos); o envelope JSON e os erros são do cli.py.
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import tempfile
from theme import theme, profiles
import backups
import lockscreen
import shortcuts

THUMBS = Path(os.environ.get('XDG_CACHE_HOME',Path.home()/'.cache'))/'rice-minimal/thumbs'
THUMB_SIZE = 400


def status():
    """Resumo geral: perfil, paleta, wallpaper escolhido x ativo, estado do bloqueio e última ação."""
    palette=theme.read_palette()
    selected=theme.selected_wallpaper()
    effective=theme.current_wallpaper()
    try:
        terminal=theme.terminal_colors(palette)
    except (KeyError,ValueError):
        terminal={}  # The GUI falls back to the palette colors.
    try:
        last=json.loads((theme.STATE/'status.json').read_text())
    except (OSError,ValueError):
        last=None
    return {'state_dir':str(theme.STATE),
            'profile':theme.current_profile(),
            'generation':(theme.STATE/'current').resolve().name,
            'generator':palette.get('generator'),
            'terminal':terminal,
            'wallpaper':{'selected':str(selected) if selected else None,
                         'effective':str(effective) if effective else None,
                         'in_sync':bool(selected and effective and selected.resolve()==effective.resolve())},
            'lock':{'enabled':(theme.STATE/'lock-enabled').exists(),'tested':(theme.STATE/'lock-tested').exists()},
            'last_status':last}


def uninterruptible():
    # Closing the GUI must not stop a change halfway, such as a new image with the old palette.
    """Ignora SIGTERM/SIGHUP: fechar a janela não pode interromper uma troca pela metade."""
    for number in (signal.SIGTERM,signal.SIGHUP):
        signal.signal(number,signal.SIG_IGN)


def thumb_path(path):
    """Caminho da miniatura de uma imagem no cache (o nome muda se a imagem mudar)."""
    info=path.stat()
    key=f'{path.resolve()}|{info.st_size}|{info.st_mtime_ns}|{THUMB_SIZE}'
    return THUMBS/(hashlib.sha256(key.encode()).hexdigest()[:32]+'.jpg')


def make_thumb(path):
    """Cria a miniatura JPEG (400 px) de um wallpaper."""
    from PIL import Image
    target=thumb_path(path)
    THUMBS.mkdir(parents=True,exist_ok=True)
    handle,temporary=tempfile.mkstemp(dir=THUMBS,suffix='.tmp')
    os.close(handle)
    try:
        with Image.open(path) as image:
            image.draft('RGB',(THUMB_SIZE*2,THUMB_SIZE*2))
            image.thumbnail((THUMB_SIZE,THUMB_SIZE))
            image.convert('RGB').save(temporary,'JPEG',quality=82)
        os.replace(temporary,target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return target


def image_size(path):
    # Only the header is read; the GUI shows it next to the name.
    """Largura e altura de uma imagem (lê só o cabeçalho)."""
    from PIL import Image  # lazy, like make_thumb
    try:
        with Image.open(path) as image:
            return list(image.size)
    except Exception:
        return None


def wallpaper_list():
    """Todos os wallpapers com miniatura, tamanho e qual está ativo (tela Wallpapers)."""
    current=theme.current_wallpaper()
    resolved=current.resolve() if current else None
    images=[]
    for path in theme.images():
        thumb=thumb_path(path)
        images.append({'path':str(path),'name':path.name,'active':path.resolve()==resolved,
                       'thumb':str(thumb) if thumb.exists() else None,
                       'bytes':path.stat().st_size,'size':image_size(path)})
    return {'folder':str(theme.library()[0]),'current':str(current) if current else None,'images':images}


def wallpaper_thumbs():
    # One JSON line per finished image, so the grid fills in while this runs.
    """Gera as miniaturas que faltam, 4 por vez, imprimindo uma linha JSON por imagem pronta."""
    def build(path):
        """Gera uma miniatura e devolve o resultado (ou o erro) para essa imagem."""
        try:
            return {'path':str(path),'thumb':str(make_thumb(path))}
        except Exception as exc:
            return {'path':str(path),'error':str(exc)}
    from concurrent.futures import ThreadPoolExecutor  # only this command needs it
    missing=[p for p in theme.images() if not thumb_path(p).exists()]
    with ThreadPoolExecutor(4) as pool:
        for line in pool.map(build,missing):
            print(json.dumps(line,ensure_ascii=False),flush=True)


def wallpaper_apply(path):
    """Aplica um wallpaper e gera a paleta nova; avisa se a cor falhou ou se outro wallpaper ficou ativo."""
    path=Path(path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f'Wallpaper not found: {path}')
    uninterruptible()
    result=theme.apply_choice(path)
    effective=theme.current_wallpaper()
    warnings=[]
    if result == 'kept-last-palette':
        warnings.append('Color generation failed; the last palette was kept')
    if not effective or effective.resolve() != path.resolve():
        warnings.append(f'Active wallpaper is {effective}, not the requested image')
    return {'requested':str(path),'effective':str(effective) if effective else None,'result':result,
            'generation':(theme.STATE/'current').resolve().name},warnings


def thumb_of(wallpaper):
    """Miniatura já existente de um wallpaper, ou None."""
    try:
        thumb=thumb_path(Path(wallpaper))
    except (OSError,TypeError):
        return None
    return str(thumb) if thumb.exists() else None


def generated_colors():
    """The colors Waybar and Kitty really use, read from the active generation (for previews)."""
    import re
    current=theme.STATE/'current'
    def read(name):
        """Lê um arquivo da geração ativa do tema (vazio se não existir)."""
        try:
            return (current/name).read_text()
        except OSError:
            return ''
    waybar=dict(re.findall(r'@define-color\s+rice_(\w+)\s+([#\w]+);',read('colors.css')))
    kitty=dict(re.findall(r'^(background|foreground|cursor|color\d+)\s+(#[0-9a-fA-F]{6})\s*$',read('kitty.conf'),re.M))
    return {'waybar':waybar,'kitty':kitty}


def palette_show():
    """A paleta atual e a anterior, para a tela Palette (inclui se dá para restaurar)."""
    palette=theme.read_palette()
    try:
        before=json.loads((theme.STATE/'previous/palette.json').read_text())
    except (OSError,ValueError):
        before=None
    summary=None
    if before:
        summary={'generation':(theme.STATE/'previous').resolve().name,'colors':before.get('colors',{}),
                 'wallpaper':before.get('wallpaper'),'thumb':thumb_of(before.get('wallpaper'))}
    return {'generation':(theme.STATE/'current').resolve().name,'generator':palette.get('generator'),
            'emergency':str(palette.get('generator')).startswith('static'),
            'wallpaper':palette.get('wallpaper'),'thumb':thumb_of(palette.get('wallpaper')),
            'colors':palette['colors'],'previous':summary,
            'scheme':theme.scheme().removeprefix('scheme-'),'schemes':[s.removeprefix('scheme-') for s in theme.SCHEMES],
            # The whole rice (Kitty, Waybar, Noctalia) is built for dark; light is not offered.
            'mode':'dark','modes':['dark'],
            **generated_colors(),
            # Profile and lock changes also move `previous`, often to identical colors.
            'can_restore':bool(before and before.get('colors') != palette['colors'])}


def palette_regenerate(scheme=None):
    """Gera a paleta de novo, opcionalmente com outro esquema do Matugen; volta o esquema se falhar."""
    uninterruptible()
    with theme.locked():
        before=theme.scheme()
        if scheme:
            theme.set_scheme(scheme if scheme.startswith('scheme-') else 'scheme-'+scheme)
        try:
            result=theme.regenerate(force=True)
        except Exception:
            theme.set_scheme(before)
            raise
        if result == 'kept-last-palette':
            theme.set_scheme(before)
    if result == 'kept-last-palette':
        theme.log_action('palette','WARN',result)
        return {'result':result},['Color generation failed; the last palette was kept']
    theme.log_action('palette','OK','regenerated: '+result)
    theme.sync_greeter()
    return {'result':result,'generation':(theme.STATE/'current').resolve().name},[]


def palette_restore():
    """Volta para a paleta anterior (só se as cores forem diferentes)."""
    shown=palette_show()
    if not shown['can_restore']:
        raise ValueError('The previous palette has the same colors as the current one')
    uninterruptible()
    generation=theme.restore_previous()
    # Later wallpaper changes keep the scheme of the palette that is now active.
    used=next((part.strip() for part in str(theme.read_palette().get('generator','')).split('/') if part.strip() in theme.SCHEMES),None)
    if used:
        theme.set_scheme(used)
    theme.log_action('palette','OK','restored '+generation)
    theme.sync_greeter()
    warnings=[]
    if shown['previous']['wallpaper'] != shown['wallpaper']:
        warnings.append('This palette was made for another wallpaper; the wallpaper was not changed')
    return {'result':'restored','generation':generation},warnings


def previous_profile():
    """Nome do perfil usado antes do atual, ou None."""
    try:
        return (theme.STATE/'previous-profile').read_text().strip() or None
    except OSError:
        return None


def profile_differences():
    """Only what really changes between the profiles, read from the files that apply them."""
    import re
    def word(value):
        """Valor → texto curto para a tabela (on/off para booleanos)."""
        return ('on' if value else 'off') if isinstance(value,bool) else str(value)
    rows=[]
    lua=(theme.ROOT/'config/hypr/rice-appearance.lua').read_text()
    if re.search(r'animations\s*=\s*\{\s*enabled\s*=\s*refined',lua):
        rows.append({'setting':'hyprland animations','minimal':'off','refined':'on'})
    for leaf,label in (('workspaces','workspace switch'),('windows','window open')):
        found=re.search(r'leaf\s*=\s*"'+leaf+r'".*?speed\s*=\s*([\d.]+)(?:.*?style\s*=\s*"(\w+))?',lua)
        if found:
            # Hyprland animation speed is in tenths of a second.
            ms=round(float(found.group(1))*100)
            rows.append({'setting':label,'minimal':'instant','refined':f"{found.group(2)+' ' if found.group(2) else ''}{ms} ms"})
    minimal,refined=profiles.settings('minimal'),profiles.settings('refined')
    for key in minimal:
        if minimal[key]!=refined[key]:
            rows.append({'setting':'noctalia '+key,'minimal':word(minimal[key]),'refined':word(refined[key])})
    rows.append({'setting':'greeter waits for colors','minimal':'0 s','refined':f'{theme.GREETER_SETTLE} s'})
    return rows


def profile_get():
    """Perfil atual, anterior e as diferenças entre os dois (tela Profiles)."""
    return {'profile':theme.current_profile(),'previous':previous_profile(),'choices':['minimal','refined'],
            'differences':profile_differences()}


def profile_set(name):
    """Troca o perfil (não faz nada se já for o atual)."""
    if name == theme.current_profile():
        return {**profile_get(),'changed':False},[]
    uninterruptible()
    profiles.switch(name)
    theme.log_action('profile','OK',name)
    return {**profile_get(),'changed':True},[]


def profile_restore():
    """Volta para o perfil anterior."""
    name=previous_profile()
    if not name:
        raise ValueError('There is no previous profile')
    return profile_set(name)


def greeter_sync():
    """Envia agora o tema atual para a tela de login."""
    uninterruptible()
    result=theme.sync_greeter(force=True)
    if result != 'sent':
        raise RuntimeError('Noctalia did not accept the sync request')
    return {'result':result},[]


def greeter_auto(value):
    """Liga/desliga o envio automático do tema para a tela de login."""
    flag=theme.STATE/'greeter-sync'
    if value == 'on':
        flag.touch()
    else:
        flag.unlink(missing_ok=True)
    theme.log_action('greeter','OK','automatic sync '+value)
    return {'auto_sync':value == 'on'}


def sync():
    """Reaplica tudo em ordem (wallpaper, paleta, bloqueio, greeter) — o botão SYNC ALL."""
    uninterruptible()
    steps=theme.sync_all()
    return {'steps':steps},[f"{s['step']}: {s['detail']}" for s in steps if s['status'] != 'OK']


def lock_status():
    """Estado do bloqueio com a miniatura do wallpaper."""
    data=lockscreen.status()
    return {**data,'thumb':thumb_of(data['wallpaper'])}


def lock_trial(confirm):
    """Teste real de bloqueio (exige --confirm); o visual anterior volta no fim."""
    if not confirm:
        raise ValueError('Real locking requires --confirm')
    # The session stays locked for as long as this waits, and the visuals restore at the end.
    uninterruptible()
    theme.log_action('lock','OK','trial started')
    try:
        message=lockscreen.run_trial()
    except Exception as exc:
        theme.log_action('lock','FAIL',exc)
        raise
    theme.log_action('lock','OK','trial finished; previous visuals restored')
    return {'result':message}


def lock_activate(confirm):
    """Ativa o visual de bloqueio testado (exige --confirm)."""
    if not confirm:
        raise ValueError('Activation requires --confirm')
    uninterruptible()
    backup=lockscreen.activate()
    theme.log_action('lock','OK','LW lock activated')
    return {'backup':str(backup)}


def lock_update():
    """Refaz o candidato do visual de bloqueio com o tema atual."""
    data={'result':lockscreen.update()}
    theme.log_action('lock','OK','candidate updated')
    return data


def lock_dim(level):
    """Muda o escurecimento do fundo do bloqueio (em %)."""
    data={'dim':lockscreen.set_dim(level/100)}
    theme.log_action('lock','OK',f'background dim {level}%')
    return data


def lock_restore():
    """Volta o visual de bloqueio anterior, com cópia de resgate."""
    data={'rescue':lockscreen.restore()}
    theme.log_action('lock','OK','previous visuals restored')
    return data


def shortcut_set(args):
    """Muda a tecla e/ou o comando de um atalho."""
    data=shortcuts.edit(args.line,args.revision,args.key,args.command,args.file,args.replace)
    theme.log_action('shortcut','OK',data['line'])
    return data


def shortcut_delete(args):
    """Remove um atalho."""
    data=shortcuts.delete(args.line,args.revision,args.file)
    theme.log_action('shortcut','OK','removed '+data['line'])
    return data


def shortcut_restore(args):
    """Volta o arquivo de atalhos para um backup."""
    data=shortcuts.restore(args.backup,args.file)
    theme.log_action('shortcut','OK','restored '+Path(args.backup).name)
    return data


def bluetooth_menu():
    """lw bt: o menu de Bluetooth no terminal."""
    import bluetooth
    return bluetooth.run()


def register(actions,common):
    """Cria os parsers deste módulo; cada um diz que função o executa."""
    def add(group,operation,run,parent=common):
        """Um subcomando com saída JSON."""
        parser=group.add_parser(operation,parents=[parent])
        parser.set_defaults(run=run)
        return parser
    def group(name):
        """Um comando que tem operações (wallpaper list, wallpaper apply…)."""
        return actions.add_parser(name).add_subparsers(dest='operation',required=True)
    add(actions,'status',lambda args: status())
    actions.add_parser('bt').set_defaults(run=lambda args: bluetooth_menu(),stream=True)
    wallpaper=group('wallpaper')
    add(wallpaper,'list',lambda args: wallpaper_list())
    wallpaper.add_parser('thumbs').set_defaults(run=lambda args: wallpaper_thumbs(),stream=True)
    add(wallpaper,'apply',lambda args: wallpaper_apply(args.path)).add_argument('path')
    palette=group('palette')
    add(palette,'show',lambda args: palette_show())
    # O esquema escolhido aqui vale também para as próximas trocas de wallpaper.
    add(palette,'regenerate',lambda args: palette_regenerate(args.scheme)).add_argument(
        '--scheme',choices=[s.removeprefix('scheme-') for s in theme.SCHEMES])
    add(palette,'restore',lambda args: palette_restore())
    profile=group('profile')
    add(profile,'get',lambda args: profile_get())
    add(profile,'set',lambda args: profile_set(args.name)).add_argument('name',choices=['minimal','refined'])
    add(profile,'restore',lambda args: profile_restore())
    greeter=group('greeter')
    add(greeter,'status',lambda args: theme.greeter_status())
    add(greeter,'sync',lambda args: greeter_sync())
    add(greeter,'auto',lambda args: greeter_auto(args.value)).add_argument('value',choices=['on','off'])
    add(actions,'sync',lambda args: sync())
    # --file troca o arquivo de atalhos (testes).
    files=argparse.ArgumentParser(add_help=False,parents=[common])
    files.add_argument('--file',help=argparse.SUPPRESS)
    keys=group('shortcuts')
    add(keys,'list',lambda args: shortcuts.read(args.file),files)
    add(keys,'check',lambda args: shortcuts.check(args.file),files)
    add(keys,'backups',lambda args: shortcuts.backups(args.file),files)
    change=add(keys,'set',shortcut_set,files)
    change.add_argument('--line',type=int,required=True)
    change.add_argument('--revision',required=True)
    change.add_argument('--key',default='')
    change.add_argument('--command',default='')
    change.add_argument('--replace',action='store_true',help='let --command replace a dispatcher or function action')
    drop=add(keys,'delete',shortcut_delete,files)
    drop.add_argument('--line',type=int,required=True)
    drop.add_argument('--revision',required=True)
    add(keys,'restore',shortcut_restore,files).add_argument('backup')
    add(group('backups'),'list',lambda args: backups.listing())
    lock=group('lock')
    add(lock,'status',lambda args: lock_status())
    add(lock,'check',lambda args: {'result':lockscreen.validate()})
    add(lock,'update',lambda args: lock_update())
    add(lock,'restore',lambda args: lock_restore())
    # 35 é o nível claro da TUI; o controle da GUI vai de 55 a 85, de 5 em 5.
    add(lock,'dim',lambda args: lock_dim(args.level)).add_argument('level',type=int,choices=[35,*range(55,90,5)])
    add(lock,'trial',lambda args: lock_trial(args.confirm)).add_argument('--confirm',action='store_true')
    add(lock,'activate',lambda args: lock_activate(args.confirm)).add_argument('--confirm',action='store_true')
