import io
import json
import os
import sys
import tempfile
import tomllib
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'extras'))
import radio  # noqa: E402


class Radio(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        env = patch.dict(os.environ, {'XDG_CONFIG_HOME': self.home.name})
        env.start()
        self.addCleanup(env.stop)

    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = radio.main(list(argv))
        return code, json.loads(out.getvalue())

    def test_add_appends_a_station_cliamp_can_read_and_refuses_duplicates(self):
        path = radio.radios_path()
        path.parent.mkdir(parents=True)
        path.write_text('[[station]]\nname = "Old"\nurl = "http://old.example/stream"\n')
        code, data = self.run_cli('add', '--name', 'Jazz "FM"', '--url', 'https://jazz.example/live')
        self.assertEqual(code, 0)
        stations = tomllib.loads(path.read_text())['station']
        self.assertEqual([s['name'] for s in stations], ['Old', 'Jazz "FM"'])
        self.assertEqual(self.run_cli('saved')[1]['stations'][1]['url'], 'https://jazz.example/live')
        self.assertFalse(self.run_cli('add', '--name', 'Again', '--url', 'https://jazz.example/live')[1]['ok'])
        self.assertFalse(self.run_cli('add', '--name', 'Bad', '--url', 'ftp://x')[1]['ok'])
        self.assertFalse(self.run_cli('add', '--name', 'Bad\nname', '--url', 'https://x.example')[1]['ok'])
        self.assertEqual(len(tomllib.loads(path.read_text())['station']), 2)

    def test_saved_without_a_file_is_empty(self):
        self.assertEqual(self.run_cli('saved')[1]['stations'], [])

    def test_search_tries_the_next_server_and_keeps_only_playable_entries(self):
        reply = io.BytesIO(json.dumps([
            {'name': 'Lofi', 'url_resolved': 'http://a/stream', 'codec': 'MP3', 'bitrate': 128, 'votes': 9, 'countrycode': 'US'},
            {'name': 'Broken', 'url_resolved': '', 'url': ''}]).encode())
        calls = []

        def urlopen(request, timeout):
            calls.append(request.full_url)
            if len(calls) == 1:
                raise OSError('down')
            return reply
        with patch.object(radio, 'servers', return_value=['one.example', 'two.example']), \
             patch.object(radio.urllib.request, 'urlopen', side_effect=urlopen):
            code, data = self.run_cli('search', '--tag', 'lofi')
        self.assertEqual((code, data['server']), (0, 'two.example'))
        self.assertEqual([s['name'] for s in data['stations']], ['Lofi'])
        self.assertIn('hidebroken=true', calls[1])
        self.assertIn('order=votes', calls[1])

    def test_search_reports_when_every_server_fails(self):
        with patch.object(radio, 'servers', return_value=['one.example']), \
             patch.object(radio.urllib.request, 'urlopen', side_effect=OSError('offline')):
            code, data = self.run_cli('search', '--name', 'x')
        self.assertEqual(code, 1)
        self.assertIn('fora do alcance', data['error'])


if __name__ == '__main__':
    unittest.main()
