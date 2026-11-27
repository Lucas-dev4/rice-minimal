"""Visual safety, auth preservation, read-only diagnostics and single-session routing."""
# Testes gerais do projeto (nomes, arquivos esperados, regras que não podem quebrar).
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import tomllib
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extras'))
import lockscreen
import rice
import doctor
from theme import theme


class Final(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state=Path(self.temp.name)
        self.old=theme.STATE
        theme.STATE=self.state
        self.addCleanup(setattr,theme,'STATE',self.old)

    def test_lock_renderer_contains_only_visual_settings_and_native_login(self):
        rendered=lockscreen.render({'wallpaper':'/tmp/quoted " file.png'},'refined')
        data=tomllib.loads(rendered)
        self.assertEqual(set(data['lockscreen']),lockscreen.VISUAL_KEYS)
        self.assertEqual(data['lockscreen']['blur_intensity'],0)
        self.assertEqual([w['type'] for w in data['lockscreen_widgets']['widget'].values()],['login_box'])
        self.assertNotIn('font_family',rendered)
        self.assertTrue(any(w['type']=='login_box' for w in data['lockscreen_widgets']['widget'].values()))
        self.assertEqual(data['lockscreen']['wallpaper'],'/tmp/quoted " file.png')

    def test_auth_overrides_survive_visual_override_filter(self):
        original='''[lockscreen]
allow_empty_password = false
fingerprint = true
grace_period_seconds = 0
lock_before_suspend = true
blur_intensity = 0.7
[lockscreen_widgets]
enabled = false
[lockscreen_widgets.widget.test]
type = "label"
[shell]
polkit_agent = true
'''
        filtered=tomllib.loads(lockscreen.strip_visual_overrides(original))
        self.assertFalse(filtered['lockscreen']['allow_empty_password'])
        self.assertEqual(filtered['lockscreen']['grace_period_seconds'],0)
        self.assertTrue(filtered['lockscreen']['lock_before_suspend'])
        self.assertTrue(filtered['shell']['polkit_agent'])
        self.assertNotIn('lockscreen_widgets',filtered)

    def test_visual_snapshot_excludes_authentication_and_other_settings(self):
        snapshot=lockscreen.visual_snapshot('[lockscreen]\nfingerprint = false\ntint_intensity = 0.7\n[shell]\nfont_family = "old"\n[lockscreen_widgets]\nenabled = true\n')
        data=tomllib.loads(snapshot)
        self.assertEqual(data['lockscreen'],{'tint_intensity':.7})
        self.assertNotIn('shell',data)
        self.assertTrue(data['lockscreen_widgets']['enabled'])

    def test_lock_restore_preserves_later_profile_and_auth_choices(self):
        settings=self.state/'settings.toml'
        settings.write_text('[lockscreen]\nfingerprint = true\ntint_intensity = 0.8\n[shell.animation]\nenabled = false\n')
        config=self.state/'config';config.mkdir()
        backup=self.state/'backup';backup.mkdir()
        (backup/'settings.toml').write_text('[lockscreen]\nfingerprint = false\ntint_intensity = 0.3\n[shell.animation]\nenabled = true\n')
        (config/'rice-lock.toml').write_text('candidate')
        (self.state/'lock-enabled').write_text('enabled')
        with patch.object(lockscreen,'SETTINGS',settings),patch.object(lockscreen,'CONFIG',config),patch.object(theme,'command'),patch.object(theme,'reload_components'):
            lockscreen.restore(backup)
        data=tomllib.loads(settings.read_text())
        self.assertTrue(data['lockscreen']['fingerprint'])
        self.assertFalse(data['shell']['animation']['enabled'])
        self.assertEqual(data['lockscreen']['tint_intensity'],.3)
        self.assertFalse((config/'rice-lock.toml').exists())
        self.assertFalse((self.state/'lock-enabled').exists())

    def test_profile_changes_do_not_turn_on_lock_automatically(self):
        result=theme.render({'colors':theme.FALLBACK.copy(),'generator':'test'})
        self.assertIn('lockscreen.toml',result)
        self.assertFalse((self.state/'lock-enabled').exists())
        self.assertIn('rice_active_bg transparent',result['colors.css'])
        self.assertIn('rice_active_border transparent',result['colors.css'])

    def test_main_routes_super_in_same_screen_without_wrapper(self):
        screen=object()
        with patch.object(rice.ui,'setup'), patch.object(rice.ui,'choose',side_effect=[1,None]), patch.object(rice.shortcuts,'selector') as selector, patch.object(rice.curses,'wrapper') as wrapper:
            rice.menu(screen)
        selector.assert_called_once_with(screen)
        wrapper.assert_not_called()

    def test_cli_requires_confirmation_before_lock(self):
        with patch.object(sys,'argv',['rice','lock-trial']), patch.object(lockscreen,'trial') as trial:
            with self.assertRaises(SystemExit): rice.main()
        trial.assert_not_called()

    def test_standalone_theme_entrypoints_resolve_shared_package(self):
        for path,args in [('extras/theme/profiles.py',['current']),('extras/theme/theme.py',['show'])]:
            result=subprocess.run([sys.executable,str(theme.ROOT/path),*args],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_doctor_never_repairs_or_generates(self):
        calls=[]
        def run(args,**kwargs):
            calls.append([str(v) for v in args])
            return type('P',(),{'returncode':0,'stdout':'','stderr':''})()
        with patch.object(doctor.subprocess,'run',side_effect=run),patch.object(lockscreen,'validate',return_value='candidate valid'):
            doctor.inspect()
        joined=' '.join(' '.join(c) for c in calls)
        for forbidden in ('config-set','config-reload','regenerate','session lock','wallpaper-set'):
            self.assertNotIn(forbidden,joined)

    def test_doctor_stream_reports_every_result_in_order(self):
        def run(args,**kwargs):
            return type('P',(),{'returncode':0,'stdout':'','stderr':''})()
        seen=[]
        with patch.object(doctor.subprocess,'run',side_effect=run),patch.object(lockscreen,'validate',return_value='candidate valid'):
            results=doctor.inspect(seen.append)
        self.assertEqual(seen,results)
        self.assertGreater(len(results),20)


class Dependencies(unittest.TestCase):
    """O lw doctor e as dependências dos módulos ativos."""
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home=Path(temp.name)
        self.config=self.home/'lw/config.toml'
        self.config.parent.mkdir()
        env=patch.dict(doctor.os.environ,{'XDG_CONFIG_HOME':str(self.home)})
        env.start()
        self.addCleanup(env.stop)

    def check(self,missing=(),conflicts=()):
        """As linhas das dependências, com só essas faltando."""
        found=[]
        def located(dep):
            names=dep.get('command') or dep.get('python') or dep.get('font')
            return '' if names in missing else '/x'
        with patch.object(doctor,'located',side_effect=located),patch.object(doctor,'installed',side_effect=lambda names: set(names)&set(conflicts)):
            doctor.dependencies(lambda status,name,detail='',**extra: found.append({'status':status,'name':name,'detail':detail,**extra}))
        return found

    def test_every_active_module_is_checked_required_first(self):
        found=self.check()
        self.assertEqual({r['status'] for r in found},{'OK'})
        self.assertEqual(list(dict.fromkeys((r['module'],r['optional']) for r in found)),
                         [('system',False),('system',True),('music',False),('music',True),('games',True)])

    def test_module_and_name_identify_a_line(self):
        # É a chave da tela DOCTOR; o nome sozinho se repete (wpctl, zenity).
        found=self.check()
        keys=[(r['module'],r['name']) for r in found]
        self.assertEqual(len(keys),len(set(keys)))
        self.assertLess(len({r['name'] for r in found}),len(found))

    def test_a_module_turned_off_is_not_checked(self):
        self.config.write_text('[modules]\nmusic = false\n')
        found=self.check(missing=('cliamp','cava'))
        self.assertEqual({r['module'] for r in found},{'system','games'})

    def test_missing_required_fails_and_missing_optional_informs(self):
        found={r['name']:r for r in self.check(missing=('pactl','cava'))}
        self.assertEqual((found['pactl']['status'],found['cava']['status']),('FAIL','INFO'))
        self.assertIn('o visualizador',found['cava']['detail'])
        self.assertEqual((found['Pacotes obrigatórios']['status'],found['Pacotes obrigatórios']['detail']),('WARN','sudo pacman -S --needed libpulse'))
        self.assertEqual((found['Pacotes opcionais']['status'],found['Pacotes opcionais']['detail']),('INFO','sudo pacman -S --needed cava'))

    def test_each_package_is_asked_once(self):
        # wpctl é opcional em SISTEMA e obrigatório em MÚSICA; zenity e ffmpeg aparecem duas vezes.
        found=self.check(missing=('wpctl','zenity','ffmpeg','ffprobe',['ppsspp','PPSSPPSDL']))
        lines={r['name']:r['detail'] for r in found if 'module' not in r}
        self.assertEqual(lines,{'Pacotes obrigatórios':'sudo pacman -S --needed wireplumber',
                                'Pacotes opcionais':'sudo pacman -S --needed ffmpeg zenity ppsspp'})
        self.assertIn('ppsspp / PPSSPPSDL',[r['name'] for r in found])

    def test_a_conflicting_package_installed_fails_and_is_never_asked(self):
        # Máquina com o noctalia-shell: o qs existe (do noctalia-qs), mas não é o quickshell.
        found={r['name']:r for r in self.check(missing=('noctalia',),conflicts=('noctalia-qs','noctalia-shell'))}
        self.assertEqual(found['qs']['status'],'FAIL')
        self.assertIn('conflito · noctalia-qs instalado, que conflita com quickshell',found['qs']['detail'])
        self.assertIn('noctalia-shell instalado',found['noctalia']['detail'])
        self.assertNotIn('Pacotes obrigatórios',found)

    def test_what_is_not_a_package_says_its_own_way(self):
        found=self.check(missing=('cliamp',))
        item=next(r for r in found if r['name'] == 'cliamp')
        self.assertEqual(item['status'],'FAIL')
        self.assertIn('modules/music/README.md',item['detail'])
        self.assertEqual([r for r in found if 'module' not in r],[])

    def test_each_kind_of_dependency_is_located(self):
        self.assertTrue(doctor.located({'python':'json'}))
        self.assertEqual(doctor.located({'python':'nao_existe_x'}),'')
        self.assertEqual(doctor.located({'command':'nao-existe-x'}),'')
        self.assertTrue(doctor.located({'command':['nao-existe-x','sh']}))
        with patch.object(doctor.subprocess,'run',side_effect=FileNotFoundError('fc-list')):
            self.assertEqual(doctor.located({'font':'X'}),'')
        local=self.home/'.local/bin/meu-prog'
        local.parent.mkdir(parents=True)
        local.write_text('')
        local.chmod(0o755)
        with patch.object(doctor.Path,'home',return_value=self.home):
            self.assertEqual(doctor.located({'command':'meu-prog'}),str(local))

    def test_the_terminal_text_has_a_title_per_block(self):
        text=doctor.lines([{'status':'OK','name':'Sessão','detail':''},*self.check(missing=('pactl',))])
        self.assertEqual(text[:3],['[ OK ] Sessão','','SISTEMA — obrigatórias'])
        for title in ('SISTEMA — opcionais','MÚSICA — obrigatórias','MÚSICA — opcionais','JOGOS — opcionais'):
            self.assertIn(title,text)
        self.assertEqual(text[-2:],['INSTALAR','[ WARN ] Pacotes obrigatórios — sudo pacman -S --needed libpulse'])

if __name__ == '__main__': unittest.main()
