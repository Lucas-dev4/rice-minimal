# Testes dos manifestos dos módulos (extras/modules.py, contrato em docs/modulos.md).
import argparse
import importlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'extras'))
import modules  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


class Manifests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def manifest(self, folder, text):
        (self.base/folder).mkdir()
        (self.base/folder/'module.toml').write_text(text)

    def test_the_three_modules_are_valid(self):
        found, errors = modules.load()
        self.assertEqual(errors, [])
        self.assertEqual({k: m['name'] for k, m in found.items()},
                         {'system': 'SISTEMA', 'music': 'MÚSICA', 'games': 'JOGOS'})

    def test_the_contract_example_is_accepted(self):
        text = (Path(__file__).resolve().parents[1]/'docs/modulos.md').read_text()
        self.manifest('music', text.split('```toml\n', 1)[1].split('```', 1)[0])
        found, errors = modules.load(self.base)
        self.assertEqual(errors, [])
        self.assertEqual(found['music']['commands']['open'], 'music')

    def test_a_bad_manifest_is_left_out_and_the_rest_loads(self):
        good = 'id = "{0}"\nname = "X"\n'
        self.manifest('bom', good.format('bom'))
        self.manifest('campo', good.format('campo') + 'cor = "azul"\n')
        self.manifest('nome', good.format('outro'))
        self.manifest('quebrado', 'id = \n')
        self.manifest('semnome', 'id = "semnome"\n')
        self.manifest('tipo', good.format('tipo') + 'order = "1"\n')
        self.manifest('config', good.format('config') + '[config.dir]\ndescription = "sem padrão"\n')
        self.manifest('lista', good.format('lista') + '[config.dirs]\ndefault = [1]\n')
        self.manifest('dep', good.format('dep') + '[[dependency]]\ncomando = "x"\n')
        found, errors = modules.load(self.base)
        self.assertEqual(list(found), ['bom'])
        self.assertEqual(sorted(e.split(':')[0] for e in errors),
                         ['campo', 'config', 'dep', 'lista', 'nome', 'quebrado', 'semnome', 'tipo'])

    def test_order_is_the_sidebar_order(self):
        self.manifest('a', 'id = "a"\nname = "A"\norder = 30\n')
        self.manifest('b', 'id = "b"\nname = "B"\norder = 10\n')
        self.assertEqual(list(modules.load(self.base)[0]), ['b', 'a'])


class Contract(unittest.TestCase):
    """O que cada manifesto do repositório declara existe de verdade."""
    def setUp(self):
        self.found = modules.load()[0]

    def test_the_screens_and_the_hook_exist_and_the_folder_is_imported(self):
        shell = (ROOT/'gui/shell.qml').read_text()
        for m in self.found.values():
            folder = m['gui']['folder']
            files = [s['file'] for s in m['gui']['screens']] + ([m['gui']['hook']] if 'hook' in m['gui'] else [])
            for name in files:
                self.assertTrue((ROOT/'gui'/folder/name).is_file(), f'{m["id"]}: {name}')
            self.assertRegex(shell, rf'(?m)^import qs\.{folder}$')

    def test_the_handler_registers_exactly_the_declared_names(self):
        for m in self.found.values():
            if 'commands' not in m:
                continue
            actions = argparse.ArgumentParser().add_subparsers(dest='action')
            importlib.import_module(m['commands']['handler']).register(actions, argparse.ArgumentParser(add_help=False))
            self.assertEqual(sorted(actions.choices), sorted(m['commands']['names']))

    def test_no_command_has_two_owners(self):
        names = [n for m in self.found.values() for n in m.get('commands', {}).get('names', [])]
        names += [m['commands']['open'] for m in self.found.values() if 'open' in m.get('commands', {})]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names) & {'gui', 'doctor', 'modules'}, set())

    def test_the_declared_shortcuts_are_in_the_lua(self):
        lua = (ROOT/'config/hypr/rice-integration.lua').read_text()
        for m in self.found.values():
            for s in m.get('shortcut', []):
                self.assertRegex(lua, rf'hl\.bind\("{re.escape(s["keys"])}", .*/{re.escape(s["command"])}"\)')

    def test_each_dependency_has_one_check_and_one_way_out(self):
        for m in self.found.values():
            for d in m.get('dependency', []):
                self.assertEqual(sum(k in d for k in ('command', 'python', 'font')), 1, d)
                self.assertEqual(sum(k in d for k in ('package', 'aur', 'manual')), 1, d)
                self.assertTrue(d.get('why'), d)

    def test_the_window_starts_with_the_system_of_the_manifest(self):
        # gui/Modules.qml mostra SISTEMA antes de o "lw modules list" responder.
        text = (ROOT/'gui/Modules.qml').read_text()
        seed = json.loads(re.search(r'property var system: \((\{.*?\n    \})\)', text, re.S).group(1))
        system = self.found['system']
        self.assertTrue(system['required'])
        self.assertEqual(seed, {'id': 'system', 'name': system['name'], 'folder': system['gui']['folder'],
                                'hook': system['gui']['hook'], 'screens': system['gui']['screens'],
                                'config': {k: v['default'] for k, v in system.get('config', {}).items()}})

    def test_the_open_command_leads_to_its_module(self):
        self.assertEqual(modules.openers(), {'music': 'music'})

    def test_the_window_does_not_know_music(self):
        shell = (ROOT/'gui/shell.qml').read_text()
        self.assertEqual(re.findall(r'\b(?:Music|Spectrum|Downloads|inMusic)\b', shell), [])

    def test_the_music_screens_have_no_logic_of_their_own(self):
        # Nada chama os scripts direto nem escreve a pasta das músicas fixa.
        for path in (ROOT/'gui').glob('**/*.qml'):
            text = path.read_text()
            self.assertNotRegex(text, r'extras/(library|organize|radio|ytdl)\.py', path.name)
            self.assertNotIn('"yt-dlp", "', text, path.name)
            self.assertNotIn('Músicas', text, path.name)

    def test_every_hook_field_is_documented_and_exists(self):
        base = (ROOT/'gui/components/LwModule.qml').read_text()
        found = set(re.findall(r'(?m)^    (?:property \w+|signal|function) (\w+)', base))
        doc = (ROOT/'docs/modulos.md').read_text()
        table = doc.split('**Nenhum campo é obrigatório.**', 1)[1].split('Quem recebe o quê', 1)[0]
        named = set()
        for row in re.findall(r'(?m)^\| (`[^|]+?) \|', table):
            named |= set(re.findall(r'`(\w+)', row))
        self.assertEqual(found, named)


if __name__ == '__main__':
    unittest.main()
