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
