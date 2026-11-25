"""Subcomandos do módulo MÚSICA: biblioteca, organização, rádio, busca online, download e cliamp."""
# cmd_music.py — os comandos declarados em modules/music/module.toml (contrato em docs/modulos.md).
# Só chama a lógica (library.py, organize.py, radio.py, ytdl.py e cliamp.py); o envelope JSON e os
# erros são do cli.py. O `download` é um fluxo: uma linha JSON por evento, sem envelope.
import argparse
from pathlib import Path
import cliamp
import library
import organize
import radio
import settings
import ytdl


def folder(args):
    """A pasta das músicas: --root ou, sem ele, music.dir."""
    return args.root or settings.get('music','dir')


def organized(args,action,*values):
    """Roda uma ação do organize.py; o {"ok": false} dele vira o erro do envelope."""
    root=folder(args)
    if not Path(root).is_dir():
        raise FileNotFoundError('pasta de música não existe: '+root)
    result=action(root,*values)
    if not result.pop('ok'):
        raise ValueError(result['error'])
    return result


def download(args):
    """lw download URL: os eventos do ytdl.py, linha a linha; devolve o código de saída."""
    return ytdl.main(['download','--root',folder(args),*(['--playlist'] if args.playlist else []),'--',args.url])


def register(actions,common):
    """Cria os parsers deste módulo; cada um diz que função o executa."""
    # --root troca a pasta das músicas (testes e uso avulso).
    rooted=argparse.ArgumentParser(add_help=False)
    rooted.add_argument('--root')
    def add(group,operation,run,*parents):
        """Um subcomando com saída JSON."""
        parser=group.add_parser(operation,parents=[common,*parents])
        parser.set_defaults(run=run)
        return parser
    def group(name):
        """Um comando que tem operações (library scan, library lookup…)."""
        return actions.add_parser(name).add_subparsers(dest='operation',required=True)
    index=group('library')
    add(index,'scan',lambda args: library.scan(folder(args)),rooted)
    add(index,'lookup',lambda args: library.lookup(folder(args),args.out),rooted).add_argument('--out',required=True)
    add(index,'apply',lambda args: library.apply(args.plan)).add_argument('--plan',required=True)
    tidy=group('organize')
    add(tidy,'plan',lambda args: organized(args,organize.plan),rooted)
    add(tidy,'apply',lambda args: organized(args,organize.apply),rooted)
    move=add(tidy,'move',lambda args: organized(args,organize.move_one,args.file,args.folder),rooted)
    move.add_argument('file')
    move.add_argument('folder')
    stations=group('radio')
    find=add(stations,'search',lambda args: radio.search(args.name,args.tag,max(1,min(500,args.limit))))
    find.add_argument('--name',default='')
    find.add_argument('--tag',default='')
    find.add_argument('--limit',type=int,default=100)
    add(stations,'saved',lambda args: radio.saved())
    new=add(stations,'add',lambda args: radio.add(args.name,args.url))
    new.add_argument('--name',required=True)
    new.add_argument('--url',required=True)
    online=group('online')
    add(online,'status',lambda args: {'ytdlp':ytdl.installed()})
    add(online,'search',lambda args: ytdl.search(args.query)).add_argument('query')
    get=actions.add_parser('download',parents=[rooted])
    get.add_argument('url')
    get.add_argument('--playlist',action='store_true')
    get.set_defaults(run=download,stream=True)
    add(group('cliamp'),'sync',lambda args: cliamp.sync())
