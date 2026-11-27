# Super

Esta pasta tem a implementação local que já funcionava, trazida para cá sem mudar o editor nem os ajudantes de segurança. `Supers`, `safe_io.py` e `test_safety.py` são iguais à versão local de antes da Fase 3.

O `~/.local/bin/supers` agora abre esta cópia. Os wrappers de compatibilidade na pasta `super/` original do projeto mantêm os pontos de entrada antigos funcionando. O clone do GitHub em `referencias/` não foi modificado nem enviado.

Escrita atômica, backups únicos, validação do Lua, checagem de conflito e de edição simultânea e `supers --restore CAMINHO` continuam. Expressões Lua dinâmicas ficam fora da edição estática. Rode `supers --check` ou `python3 extras/supers/test_safety.py` para validar.
