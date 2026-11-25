# Testes da janela de verdade: abre o gui/ no Quickshell sem tela (offscreen), num HOME e num
# XDG_RUNTIME_DIR temporários, com um cliamp falso. Não encosta na sessão, no som nem no cliamp real.
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# O cliamp falso: o daemon demora `delay` s para responder; cada comando fica em calls.txt.
CLIAMP = '''#!{python}
import json, os, signal, sys, time
from pathlib import Path
here = Path({folder!r})
up = here/'up'
args = sys.argv[1:]
def number(name): return float((here/name).read_text()) if (here/name).exists() else 0
if args[:1] == ['--daemon']:
    (here/'daemon.tmp').write_text(str(os.getpid()))
    (here/'daemon.tmp').rename(here/'daemon.pid')
    time.sleep(number('delay'))
    up.write_text('')
    config = Path(os.environ['XDG_CONFIG_HOME'])/'cliamp'
    config.mkdir(parents=True, exist_ok=True)
    (config/'cliamp.sock.pid').write_text(str(os.getpid()))
    time.sleep(60)
elif not up.exists():
    sys.exit(1)
elif args[:2] == ['remote', 'events']:
    print(json.dumps({{'event': 'runtime.state', 'data': {{'state': 'paused', 'playlist_revision': 1, 'duration': 60,
          'position': 0, 'volume': -50, 'track': {{'path': {song!r}, 'title': 'A'}}}}}}), flush=True)
    # Sai com a janela.
    window = os.getppid()
    while os.getppid() == window: time.sleep(0.2)
elif args[:2] == ['remote', 'call']:
    op, params = args[2], json.loads(args[4])
    with open(here/'calls.txt', 'a') as out: out.write(op + '\\n')
    result = {{}}
    if op == 'queue.list':
        result = {{'tracks': [{{'path': {song!r}, 'title': 'A'}}], 'total': 1}}
    elif op == 'provider.list':
        result = {{'providers': [{{'key': 'soundcloud', 'name': 'SoundCloud', 'searchable': True}}]}}
    elif op == 'provider.search':
        if params['query'].startswith('velha'):
            time.sleep(1.5)
            print(json.dumps({{'ok': False, 'error': {{'message': 'quebrou'}}}}))
            (here/'failed').write_text('')
            sys.exit(1)
        result = {{'tracks': [{{'title': 'SC ' + params['query'], 'path': 'https://soundcloud.com/x'}}]}}
    elif op == 'queue.play':
        time.sleep(number('resume'))
    print(json.dumps({{'ok': True, 'result': result}}))
'''


