#!/usr/bin/env python3
"""RICE // CONTROL — one modular, event-driven curses session."""
import argparse
import curses
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from theme import theme, profiles
from wallpapers.wallpaper_tui import selector
import backups
import cli
import doctor
import lockscreen
import shortcuts
import ui


def appearance(screen):
    message='Active: '+theme.current_profile()
    while True:
        choice=ui.choose(screen,'RICE // APPEARANCE',['Minimal','Refined','Current Profile','Restore previous profile','Toggle menu animations'],message)
        if choice is None: return
        if choice in (0,1): message='[ OK ] Active: '+profiles.switch(('minimal','refined')[choice])
        elif choice == 2: message='Current Profile: '+theme.current_profile()
        elif choice == 3: message='[ OK ] Restored: '+profiles.previous()
        else: message='Animations: '+str(ui.toggle_animations())


def palette_menu(screen):
    message=''
    while True:
        choice=ui.choose(screen,'RICE // COLOR PALETTE',['View current palette','Update adaptive colors','Restore previous palette'],message)
        if choice is None: return
        if choice == 0:
            p=theme.read_palette()
            ui.page(screen,'RICE // PALETTE',[p.get('generator','unknown'),p.get('wallpaper','')]+[f'{k:20} {v}' for k,v in p['colors'].items()])
        elif choice == 1:
            with theme.locked(): message='[ OK ] '+theme.regenerate(force=True)
            theme.sync_greeter()
        elif choice == 2:
            message='[ OK ] Restored: '+theme.restore_previous()
            theme.sync_greeter()


def restore_menu(screen):
    message=''
    while True:
        choice=ui.choose(screen,'RICE // RESTORE / BACKUPS',['List backups','Restore previous profile','Restore previous palette','Recovery instructions'],message)
        if choice is None: return
        if choice == 0:
            ui.page(screen,'RICE // BACKUPS',[f"{b['kind']:9}{b['name']}" for b in backups.listing()['backups']] or ['No backups yet'])
        elif choice == 1:
            if ui.confirm(screen,'RICE // CONFIRM','Restore previous appearance profile?'): message=profiles.previous()
        elif choice == 2:
            if ui.confirm(screen,'RICE // CONFIRM','Restore previous adaptive palette?'):
                message=theme.restore_previous()
                theme.sync_greeter()
        else:
            full=backups.listing()['recovery']['full']
            ui.page(screen,'RICE // RECOVERY',['Full restore is run from a normal terminal:',full or 'No full backup found.','It saves a rescue snapshot before restoring.','No reboot, suspend or logout is performed.'])


def lock_menu(screen):
    message='Existing secure locker: Noctalia; live test requires confirmation.'
    while True:
        choice=ui.choose(screen,'RICE // LOCK SCREEN',['View settings','Update colors / candidate','Background dim level','Check configuration','Restore previous lock visuals','Trial lock (restores after unlock)','Activate reviewed RICE // LOCKED'],message)
        if choice is None: return
        if choice == 0:
            ui.page(screen,'RICE // LOCK SETTINGS',[
                'Locker: Noctalia (native Wayland session lock)',
                'Visuals: '+('active' if (theme.STATE/'lock-enabled').exists() else 'candidate only'),
                'Dim: '+str(lockscreen.dim()),'PAM / password / authentication: unchanged',
                'Candidate: '+str(theme.STATE/'current/lockscreen.toml'),
                'Shortcut: existing Super+L; idle/suspend integration preserved'])
        elif choice == 1:
            message=lockscreen.update()
        elif choice == 2:
            level=ui.choose(screen,'RICE // BACKGROUND DIM',['Light (35%)','Balanced (55%)','Dark (75%)'])
            if level is not None:
                lockscreen.set_dim((.35,.55,.75)[level])
                message='[ OK ] Background dim updated'
        elif choice == 3: message=lockscreen.validate()
        elif choice == 4:
            if ui.confirm(screen,'RICE // RESTORE LOCK','Restore prior lock visuals, preserving a rescue backup?'): message=lockscreen.restore()
        elif choice == 5:
            if ui.confirm(screen,'RICE // CONFIRM REAL LOCK','Locks this session. Unlock with your normal password. Previous visuals restore automatically after unlock. Recovery: see RICE-FINAL.md.'):
                message=lockscreen.run_trial()
        elif choice == 6:
            if not lockscreen.tested():
                message='[ WARN ] Run the confirmed lock trial first; candidate remains staged.'
            elif ui.confirm(screen,'RICE // ACTIVATE LOCK','Activate the layout you reviewed in the lock trial?'):
                message='[ OK ] Activated; backup: '+str(lockscreen.activate())


def menu(screen):
    ui.setup(screen)
    message='Profile: '+theme.current_profile()
    actions=[selector,shortcuts.selector,appearance,palette_menu,
             lambda s:ui.page(s,'RICE // SYSTEM DOCTOR',doctor.lines(doctor.inspect())),restore_menu,lock_menu]
    entries=['Wallpapers','Super Shortcuts','Appearance / Profiles','Color Palette','System Doctor','Restore / Backups','Lock Screen Settings']
    while True:
        choice=ui.choose(screen,'RICE // CONTROL',entries,message)
        if choice is None: return
        try:
            actions[choice](screen)
            message='[ OK ] RICE // '+theme.current_profile()
        except Exception as exc:
            message='[ FAIL ] '+str(exc)


def main():
    if sys.argv[1:2] and sys.argv[1] in cli.COMMANDS: return cli.main(sys.argv[1:])
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',nargs='?',choices=['doctor','lock-check','lock-trial','lock-restore'])
    parser.add_argument('--json',action='store_true')
    parser.add_argument('--confirm',action='store_true',help='Explicit consent for a real lock trial')
    args=parser.parse_args()
    if args.action == 'doctor':
        import json
        result=doctor.inspect()
        print(json.dumps(result,indent=2,ensure_ascii=False) if args.json else '\n'.join(doctor.lines(result)))
        return int(any(r['status']=='FAIL' for r in result))
    if args.action == 'lock-check': print(lockscreen.validate())
    elif args.action == 'lock-restore': print(lockscreen.restore())
    elif args.action == 'lock-trial':
        if not args.confirm: parser.error('Real locking requires --confirm; read RICE-FINAL.md recovery instructions first')
        print(lockscreen.run_trial())
    else: curses.wrapper(menu)
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print('rice: '+str(exc),file=sys.stderr)
        sys.exit(1)
