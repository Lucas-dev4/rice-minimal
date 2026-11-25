# Testes do compat.py: leitura do hardware com /proc, /sys, lspci, nvidia-smi e Steam falsos,
# e a avaliação ok / lim / no / na igual ao evalG de docs/lw-jogos-prototype.html.
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'extras'))
import compat  # noqa: E402

GTX = ('0000:01:00.0 "VGA compatible controller [0300]" "NVIDIA Corporation [10de]" '
       '"TU117 [GeForce GTX 1650] [1f82]" -ra1 -p00 "NVIDIA Corporation [10de]" "Device [145c]"')
UHD = ('0000:00:02.0 "VGA compatible controller [0300]" "Intel Corporation [8086]" '
       '"CometLake-S GT2 [UHD Graphics 630] [9bc5]" -r03 -p00 "Intel Corporation [8086]" "Device [8694]"')
VEGA = ('0000:03:00.0 "VGA compatible controller [0300]" "Advanced Micro Devices, Inc. [AMD/ATI] [1002]" '
        '"Picasso/Raven 2 [Radeon Vega Series / Radeon Vega Mobile Series] [15d8]" -rc2 -p00 "Acer Incorporated [ALI] [1025]" "Device [1323]"')
AUDIO = ('0000:01:00.1 "Audio device [0403]" "NVIDIA Corporation [10de]" "TU117 High Definition Audio Controller [10fa]" '
         '-ra1 -p00 "NVIDIA Corporation [10de]" "Device [145c]"')


