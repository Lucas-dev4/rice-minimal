# Testes dos manifestos dos módulos (extras/modules.py, contrato em docs/modulos.md).
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'extras'))
import modules  # noqa: E402


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


if __name__ == '__main__':
    unittest.main()
