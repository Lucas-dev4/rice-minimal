# Testes do ytdl.py: linha de comando do yt-dlp, leitura da saída e o resumo final.
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'extras'))
import ytdl  # noqa: E402


class Command(unittest.TestCase):
    def test_single_song_goes_to_downloads_as_mp3_with_tags_and_cover(self):
        cmd = ytdl.command('https://youtu.be/x', '/m')
        self.assertEqual(cmd[-2:], ['--', 'https://youtu.be/x'])
        self.assertIn('--no-playlist', cmd)
        self.assertEqual(cmd[cmd.index('--audio-format')+1], 'mp3')
        for flag in ('--embed-metadata', '--embed-thumbnail', '--download-archive', '--no-quiet'):
            self.assertIn(flag, cmd)
        self.assertTrue(cmd[cmd.index('-o')+1].startswith('/m/Downloads/%(artist'))

    def test_playlist_gets_its_own_folder_numbered_with_album_and_track(self):
        cmd = ytdl.command('https://youtube.com/playlist?list=1', '/m', playlist=True)
        self.assertIn('--yes-playlist', cmd)
        self.assertIn('/m/Downloads/%(playlist_title', cmd[cmd.index('-o')+1])
        self.assertIn('%(playlist_title,playlist|)s:%(meta_album)s', cmd)

    def test_square_cover_filter_survives_yt_dlp_argument_splitting(self):
        import shlex
        ppa = ytdl.command('https://youtu.be/x', '/m')
        arg = ppa[ppa.index('--ppa')+1].split(':', 1)[1]
        self.assertIn("crop='if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'", shlex.split(arg))


class Parse(unittest.TestCase):
    def test_reads_the_lines_it_asked_yt_dlp_to_print(self):
        self.assertEqual(ytdl.parse('LW\titem\t3\t12\tMúsica\tcom tab\n'),
                         {'event': 'item', 'index': 3, 'total': 12, 'title': 'Música\tcom tab'})
        self.assertEqual(ytdl.parse('LW\tdone\t/m/a.mp3'), {'event': 'done', 'file': '/m/a.mp3'})
        self.assertEqual(ytdl.parse('LW\tprogress\t512\t1024'), {'event': 'progress', 'percent': 50.0})
        self.assertEqual(ytdl.parse('LW\tprogress\t512\tNA'), {'event': 'progress', 'percent': 0})

    def test_skips_and_errors_and_ignores_the_rest(self):
        self.assertEqual(ytdl.parse('[download] abc: has already been recorded in the archive')['event'], 'skip')
        self.assertEqual(ytdl.parse('ERROR: [youtube] abc: Video unavailable'),
                         {'event': 'error', 'message': '[youtube] abc: Video unavailable'})
        self.assertIsNone(ytdl.parse('[youtube] Extracting URL'))


class Cli(unittest.TestCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = ytdl.main(list(argv))
        return code, [json.loads(line) for line in out.getvalue().splitlines()]

    def test_refuses_something_that_is_not_a_link(self):
        code, events = self.run_cli('download', 'rm -rf')
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]['message'], 'link inválido')

    def test_says_what_to_install_without_yt_dlp(self):
        with patch.object(ytdl.shutil, 'which', return_value=None):
            code, events = self.run_cli('download', 'https://youtu.be/x')
        self.assertEqual(code, 1)
        self.assertIn('sudo pacman -S yt-dlp', events[-1]['message'])

    def test_counts_done_skipped_and_errors_from_a_fake_yt_dlp(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp)/'yt-dlp'
            fake.write_text('#!/bin/sh\nprintf "LW\\titem\\t1\\t2\\tA\\nLW\\tdone\\t/m/A.mp3\\n'
                            '[download] b: has already been recorded in the archive\\n'
                            'ERROR: [youtube] c: Private video\\n"\nexit 1\n')
            fake.chmod(0o755)
            env = {'PATH': f'{tmp}:{os.environ["PATH"]}', 'XDG_DATA_HOME': tmp}
            with patch.dict(os.environ, env):
                code, events = self.run_cli('download', 'https://youtu.be/x', '--root', tmp)
        self.assertEqual(code, 1)
        end = events[-1]
        self.assertEqual((end['done'], end['skipped'], end['errors']), (1, 1, 1))
        self.assertEqual(end['message'], '[youtube] c: Private video')


if __name__ == '__main__':
    unittest.main()
