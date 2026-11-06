# Super

This directory contains the existing functional local implementation, moved here without changing its editor or safety helpers. `Supers`, `safe_io.py` and `test_safety.py` match the pre-Phase-3 local version.

`~/.local/bin/supers` now launches this copy. Compatibility wrappers in the original project `super/` keep previous entrypoints working. The GitHub clone under `referencias/` was not modified or pushed.

Atomic writes, unique backups, Lua validation, conflict/concurrent-edit checks and `supers --restore PATH` are preserved. Dynamic Lua expressions remain outside static editing. Run `supers --check` or `python3 extras/supers/test_safety.py` for validation.
