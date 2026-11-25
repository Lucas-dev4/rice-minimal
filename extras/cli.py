"""Scriptable commands shared by the GUI: one JSON envelope, no curses."""
# cli.py — os subcomandos do "lw" (lw status, lw wallpaper apply, lw gui...).
# É a ponte entre a janela do LW (QML) e o Python: a GUI chama "lw <comando> --json" e recebe
# sempre o mesmo envelope {"ok", "action", "data", "warnings"} ou {"ok": false, "error"}.
import argparse
import importlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from theme import theme
import modules
import settings

# Comando → handler (extras/cmd_<id>.py) do módulo dono, pelos manifestos.
HANDLERS = modules.handlers()
# Do núcleo: gui e modules. MÚSICA e JOGOS ainda não têm handler (docs/modulos.md, sessões 4 e 5).
COMMANDS = {'gui','modules','music','games','compat','emu','cliamp',*HANDLERS}


def modules_list():
    """Os módulos na ordem da barra lateral, com telas, gancho e config já resolvida (lw modules list)."""
    found=modules.load()[0]
    return [{'id':m['id'],'name':m['name'],'folder':m['gui']['folder'],'hook':m['gui'].get('hook',''),
             'screens':m['gui'].get('screens',[]),'config':settings.section(m['id'])}
            for m in found.values() if m.get('gui',{}).get('folder')]


def gui(section='system'):
    # LW: one window (gui/shell.qml) with SISTEMA, MÚSICA and JOGOS. Super+BackSpace,
    # Super+M and Super+G call this with their section: closed → opens there; hidden
    # (Ctrl+J) → comes back there; open on another section → switches; same → closes.
    """Abre/alterna a janela do LW numa seção (system, music, games). Nunca trava o atalho."""
    (theme.STATE/'actions.jsonl').touch()
    path=str(theme.ROOT/'gui')
    # `qs list` names the instance by its root file.
    root=str(theme.ROOT/'gui'/'shell.qml')
    import fcntl
    lock=open(Path(os.environ.get('XDG_RUNTIME_DIR','/tmp'))/'lw-window.lock','w')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        return 0
    # Every call to the running window has a time limit: the shortcut must never hang.
    def ipc(*args):
        """Chama uma função IPC da janela aberta (com 3 s de limite)."""
        return subprocess.run(['qs','ipc','-p',path,'call','lw',*args],capture_output=True,text=True,timeout=3)
    try:
        probe=ipc('section')
        shown=probe.stdout.strip() if probe.returncode == 0 else ''
    except subprocess.TimeoutExpired:
        kill_instances(music_instances(root))
        shown=''
    if shown:
        try:
            if ipc('hidden').stdout.strip() == 'yes':
                ipc('reveal')
                ipc('go',section)
            elif shown == section:
                ipc('close')
                for _ in range(30):
                    if not music_instances(root):
                        return 0
                    time.sleep(0.1)
                kill_instances(music_instances(root))
            else:
                ipc('go',section)
        except subprocess.TimeoutExpired:
            kill_instances(music_instances(root))
        return 0
    os.environ['LW_START_GROUP']=section
    os.environ['LW_MODULES']=json.dumps(modules_list(),ensure_ascii=False)
    # GPU rendering: the visualizer and the cover grid draw a lot.
    os.environ.pop('QT_QUICK_BACKEND',None)
    # cliamp and other user tools live in ~/.local/bin, not on the PATH Hyprland passes.
    local=str(Path.home()/'.local'/'bin')
    if local not in os.environ.get('PATH','').split(':'):
        os.environ['PATH']=local+':'+os.environ.get('PATH','')
    # The window animates in every profile; RICE_GUI_MOTION=0 turns it off.
    os.environ.setdefault('RICE_GUI_MOTION','1')
    os.execvp('qs',['qs','-n','-d','-p',path])


def music_instances(path):
    # PIDs of the Quickshell instances running this config (`qs list --all`).
    """PIDs das janelas do LW rodando (pela lista do Quickshell)."""
    out=subprocess.run(['qs','list','--all'],capture_output=True,text=True,timeout=3).stdout
    pids,pid=[],None
    for line in out.splitlines():
        line=line.strip()
        if line.startswith('Process ID:'):
            pid=int(line.split(':',1)[1])
        elif line.startswith('Config path:') and pid and line.split(':',1)[1].strip()==path:
            pids.append(pid)
    return pids


