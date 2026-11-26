# Pendências

Decisões tomadas sem confirmar, sempre pela opção mais conservadora (manter o comportamento de antes), e coisas achadas no caminho que ficaram como estavam. Apague o item quando resolver.

## Sessão 4 (MÚSICA), 2026-11-24

### Decidido sem confirmar

- **`left()` virou `exited()` no gancho.** O nome do contrato não funciona: `left` já é uma âncora final do `Item`, e chamá-lo lança erro (o `entered()` seguinte nem rodava). Nenhum módulo usava.
- **O `main()` de `library.py`, `organize.py`, `radio.py` e `ytdl.py` continua.** A GUI não usa mais, mas os testes usam e o `lw download` chama o do `ytdl.py`. Dá para tirar depois, levando os testes para `cli.main`.

### Achado e não mexido

- **O `ffmpeg` que o `yt-dlp` lança** não recebe o aviso do kernel: se o LW fechar no meio de uma conversão, ela pode seguir até acabar (não testado). O `yt-dlp` já morre junto com o `lw`.
- **`Downloads.dest`** não é usado por nenhuma tela; só passou a seguir `music.dir`.

## Sessão 5 (JOGOS), 2026-11-25

### Decidido

- **Contas no QML** (`Games.qml`, `StatsView.qml`, `InstallSheet.qml`) ficaram como exceção provisória do contrato. Mover as semanas e as recomendações para o Python é uma sessão própria.
- **O `main()` do `games.py` continua:** o vigia (`watch`) e a instalação (`install-run`) rodam por ele, e os testes o usam.
- **`games-config.json`:** o `games.py` ainda o lê, mas os textos da janela só veem o `config.toml`.

### Achado e não mexido

- **Prefixos em `+ JOGO`:** só aparecem `~/.wine*` e os de `prefix_dir` que já rodaram com Proton (têm `pfx`). Um prefixo instalado só com o Wine não entra na lista.
- **Aviso do `OnlineScreen.qml:56`** no log, de vez em quando, ao sair de ONLINE antes de uma resposta (`indexOf` de `undefined`). Já existia; é de MÚSICA.
- **Jogo da Steam com Proton:** a sessão vive enquanto o `reaper` viver. Se o Wine demorar a sair depois do jogo, esse tempo conta (não testado com jogo real de Windows).
- **Centuries Demo, 25/11:** a sessão 16:53–17:06 tem uns 5 min a mais (a Steam aberta contava antes do fix). O `games.json` não foi editado.

## Sessão 6 (escolher módulos e doctor), 2026-11-25

### Decidido

- **Desligar MÚSICA não para o cliamp** que já toca; a Waybar ainda o pausa (clique direito).
- **`settings.py` tem o próprio `backup`/`write`**, iguais aos do `cliamp.py`: o núcleo não depende de um módulo. Dá para o `cliamp.py` passar a usar os do `settings.py`.

### Achado e não mexido

- **`waypaper` e `ryujinx`** estão no repositório do CachyOS, não no do Arch: no Arch puro a linha do `pacman` falha (sessão 13).
- **Tela DOCTOR:** `↑↓` não rola a lista quando a seleção sai da área visível. Já existia.

## Sessão 7 (`lw setup` e teste na VM), 2026-11-25

### Decidido

- **Teclas do `lw setup`:** painel dos módulos e mini painel das dependências (`Tab` troca); `Espaço` liga/desliga ou marca; `i` instala o que está marcado (as obrigatórias que faltam já vêm marcadas). Textos e mapa das teclas em pt-BR, diferente da TUI do `lw`, que é em inglês.
- **Instalada = o programa existe** (mesma checagem do `lw doctor`), não `pacman -Q`.

### Achado e não mexido

- **Waybar com `/home/lucas` fixo:** o `scripts/session.py` abre a Waybar com `config/waybar/*` do repositório, sem trocar o caminho. Numa máquina com outro usuário, o módulo LW e as cores da barra quebram (`docs/teste-vm.md`).
- **`extras/theme/README.md`, `extras/supers/README.md` e `extras/wallpapers/README.md`** ainda estão em inglês e descrevem fases antigas.
- **`CLAUDE.md`** diz que `extras/cli.py` é o comando `lw`; quem o instala é o `extras/rice.py`, que repassa ao `cli.py`.
