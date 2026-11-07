"""RICE // lock visuals for the existing secure Noctalia locker. No auth changes."""
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
import tomllib
from theme import theme

CONFIG = Path.home()/'.config/noctalia'
SETTINGS = Path.home()/'.local/state/noctalia/settings.toml'
VISUAL_KEYS = {'wallpaper','transition','transition_duration','blurred_desktop','blur_intensity','tint_intensity'}


def atomic(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.rice-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            stream.write(text); stream.flush(); os.fsync(stream.fileno())
        os.chmod(tmp,0o600)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def dim():
    try:
        return max(.35,min(.85,float((theme.STATE/'lock-dim').read_text())))
    except (OSError,ValueError):
        return .55


def displays():
    try:
        data=json.loads((theme.STATE/'lock-displays.json').read_text())
        if isinstance(data,list) and data: return data
    except (OSError,ValueError):
        pass
    return [{'name':'HDMI-A-1','width':1920,'height':1080,'scale':1}]


def layout(monitors):
    return sorted((m['name'],m['width'],m['height'],m.get('scale',1)) for m in monitors)


def live_displays():
    return json.loads(theme.command(['hyprctl','-j','monitors']))


def capture_displays():
    # Rewriting an unchanged layout would needlessly invalidate the last trial.
    data=live_displays()
    if layout(data) != layout(displays()) or not (theme.STATE/'lock-displays.json').exists():
        atomic(theme.STATE/'lock-displays.json',json.dumps(data))


def tested():
    # A trial only vouches for the monitor layout it was shown on.
    try:
        stamp=(theme.STATE/'lock-tested').stat().st_mtime_ns
    except OSError:
        return False
    try:
        return stamp >= (theme.STATE/'lock-displays.json').stat().st_mtime_ns
    except OSError:
        return True


def status():
    candidate=tomllib.loads((theme.STATE/'current/lockscreen.toml').read_text())['lockscreen']
    try:
        current=layout(live_displays()) == layout(displays())
    except Exception:
        current=None
    try:
        session=json.loads(theme.command(['noctalia','msg','status']))['locked']
    except Exception:
        session=None
    return {'enabled':(theme.STATE/'lock-enabled').exists(),'tested':tested(),'dim':dim(),
            'effective_dim':candidate['tint_intensity'],'wallpaper':candidate['wallpaper'],
            'title':'RICE // LOCKED' if theme.current_profile() == 'refined' else 'RICE //',
            'displays':[m['name'] for m in displays()],'layout_current':current,'session_locked':session}


def require_palette():
    # read_palette() silently falls back, which must not be published as a real generation.
    if not (theme.STATE/'current/palette.json').is_file():
        raise RuntimeError('No published palette to build the lock candidate from')


def update():
    require_palette()
    with theme.locked():
        capture_displays()
        theme.activate(theme.read_palette())
    return validate()


def set_dim(level):
    require_palette()
    with theme.locked():
        atomic(theme.STATE/'lock-dim',str(level))
        theme.activate(theme.read_palette())
    return dim()


def activate():
    if not tested():
        raise RuntimeError('Run a lock trial on this monitor layout first')
    return install()


def run_trial():
    message=trial()
    atomic(theme.STATE/'lock-tested','unlocked successfully\n')
    return message


def effective_dim(palette):
    """Raise the chosen minimum only as needed for readable center text."""
    amount=dim()
    try:
        from PIL import Image, ImageOps
        c=palette['colors']
        with Image.open(palette['wallpaper']) as image:
            sample=ImageOps.fit(image.convert('RGB'),(96,54)).crop((24,12,72,42))
            pixels=[theme.hexcolor(v/255 for v in pixel) for pixel in sample.get_flattened_data()]
        while amount < .90:
            ratios=sorted(theme.ratio(c['foreground'],theme.mix(pixel,c['background'],amount)) for pixel in pixels)
            if ratios[len(ratios)//20] >= 4.5: break
            amount=round(amount+.05,2)
        return min(.90,amount)
    except (OSError,KeyError,ValueError):
        return amount


def render(palette,profile):
    refined=profile == 'refined'
    wallpaper=palette.get('wallpaper','')
    lines=['# RICE // LOCKED — generated visual settings only.',
           '[lockscreen]', 'wallpaper = '+json.dumps(wallpaper,ensure_ascii=False),
           'blurred_desktop = false','blur_intensity = 0.0',f'tint_intensity = {effective_dim(palette)}',
           'transition = ["fade"]',f'transition_duration = {150.0 if refined else 100.0}',
           '[lockscreen_widgets]','enabled = true','schema_version = 2']
    order=[]; widgets=[]
    for i,m in enumerate(displays()):
        w=m['width']/m.get('scale',1); h=m['height']/m.get('scale',1)
        output=m['name']
        rows=[('title','label',.33,360,40,{'title':'RICE // LOCKED' if refined else 'RICE //','color':'on_surface','background':False,'shadow':False}),
              ('time','clock',.43,480 if refined else 320,110 if refined else 70,{'format':'{:%H:%M}','color':'on_surface','background':False,'shadow':False,'show_seconds':False}),
              ('date','clock',.52,500,36,{'format':'{:%A, %d %B %Y}','color':'on_surface','background':False,'shadow':False,'show_seconds':False}),
              ('input','login_box',.65,400,100,{'layout':'compact','background_opacity':.94,'background_radius':2.0,'input_radius':2.0,'show_weather':False,'show_media':False,'show_session_buttons':False,'show_password_reveal':False,'show_caps_lock':True,'show_keyboard_layout':True,'show_login_button':True,'show_unlock_hint':True,'center_password_text':True})]
        for name,kind,y,bw,bh,settings in rows:
            widget_id=f'rice-{name}-{i}' if kind != 'login_box' else 'lockscreen-login-box@'+output
            order.append(widget_id)
            widgets += ['[lockscreen_widgets.widget.'+json.dumps(widget_id)+']',
                        'type = '+json.dumps(kind),'enabled = true','output = '+json.dumps(output),
                        f'cx = {w/2}',f'cy = {h*y}',f'box_width = {min(bw,w*.85)}',f'box_height = {bh}',
                        f'placement_width = {w}',f'placement_height = {h}','rotation = 0.0',
                        '[lockscreen_widgets.widget.'+json.dumps(widget_id)+'.settings]']
            settings=dict(settings,font_family='DejaVu Sans Mono')
            for key,value in settings.items():
                widgets.append(key+' = '+json.dumps(value,ensure_ascii=False))
    lines += ['widget_order = '+json.dumps(order),'[lockscreen_widgets.grid]','visible = false','cell_size = 16','major_interval = 4']
    return '\n'.join(lines+widgets)+'\n'


def strip_visual_overrides(text):
    lines=[]; section=''
    for line in text.splitlines(True):
        if line.lstrip().startswith('['):
            section=line.strip().strip('[]')
        if section == 'lockscreen_widgets' or section.startswith('lockscreen_widgets.'):
            continue
        key=line.split('=',1)[0].strip()
        if section == 'lockscreen' and key in VISUAL_KEYS:
            continue
        lines.append(line)
    return ''.join(lines)


def visual_snapshot(text):
    """Select lock visuals only; never restore unrelated shell/auth settings."""
    parsed=tomllib.loads(text)
    lines=[]
    visual={key:value for key,value in parsed.get('lockscreen',{}).items() if key in VISUAL_KEYS}
    if visual:
        lines.append('[lockscreen]')
        lines += [key+' = '+json.dumps(value,ensure_ascii=False) for key,value in visual.items()]
    # Widget tables contain visual layout and native login-box presentation only.
    section=''
    for line in text.splitlines(True):
        if line.lstrip().startswith('['): section=line.strip().strip('[]')
        if section == 'lockscreen_widgets' or section.startswith('lockscreen_widgets.'):
            lines.append(line.rstrip('\n'))
    return '\n'.join(lines)+'\n'


def validate():
    path=theme.STATE/'current/lockscreen.toml'
    data=tomllib.loads(path.read_text())
    if set(data['lockscreen']) != VISUAL_KEYS:
        raise ValueError('Unexpected lockscreen settings; refusing nonvisual changes')
    if data['lockscreen']['blur_intensity'] != 0:
        raise ValueError('Blur must remain disabled')
    wallpaper=data['lockscreen']['wallpaper']
    if not wallpaper or not Path(wallpaper).is_file():
        raise ValueError('Wallpaper unavailable')
    theme.command(['noctalia','config','validate',path])
    return '[ OK ] Native Noctalia config valid; authentication untouched'


def install():
    with theme.locked():
        return _install()


def _install():
    validate()
    backup=theme.ROOT/'backups'/('lock-visual-'+str(time.time_ns()))
    backup.mkdir(parents=True)
    shutil.copy2(SETTINGS,backup/'settings.toml')
    overlay=CONFIG/'rice-lock.toml'
    if overlay.exists(): shutil.copy2(overlay,backup/'rice-lock.toml')
    previous=SETTINGS.read_text()
    candidate=strip_visual_overrides(previous)
    tomllib.loads(candidate)
    # Validate the complete merged visual candidate before writing anything live.
    with tempfile.TemporaryDirectory(prefix='rice-lock-validate-') as folder:
        target=Path(folder)
        for source in CONFIG.glob('*.toml'):
            if source.name != 'rice-lock.toml': shutil.copy2(source,target/source.name)
        (target/'rice-lock.toml').write_text((theme.STATE/'current/lockscreen.toml').read_text())
        (target/'zz-state.toml').write_text(candidate)
        theme.command(['noctalia','config','validate',target])
    try:
        atomic(SETTINGS,candidate)
        atomic(overlay,(theme.STATE/'current/lockscreen.toml').read_text())
        theme.command(['noctalia','msg','config-reload'])
        atomic(theme.STATE/'lock-enabled','enabled\n')
        atomic(theme.STATE/'lock-backup',str(backup)+'\n')
        theme.reload_components()
    except Exception:
        _restore(backup)
        raise
    return backup


def restore(backup=None):
    with theme.locked():
        return _restore(backup)


def _restore(backup=None):
    backup=Path(backup or (theme.STATE/'lock-backup').read_text().strip())
    # Save the current visuals/settings before restoring the earlier snapshot.
    rescue=backup/('before-restore-'+str(time.time_ns()))
    rescue.mkdir(parents=True)
    shutil.copy2(SETTINGS,rescue/'settings.toml')
    overlay=CONFIG/'rice-lock.toml'
    if overlay.exists(): shutil.copy2(overlay,rescue/'rice-lock.toml')
    base=strip_visual_overrides(SETTINGS.read_text()).rstrip()+'\n'
    saved=visual_snapshot((backup/'settings.toml').read_text())
    if '[lockscreen]' in base and '[lockscreen]' in saved:
        visual,separator,widgets=saved.partition('[lockscreen_widgets]')
        fields=visual.removeprefix('[lockscreen]\n')
        base=base.replace('[lockscreen]','[lockscreen]\n'+fields,1)
        saved=(separator+widgets) if separator else ''
    restored=base+'\n'+saved
    tomllib.loads(restored)
    atomic(SETTINGS,restored)
    if (backup/'rice-lock.toml').exists():
        atomic(overlay,(backup/'rice-lock.toml').read_text())
    else:
        overlay.unlink(missing_ok=True)
        (theme.STATE/'lock-enabled').unlink(missing_ok=True)
    theme.command(['noctalia','msg','config-reload'])
    theme.reload_components()
    return str(rescue)


def trial():
    """Called only after explicit confirmation; always restore visuals after unlock."""
    if json.loads(theme.command(['noctalia','msg','status']))['locked']:
        raise RuntimeError('Session already locked; refusing to start a trial')
    backup=install()
    try:
        theme.command(['noctalia','msg','session','lock'])
        deadline=time.monotonic()+15
        while not json.loads(theme.command(['noctalia','msg','status']))['locked']:
            if time.monotonic()>deadline: raise RuntimeError('Lock was not confirmed')
            time.sleep(.2)
        while json.loads(theme.command(['noctalia','msg','status']))['locked']:
            time.sleep(.5)
        return '[ OK ] Trial ended; previous lock visuals restored'
    finally:
        restore(backup)
