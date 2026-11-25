# Pendências

Decisões tomadas sem confirmar, sempre pela opção mais conservadora (manter o comportamento de antes), e coisas achadas no caminho que ficaram como estavam. Apague o item quando resolver.

## Sessão 4 (MÚSICA), 2026-11-24

### Decidido sem confirmar

- **`left()` virou `exited()` no gancho.** O nome do contrato não funciona: `left` já é uma âncora final do `Item`, e chamá-lo lança erro (o `entered()` seguinte nem rodava). Nenhum módulo usava.
- **O `main()` de `library.py`, `organize.py`, `radio.py` e `ytdl.py` continua.** A GUI não usa mais, mas os testes usam e o `lw download` chama o do `ytdl.py`. Dá para tirar depois, levando os testes para `cli.main`.
- **`Theme.lw` e `Games.lw` são iguais.** O segundo sai com JOGOS, na sessão 5.

### Achado e não mexido

- **O `ffmpeg` que o `yt-dlp` lança** não recebe o aviso do kernel: se o LW fechar no meio de uma conversão, ela pode seguir até acabar (não testado). O `yt-dlp` já morre junto com o `lw`.
- **Avisos do `EmulatorsView.qml`** no log ao abrir EMULADORES; é de JOGOS (sessão 5).
- **`Downloads.dest`** não é usado por nenhuma tela; só passou a seguir `music.dir`.
