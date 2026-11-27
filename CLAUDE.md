# CLAUDE.md — rice-minimal / LW

Responda em português do Brasil. Seja direto; se eu estiver errado, diga.

## O que é
Ambiente CachyOS + Hyprland com um app de controle, o **LW**:
- `extras/` — Python. O comando `lw` instalado é o `extras/rice.py` (TUI sem argumentos); os subcomandos com `--json` ficam em `extras/cli.py`, para onde o `rice.py` repassa.
- `gui/` — Quickshell/QML. `gui/shell.qml` é a janela; telas em `gui/screens/` (SISTEMA), `gui/player/` (MÚSICA), `gui/arcade/` (JOGOS); cores, fontes e tempos só em `gui/Theme.qml`.
- `config/` — configs gerenciadas (hypr, kitty, fish, waybar, nvim…). `scripts/` — install, restore, integridade.
- `docs/` — protótipos HTML (`lw-prototype.html`, `lw-jogos-prototype.html`, `prototipos/lw-*.html`). São a referência visual de toda tela nova.

## Regras que não se quebram
- **A GUI não tem lógica.** Toda ação é `lw <cmd> --json`, com o envelope `{"ok","action","data","warnings"}` ou `{"ok": false, "error"}`. Tela nova = subcomando novo + teste em `tests/test_cli_json.py`.
- **Nunca** mexer em PAM, senha, boot, kernel, partições, drivers, nem rodar `sudo`. Se algo precisar de pacote, escreva o `sudo pacman -S …` para eu rodar.
- Escrita de arquivo do usuário: atômica (temp + rename) e com backup antes, como o código já faz.
- Edições mínimas no que existe. Não reformatar nem renomear o que não faz parte da tarefa.
- Comandos de shell/sed em vez de pedir edição manual.
- Não apagar nada em `~/.local/state/rice-minimal/` nem backups.

## Testes
- Rodar: `python3 -m unittest discover -s tests -q`
- `docs/BASELINE.md` lista os testes que já falhavam antes do trabalho de módulos. Só conta como regressão o que não está lá.
- `scripts/test_*.py` mexem na sessão real (Waybar, Noctalia): **não rode** sem eu pedir.

## Plano em andamento (branch `modulos`)
O LW está virando um produto modular. Ordem e prompts em `SESSOES.md`; o contrato de módulo fica em `docs/modulos.md` (criado na sessão 1).
- Uma tarefa por sessão. Em tarefa grande: **plano primeiro, espere meu ok, depois código.**
- Dados pessoais (caminhos como `~/Músicas`, `~/Jogos/ROMs`, listas de jogos) saem do código para `~/.config/lw/config.toml`, com o valor atual como padrão.
- Se o contrato de módulo não der conta de algo, pare e me diga; não contorne mexendo no núcleo.
- No fim da sessão: testes passando (fora a baseline), um commit na branch `modulos` com mensagem em pt-BR no estilo do log (`feat(musica): …`, `refactor(lw): …`), e um resumo de 5 linhas do que mudou e do que ficou pendente.

## Estilo
- Python 3 só com a biblioteca padrão, salvo o que já é usado.
- Comentários seguem o arquivo: comentário de topo em pt-BR explicando o arquivo; não misture idiomas num arquivo novo (use pt-BR).
- Nome de módulo diz o que faz para quem não me conhece (ex.: "Dispositivos", não "Mecânicas").