@unittest.skipUnless(shutil.which('qs'), 'precisa do Quickshell (qs)')
class Window(unittest.TestCase):
    """Uma janela do LW por teste."""
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.bin = self.home/'bin'
        for name in ('bin', 'run', '.config', 'Músicas'):
            (self.home/name).mkdir()
        (self.home/'run').chmod(0o700)
        self.song = self.home/'Músicas/a.mp3'
        self.song.write_text('')
        # Nada daqui chega ao som nem ao Noctalia.
        for name in ('pactl', 'wpctl', 'noctalia', 'cava', 'playerctl', 'ffprobe'):
            self.program(name, '#!/bin/sh\nexit 1\n')
        self.program('cliamp', CLIAMP.format(python=sys.executable, folder=str(self.home), song=str(self.song)))
        self.session = self.home/'.local/state/rice-minimal/gui/music-session.json'
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(('LW_', 'RICE_', 'HYPRLAND_', 'XDG_')) and k not in ('WAYLAND_DISPLAY', 'DISPLAY', 'DBUS_SESSION_BUS_ADDRESS')}
        self.env.update(HOME=str(self.home), XDG_CONFIG_HOME=str(self.home/'.config'), XDG_RUNTIME_DIR=str(self.home/'run'),
                        PATH=f'{self.bin}:{os.environ["PATH"]}', RICE_CLIAMP=str(self.bin/'cliamp'),
                        RICE_MUSIC_VOLUME='cliamp', RICE_GUI_MOTION='0', QT_QPA_PLATFORM='offscreen')
        self.addCleanup(self.stop_daemon)

    def program(self, name, text):
        """Um programa falso na frente do PATH."""
        (self.bin/name).write_text(text)
        (self.bin/name).chmod(0o755)

    def save_session(self):
        """Uma sessão salva, com uma posição que o cliamp falso nunca dá."""
        self.session.parent.mkdir(parents=True, exist_ok=True)
        self.session.write_text(json.dumps({'paths': [str(self.song)], 'index': 0, 'position': 42, 'volume': -3}) + '\n')
        return self.session.read_text()

    def open(self, section):
        """Abre a janela numa seção e espera ela responder lá."""
        log = open(self.home/'log', 'w')
        self.addCleanup(log.close)
        self.qs = subprocess.Popen(['qs', '-p', str(ROOT/'gui')], env=dict(self.env, LW_START_GROUP=section),
                                   stdout=log, stderr=subprocess.STDOUT)
        self.addCleanup(self.close)
        self.until(lambda: self.state().get('section') == section)

    def ipc(self, *args):
        return subprocess.run(['qs', 'ipc', '--pid', str(self.qs.pid), 'call', 'lw', *args], env=self.env,
                              capture_output=True, text=True, timeout=10).stdout

    def state(self):
        try:
            return json.loads(self.ipc('state'))
        except ValueError:
            return {}

    def until(self, test, limit=15):
        """Espera test() dar algo verdadeiro."""
        end = time.time() + limit
        while time.time() < end:
            value = test()
            if value:
                return value
            time.sleep(0.05)
        self.fail('não aconteceu a tempo:\n' + (self.home/'log').read_text())

    def quit(self):
        """Fecha pelo mesmo caminho do q e do atalho."""
        self.ipc('close')
        self.qs.wait(timeout=10)

    def close(self):
        if self.qs.poll() is None:
            self.qs.kill()
        self.qs.wait()

    def daemon(self):
        """O PID do cliamp falso (espera ele nascer)."""
        return int(self.until(lambda: (self.home/'daemon.pid').exists() and (self.home/'daemon.pid').read_text()))

    def alive(self, pid):
        # O init (ou o subreaper) pode demorar a recolher: zumbi conta como morto.
        try:
            return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] != 'Z'
        except OSError:
            return False

    def lw(self, *args):
        """Um comando lw no HOME de teste (com --json)."""
        return subprocess.run([sys.executable, str(ROOT/'extras/rice.py'), *args, '--json'], env=self.env,
                              capture_output=True, text=True).stdout

    def warnings(self):
        """Os avisos do shell e de JOGOS no log (o de MÚSICA está em docs/pendencias.md)."""
        return [l for l in (self.home/'log').read_text().splitlines() if re.search(r'@(shell|Games|arcade/\w+)\.qml\[', l)]

    def stop_daemon(self):
        if (self.home/'daemon.pid').exists() and self.alive(int((self.home/'daemon.pid').read_text())):
            os.kill(int((self.home/'daemon.pid').read_text()), signal.SIGKILL)


