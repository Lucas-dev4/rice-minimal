#!/usr/bin/env python3
"""Exercise real session components without logging out or restarting Hyprland."""
# Teste na sessão real do scripts/session.py e da Waybar (manual).
import json
import os
import signal
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
results = []

def run(args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=30)
    results.append({'command': args, 'exit_code': p.returncode,
                    'output': (p.stdout+p.stderr)[-6000:]})
    if p.returncode:
        raise RuntimeError(results[-1])
    return p.stdout.strip()

try:
    original = run(['noctalia', 'msg', 'wallpaper-get'])
    wallpaper = str(Path.home()/'Imagens/Wallpapers/default-wallpaper.png')
    try:
        run(['waypaper', '--wallpaper', wallpaper])
        time.sleep(2)
        selected = run(['noctalia', 'msg', 'wallpaper-get'])
        assert Path(selected).resolve() == Path(wallpaper).resolve(), selected
        run(['waypaper', '--restore'])
        time.sleep(1)
        assert Path(run(['noctalia', 'msg', 'wallpaper-get'])).resolve() == Path(wallpaper).resolve()
    except Exception:
        if original:
            run(['noctalia', 'msg', 'wallpaper-set', original])
        raise
    with (ROOT/'diagnostico/waypaper-session.log').open('w') as log:
        gui = subprocess.Popen(['waypaper'], stdout=log, stderr=subprocess.STDOUT)
        try:
            time.sleep(3)
            assert gui.poll() is None, 'Waypaper GUI exited'
            clients = json.loads(run(['hyprctl','-j','clients']))
            assert any(c['pid'] == gui.pid for c in clients), 'Waypaper has no window'
        finally:
            if gui.poll() is None:
                gui.terminate()
                gui.wait(timeout=10)
    with (ROOT/'diagnostico/waybar-session.log').open('w') as log:
        supervisor = subprocess.Popen(['python3', str(ROOT/'scripts/session.py')], stdout=log, stderr=subprocess.STDOUT)
        try:
            time.sleep(12)
            assert supervisor.poll() is None, 'Waybar supervisor exited'
            layers = run(['hyprctl','-j','layers'])
            assert 'waybar' in layers.lower()
            assert not json.loads(run(['noctalia','msg','status']))['barVisible']
            run(['wpctl','get-volume','@DEFAULT_AUDIO_SINK@'])
        finally:
            if supervisor.poll() is None:
                supervisor.terminate()
                supervisor.wait(timeout=10)
        for _ in range(20):
            if json.loads(run(['noctalia','msg','status']))['barVisible']:
                break
            time.sleep(0.25)
        else:
            raise AssertionError('Fallback bar not restored')
    subprocess.run(['kitty','--title','rice-minimal-super-test','--detach','-e',str(Path.home()/'.local/bin/supers')],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=10)
    time.sleep(3)
    clients = json.loads(run(['hyprctl','-j','clients']))
    windows = [c for c in clients if c.get('initialTitle') == 'rice-minimal-super-test']
    assert windows, 'Super terminal did not open'
    for window in windows:
        # Only terminate Kitty processes created with our dedicated test title.
        os.kill(window['pid'], signal.SIGTERM)
    run(['python3',str(ROOT/'super/test_safety.py')])
    run(['python3',str(ROOT/'super/Supers'),'--check'])
    assert not run(['hyprctl','configerrors'])
    results.append({'session_tests':'passed', 'notes':'Waypaper selection/restore/GUI; Waybar layer and fallback; Kitty/Super window; audio query; Lua runtime'})
finally:
    (ROOT/'VALIDACAO-SESSAO.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(results[-1], indent=2))
