import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'extras'))
import bluetooth  # noqa: E402


class BluetoothTest(unittest.TestCase):
    def test_devices_and_info_parse(self):
        self.assertEqual(bluetooth.parse_devices('Device 84:67:a8:98:f3:51 AZ09\njunk\n'), [('84:67:A8:98:F3:51', 'AZ09')])
        info = bluetooth.parse_info("""Device 84:67:A8:98:F3:51 (public)
\tName: AZ09
\tAlias: AZ09
\tIcon: audio-headset
\tPaired: yes
\tTrusted: no
\tConnected: yes
\tBattery Percentage: 0x64 (100)""")
        self.assertEqual(info, {'Name': 'AZ09', 'Alias': 'AZ09', 'Icon': 'audio-headset', 'Paired': True,
                                'Trusted': False, 'Connected': True, 'Battery': 100})

    def test_row_shows_dash_without_data(self):
        line = bluetooth.row({'mac': 'AA:BB:CC:DD:EE:FF', 'name': 'Novo'})
        self.assertIn('novo', line)
        self.assertIn('—', line)
        self.assertIn('AA:BB:CC:DD:EE:FF', line)


if __name__ == '__main__':
    unittest.main()