class Machine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root, self.home = base/'root', base/'home'
        (self.root/'proc').mkdir(parents=True)
        self.home.mkdir()
        self.out = {}
        self.free = {}
        for p in (patch.object(compat, 'ROOT', self.root),
                  patch.object(compat, 'run', lambda cmd: self.out.get(cmd[0])),
                  patch.object(compat, 'free_gb', lambda path: self.free.get(str(path), 100.0)),
                  patch.dict(os.environ, {'HOME': str(self.home), 'XDG_DATA_HOME': str(self.home/'.local/share'), 'XDG_CONFIG_HOME': str(self.home/'.config')})):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def hardware(self, model, kb, threads, lspci, nvidia=None):
        (self.root/'proc/cpuinfo').write_text(f'processor\t: 0\nvendor_id\t: x\nmodel name\t: {model}\nflags\t\t: fpu\n\n')
        (self.root/'proc/meminfo').write_text(f'MemTotal:       {kb} kB\nMemFree:        1000 kB\n')
        self.out.update(nproc=f'{threads}\n', lspci='\n'.join(lspci) + '\n')
        if nvidia:
            self.out['nvidia-smi'] = nvidia

    def drm(self, card, slot, vram_bytes):
        device = self.root/f'sys/class/drm/{card}/device'
        device.mkdir(parents=True)
        (device/'uevent').write_text(f'DRIVER=amdgpu\nPCI_SLOT_NAME={slot}\n')
        (device/'mem_info_vram_total').write_text(f'{vram_bytes}\n')

    def steam(self, *libraries):
        apps = self.home/'.local/share/Steam/steamapps'
        apps.mkdir(parents=True)
        body = ''
        for i, (path, free) in enumerate(libraries):
            Path(path).mkdir(parents=True, exist_ok=True)
            self.free[str(path)] = free
            body += f'\t"{i}"\n\t{{\n\t\t"path"\t\t"{path}"\n\t}}\n'
        (apps/'libraryfolders.vdf').write_text('"libraryfolders"\n{\n' + body + '}\n')

    def by_name(self, result):
        return {g['n']: g for g in result['games']}

    def test_desktop_gtx_1650(self):
        self.hardware('Intel(R) Core(TM) i5-10400F CPU @ 2.90GHz', 24459576, 12, [GTX, AUDIO],
                      '00000000:01:00.0, 4096\n')
        lib = self.home/'Games'
        self.steam((self.home/'.local/share/Steam', 30.0), (lib, 250.5))
        m = compat.scan()
        self.assertEqual((m['cpu'], m['threads'], m['ram_gb'], m['vram_gb']),
                         ('Intel(R) Core(TM) i5-10400F CPU @ 2.90GHz', 12, 23.3, 4.0))
        self.assertEqual(m['gpu'], 'NVIDIA Corporation TU117 [GeForce GTX 1650]')
        self.assertEqual(len(m['gpus']), 1)                     # the audio function is not a GPU
        self.assertEqual((m['disk']['source'], m['disk']['path'], m['disk']['free_gb']), ('steam', str(lib), 250.5))
        g = self.by_name(compat.check(m))
        self.assertEqual((g['Elden Ring']['k'], g['Elden Ring']['w']), ('lim', 'GPU no limite (39 vs 42)'))
        self.assertEqual((g['Monster Hunter Wilds']['k'], g['Monster Hunter Wilds']['reasons']),
                         ('no', ['GPU fraca (39 vs 55 mín)', 'VRAM 4/6 GB']))
        self.assertEqual((g['Cuphead']['k'], g['Cuphead']['w']), ('ok', 'folga: GPU ×4,9'))
        self.assertEqual((g['Bloodborne']['k'], g['Bloodborne']['s']), ('na', 0))
        self.assertIn('via emulador (Switch)', g['Monster Hunter Generations Ultimate']['reasons'])
        self.assertEqual((g['Elden Ring']['s'], g['Doom']['s']), (1, 0))   # verificado / estimativa

    def test_notebook_vega_3_picasso(self):
        self.hardware('AMD Ryzen 3 3200U with Radeon Vega Mobile Gfx', 5976883, 4, [VEGA])
        self.drm('card1', '0000:03:00.0', 2*1073741824)
        m = compat.scan()
        self.assertEqual((m['ram_gb'], m['vram_gb'], m['gpus'][0]['score']), (5.7, 2.0, 12))
        self.assertEqual(m['disk']['source'], 'home')           # no Steam: the home folder
        g = self.by_name(compat.check(m))
        ng = g['Ninja Gaiden: Ragebound']                         # g 15, r 8, c 35
        self.assertEqual((ng['k'], ng['reasons']), ('no', ['GPU no limite (12 vs 15)', 'RAM 5.7/8 GB', 'CPU no limite']))
        self.assertEqual(g['Katana Zero']['k'], 'ok')
        self.assertEqual(g['Elden Ring']['k'], 'no')

    def test_two_gpus_the_strongest_wins_and_its_own_vram(self):
        self.hardware('Intel(R) Core(TM) i5-10400 CPU @ 2.90GHz', 16000000, 12, [UHD, GTX],
                      '00000000:01:00.0, 4096\n')
        m = compat.scan()
        self.assertEqual([c['score'] for c in m['gpus']], [6, 39])
        self.assertEqual((m['gpu'], m['vram_gb']), ('NVIDIA Corporation TU117 [GeForce GTX 1650]', 4.0))

    def test_amd_igpu_and_nvidia_reads_the_vram_of_the_chosen_one(self):
        self.hardware('AMD Ryzen 5 5600H', 16000000, 12, [VEGA, GTX], '00000000:01:00.0, 4096\n')
        self.drm('card0', '0000:03:00.0', 512*1048576)
        self.assertEqual(compat.scan()['vram_gb'], 4.0)

    def test_missing_tools_give_unknowns_not_errors(self):
        (self.root/'proc/cpuinfo').write_text('processor\t: 0\n')
        m = compat.scan()
        self.assertEqual((m['cpu'], m['threads'], m['ram_gb'], m['gpu'], m['vram_gb']), (None, None, None, None, None))
        g = self.by_name(compat.check(m))
        self.assertEqual(g['Celeste']['reasons'], ['GPU desconhecida'])

    def test_low_disk_fails_and_installed_games_are_marked(self):
        self.hardware('Intel(R) Core(TM) i5-10400F CPU @ 2.90GHz', 24459576, 12, [GTX], '00000000:01:00.0, 4096\n')
        self.steam((self.home/'lib', 12.0))
        db = self.home/'.local/share/lw'
        db.mkdir(parents=True)
        (db/'games.json').write_text(json.dumps({'games': [
            {'id': 'hydra:1', 'title': 'Cuphead', 'missing': False},
            {'id': 'wine:2', 'title': 'Hades', 'missing': True}]}))
        g = self.by_name(compat.check())
        self.assertEqual((g['Cuphead']['k'], g['Cuphead']['reasons']), ('no', ['falta disco (12/20 GB)']))
        self.assertEqual((g['Cuphead']['installed'], g['Cuphead']['game_id']), (True, 'hydra:1'))
        self.assertFalse(g['Hades']['installed'])                # gone from its source


class Data(unittest.TestCase):
    def test_every_game_has_requirements_and_a_source_flag(self):
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {'HOME': home, 'XDG_CONFIG_HOME': home, 'XDG_DATA_HOME': home}):
            d = compat.data()
        names = [g['n'] for g in d['list']] + [g['n'] for g in d['mystery']]
        self.assertEqual((len(d['list']), len(d['mystery'])), (35, 21))
        self.assertEqual(sorted(names), sorted(d['req']))
        self.assertTrue(all(q.get('s', 0) in (0, 1) for q in d['req'].values()))
        self.assertEqual(compat.gpu_info('geforce gtx 1650', d['gpu_table']), (39, 4))
        self.assertEqual(compat.gpu_info('geforce gtx 1650 super', d['gpu_table']), (52, 4))
        self.assertEqual(compat.cpu_score('Intel Core i5-10400F', 12, d['cpu_table']), 100)


if __name__ == '__main__':
    unittest.main()