def kill_instances(pids):
    # A frozen instance never answers IPC: kill it and its helpers (events, pactl, cava).
    """Mata uma janela travada e os processos filhos dela."""
    for pid in pids:
        subprocess.run(['pkill','-KILL','-P',str(pid)],capture_output=True)
        try:
            os.kill(pid,signal.SIGKILL)
        except ProcessLookupError:
            pass


def music():
    """lw music = abrir o LW em MÚSICA."""
    return gui('music')


def games():
    """lw games = abrir o LW em JOGOS."""
    return gui('games')


def failure(action,exc):
    """Monta o JSON de erro (código not_found/invalid/busy/failed + mensagem)."""
    return {'ok':False,'action':action,'error':{
        'code':'not_found' if isinstance(exc,FileNotFoundError) else 'invalid' if isinstance(exc,ValueError)
               else 'busy' if isinstance(exc,TimeoutError) else 'failed',
        'message':str(exc),
        'stderr':(getattr(exc,'stderr',None) or '').strip()}}


def main(argv):
    """Lê os argumentos, executa o subcomando e imprime o resultado (JSON com --json)."""
    parser=argparse.ArgumentParser(prog='lw')
    common=argparse.ArgumentParser(add_help=False)
    common.add_argument('--json',action='store_true')
    actions=parser.add_subparsers(dest='action',required=True)
    actions.add_parser('gui')
    actions.add_parser('music')
    actions.add_parser('games')
    actions.add_parser('modules').add_subparsers(dest='operation',required=True).add_parser('list',parents=[common])
    # Jogos x hardware desta máquina (extras/compat.py).
    compat_cmd=actions.add_parser('compat').add_subparsers(dest='operation',required=True)
    for operation in ('scan','check'):
        compat_cmd.add_parser(operation,parents=[common])
    # Pasta das músicas no cliamp (extras/cliamp.py).
    actions.add_parser('cliamp').add_subparsers(dest='operation',required=True).add_parser('sync',parents=[common])
    # Emuladores e controle (extras/emulators.py).
    emu=actions.add_parser('emu').add_subparsers(dest='operation',required=True)
    emu.add_parser('list',parents=[common])
    emu.add_parser('pads',parents=[common])
    change_emu=emu.add_parser('set',parents=[common])
    for name in ('emulator','key','value'):
        change_emu.add_argument(name)
    emu.add_parser('apply-pad',parents=[common]).add_argument('emulator')
    emu.add_parser('pad-watch').add_argument('event')
    save_pad=emu.add_parser('pad-save',parents=[common])
    save_pad.add_argument('guid')
    save_pad.add_argument('name')
    save_pad.add_argument('pairs',nargs='+')
    # Só o handler dono do comando pedido é importado.
    if argv and argv[0] in HANDLERS:
        importlib.import_module(HANDLERS[argv[0]]).register(actions,common)
    args=parser.parse_args(argv)
    if args.action == 'emu' and args.operation == 'pad-watch':
        import emulators
        try:
            emulators.watch(args.event)
        except (KeyboardInterrupt,BrokenPipeError):
            pass
        except (OSError,ValueError) as exc:
            print(json.dumps({'error':str(exc)},ensure_ascii=False),flush=True)
            return 1
        return 0
    if args.action == 'gui':
        return gui()
    if args.action == 'music':
        return music()
    if args.action == 'games':
        return games()
    if getattr(args,'stream',False):
        return args.run(args) or 0
    name=args.action+(' '+args.operation if hasattr(args,'operation') else '')
    try:
        warnings=[]
        if hasattr(args,'run'):
            data=args.run(args)
            if isinstance(data,tuple): data,warnings=data
        elif name == 'modules list': data=modules_list()
        elif name == 'compat scan':
            import compat
            data=compat.scan()
        elif name == 'compat check':
            import compat
            data=compat.check()
        elif name == 'cliamp sync':
            import cliamp
            data,warnings=cliamp.sync()
        else:
            import emulators
            if name == 'emu list': data=emulators.listing()
            elif name == 'emu pads': data=emulators.pads()
            elif name == 'emu set': data=emulators.set_value(args.emulator,args.key,args.value)
            elif name == 'emu apply-pad': data=emulators.apply_pad(args.emulator)
            else: data=emulators.pad_save(args.guid,args.name,args.pairs)
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
