#!/usr/bin/env python3
"""LW // MUSIC radio helper. Prints one JSON object; exit 1 on failure.

  radio.py search [--name TEXT] [--tag TAG] [--limit N]
      radio-browser.info, the directory cliamp's own radio browser uses. The server
      comes from the official list (DNS all.api.radio-browser.info, each address
      resolved back to its name for HTTPS), tried in random order.
      Working streams only, most voted first.
  radio.py saved
      Stations in ~/.config/cliamp/radios.toml ([[station]] name/url).
  radio.py add --name NAME --url URL
      Appends one [[station]] to radios.toml; the result must still parse.
"""
import argparse
import json
import os
import random
import socket
import sys
import tempfile
import tomllib
import urllib.parse
import urllib.request
from pathlib import Path

AGENT = 'rice-minimal-lw-music/1.0'
TIMEOUT = 6


def radios_path():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))/'cliamp'/'radios.toml'


def servers():
    names = set()
    for *_, address in socket.getaddrinfo('all.api.radio-browser.info', 443, proto=socket.IPPROTO_TCP):
        try:
            names.add(socket.gethostbyaddr(address[0])[0])
        except OSError:
            pass
    names = sorted(names)
    random.shuffle(names)
    return names or ['de1.api.radio-browser.info']


def search(name='', tag='', limit=100):
    query = {'hidebroken': 'true', 'order': 'votes', 'reverse': 'true', 'limit': str(limit)}
    if name:
        query['name'] = name
    if tag:
        query['tag'] = tag
        query['tagExact'] = 'false'
    errors = []
    for host in servers():
        url = 'https://' + host + '/json/stations/search?' + urllib.parse.urlencode(query)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': AGENT}), timeout=TIMEOUT) as reply:
                found = json.load(reply)
        except (OSError, ValueError) as exc:
            errors.append(host + ': ' + str(getattr(exc, 'reason', exc)))
            continue
        return {'server': host, 'stations': [{
            'name': (s.get('name') or '').strip() or s.get('url_resolved', ''),
            'country': s.get('country') or '', 'countrycode': s.get('countrycode') or '',
            'codec': s.get('codec') or '', 'bitrate': s.get('bitrate') or 0, 'votes': s.get('votes') or 0,
            'url': s.get('url_resolved') or s.get('url') or '', 'homepage': s.get('homepage') or '',
            'tags': s.get('tags') or ''} for s in found if s.get('url_resolved') or s.get('url')]}
    raise ConnectionError('radio-browser fora do alcance (' + '; '.join(errors) + ')')


def saved():
    path = radios_path()
    if not path.is_file():
        return {'path': str(path), 'stations': []}
    data = tomllib.loads(path.read_text())
    return {'path': str(path), 'stations': [{'name': s.get('name', ''), 'url': s.get('url', '')}
                                             for s in data.get('station', []) if isinstance(s, dict) and s.get('url')]}


def toml_string(value):
    if any(ord(c) < 32 for c in value):
        raise ValueError('caracteres de controle não são permitidos')
    return json.dumps(value, ensure_ascii=False)


def add(name, url):
    name, url = name.strip(), url.strip()
    if not name or not urllib.parse.urlparse(url).scheme in ('http', 'https'):
        raise ValueError('a estação precisa de nome e de uma URL http(s)')
    path = radios_path()
    current = path.read_text() if path.is_file() else ''
    if any(s['url'] == url for s in saved()['stations']):
        raise ValueError('já está salva: ' + name)
    text = current + ('' if current.endswith('\n') or not current else '\n') + \
        ('\n' if current else '') + '[[station]]\nname = ' + toml_string(name) + '\nurl = ' + toml_string(url) + '\n'
    tomllib.loads(text)  # never write a file cliamp could not read
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.radios-', suffix='.toml', dir=path.parent)
    with os.fdopen(fd, 'w') as stream:
        stream.write(text)
    os.replace(temp, path)
    return {'path': str(path), 'added': {'name': name, 'url': url}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='action', required=True)
    find = sub.add_parser('search')
    find.add_argument('--name', default='')
    find.add_argument('--tag', default='')
    find.add_argument('--limit', type=int, default=100)
    sub.add_parser('saved')
    new = sub.add_parser('add')
    new.add_argument('--name', required=True)
    new.add_argument('--url', required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == 'search':
            data = search(args.name, args.tag, max(1, min(500, args.limit)))
        elif args.action == 'saved':
            data = saved()
        else:
            data = add(args.name, args.url)
    except Exception as exc:  # one JSON line either way
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(dict(ok=True, **data), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
