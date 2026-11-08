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

COMMANDS = {'status','gui','wallpaper','palette','profile','greeter','sync','shortcuts','lock','backups'}
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


def wallpaper_list():
    current=theme.current_wallpaper()
    resolved=current.resolve() if current else None
    images=[]
    for path in theme.images():
        thumb=thumb_path(path)
        images.append({'path':str(path),'name':path.name,'active':path.resolve()==resolved,
                       'thumb':str(thumb) if thumb.exists() else None})
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
            # Profile and lock changes also move `previous`, often to identical colors.
            'can_restore':bool(before and before.get('colors') != palette['colors'])}


def palette_regenerate():
    uninterruptible()
    with theme.locked():
        result=theme.regenerate(force=True)
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


def profile_get():
    return {'profile':theme.current_profile(),'previous':previous_profile(),'choices':['minimal','refined']}


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
    wallpaper=actions.add_parser('wallpaper').add_subparsers(dest='operation',required=True)
    wallpaper.add_parser('list',parents=[common])
    wallpaper.add_parser('thumbs')
    wallpaper.add_parser('apply',parents=[common]).add_argument('path')
    palette=actions.add_parser('palette').add_subparsers(dest='operation',required=True)
    for operation in ('show','regenerate','restore'):
        palette.add_parser(operation,parents=[common])
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
    keys.add_parser('restore',parents=[common]).add_argument('backup')
    saved=actions.add_parser('backups').add_subparsers(dest='operation',required=True)
    saved.add_parser('list',parents=[common])
    lock=actions.add_parser('lock').add_subparsers(dest='operation',required=True)
    for operation in ('status','check','update','restore'):
        lock.add_parser(operation,parents=[common])
    lock.add_parser('dim',parents=[common]).add_argument('level',type=int,choices=[35,55,75])
    for operation in ('trial','activate'):
        lock.add_parser(operation,parents=[common]).add_argument('--confirm',action='store_true')
    args=parser.parse_args(argv)
    if args.action == 'gui':
        return gui()
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
        elif name == 'palette regenerate': data,warnings=palette_regenerate()
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
        elif name == 'shortcuts set':
            data=shortcuts.edit(args.line,args.revision,args.key,args.command,args.file)
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