class ClosingMusic(Window):
    """Fechar em MÚSICA desliga o cliamp e salva a sessão; fechar de outra seção só salva."""
    def test_before_cliamp_answers(self):
        before = self.save_session()
        (self.home/'delay').write_text('30')
        self.open('music')
        pid = self.daemon()
        self.assertIs(self.state()['online'], False)
        self.quit()
        self.until(lambda: not self.alive(pid), 5)
        self.assertEqual(self.session.read_text(), before)

    def test_after_the_answer(self):
        self.resumed()
        self.leaves(alive=False)

    def test_outside_music_it_keeps_playing(self):
        for section in ('system', 'games'):
            with self.subTest(section=section):
                self.resumed()
                self.ipc('go', section)
                self.leaves(alive=True)
                self.stop_daemon()
                for name in ('up', 'calls.txt', 'daemon.pid'):
                    (self.home/name).unlink()

    def test_outside_music_before_the_answer_it_stays_on(self):
        before = self.save_session()
        (self.home/'delay').write_text('30')
        self.open('music')
        pid = self.daemon()
        self.ipc('go', 'system')
        self.assertIs(self.state()['online'], False)
        self.quit()
        time.sleep(1)
        self.assertTrue(self.alive(pid))
        self.assertEqual(self.session.read_text(), before)

    def test_right_after_opening(self):
        # Fechar no meio do START (antes de o cliamp nascer) também não deixa nenhum.
        self.save_session()
        (self.home/'delay').write_text('30')
        self.open('music')
        self.until(lambda: 'online' in self.state())
        self.quit()
        time.sleep(1.5)
        self.assertFalse((self.home/'daemon.pid').exists() and self.alive(self.daemon()))

    def test_the_session_survives_closing_while_cliamp_goes_back_to_it(self):
        # No meio da volta o cliamp está no começo da fila e mudo: isso não é a sessão.
        (self.home/'resume').write_text('3')
        for section in ('music', 'system'):
            with self.subTest(section=section):
                before = self.save_session()
                self.open('music')
                pid = self.daemon()
                self.until(lambda: 'queue.play' in self.calls())
                self.ipc('go', section)
                self.quit()
                if section == 'music':
                    self.until(lambda: not self.alive(pid), 5)
                self.assertEqual(self.session.read_text(), before)
                self.stop_daemon()
                for name in ('up', 'calls.txt', 'daemon.pid'):
                    (self.home/name).unlink()

    def resumed(self):
        """Abre em MÚSICA e espera o cliamp voltar para a sessão salva."""
        self.save_session()
        self.open('music')
        self.daemon()
        self.until(lambda: self.calls().count('volume') == 2)
        time.sleep(0.3)

    def leaves(self, alive):
        """Fecha e confere o cliamp e a sessão, que agora é a do cliamp (posição 0)."""
        pid = self.daemon()
        self.quit()
        if alive:
            time.sleep(1)
            self.assertTrue(self.alive(pid))
        else:
            self.until(lambda: not self.alive(pid), 5)
        saved = json.loads(self.session.read_text())
        self.assertEqual((saved['paths'], saved['position']), ([str(self.song)], 0))

    def test_a_cliamp_that_was_already_on_keeps_playing_outside_music(self):
        mine = subprocess.Popen([str(self.bin/'cliamp'), '--daemon'], env=self.env)
        self.addCleanup(mine.wait)
        self.addCleanup(mine.kill)
        pid = self.daemon()
        self.until((self.home/'up').exists)
        self.open('system')
        self.until(lambda: self.state().get('playlist'))
        self.quit()
        time.sleep(1)
        self.assertTrue(self.alive(pid))
        self.assertTrue(self.session.exists())

    def calls(self):
        path = self.home/'calls.txt'
        return path.read_text().split() if path.exists() else []


class OnlineSearch(Window):
    """A falha de uma busca que já foi trocada por outra não aparece."""
    def setUp(self):
        super().setUp()
        self.program('yt-dlp', '#!/bin/sh\necho \'{"entries":[{"title":"YT","url":"https://y/v"}]}\'\n')
        self.save_session()
        self.open('music')
        screens = json.loads(subprocess.run([sys.executable, str(ROOT/'extras/rice.py'), 'modules', 'list', '--json'],
                                            env=self.env, capture_output=True, text=True).stdout)['data']
        self.online = next(m for m in screens if m['id'] == 'music')['screens'].index({'name': 'ONLINE', 'file': 'OnlineScreen.qml'})
        self.until(lambda: self.state().get('online'))
        self.ipc('open', str(self.online))
        # A fonte que aparece primeiro depende de quem responde antes; Tab só troca com as duas.
        self.tab_to('ytdlp')
        self.tab_to('soundcloud')

    def search(self):
        return self.state().get('online_search') or {}

    def tab_to(self, provider):
        """Tab até a fonte ser essa."""
        def there():
            if self.search().get('provider') == provider:
                return True
            self.ipc('key', 'Tab')
        self.until(there)

    def old_fails(self):
        """Espera a busca velha falhar e a janela receber a falha."""
        self.until((self.home/'failed').exists)
        time.sleep(0.5)

    def test_the_failure_of_the_current_search_shows(self):
        self.ipc('query', 'velha')
        self.until(lambda: self.search()['error'] == 'quebrou')
        self.assertFalse(self.search()['searching'])
        self.assertIn('quebrou', self.state()['message'])

    def test_an_old_soundcloud_failure_does_not_reach_a_new_soundcloud_search(self):
        self.ipc('query', 'velha')
        self.ipc('query', 'nova')
        self.until(lambda: self.search()['results'] == ['SC nova'])
        self.old_fails()
        self.assertEqual((self.search()['results'], self.search()['error']), (['SC nova'], ''))
        self.assertNotIn('quebrou', self.state()['message'])

    def test_an_old_soundcloud_failure_does_not_reach_youtube(self):
        self.ipc('query', 'velha')
        self.ipc('key', 'Tab')      # a mesma busca, agora no YouTube
        self.until(lambda: self.search()['results'] == ['YT'])
        self.old_fails()
        self.assertEqual((self.search()['results'], self.search()['error']), (['YT'], ''))
        self.assertNotIn('quebrou', self.state()['message'])

    def test_a_failure_from_before_leaving_the_screen_does_not_reach_the_new_one(self):
        self.ipc('query', 'velha')
        self.ipc('open', '0')
        self.ipc('open', str(self.online))
        self.until(lambda: self.search().get('provider'))
        self.old_fails()
        self.assertEqual((self.search()['searching'], self.search()['error']), (False, ''))


