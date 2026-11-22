# Testes do organize.py: o artista decide a pasta, nada é sobrescrito e tudo vai para o log.
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'extras'))
import organize  # noqa: E402


def song(path, artist=None, title=None):
    """Um MP3 curto de verdade (com tags, se pedidas)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = [x for k, v in (('artist', artist), ('title', title)) if v for x in ('-metadata', f'{k}={v}')]
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'anullsrc=d=0.2', *meta, str(path)], check=True)
    return path


class Organize(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ('Rap Geek (Anime & Nerd)/WLO - Boxeador.mp3', 'Rap Geek (Anime & Nerd)/WLO X Rodrigo Zin - Rei.mp3',
                     'K-Pop/BLACKPINK - Pink Venom.mp3', 'K-Pop/Stromae - Errado.mp3',
                     'Francesa/Stromae - Papaoutai.mp3', 'Francesa/Stromae - Alors.mp3'):
            (self.root/name).parent.mkdir(parents=True, exist_ok=True)
            (self.root/name).write_bytes(b'x')

    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = organize.main(['--root', str(self.root), *argv])
        return code, json.loads(out.getvalue())

    def test_known_artist_goes_to_their_folder_with_the_repeated_name_removed(self):
        song(self.root/'Downloads/WLO - WLO - Boxeador Perfeito.mp3', artist='WLO', title='WLO - Boxeador Perfeito')
        code, result = self.run_cli('apply')
        self.assertEqual(code, 0)
        self.assertEqual(result['moved'][0]['folder'], 'Rap Geek (Anime & Nerd)')
        self.assertTrue((self.root/'Rap Geek (Anime & Nerd)/WLO - Boxeador Perfeito.mp3').exists())
        self.assertFalse(any((self.root/'Downloads').iterdir()))
        log = json.loads((self.root/'.organizacao-log.json').read_text())
        self.assertTrue(log[-1][1].endswith('WLO - Boxeador Perfeito.mp3'))

    def test_featuring_and_accents_find_the_main_artist_and_majority_wins(self):
        song(self.root/'Downloads/Wló ft. Alguém - Nova.mp3')
        song(self.root/'Downloads/stromae - Santé.mp3')
        moves = {m['artist']: m['folder'] for m in self.run_cli('plan')[1]['moves']}
        self.assertEqual(moves, {'Wló ft. Alguém': 'Rap Geek (Anime & Nerd)', 'stromae': 'Francesa'})

    def test_playlist_files_use_the_tag_artist_and_the_empty_folder_is_removed(self):
        song(self.root/'Downloads/Minha Lista/01 - Shut Down.mp3', artist='BLACKPINK', title='Shut Down')
        _, result = self.run_cli('apply')
        self.assertEqual(result['moved'][0]['name'], 'BLACKPINK - Shut Down.mp3')
        self.assertFalse((self.root/'Downloads/Minha Lista').exists())

    def test_new_artist_waits_and_a_chosen_folder_teaches_the_next_song(self):
        first = song(self.root/'Downloads/Banda Nova - Um.mp3')
        song(self.root/'Downloads/Banda Nova - Dois.mp3')
        _, result = self.run_cli('apply')
        self.assertEqual(len(result['unknown']), 2)
        self.assertNotIn('Downloads', result['folders'])
        code, moved = self.run_cli('move', str(first), 'K-Pop')
        self.assertEqual(code, 0)
        self.assertEqual(self.run_cli('apply')[1]['moved'][0]['dest'], str(self.root/'K-Pop/Banda Nova - Dois.mp3'))

    def test_never_overwrites_and_refuses_files_outside_downloads_or_unknown_folders(self):
        song(self.root/'Downloads/WLO - Boxeador.mp3')
        _, result = self.run_cli('apply')
        self.assertEqual(result['skipped'][0]['reason'], 'já existe em Rap Geek (Anime & Nerd)')
        self.assertEqual((self.root/'Rap Geek (Anime & Nerd)/WLO - Boxeador.mp3').read_bytes(), b'x')
        self.assertTrue((self.root/'Downloads/WLO - Boxeador.mp3').exists())
        self.assertFalse(self.run_cli('move', str(self.root/'K-Pop/BLACKPINK - Pink Venom.mp3'), 'Francesa')[1]['ok'])
        self.assertFalse(self.run_cli('move', str(self.root/'Downloads/WLO - Boxeador.mp3'), '../fora')[1]['ok'])


if __name__ == '__main__':
    unittest.main()
