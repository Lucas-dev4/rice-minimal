#!/usr/bin/env python3
"""Exercise real curses UIs in a controlling PTY, without applying images."""
# Teste rápido das TUIs em curses (abrem e fecham sem erro).
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import signal
import struct
import sys
import termios
import time

ROOT = Path(__file__).resolve().parents[1]

def exercise(args, actions, size=(24,100), resizes=()):
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.execvp(str(args[0]), [str(a) for a in args])
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH',*size,0,0))
    output = bytearray()
    started = time.monotonic()
    pending = list(actions)
    resize_pending = list(resizes)
    status = None
    try:
        while time.monotonic()-started < 12:
            elapsed = time.monotonic()-started
            while resize_pending and elapsed >= resize_pending[0][0]:
                _,rows,columns=resize_pending.pop(0)
                fcntl.ioctl(fd,termios.TIOCSWINSZ,struct.pack('HHHH',rows,columns,0,0))
                os.kill(pid,signal.SIGWINCH)
            while pending and elapsed >= pending[0][0]:
                _, keys = pending.pop(0)
                os.write(fd, keys)
            if select.select([fd], [], [], .05)[0]:
                try:
                    block = os.read(fd,65536)
                    output.extend(block)
                except OSError:
                    pass
            done, value = os.waitpid(pid, os.WNOHANG)
            if done:
                status = os.waitstatus_to_exitcode(value)
                break
        if status is None:
            os.kill(pid,signal.SIGTERM)
            os.waitpid(pid,0)
            raise AssertionError(f'PTY timeout: {args}')
        if status != 0 or b'Traceback' in output or b'Error:' in output:
            raise AssertionError(f'PTY failed ({status}): {bytes(output)[-1800:]!r}')
        return {'program':str(args[-1]),'exit_code':status,'bytes_rendered':len(output)}
    finally:
        os.close(fd)

def main():
    results = []
    results.append(exercise([sys.executable,ROOT/'extras/wallpapers/wallpaper_tui.py'],
        [(1,b'j'),(1.2,b'k'),(1.4,b'/wall'),(1.6,b'\n'),(1.8,b'r'),(2,b'q')]))
    results.append(exercise([sys.executable,ROOT/'extras/rice.py'],
        [(1,b'3'),(1.3,b'j'),(1.6,b'q'),(1.9,b'1'),(2.2,b'q'),(2.5,b'q')]))
    results.append(exercise([sys.executable,ROOT/'extras/supers/Supers'],[(1,b'q')]))
    print(json.dumps(results,indent=2))

if __name__ == '__main__':
    main()
