#!/usr/bin/env python3
"""Real PTY navigation through every control module, without applying/locking."""
# Teste na sessão real da TUI do lw (manual).
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from tui_smoke import exercise

# Doctor runs separately; this traversal exercises its page without any repair.
keys=[b'1',b'q',b'2',b'q',b'3',b'3',b'q',b'4',b'1',b'q',b'q',b'6',b'1',b'q',b'q',b'7',b'1',b'q',b'4',b'q',b'q']
# The final q exits the root; all entries share the one original curses screen.
print(exercise([sys.executable,ROOT/'extras/rice.py'],[(.4+i*.16,k) for i,k in enumerate(keys)]))

print(exercise([sys.executable,ROOT/'extras/rice.py'],[(.4,b'2'),(.6,b'j'),(1.3,b'q'),(1.6,b'q')],size=(12,44),resizes=[(.8,6,24),(1.1,28,110)]))