class GamesSection(Window):
    """JOGOS na janela, com jogos falsos: nenhum jogo, Steam, Wine ou emulador real é chamado."""
    def setUp(self):
        super().setUp()
        for name in ('steam', 'wine', 'wineserver', 'umu-run', 'ryujinx', 'gamemoderun', 'mangohud', 'gamescope', 'zenity', 'hyprctl'):
            self.program(name, '#!/bin/sh\nexit 1\n')
        self.program('jogo', '#!/bin/sh\nexec sleep 6\n')
        self.db = self.home/'.local/share/lw/games.json'
        self.addCleanup(self.kill_games)

    def kill_games(self):
        """Nada do HOME de teste fica vivo."""
        mark = b'HOME=' + str(self.home).encode()
        for entry in Path('/proc').iterdir():
            try:
                if entry.name.isdigit() and mark in (entry/'environ').read_bytes().split(b'\0'):
                    os.kill(int(entry.name), signal.SIGKILL)
            except OSError:
                pass

    def doc(self):
        return json.loads(self.db.read_text())

    def game(self, name='jogo'):
        """Põe um programa falso na biblioteca; devolve o id."""
        return json.loads(self.lw('game', 'add', '--exe', str(self.bin/name)))['data']['added']['id']

    def enter(self):
        self.open('games')
        self.until(lambda: self.db.exists() and self.doc().get('scanned_at') and self.state().get('scanning') is False)

    def play(self, gid):
        """Abre a ficha e joga, como o Enter faz; espera a sessão abrir."""
        self.ipc('openSheet', gid)
        self.ipc('key', 'Return')
        self.until(lambda: (self.state().get('session') or {}).get('id') == gid)

    def sessions(self, gid):
        return next(g['sessions'] for g in self.doc()['games'] if g['id'] == gid)

    def test_the_scan_runs_once_per_window(self):
        self.open('system')
        time.sleep(1)
        self.assertFalse(self.db.exists())      # só ao entrar em JOGOS
        self.ipc('go', 'games')
        self.until(lambda: self.db.exists() and self.state().get('scanning') is False)
        before = self.db.stat().st_mtime_ns
        self.ipc('go', 'system')
        self.ipc('go', 'games')
        time.sleep(1.5)
        self.assertEqual(self.db.stat().st_mtime_ns, before)

    def test_the_sheets_take_the_keys_and_close_when_the_section_changes(self):
        gid = self.game()
        self.enter()
        for opens in (('openSheet', gid), ('installer',)):
            with self.subTest(opens=opens[0]):
                self.ipc(*opens)
                self.ipc('key', '2')
                self.assertEqual(self.state()['view'], 0)      # a ficha é modal
                self.ipc('go', 'system')
                self.ipc('go', 'games')
                self.ipc('key', '2')
                self.assertEqual(self.state()['view'], 1)
                self.ipc('open', '0')

    def test_the_installer_opens_on_its_own_section(self):
        self.open('system')
        self.until(lambda: 'games' in self.state())
        self.ipc('installer')
        self.assertEqual(self.state()['section'], 'games')

    def test_emulators_leaves_no_warning_when_left_early(self):
        self.enter()
        for _ in range(4):
            self.ipc('open', '3')
            self.ipc('open', '0')
        self.ipc('open', '3')
        self.ipc('go', 'system')
        time.sleep(1.5)
        self.assertEqual(self.warnings(), [])

    def test_the_session_counts_by_game_id_even_with_lw_closed(self):
        gid = self.game()
        self.enter()
        self.play(gid)
        self.assertEqual(self.doc()['open_session']['id'], gid)
        self.quit()
        self.until(lambda: self.sessions(gid), 20)
        session = self.sessions(gid)[0]
        self.assertTrue(4 <= session['end'] - session['start'] <= 8, session)
        self.assertNotIn('open_session', self.doc())

    def emulated(self):
        """Um emulador falso que se marca como não-dumpable, como o Ryujinx, e uma ROM dele."""
        self.program('ryujinx', f'#!{sys.executable}\nimport ctypes, time\nctypes.CDLL(None).prctl(4, 0, 0, 0, 0)\n'
                                'open("%s", "w").write(str(__import__("os").getpid()))\ntime.sleep(8)\n' % (self.home/'emulador'))
        rom = self.home/'Jogos/ROMs/switch/Monstro.nsp'
        rom.parent.mkdir(parents=True)
        rom.write_text('x')
        self.lw('game', 'scan')
        self.enter()
        gid = next(g['id'] for g in self.doc()['games'] if g['source'] == 'rom')
        self.play(gid)
        pid = int(self.until(lambda: (self.home/'emulador').exists() and (self.home/'emulador').read_text()))
        self.addCleanup(lambda: self.alive(pid) and os.kill(pid, signal.SIGKILL))
        self.until(lambda: not os.access(f'/proc/{pid}/environ', os.R_OK))     # ilegível de verdade
        return gid, pid

    def test_an_emulator_that_hides_its_environment_counts_whole_even_with_lw_closed(self):
        gid, pid = self.emulated()
        self.quit()
        self.until(lambda: self.sessions(gid), 25)
        session = self.sessions(gid)[0]
        self.assertTrue(6 <= session['end'] - session['start'] <= 10, session)

    def test_stop_reaches_the_hidden_emulator(self):
        gid, pid = self.emulated()
        self.assertEqual(json.loads(self.lw('game', 'stop', gid))['data'], {'signalled': 1})
        self.until(lambda: not self.alive(pid), 5)
        self.until(lambda: self.sessions(gid), 15)

    def test_a_steam_game_counts_by_its_app_id(self):
        # Uma Steam falsa, já aberta: só entrega o jogo, com o SteamAppId no ambiente.
        self.program('steam', '#!/bin/sh\nunset LW_GAME_ID\nSteamAppId=620 setsid sleep 6 &\n')
        self.db.parent.mkdir(parents=True)
        self.db.write_text(json.dumps({'games': [{'id': 'steam:620', 'title': 'Portal 2', 'source': 'steam',
                                                  'launch': 'steam steam://rungameid/620', 'status': 'want', 'hours': 0, 'sessions': []}]}))
        self.open('system')
        self.lw('game', 'launch', 'steam:620')
        self.until(lambda: (self.state().get('session') or {}).get('id') == 'steam:620')
        self.until(lambda: self.sessions('steam:620'), 20)
        session = self.sessions('steam:620')[0]
        self.assertTrue(4 <= session['end'] - session['start'] <= 8, session)


