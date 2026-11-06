#!/usr/bin/env python3
"""Real-session acceptance tests, restoring the starting wallpaper on completion."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'extras'),str(ROOT/'tests')]
from theme import theme
from tui_smoke import exercise

RESULTS = []
def run(args):
    p = subprocess.run([str(a) for a in args],capture_output=True,text=True,timeout=45)
    RESULTS.append({'command':[str(a) for a in args],'exit_code':p.returncode,'output':(p.stdout+p.stderr)[-4000:]})
    if p.returncode:
        raise RuntimeError(RESULTS[-1])
    return p.stdout.strip()

def wait_palette(wallpaper):
    target = str(wallpaper.resolve())
    for _ in range(100):
        p = theme.read_palette()
        if p.get('wallpaper') == target and theme.current_wallpaper().resolve() == wallpaper.resolve():
            return p
        time.sleep(.1)
    raise AssertionError('Wallpaper hook did not finish: '+str(wallpaper))

def test_menu():
    before = (theme.STATE/'current').resolve()
    result = exercise([Path.home()/'.local/bin/rice'],[
        (.5,b'2'),(.9,b'q'),(1.2,b'4'),(1.5,b'1'),(1.8,b'q'),(2.1,b'2'),(4,b'3'),(5,b'3'),(6,b'q'),(6.3,b'q')])
    assert (theme.STATE/'current').resolve() != before, 'Menu did not regenerate'
    assert json.loads((theme.STATE/'status.json').read_text())['result'] == 'restored', 'Menu did not restore'
    return result

def main():
    original = theme.current_wallpaper()
    assert original
    changed = False
    try:
        run(['hyprctl','reload','config-only'])
        run([sys.executable,ROOT/'extras/theme/theme.py','regenerate'])
        first = wait_palette(original)
        assert first['generator'].startswith('matugen'), first
        assert not run(['hyprctl','configerrors'])
        RESULTS.append({'test':'initial colors generated','palette':first})
        import gi
        gi.require_version('Gtk','3.0')
        from gi.repository import Gtk
        Gtk.CssProvider().load_from_data((ROOT/'config/waybar/style.css').read_bytes())
        RESULTS.append({'test':'complete Waybar CSS parsed by GTK3','passed':True})
        # Start from an explicit search so Enter chooses a known existing image.
        choices = theme.images()
        chosen = next(p for p in choices if p.resolve() != original.resolve())
        changed = True
        RESULTS.append(exercise([Path.home()/'.local/bin/wallpapers'],
            [(1,('/'+chosen.name+'\n').encode()),(1.5,b'\n'),(5,b'q')]))
        selected = wait_palette(chosen)
        assert theme.selected_wallpaper().resolve() == chosen.resolve()
        listed = json.loads(run(['waypaper','--list']))
        assert any(Path(x['wallpaper']).expanduser().resolve() == chosen.resolve() for x in listed), listed
        RESULTS.append({'test':'TUI Enter -> Waypaper state -> Noctalia -> palette','passed':True})
        # GUI and --restore use the configured asynchronous hook, with no TUI shortcut.
        run(['waypaper','--wallpaper',original])
        restored = wait_palette(original)
        assert restored['fingerprint'] == first['fingerprint']
        run(['waypaper','--restore'])
        time.sleep(1)
        assert theme.read_palette()['fingerprint'] == restored['fingerprint']
        RESULTS.append({'test':'Waypaper hook and --restore','passed':True})
        before = (theme.STATE/'current').resolve()
        run([sys.executable,ROOT/'extras/theme/theme.py','restore'])
        assert theme.read_palette()['fingerprint'] == selected['fingerprint']
        run([sys.executable,ROOT/'extras/theme/theme.py','restore'])
        assert (theme.STATE/'current').resolve() == before
        RESULTS.append({'test':'previous theme restoration and return','passed':True})
        with tempfile.TemporaryDirectory(prefix='rice-filename-') as directory:
            special = Path(directory)/"retro ' ; $monitor $(touch SHOULD_NOT_EXIST).png"
            special.symlink_to(original.resolve())
            # Selection remains the original image; exercise literal characters through Waypaper.
            theme.apply_choice(special)
            assert theme.selected_wallpaper().resolve() == original.resolve()
            assert not (ROOT/'SHOULD_NOT_EXIST').exists()
            theme.apply_choice(original)
        RESULTS.append({'test':'literal spaces, quotes, semicolon and dollar expressions through Waypaper','passed':True})
        previous = (theme.STATE/'current').resolve()
        theme.cached(restore_wallpaper=True)
        assert (theme.STATE/'current').resolve() == previous
        RESULTS.append({'test':'login cached palette + shared wallpaper restore, no Matugen','passed':True})
        run(['kitty','+runpy', 'from kitty.config import load_config; o=load_config("/home/lucas/.config/kitty/kitty.conf"); assert o.background_opacity == 0.85; print(o.background, o.foreground, o.background_opacity)'])
        run(['fish','-n',Path.home()/'.config/fish/config.fish'])
        run(['fish','-c','source ~/Projetos/rice-minimal/extras/theme/rice-adaptive.fish; test -n "$rice_prompt_color"; or exit 1; echo $rice_prompt_color'])
        colors = theme.read_palette()['colors']
        script = f"assert(vim.api.nvim_get_hl(0, {{name='Normal'}}).fg == {int(colors['foreground'][1:],16)}); assert(vim.o.number); assert(vim.o.shiftwidth == 4)"
        run(['nvim','--headless','-c','lua '+script,'+qa'])
        RESULTS.append(test_menu())
        RESULTS.append({'test':'rice menu opens Super/palette, regenerates and restores twice','passed':True})
        RESULTS.append(exercise([Path.home()/'.local/bin/supers'],[(1,b'q')]))
        run([Path.home()/'.local/bin/supers','--check'])
        run([sys.executable,ROOT/'extras/supers/test_safety.py'])
        status = json.loads(run(['noctalia','msg','status']))
        assert not status['barVisible'], status
        layers = json.loads(run(['hyprctl','-j','layers']))
        assert 'waybar' in json.dumps(layers).lower()
        run(['hyprctl','eval','assert(hl.get_config("general.border_size") == 1); '
             'assert(hl.get_config("decoration.blur.enabled") == false); '
             'assert(hl.get_config("decoration.rounding") == 0); '
             'assert(hl.get_config("animations.enabled") == false)'])
        assert not run(['hyprctl','configerrors'])
        RESULTS.append({'test':'session acceptance','passed':True,'original_wallpaper_preserved':True})
    finally:
        if changed and theme.current_wallpaper().resolve() != original.resolve():
            theme.apply_choice(original)
        (ROOT/'VALIDACAO-FASE3.json').write_text(json.dumps(RESULTS,indent=2,ensure_ascii=False)+'\n')
        print(json.dumps(RESULTS[-1],indent=2))

if __name__ == '__main__':
    if '--menu-only' in sys.argv:
        result = test_menu()
        result['test'] = 'menu actions verified by generation change and restored status'
        evidence = ROOT/'VALIDACAO-FASE3.json'
        records = json.loads(evidence.read_text())
        records.append(result)
        evidence.write_text(json.dumps(records,indent=2,ensure_ascii=False)+'\n')
        print(json.dumps(result,indent=2))
    else:
        main()
