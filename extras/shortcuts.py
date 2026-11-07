"""Shared Super UI; reuse its parser, validation, atomic writes and unique backups."""
from importlib.machinery import SourceFileLoader
from importlib.util import spec_from_loader, module_from_spec
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import ui

ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'supers'))
loader = SourceFileLoader('rice_supers_backend',str(ROOT/'supers/Supers'))
backend = module_from_spec(spec_from_loader(loader.name,loader))
loader.exec_module(backend)


INTEGRATION = Path.home()/'.config/hypr/config/rice-integration.lua'
EXEC = re.compile(r'^hl\.dsp\.exec_cmd\((?:(\w+) \.\. )?("(?:[^"\\]|\\.)*")\)$')
MODIFIERS = {'SHIFT':1,'CONTROL':4,'ALT':8,'SUPER':64}


def display_key(expression):
    # Editing starts from this text, so the key keeps the exact spelling from the file.
    match = re.fullmatch(r'mainMod\s*\.\.\s*"([^"]*)"|"([^"]*)"', expression.strip())
    parts = [part.strip() for part in (('SUPER'+match[1]) if match[1] is not None else match[2]).split('+')]
    modifiers = sorted((part.upper() for part in parts[:-1]), key=lambda part: ('SUPER','CONTROL','ALT','SHIFT').index(part) if part in MODIFIERS else 9)
    return ' + '.join(modifiers+parts[-1:])


def describe(bind, section=''):
    match = EXEC.match(bind['action_clean'])
    return {'line':bind['line_idx'],'key':display_key(bind['key_clean']),'action':bind['action_clean'],'section':section,
            'command':json.loads(match[2]) if match else None,'editable':True}


def read(path=None):
    target = Path(path or backend.CONFIG_PATH)
    text = target.read_text()
    lines = text.splitlines(True)
    sections = {}
    current = ''
    for index, line in enumerate(lines):
        comment = re.match(r'\s*--\s*([^-\s].*?)\s*-*$', line)
        if comment:
            current = comment[1]
        sections[index] = current
    external = []
    if INTEGRATION.is_file() and not path:
        external = [{**describe(b),'editable':False} for b in backend.parse_binds(INTEGRATION.read_text().splitlines(True))]
    return {'path':str(target),'revision':hashlib.sha256(text.encode()).hexdigest(),
            'binds':[describe(b,sections[b['line_idx']]) for b in backend.parse_binds(lines)],'external':external}


def live_conflict(key):
    # Covers what the file parser cannot see: binds built in loops and other config files.
    mask = sum(MODIFIERS.get(part,0) for part in key[:-1])
    name = key[-1]
    code = {'0':19,**{str(d):9+d for d in range(1,10)}}.get(name)
    try:
        active = json.loads(subprocess.run(['hyprctl','-j','binds'],capture_output=True,text=True,timeout=5).stdout)
    except (OSError,ValueError,subprocess.SubprocessError):
        return False
    return any(b.get('modmask') == mask and (b.get('key','').upper() == name or (code and b.get('keycode') == code)) for b in active)


def plan_edit(bind, binds, key='', command=''):
    replacement = bind['raw_line']
    if key:
        new_key = backend.format_lua_key(re.sub(r'\b(super|mainmod)\s*\+\s*','',key,flags=re.IGNORECASE))
        normalized = backend.normalize_key(new_key)
        if normalized != backend.normalize_key(bind['key_clean']):
            if any(b['line_idx'] != bind['line_idx'] and backend.normalize_key(b['key_clean']) == normalized for b in binds) or live_conflict(normalized):
                raise ValueError('Shortcut already assigned')
        replacement = replacement.replace(bind['key_exact'],new_key,1)
    if command:
        # Anything else is a dispatcher or a variable that a plain command would silently replace.
        match = EXEC.match(bind['action_clean'])
        if not match:
            raise ValueError('This action is not a plain command; only its combination can change')
        prefix = match[1]+' .. ' if match[1] else ''
        replacement = replacement.replace(bind['action_clean'],'hl.dsp.exec_cmd('+prefix+backend.lua_string(command)+')',1)
    return replacement


def edit(line, revision, key='', command='', path=None):
    target = Path(path or backend.CONFIG_PATH)
    original = target.read_text()
    if hashlib.sha256(original.encode()).hexdigest() != revision:
        raise ValueError('The shortcut file changed; reload and try again')
    if not (key or command):
        raise ValueError('Nothing to change')
    binds = backend.parse_binds(original.splitlines(True))
    bind = next((b for b in binds if b['line_idx'] == line),None)
    if bind is None:
        raise ValueError('That line is not an editable shortcut')
    lines = original.splitlines(True)
    lines[line] = plan_edit(bind,binds,key,command)
    return {'backup':str(backend.safe_write(target,original,''.join(lines))),'line':lines[line].strip()}


def check(path=None):
    target = Path(path or backend.CONFIG_PATH)
    result = subprocess.run(['luac','-p',str(target)],capture_output=True,text=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or 'Invalid Lua')
    binds = backend.parse_binds(target.read_text().splitlines(True))
    keys = [backend.normalize_key(b['key_clean']) for b in binds]
    return {'count':len(keys),'duplicates':sorted({display_key(b['key_clean']) for b,key in zip(binds,keys) if keys.count(key) > 1})}


def backups(path=None):
    target = Path(path or backend.CONFIG_PATH)
    found = sorted(target.parent.glob(target.name+'.supers-*.bak'),key=lambda p:p.stat().st_mtime_ns,reverse=True)
    return {'backups':[{'path':str(p),'time_ns':p.stat().st_mtime_ns} for p in found]}


def restore(backup, path=None):
    target = Path(path or backend.CONFIG_PATH)
    source = Path(backup).expanduser().resolve()
    if source.parent != target.resolve().parent or not source.name.startswith(target.name+'.supers-') or source.suffix != '.bak':
        raise ValueError('Use a .supers-*.bak backup of the same file')
    return {'saved':str(backend.safe_write(target,target.read_text(),source.read_text()))}


def selector(screen, path=None):
    target = Path(path or backend.CONFIG_PATH)
    message = ''
    selected = 0
    while True:
        original = target.read_text()
        binds = backend.parse_binds(original.splitlines(True))
        entries = [b['key_clean'].replace('mainMod .. ','SUPER')+' | '+b['action_clean'] for b in binds]
        if not entries:
            ui.page(screen,'RICE // SUPER',['No editable static shortcuts. Dynamic expressions are preserved.'])
            return
        choice = ui.choose(screen,'RICE // SUPER SHORTCUTS',entries,message,selected)
        if choice is None:
            return
        selected = choice
        bind = binds[choice]
        try:
            key = ui.input_text(screen,'RICE // EDIT SHORTCUT','Combination (empty keeps current):')
            if key is None:
                continue
            command = ui.input_text(screen,'RICE // EDIT SHORTCUT','Command (empty keeps current):')
            if command is None or not (key or command):
                continue
            replacement = plan_edit(bind,binds,key,command)
            if ui.confirm(screen,'RICE // SAVE SHORTCUT',replacement.strip()):
                lines=original.splitlines(True)
                lines[bind['line_idx']]=replacement
                backup=backend.safe_write(target,original,''.join(lines))
                message='[ OK ] Saved; backup: '+backup.name
        except Exception as exc:
            message='[ FAIL ] '+str(exc)
