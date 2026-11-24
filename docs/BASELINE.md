# Baseline dos testes

Testes que já falhavam antes do trabalho de módulos. Só conta como regressão o que não está aqui.

- Comando: `python3 -m unittest discover -s tests -q`
- Data: 2026-11-24, commit `9705944` (branch `modulos`), Python 3.14.10
- Resultado: 216 testes, 2 falhas, 0 erros, 0 pulados; igual em 3 execuções seguidas

## Falhas

- `test_install.Install.test_live_system_has_nothing_pending`: o `~/.config/fish/config.fish` do sistema tem no fim um bloco "Added by Antigravity CLI installer" (um `set -gx PATH`) que o repositório não tem, então `install.plan()` não volta vazio.
- `test_integrity.Integrity.test_integrity_list_matches_the_files`: `extras/games.py` mudou no commit `e234cfb` sem atualizar `config/integrity.json` (falta rodar `scripts/integrity.py`).

## Erros

Nenhum.
