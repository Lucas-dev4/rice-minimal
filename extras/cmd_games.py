"""Subcomandos do módulo JOGOS: a biblioteca (game), o hardware (compat) e os emuladores (emu)."""
# cmd_games.py — os comandos declarados em modules/games/module.toml (contrato em docs/modulos.md).
# Só chama a lógica (games.py, compat.py e emulators.py); o envelope JSON e os erros são do cli.py.
# O `emu pad-watch` é um fluxo: uma linha JSON por evento, sem envelope. O vigia da sessão e o da
# instalação (games.py watch e install-run) rodam direto: ninguém os chama à mão.
import json
import compat
import emulators
import games


def pad_watch(args):
    """lw emu pad-watch EVENTO: os eventos do controle, linha a linha; devolve o código de saída."""
    try:
        emulators.watch(args.event)
    except (KeyboardInterrupt,BrokenPipeError):
        pass
    except (OSError,ValueError) as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False),flush=True)
        return 1
    return 0


def register(actions,common):
    """Cria os parsers deste módulo; cada um diz que função o executa."""
    def group(name):
        """Um comando que tem operações (game scan, emu list…)."""
        return actions.add_parser(name).add_subparsers(dest='operation',required=True)
    def add(parsers,operation,run):
        """Uma operação com saída JSON."""
        parser=parsers.add_parser(operation,parents=[common])
        parser.set_defaults(run=run)
        return parser
    # ---- a biblioteca, as sessões, os instaladores e o IGDB (games.py)
    game=group('game')
    add(game,'scan',lambda args: games.scan())
    add(game,'list',lambda args: games.load())
    add(game,'running',lambda args: {'running':games.running()})
    add(game,'tools',lambda args: games.tools())
    add(game,'prefixes',lambda args: games.prefixes())
    new=add(game,'add',lambda args: games.add(args.exe,args.prefix,args.title,args.args))
    new.add_argument('--exe',required=True)
    new.add_argument('--prefix')
    new.add_argument('--title')
    new.add_argument('--args',default='')
    change=add(game,'set',lambda args: games.set_fields(args.id,args.pairs))
    change.add_argument('id')
    change.add_argument('pairs',nargs='+')
    add(game,'remove',lambda args: games.remove(args.id)).add_argument('id')
    add(game,'launch',lambda args: games.launch(args.id)).add_argument('id')
    add(game,'stop',lambda args: games.stop(args.id)).add_argument('id')
    add(game,'recover',lambda args: games.recover())
    column=add(game,'arrange',lambda args: games.arrange(args.status,args.ids))
    column.add_argument('status')
    column.add_argument('ids',nargs='*')
    add(game,'installers',lambda args: games.installers())
    setup=add(game,'install',lambda args: games.install(args.setup,args.name))
    setup.add_argument('setup')
    setup.add_argument('--name')
    chosen=add(game,'install-add',lambda args: games.install_add(args.setup,args.exe))
    chosen.add_argument('setup')
    chosen.add_argument('exe')
    add(game,'install-forget',lambda args: games.install_forget(args.setup)).add_argument('setup')
    ready=add(game,'add-ready',lambda args: games.add_ready(args.exe,args.name))
    ready.add_argument('exe')
    ready.add_argument('--name',required=True)
    meta=add(game,'meta',lambda args: games.meta(args.ids,args.all))
    meta.add_argument('ids',nargs='*')
    meta.add_argument('--all',action='store_true')
    add(game,'played-add',lambda args: games.played_add(args.igdb_id)).add_argument('igdb_id',type=int)
    hide=add(game,'rec-hide',lambda args: games.rec_hide(args.igdb_id,args.clear))
    hide.add_argument('igdb_id',type=int,nargs='?')
    hide.add_argument('--clear',action='store_true')
    # ---- os jogos x o hardware desta máquina (compat.py)
    machine=group('compat')
    add(machine,'scan',lambda args: compat.scan())
    add(machine,'check',lambda args: compat.check())
    # ---- os emuladores e o controle (emulators.py)
    emu=group('emu')
    add(emu,'list',lambda args: emulators.listing())
    add(emu,'pads',lambda args: emulators.pads())
    value=add(emu,'set',lambda args: emulators.set_value(args.emulator,args.key,args.value))
    for name in ('emulator','key','value'):
        value.add_argument(name)
    add(emu,'apply-pad',lambda args: emulators.apply_pad(args.emulator)).add_argument('emulator')
    live=emu.add_parser('pad-watch')
    live.add_argument('event')
    live.set_defaults(run=pad_watch,stream=True)
    save=add(emu,'pad-save',lambda args: emulators.pad_save(args.guid,args.name,args.pairs))
    save.add_argument('guid')
    save.add_argument('name')
    save.add_argument('pairs',nargs='+')
