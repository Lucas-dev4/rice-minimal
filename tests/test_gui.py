# Testes da janela de verdade: abre o gui/ no Quickshell sem tela (offscreen), num HOME e num
# XDG_RUNTIME_DIR temporários, com um cliamp falso. Não encosta na sessão, no som nem no cliamp real.
import json
import os
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
        # Só o shell.qml: os avisos do EmulatorsView são de JOGOS (docs/pendencias.md).
        self.assertEqual([l for l in (self.home/'log').read_text().splitlines() if 'shell.qml[' in l], [])


if __name__ == '__main__':
    unittest.main()
