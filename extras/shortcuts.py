"""Shared Super UI; reuse its parser, validation, atomic writes and unique backups."""
from importlib.machinery import SourceFileLoader
from importlib.util import spec_from_loader, module_from_spec
from pathlib import Path
import sys
import ui

ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'supers'))
loader = SourceFileLoader('rice_supers_backend',str(ROOT/'supers/Supers'))
backend = module_from_spec(spec_from_loader(loader.name,loader))
loader.exec_module(backend)


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
            replacement = bind['raw_line']
            if key:
                new_key=backend.format_lua_key(key)
                if any(b['line_idx'] != bind['line_idx'] and backend.normalize_key(b['key_clean']) == backend.normalize_key(new_key) for b in binds):
                    raise ValueError('Shortcut already assigned')
                replacement=replacement.replace(bind['key_exact'],new_key,1)
            if command:
                replacement=replacement.replace(bind['action_exact'],' hl.dsp.exec_cmd('+backend.lua_string(command)+')',1)
            if ui.confirm(screen,'RICE // SAVE SHORTCUT',replacement.strip()):
                lines=original.splitlines(True)
                lines[bind['line_idx']]=replacement
                backup=backend.safe_write(target,original,''.join(lines))
                message='[ OK ] Saved; backup: '+backup.name
        except Exception as exc:
            message='[ FAIL ] '+str(exc)
