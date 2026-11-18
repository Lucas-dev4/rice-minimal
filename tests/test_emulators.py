# Testes do emulators.py: edição de INI/cfg/JSON sem estragar o resto, backups, controle
# como player 1, detecção de controles, índices SDL do teste ao vivo e controllers.txt.
import io
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'extras'))
import emulators  # noqa: E402

GAMESIR = '''I: Bus=0003 Vendor=3537 Product=1041 Version=0111
N: Name="GameSir Nova Lite"
P: Phys=usb-0000:00:14.0-2/input0
H: Handlers=event21 js0
B: EV=1b

I: Bus=0011 Vendor=0001 Product=0001 Version=ab41
N: Name="AT Translated Set 2 keyboard"
H: Handlers=sysrq kbd event3 leds
B: EV=120013
'''


class Emulators(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)/'home'
        self.root = Path(self.tmp.name)/'root'
        self.home.mkdir()
        self.root.mkdir()
        for p in (patch.dict(os.environ, {'HOME': str(self.home), 'XDG_CONFIG_HOME': str(self.home/'.config'),
                                          'XDG_DATA_HOME': str(self.home/'.local/share'),
                                          'XDG_STATE_HOME': str(self.home/'.local/state')}),
                  patch.object(emulators, 'ROOT', self.root),
                  patch.object(emulators.shutil, 'which', lambda name: '/usr/bin/' + name)):
            p.start()
            self.addCleanup(p.stop)

    def file(self, rel, text):
        path = self.home/rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def by_id(self):
        return {e['id']: e for e in emulators.listing()['emulators']}

    def test_ini_set_changes_only_the_key(self):
        text = '[UI]\nStartFullscreen = true\n\n[Pad1]\nType = DualShock2\n'
        self.assertEqual(emulators.ini_set(text, 'UI', 'StartFullscreen', 'false'), '[UI]\nStartFullscreen = false\n\n[Pad1]\nType = DualShock2\n')
        self.assertEqual(emulators.ini_set(text, 'UI', 'HideMouseCursor', 'true'),
                         '[UI]\nStartFullscreen = true\nHideMouseCursor = true\n\n[Pad1]\nType = DualShock2\n')
        self.assertTrue(emulators.ini_set(text, 'EmuCore/GS', 'upscale_multiplier', '3').endswith('\n[EmuCore/GS]\nupscale_multiplier = 3\n'))
        cfg = 'video_fullscreen = "true"\nmenu_driver = "xmb"\n'
        self.assertEqual(emulators.ini_set(cfg, None, 'video_vsync', 'false', quote=True), cfg + 'video_vsync = "false"\n')
        self.assertEqual(emulators.ini_get(cfg, None, 'video_fullscreen'), 'true')

    def test_set_writes_each_emulator_format_with_a_backup(self):
        pcsx2 = self.file('.config/PCSX2/inis/PCSX2.ini', '[UI]\nStartFullscreen = true\n')
        self.file('.config/dolphin-emu/Dolphin.ini', '[Display]\nFullscreen = True\n')
        retro = self.file('.config/retroarch/retroarch.cfg', 'video_fullscreen = "true"\n')
        ryu = self.file('.config/Ryujinx/Config.json', json.dumps({'version': 72, 'res_scale': 1, 'vsync_mode': 0, 'start_fullscreen': True}))
        e = self.by_id()
        self.assertEqual({s['key']: s['value'] for s in e['retroarch']['settings']}, {'fullscreen': True, 'vsync': True, 'fps': False})
        self.assertEqual(e['shadps4']['settings'], [])
        r = emulators.set_value('pcsx2', 'res', '3')
        self.assertIn('[EmuCore/GS]\nupscale_multiplier = 3', pcsx2.read_text())
        self.assertEqual(Path(r['backup']).read_text(), '[UI]\nStartFullscreen = true\n')
        emulators.set_value('pcsx2', 'vsync', 'true')
        self.assertIn('VsyncEnable = true', pcsx2.read_text())
        emulators.set_value('dolphin', 'res', '2')
        self.assertEqual((self.home/'.config/dolphin-emu/GFX.ini').read_text(), '[Settings]\nInternalResolution = 2\n')
        emulators.set_value('retroarch', 'vsync', 'false')
        self.assertIn('video_vsync = "false"', retro.read_text())
        emulators.set_value('ryujinx', 'vsync', 'false')
        emulators.set_value('ryujinx', 'res', '2')
        doc = json.loads(ryu.read_text())
        self.assertEqual((doc['vsync_mode'], doc['enable_vsync'], doc['res_scale'], doc['version']), (1, False, 2, 72))
        with self.assertRaises(ValueError):
            emulators.set_value('pcsx2', 'res', '7')
        with self.assertRaises(ValueError):
            emulators.set_value('retroarch', 'res', '2')
        with self.assertRaisesRegex(ValueError, 'abra o PPSSPP'):
            emulators.set_value('ppsspp', 'fullscreen', 'true')

    def test_apply_pad_pcsx2_and_dolphin(self):
        pcsx2 = self.file('.config/PCSX2/inis/PCSX2.ini', '[UI]\nStartFullscreen = true\n')
        dolphin = self.file('.config/dolphin-emu/Dolphin.ini', '[Display]\nFullscreen = True\n')
        emulators.apply_pad('pcsx2')
        text = pcsx2.read_text()
        self.assertIn('[InputSources]\nSDL = true', text)
        self.assertIn('Cross = SDL-0/FaceSouth', text)
        self.assertIn('StartFullscreen = true', text)
        (self.root/'proc/bus/input').mkdir(parents=True)
        (self.root/'proc/bus/input/devices').write_text(GAMESIR)
        emulators.apply_pad('dolphin')
        pad = (self.home/'.config/dolphin-emu/GCPadNew.ini').read_text()
        self.assertIn('Device = SDL/0/GameSir Nova Lite', pad)
        self.assertIn('Buttons/A = `Button S`', pad)
        self.assertIn('[Core]\nSIDevice0 = 6', dolphin.read_text())
        with self.assertRaises(ValueError):
            emulators.apply_pad('ryujinx')

    def test_pads_guid_mapping_and_battery(self):
        self.assertEqual(emulators.sdl_guid(3, 0x3537, 0x1041, 0x0111), '03000000373500004110000011010000')
        (self.root/'proc/bus/input').mkdir(parents=True)
        (self.root/'proc/bus/input/devices').write_text(GAMESIR)
        battery = self.root/'sys/class/input/event21/device/device/power_supply/hid-x-battery'
        battery.mkdir(parents=True)
        (battery/'capacity').write_text('80\n')
        self.file('.local/share/lw/controllers.txt', '# c\n03000000373500004110000000000000,GameSir Nova Lite,a:b0,platform:Linux,\n')
        pads = emulators.pads()['pads']
        self.assertEqual(len(pads), 1)                                     # the keyboard is not a pad
        self.assertEqual((pads[0]['name'], pads[0]['event'], pads[0]['id'], pads[0]['mapped'], pads[0]['battery']),
                         ('GameSir Nova Lite', 'event21', '3537:1041', True, 80))

    def test_layout_and_watch_give_sdl_indices(self):
        caps = self.root/'sys/class/input/event5/device/capabilities'
        caps.mkdir(parents=True)
        # BTN_SOUTH (0x130), BTN_EAST (0x131) and BTN_TRIGGER_HAPPY1 (0x2c0); ABS_X, ABS_Y, ABS_HAT0X, ABS_HAT0Y.
        key = (1 << 0x130) | (1 << 0x131) | (1 << 0x2c0)
        words = [f'{(key >> (64*i)) & (2**64 - 1):x}' for i in range(12)]
        (caps/'key').write_text(' '.join(reversed(words)) + '\n')
        (caps/'abs').write_text(f'{(1 << 0) | (1 << 1) | (1 << 0x10) | (1 << 0x11):x}\n')
        buttons, axes = emulators.layout('event5')
        self.assertEqual((buttons, axes), ({0x130: 0, 0x131: 1, 0x2c0: 2}, {0: 0, 1: 1}))
        dev = self.root/'dev/input/event5'
        dev.parent.mkdir(parents=True)
        ev = lambda kind, code, value: struct.pack('llHHi', 0, 0, kind, code, value)
        dev.write_bytes(ev(1, 0x131, 1) + ev(3, 0x10, -1) + ev(3, 0, 32767) + ev(0, 0, 0))
        out = io.StringIO()
        emulators.watch('event5', out)
        lines = [json.loads(l) for l in out.getvalue().splitlines()]
        self.assertEqual(lines, [{'ready': True, 'buttons': 3, 'axes': 2}, {'t': 'b', 'i': 1, 'v': 1},
                                 {'t': 'h', 'i': 0, 'v': 8}, {'t': 'a', 'i': 0, 'v': 1.0}])
        with self.assertRaises(ValueError):
            emulators.watch('../../etc/passwd')

    def test_pad_save_replaces_the_line_of_that_controller(self):
        path = self.file('.local/share/lw/controllers.txt', '# meu comentário\n03000000373500004110000011010000,Velho,a:b9,platform:Linux,\n')
        r = emulators.pad_save('03000000373500004110000011010000', 'GameSir, Nova', ['a=b0', 'dpup=h0.1', 'lefttrigger=a5', 'leftx=a0'])
        self.assertEqual(path.read_text(), '# meu comentário\n03000000373500004110000011010000,GameSir  Nova,a:b0,dpup:h0.1,lefttrigger:a5,leftx:a0,platform:Linux,\n')
        self.assertIn('Velho', Path(r['backup']).read_text())
        with self.assertRaises(ValueError):
            emulators.pad_save('03000000373500004110000011010000', 'X', ['a=rm -rf'])
        with self.assertRaises(ValueError):
            emulators.pad_save('nope', 'X', ['a=b0'])


if __name__ == '__main__':
    unittest.main()
