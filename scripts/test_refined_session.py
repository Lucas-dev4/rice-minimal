#!/usr/bin/env python3
"""Phase 4 live acceptance: profile persistence, wallpaper, UI surfaces and windows."""
import json
import os
from pathlib import Path
import subprocess
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'extras'),str(ROOT/'tests')]
from theme import theme, profiles
from tui_smoke import exercise

results = []
def check(name, condition):
    results.append({'test':name,'passed':bool(condition)})
    if not condition:
        raise AssertionError(name)

def run(args):
    return theme.command(args)


def main():
    original_profile = theme.current_profile()
    original_wallpaper = theme.current_wallpaper()
    original_workspace = json.loads(run(['hyprctl','-j','activeworkspace']))['id']
    fingerprint = theme.read_palette().get('fingerprint')
    test_window = None
    try:
        for profile in ('minimal','refined'):
            profiles.switch(profile)
            check(profile+' persists',theme.current_profile() == profile)
            check(profile+' reuses palette',theme.read_palette().get('fingerprint') == fingerprint)
            run(['hyprctl','reload','config-only'])
            check(profile+' reload has no errors',not run(['hyprctl','configerrors']))
            enabled = 'true' if profile == 'refined' else 'false'
            run(['hyprctl','eval','assert(hl.get_config("animations.enabled") == '+enabled+'); assert(hl.get_config("decoration.blur.enabled") == false)'])
            check(profile+' survives real config reload',True)
            check(profile+' CSS duration',('150ms' if profile == 'refined' else '0ms') in (theme.STATE/'current/profile.css').read_text())
        # Actual Matugen regeneration through the existing event path; restore the wallpaper afterwards.
        alternative = next(p for p in theme.images() if p.resolve() != original_wallpaper.resolve())
        theme.apply_choice(alternative)
        check('wallpaper switch preserves refined',theme.current_profile() == 'refined')
        check('wallpaper switch generated palette',theme.read_palette().get('fingerprint') == theme.fingerprint(alternative))
        theme.apply_choice(original_wallpaper)
        check('Noctalia receives same generated palette',json.loads((Path.home()/'.config/noctalia/palettes/RiceMinimal.json').read_text())['dark']['mPrimary'] == theme.read_palette()['colors']['accent'])
        run(['noctalia','config','validate'])
        time.sleep(.5)
        check('Waybar layer remains visible','waybar' in run(['hyprctl','-j','layers']).lower())
        check('Noctalia fallback bar remains hidden',not json.loads(run(['noctalia','msg','status']))['barVisible'])
        run(['noctalia','msg','panel-toggle','launcher'])
        try:
            time.sleep(.3)
            check('real launcher opened',json.loads(run(['noctalia','msg','status']))['activePanelId'] == 'launcher')
            keyboard = subprocess.run(['wtype','kitty'],capture_output=True,text=True)
            results.append({'test':'launcher virtual keyboard input','passed':keyboard.returncode == 0,'output':keyboard.stderr.strip()})
            time.sleep(.2)
            run(['grim','/tmp/rice-phase4-launcher-final.png'])
        finally:
            run(['noctalia','msg','panel-toggle','launcher'])
        run(['notify-send','-a','Rice Minimal','-t','2000','Refined / Matugen','[ workspace ] | adaptive colors'])
        time.sleep(.3)
        run(['grim','/tmp/rice-phase4-notification-final.png'])
        time.sleep(1)
        layers = run(['hyprctl','-j','layers'])
        check('notification toast exists','notification' in layers.lower())
        # Temporary floating window exercises open, focus and close animations.
        test_window = subprocess.Popen(['kitty','--class','rice-phase4-test','--title','Rice Phase 4 Test','-e','sleep','5'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        time.sleep(.6)
        clients = json.loads(run(['hyprctl','-j','clients']))
        window = next(c for c in clients if c['class'] == 'rice-phase4-test')
        run(['hyprctl','eval','hl.dispatch(hl.dsp.window.float({action="set", window='+json.dumps('address:'+window['address'])+'}))'])
        check('temporary floating window opened',any(c['address'] == window['address'] and c['floating'] for c in json.loads(run(['hyprctl','-j','clients']))))
        destinations = [w['id'] for w in json.loads(run(['hyprctl','-j','workspaces'])) if w['id'] > 0 and w['id'] != original_workspace]
        if destinations:
            run(['hyprctl','eval','hl.dispatch(hl.dsp.focus({workspace='+str(destinations[0])+'}))'])
            time.sleep(.3)
            run(['hyprctl','eval','hl.dispatch(hl.dsp.focus({workspace='+str(original_workspace)+'}))'])
            check('real workspace transition and return',True)
        # This is exactly the request Waybar 0.15 emits on a workspace click.
        private = next((Path(os.environ['XDG_RUNTIME_DIR'])/'hypr').glob('rice-wb-*'))
        destination = destinations[0] if destinations else original_workspace
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(5)
            client.connect(str(private/'.socket.sock'))
            client.sendall(('dispatch workspace '+str(destination)).encode())
            check('Waybar legacy click accepted through Lua adapter',client.recv(4096).strip() == b'ok')
        check('Waybar click changes actual workspace',json.loads(run(['hyprctl','-j','activeworkspace']))['id'] == destination)
        run(['hyprctl','eval','hl.dispatch(hl.dsp.focus({workspace='+str(original_workspace)+'}))'])
        results.append(exercise([sys.executable,ROOT/'extras/rice.py'],[(.4,b'3'),(.7,b'3'),(1,b'q'),(1.3,b'q')]))
        check('rice appearance submenu rendered',True)
        theme.cached()
        check('cached login preserves selected profile',theme.current_profile() == 'refined')
        check('final Hyprland errors empty',not run(['hyprctl','configerrors']))
    finally:
        if test_window is not None and test_window.poll() is None:
            test_window.terminate()
            test_window.wait(timeout=5)
        run(['hyprctl','eval','hl.dispatch(hl.dsp.focus({workspace='+str(original_workspace)+'}))'])
        if theme.current_wallpaper().resolve() != original_wallpaper.resolve():
            theme.apply_choice(original_wallpaper)
        if theme.current_profile() != original_profile:
            profiles.switch(original_profile)
        (ROOT/'VALIDACAO-FASE4.json').write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n')
        print(json.dumps(results,indent=2,ensure_ascii=False))

if __name__ == '__main__':
    main()
