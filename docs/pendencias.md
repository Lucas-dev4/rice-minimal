# Pendências

Decisões tomadas sem confirmar, sempre pela opção mais conservadora (manter o comportamento de antes), e coisas achadas no caminho que ficaram como estavam. Apague o item quando resolver.

## Sessão 4 (MÚSICA), 2026-11-24

### Decidido sem confirmar

- **`left()` virou `exited()` no gancho.** O nome do contrato não funciona: `left` já é uma âncora final do `Item`, e chamá-lo lança erro (o `entered()` seguinte nem rodava). Nenhum módulo usava.
- **O `main()` de `library.py`, `organize.py`, `radio.py` e `ytdl.py` continua.** A GUI não usa mais, mas os testes usam e o `lw download` chama o do `ytdl.py`. Dá para tirar depois, levando os testes para `cli.main`.
- **`Theme.lw` e `Games.lw` são iguais.** O segundo sai com JOGOS, na sessão 5.

### Achado e não mexido

- **Fechar o LW em MÚSICA antes de o cliamp responder** (uns 2 s depois de abrir) não desliga o cliamp nem salva: ele fica ligado, sem tocar, até a próxima vez. Aconteceu na sua sessão às 22:59 de 24/11, com o código de antes da sessão 4.
- **Fechar o LW no meio de um download:** o Quickshell mata o `lw download` sem deixar ele parar o `yt-dlp`, que pode seguir sozinho por um tempo. Já era assim com o `ytdl.py`. A busca de ONLINE passou a ter o mesmo limite, porque o `yt-dlp` agora é filho do `lw online search`; ele termina sozinho em segundos.
- **`TypeError: Value is undefined` no log ao trocar de seção:** por um instante a tela da seção nova é procurada com a lista antiga (`screens[current]`, no `shell.qml`). Não aparece na tela; já existia.
- **Avisos do `EmulatorsView.qml`** no log ao abrir EMULADORES; é de JOGOS (sessão 5).
- **`Downloads.dest`** não é usado por nenhuma tela; só passou a seguir `music.dir`.