class Sections(Window):
    """Trocar de seção não procura a tela da nova na lista da antiga."""
    def test_no_screen_is_looked_up_in_the_old_list(self):
        self.save_session()
        self.open('system')
        modules = json.loads(subprocess.run([sys.executable, str(ROOT/'extras/rice.py'), 'modules', 'list', '--json'],
                                            env=self.env, capture_output=True, text=True).stdout)['data']
        self.until(lambda: self.state().get('online') is not None)
        # A última tela de cada seção: a posição de uma não existe na outra.
        for m in modules:
            self.ipc('go', m['id'])
            self.ipc('open', str(len(m['screens'])-1))
        for a in modules:
            for b in modules:
                for m in (a, b):
                    self.ipc('go', m['id'])
                    state = self.state()
                    self.assertEqual((state['section'], state['screen']), (m['id'], m['screens'][-1]['name']))
        self.assertEqual(self.warnings(), [])

    def test_the_keyboard_leaves_the_field_of_the_old_section(self):
        self.open('system')
        self.until(lambda: self.state().get('scanning') is False and 'online' in self.state())
        for old, new in (('system', 'music'), ('games', 'system')):
            with self.subTest(old=old):
                self.ipc('go', old)
                self.ipc('key', 'Slash')
                self.assertIs(self.state()['typing'], True)
                self.ipc('go', new)
                self.assertIs(self.state()['typing'], False)

    def test_a_window_with_only_the_system_does_not_wake_the_others(self):
        data = json.loads(self.lw('modules', 'list'))['data']
        self.env['LW_MODULES'] = json.dumps([m for m in data if m['id'] == 'system'])
        self.open('system')
        time.sleep(1)
        self.assertEqual(sorted(self.state()), ['message', 'screen', 'section', 'typing', 'view'])
        self.ipc('go', 'games')
        self.assertEqual(self.ipc('openSheet', 'x').strip(), 'unknown openSheet')
        self.ipc('installer')
        self.assertEqual(self.state()['section'], 'system')
        self.assertEqual(self.warnings(), [])


if __name__ == '__main__':
    unittest.main()
