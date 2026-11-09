"""Scriptable commands shared by the GUI: one JSON envelope, no curses."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from theme import theme, profiles
import backups
import lockscreen
import shortcuts

COMMANDS = {'status','gui','music','wallpaper','palette','profile','greeter','sync','shortcuts','lock','backups'}
THUMBS = Path(os.environ.get('XDG_CACHE_HOME',Path.home()/'.cache'))/'rice-minimal/thumbs'
THUMB_SIZE = 400


def status():
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
    for number in (signal.SIGTERM,signal.SIGHUP):
        signal.signal(number,signal.SIG_IGN)


def thumb_path(path):
    info=path.stat()
    key=f'{path.resolve()}|{info.st_size}|{info.st_mtime_ns}|{THUMB_SIZE}'
    return THUMBS/(hashlib.sha256(key.encode()).hexdigest()[:32]+'.jpg')


def make_thumb(path):
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
    from PIL import Image  # lazy, like make_thumb
    try:
        with Image.open(path) as image:
            return list(image.size)
    except Exception:
        return None


def wallpaper_list():
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
    def build(path):
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
        try:
            return (current/name).read_text()
        except OSError:
            return ''
    waybar=dict(re.findall(r'@define-color\s+rice_(\w+)\s+([#\w]+);',read('colors.css')))
    kitty=dict(re.findall(r'^(background|foreground|cursor|color\d+)\s+(#[0-9a-fA-F]{6})\s*$',read('kitty.conf'),re.M))
    return {'waybar':waybar,'kitty':kitty}


def palette_show():
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
    try:
        return (theme.STATE/'previous-profile').read_text().strip() or None
    except OSError:
        return None


def profile_differences():
    """Only what really changes between the profiles, read from the files that apply them."""
    import re
    def word(value):
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
    return {'profile':theme.current_profile(),'previous':previous_profile(),'choices':['minimal','refined'],
            'differences':profile_differences()}


def profile_set(name):
    if name == theme.current_profile():
        return {**profile_get(),'changed':False},[]
    uninterruptible()
    profiles.switch(name)
    theme.log_action('profile','OK',name)
    return {**profile_get(),'changed':True},[]


def profile_restore():
    name=previous_profile()
    if not name:
        raise ValueError('There is no previous profile')
    return profile_set(name)


def greeter_sync():
    uninterruptible()
    result=theme.sync_greeter(force=True)
    if result != 'sent':
        raise RuntimeError('Noctalia did not accept the sync request')
    return {'result':result},[]


def greeter_auto(value):
    flag=theme.STATE/'greeter-sync'
    if value == 'on':
        flag.touch()
    else:
        flag.unlink(missing_ok=True)
    theme.log_action('greeter','OK','automatic sync '+value)
    return {'auto_sync':value == 'on'}


def sync():
    uninterruptible()
    steps=theme.sync_all()
    return {'steps':steps},[f"{s['step']}: {s['detail']}" for s in steps if s['status'] != 'OK']


def lock_status():
    data=lockscreen.status()
    return {**data,'thumb':thumb_of(data['wallpaper'])}


def lock_trial(confirm):
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
    if not confirm:
        raise ValueError('Activation requires --confirm')
    uninterruptible()
    backup=lockscreen.activate()
    theme.log_action('lock','OK','RICE // LOCKED activated')
    return {'backup':str(backup)}


def gui():
    (theme.STATE/'actions.jsonl').touch()
    # A second press closes the open window, so the shortcut works as a toggle.
    path=str(theme.ROOT/'gui')
    probe=subprocess.run(['qs','ipc','-p',path,'show'],capture_output=True,text=True)
    if probe.returncode == 0 and 'target rice' in probe.stdout:
        subprocess.run(['qs','ipc','-p',path,'call','rice','close'],capture_output=True)
        return 0
    # Software rendering looks the same here and uses ~25% less memory, starting twice as fast.
    os.environ.setdefault('QT_QUICK_BACKEND','software')
    os.execvp('qs',['qs','-n','-d','-p',path])


def music():
    # LW // MUSIC: a second Quickshell instance of the same config folder (gui/music.qml).
    # A second press closes it. GPU rendering: the visualizer draws every frame.
    path=str(theme.ROOT/'gui'/'music.qml')
    probe=subprocess.run(['qs','ipc','-p',path,'show'],capture_output=True,text=True)
    if probe.returncode == 0 and 'target music' in probe.stdout:
        subprocess.run(['qs','ipc','-p',path,'call','music','close'],capture_output=True)
        return 0
    os.environ.pop('QT_QUICK_BACKEND',None)
    # The player animates like its prototype in every profile; RICE_GUI_MOTION=0 turns it off.
    os.environ.setdefault('RICE_GUI_MOTION','1')
    os.execvp('qs',['qs','-n','-d','-p',path])


def failure(action,exc):
    return {'ok':False,'action':action,'error':{
        'code':'not_found' if isinstance(exc,FileNotFoundError) else 'invalid' if isinstance(exc,ValueError)
               else 'busy' if isinstance(exc,TimeoutError) else 'failed',
        'message':str(exc),
        'stderr':(getattr(exc,'stderr',None) or '').strip()}}


def main(argv):
    parser=argparse.ArgumentParser(prog='rice')
    common=argparse.ArgumentParser(add_help=False)
    common.add_argument('--json',action='store_true')
    actions=parser.add_subparsers(dest='action',required=True)
    actions.add_parser('status',parents=[common])
    actions.add_parser('gui')
    actions.add_parser('music')
    wallpaper=actions.add_parser('wallpaper').add_subparsers(dest='operation',required=True)
    wallpaper.add_parser('list',parents=[common])
    wallpaper.add_parser('thumbs')
    wallpaper.add_parser('apply',parents=[common]).add_argument('path')
    palette=actions.add_parser('palette').add_subparsers(dest='operation',required=True)
    for operation in ('show','regenerate','restore'):
        palette.add_parser(operation,parents=[common])
    # The scheme chosen here is kept for later wallpaper changes too.
    palette.choices['regenerate'].add_argument('--scheme',choices=[s.removeprefix('scheme-') for s in theme.SCHEMES])
    profile=actions.add_parser('profile').add_subparsers(dest='operation',required=True)
    profile.add_parser('get',parents=[common])
    profile.add_parser('set',parents=[common]).add_argument('name',choices=['minimal','refined'])
    profile.add_parser('restore',parents=[common])
    greeter=actions.add_parser('greeter').add_subparsers(dest='operation',required=True)
    greeter.add_parser('status',parents=[common])
    greeter.add_parser('sync',parents=[common])
    greeter.add_parser('auto',parents=[common]).add_argument('value',choices=['on','off'])
    actions.add_parser('sync',parents=[common])
    common.add_argument('--file',help=argparse.SUPPRESS)
    keys=actions.add_parser('shortcuts').add_subparsers(dest='operation',required=True)
    for operation in ('list','check','backups'):
        keys.add_parser(operation,parents=[common])
    change=keys.add_parser('set',parents=[common])
    change.add_argument('--line',type=int,required=True)
    change.add_argument('--revision',required=True)
    change.add_argument('--key',default='')
    change.add_argument('--command',default='')
    change.add_argument('--replace',action='store_true',help='let --command replace a dispatcher or function action')
    drop=keys.add_parser('delete',parents=[common])
    drop.add_argument('--line',type=int,required=True)
    drop.add_argument('--revision',required=True)
    keys.add_parser('restore',parents=[common]).add_argument('backup')
    saved=actions.add_parser('backups').add_subparsers(dest='operation',required=True)
    saved.add_parser('list',parents=[common])
    lock=actions.add_parser('lock').add_subparsers(dest='operation',required=True)
    for operation in ('status','check','update','restore'):
        lock.add_parser(operation,parents=[common])
    # 35 is the TUI's light level; the GUI slider moves from 55 to 85 in steps of 5.
    lock.add_parser('dim',parents=[common]).add_argument('level',type=int,choices=[35,*range(55,90,5)])
    for operation in ('trial','activate'):
        lock.add_parser(operation,parents=[common]).add_argument('--confirm',action='store_true')
    args=parser.parse_args(argv)
    if args.action == 'gui':
        return gui()
    if args.action == 'music':
        return music()
    if getattr(args,'operation','') == 'thumbs':
        wallpaper_thumbs()
        return 0
    name=args.action+(' '+args.operation if hasattr(args,'operation') else '')
    try:
        warnings=[]
        if name == 'status': data=status()
        elif name == 'wallpaper list': data=wallpaper_list()
        elif name == 'wallpaper apply': data,warnings=wallpaper_apply(args.path)
        elif name == 'palette show': data=palette_show()
        elif name == 'palette regenerate': data,warnings=palette_regenerate(args.scheme)
        elif name == 'palette restore': data,warnings=palette_restore()
        elif name == 'profile get': data=profile_get()
        elif name == 'profile set': data,warnings=profile_set(args.name)
        elif name == 'profile restore': data,warnings=profile_restore()
        elif name == 'greeter status': data=theme.greeter_status()
        elif name == 'greeter sync': data,warnings=greeter_sync()
        elif name == 'greeter auto': data=greeter_auto(args.value)
        elif name == 'sync': data,warnings=sync()
        elif name == 'shortcuts list': data=shortcuts.read(args.file)
        elif name == 'shortcuts check': data=shortcuts.check(args.file)
        elif name == 'shortcuts backups': data=shortcuts.backups(args.file)
        elif name == 'backups list': data=backups.listing()
        elif name == 'lock status': data=lock_status()
        elif name == 'lock check': data={'result':lockscreen.validate()}
        elif name == 'lock update':
            data={'result':lockscreen.update()}
            theme.log_action('lock','OK','candidate updated')
        elif name == 'lock dim':
            data={'dim':lockscreen.set_dim(args.level/100)}
            theme.log_action('lock','OK',f'background dim {args.level}%')
        elif name == 'lock trial': data=lock_trial(args.confirm)
        elif name == 'lock activate': data=lock_activate(args.confirm)
        elif name == 'lock restore':
            data={'rescue':lockscreen.restore()}
            theme.log_action('lock','OK','previous visuals restored')
        elif name == 'shortcuts delete':
            data=shortcuts.delete(args.line,args.revision,args.file)
            theme.log_action('shortcut','OK','removed '+data['line'])
        elif name == 'shortcuts set':
            data=shortcuts.edit(args.line,args.revision,args.key,args.command,args.file,args.replace)
            theme.log_action('shortcut','OK',data['line'])
        else:
            data=shortcuts.restore(args.backup,args.file)
            theme.log_action('shortcut','OK','restored '+Path(args.backup).name)
        result={'ok':True,'action':name,'data':data,'warnings':warnings}
    except Exception as exc:
        result=failure(name,exc)
    if args.json:
        print(json.dumps(result,indent=2,ensure_ascii=False))
    elif result['ok']:
        print(json.dumps(result['data'],indent=2,ensure_ascii=False))
    else:
        print('rice: '+result['error']['message'],file=sys.stderr)
    return 0 if result['ok'] else 1
