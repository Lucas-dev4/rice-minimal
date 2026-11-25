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
# Comando → módulo em que ele abre a janela (lw music).
OPENERS = modules.openers()
# Do núcleo: gui e modules.
COMMANDS = {'gui','modules',*OPENERS,*HANDLERS}


def modules_list():
    """Todos os módulos na ordem da barra lateral, com telas, gancho e config já resolvida (lw modules list)."""
    found=modules.load()[0]
    on=settings.switches()
    return [{'id':m['id'],'name':m['name'],'folder':m['gui']['folder'],'hook':m['gui'].get('hook',''),
             'screens':m['gui'].get('screens',[]),'config':settings.section(m['id']),
             'enabled':on[m['id']],'required':m.get('required',False)}
            for m in found.values() if m.get('gui',{}).get('folder')]


def modules_text(data):
    """A lista de módulos para o terminal."""
    return '\n'.join(f"{'ligado   ' if m['enabled'] else 'desligado'}  {modules.plain(m['name']):10}  {m['name']}"
                     +(' (obrigatório)' if m['required'] else '') for m in data)


def switch_text(data):
    """O resultado de ligar ou desligar, para o terminal."""
    state='ligado' if data['enabled'] else 'desligado'
    return f"módulo {data['name']} {state} · vale na próxima abertura do LW" if data['changed'] else f"módulo {data['name']} já está {state}"


def ipc(*args):
    # Every call to the running window has a time limit: the shortcut must never hang.
    """Chama uma função IPC da janela aberta (com 3 s de limite)."""
    return subprocess.run(['qs','ipc','-p',str(theme.ROOT/'gui'),'call','lw',*args],capture_output=True,text=True,timeout=3)


def warn(text):
    # Over a fullscreen LW the notification may not show, so the window says it too.
    """Avisa quem usou um atalho: notificação do Noctalia e, com o LW aberto, o rodapé dele."""
    for call in (lambda: subprocess.run(['noctalia','msg','notification-show','LW',text],capture_output=True,text=True,timeout=3),
                 lambda: ipc('notice',text)):
        try:
            call()
        except (OSError,subprocess.SubprocessError):
            pass
    print('lw: '+text,file=sys.stderr)
    return 1


def gui(section='system'):
    # LW: one window (gui/shell.qml) with SISTEMA, MÚSICA and JOGOS. Super+BackSpace,
    # Super+M and Super+G call this with their section: closed → opens there; hidden
    # (Ctrl+J) → comes back there; open on another section → switches; same → closes.
    """Abre/alterna a janela do LW numa seção (system, music, games). Nunca trava o atalho."""
    if not settings.switches().get(section,True):
        return warn(modules.off_text(section))
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
    try:
        probe=ipc('section')
        shown=probe.stdout.strip() if probe.returncode == 0 else ''
    except subprocess.TimeoutExpired:
        kill_instances(music_instances(root))
        shown=''
    if shown:
        found=None
        try:
            if ipc('hidden').stdout.strip() == 'yes':
                ipc('reveal')
                found=ipc('go',section)
            elif shown == section:
                ipc('close')
                for _ in range(30):
                    if not music_instances(root):
                        return 0
                    time.sleep(0.1)
                kill_instances(music_instances(root))
            else:
                found=ipc('go',section)
        except subprocess.TimeoutExpired:
            kill_instances(music_instances(root))
            return 0
        # A module enabled after the window opened: it is not in there yet.
        if found and found.stdout.strip() == 'unknown':
            return warn(f"módulo {modules.load()[0][section]['name']} ligado · feche e abra o LW")
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
    for name in OPENERS:
        actions.add_parser(name)
    switch=actions.add_parser('modules').add_subparsers(dest='operation',required=True)
    switch.add_parser('list',parents=[common]).set_defaults(run=lambda args: modules_list(),show=modules_text)
    for name,on in (('enable',True),('disable',False)):
        option=switch.add_parser(name,parents=[common])
        option.add_argument('name')
        option.set_defaults(run=lambda args,on=on: settings.set_module(args.name,on),show=switch_text)
    # Só o handler dono do comando pedido é importado; o de um módulo desligado, nem isso.
    if argv and argv[0] in HANDLERS:
        owner=modules.owners()[argv[0]]
        if not settings.switches()[owner]:
            text=modules.off_text(owner)
            if '--json' in argv:
                print(json.dumps(failure(argv[0],ValueError(text)),indent=2,ensure_ascii=False))
            else:
                print('lw: '+text,file=sys.stderr)
            return 1
        importlib.import_module(HANDLERS[argv[0]]).register(actions,common)
    args=parser.parse_args(argv)
    if args.action == 'gui':
        return gui()
    if args.action in OPENERS:
        return gui(OPENERS[args.action])
    if getattr(args,'stream',False):
        return args.run(args) or 0
    name=args.action+(' '+args.operation if hasattr(args,'operation') else '')
    try:
        warnings=[]
        data=args.run(args)
        if isinstance(data,tuple): data,warnings=data
        result={'ok':True,'action':name,'data':data,'warnings':warnings}
    except Exception as exc:
        result=failure(name,exc)
    if args.json:
        print(json.dumps(result,indent=2,ensure_ascii=False))
    elif result['ok']:
        print(args.show(result['data']) if hasattr(args,'show') else json.dumps(result['data'],indent=2,ensure_ascii=False))
    else:
        print('rice: '+result['error']['message'],file=sys.stderr)
    return 0 if result['ok'] else 1
