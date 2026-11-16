# Testes do library.py: leitura de tags, cache e comparação de faixas online.
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'extras'))
import library  # noqa: E402


def make_mp3(path, **tags):
    args = ['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=f=440:d=1']
    for key, value in tags.items():
        args += ['-metadata', f'{key}={value}']
    subprocess.run(args + ['-c:a', 'libmp3lame', str(path)], check=True)


def tags_of(path):
    out = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', str(path)], capture_output=True, text=True).stdout
    return {k.lower(): v for k, v in json.loads(out)['format'].get('tags', {}).items()}


class Library(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)/'Músicas'
        (self.root/'WLO').mkdir(parents=True)
        env = patch.dict(os.environ, {'XDG_CACHE_HOME': self.dir.name + '/cache'})
        env.start()
        self.addCleanup(env.stop)
        self.song = self.root/'WLO'/'Boxeador.mp3'
        make_mp3(self.song, title='﻿Boxeador', artist='﻿WLO', lyrics='soco e luva ' * 900)

    def test_scan_cleans_tags_cuts_lyrics_and_reuses_the_cache(self):
        first = library.scan(self.root)
        track = first['tracks'][0]
        self.assertEqual((track['title'], track['artist'], first['read']), ('Boxeador', 'WLO', 1))
        self.assertEqual(len(track['lyrics']), library.LYRICS_LIMIT)
        self.assertEqual(library.scan(self.root)['read'], 0)
        make_mp3(self.root/'WLO'/'Novo.mp3', title='Novo')
        self.assertEqual(library.scan(self.root)['read'], 1)

    def test_match_needs_both_artist_and_title(self):
        track = {'artist': 'WLO, Blxck', 'title': 'Boxeador'}
        self.assertTrue(library.best_match(track, [{'artist': 'WLO', 'title': 'Boxeador (Ao Vivo)'}]))
        self.assertIsNone(library.best_match(track, [{'artist': 'Bunbury', 'title': 'El boxeador'}]))
        self.assertIsNone(library.best_match(track, [{'artist': 'WLO', 'title': 'Outra Música'}]))

    def test_apply_sets_genre_and_year_keeps_lyrics_and_audio(self):
        before = library.audio_md5(self.song)
        with patch.object(library.subprocess, 'run', wraps=subprocess.run) as run:
            result = library.apply_one({'path': str(self.song), 'set': {'genre': 'Rap/Hip Hop', 'date': '2024'}})
        self.assertTrue(result['ok'])
        self.assertTrue(any(c.args[0][:2] == ['gio', 'trash'] for c in run.call_args_list))
        tags = tags_of(self.song)
        self.assertEqual((tags['genre'], tags['date'], tags['title']), ('Rap/Hip Hop', '2024', 'Boxeador'))
        self.assertEqual(len(tags['lyrics-eng'] if 'lyrics-eng' in tags else tags['lyrics']), len('soco e luva ' * 900))
        self.assertEqual(library.audio_md5(self.song), before)
        self.assertFalse(list(self.song.parent.glob('.lw-tmp-*')) + list(self.song.parent.glob('.lw-tags-*')))


if __name__ == '__main__':
    unittest.main()
