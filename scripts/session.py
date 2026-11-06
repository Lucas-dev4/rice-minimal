#!/usr/bin/env python3
"""Supervise Waybar while keeping Noctalia services and a fallback bar."""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from waybar_ipc import compatible_environment

ROOT = Path(__file__).resolve().parents[1]

def main():
    runtime = Path(os.environ['XDG_RUNTIME_DIR'])
    with (runtime / 'rice-minimal.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        # The existing Hyprland autostart remains responsible for Noctalia.
        for _ in range(60):
            if subprocess.run(['noctalia', 'msg', 'status'], capture_output=True).returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError('Noctalia IPC unavailable; keeping its bar unchanged')
        subprocess.run(['python3', str(ROOT/'extras/theme/theme.py'),
                        'cached', '--restore-wallpaper'], check=True)
        if subprocess.run(['pgrep', '-x', 'waybar'], capture_output=True).returncode == 0:
            raise RuntimeError('Another Waybar is already running')
        with compatible_environment() as waybar_environment:
            child = subprocess.Popen(['waybar', '-c', str(ROOT/'config/waybar/config.jsonc'),
                                      '-s', str(ROOT/'config/waybar/style.css')], env=waybar_environment)
            def stop(*_):
                child.terminate()
            signal.signal(signal.SIGTERM, stop)
            signal.signal(signal.SIGINT, stop)
            try:
                for _ in range(40):
                    if child.poll() is not None:
                        raise RuntimeError('Waybar exited before becoming ready')
                    layers = subprocess.check_output(['hyprctl', '-j', 'layers'], text=True)
                    if 'waybar' in layers.lower():
                        subprocess.run(['noctalia', 'msg', 'bar-hide'], check=True)
                        break
                    time.sleep(0.25)
                else:
                    raise RuntimeError('Waybar layer did not appear')
                child.wait()
            finally:
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
                subprocess.run(['noctalia', 'msg', 'bar-show'], check=False)

if __name__ == '__main__':
    main()
