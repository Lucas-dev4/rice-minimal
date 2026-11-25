# Baseline dos testes

Testes que já falhavam antes do trabalho de módulos. Só conta como regressão o que não está aqui.

- Comando: `python3 -m unittest discover -s tests -q`
- Data: 2026-11-25, commit `fix(jogos): sessão curta aparece na ficha e ao reabrir o LW` (branch `modulos`), Python 3.14.10
- Resultado: 306 testes, 0 falhas, 0 erros, 0 pulados; igual em 3 execuções seguidas

Baseline verde: qualquer falha ou erro daqui em diante é regressão.

## Falhas

Nenhuma. As 2 que existiam em `9705944` foram resolvidas:

- `test_install.Install.test_live_system_has_nothing_pending`: o bloco do Antigravity CLI saiu do `~/.config/fish/config.fish` para `~/.config/fish/conf.d/antigravity.fish`.
- `test_integrity.Integrity.test_integrity_list_matches_the_files`: `config/integrity.json` atualizado com o `extras/games.py` do commit `e234cfb`.

## Erros

Nenhum.
