> **RICE // Fase 4 Final:** controle ncurses unificado, System Doctor e bloqueio nativo personalizado em validação. Consulte [RICE-FINAL.md](RICE-FINAL.md) para estado, testes e recuperação.

> **Fase 4 implementada:** perfil `refined` ativo, Waybar ASCII, animações Lua, Noctalia integrado à paleta e perfis intercambiáveis. Consulte [PHASE4.md](PHASE4.md) para arquivos, testes, limitações e restauração. As seções anteriores abaixo descrevem a Fase 3.

# Rice minimal — adaptive

## Fase 3 — instalada e testada

Comandos ativos: `rice`, `wallpapers` e `supers`. A implementação principal dos utilitários está em `extras/`; as entradas antigas do Super continuam compatíveis.

Waypaper e a TUI compartilham a seleção persistida no Waypaper e o mesmo hook. Noctalia permanece como único renderer de wallpaper e mantém os serviços essenciais. Matugen 4.2.0 gera uma paleta escura e pouco saturada somente por troca ou regeneração explícita. Os temas são publicados atomicamente, com lock, cache, fallback estático e restauração da geração anterior.

A Waybar está transparente, com módulos ASCII e texto adaptado às regiões do wallpaper. Kitty mantém opacidade 0.85; Fish, Neovim e as bordas Lua do Hyprland usam arquivos de cores separados. Blur, animações e arredondamento continuam desativados.

- [Uso, arquivos gerados, login, limitações e restauração](extras/theme/README.md)
- [Seletor de wallpapers e atalhos](extras/wallpapers/README.md)
- [Super e compatibilidade](extras/supers/README.md)
- [Resultados na sessão real](VALIDACAO-FASE3.json)

Backup desta fase: `backups/phase3-20261105-220201-094267`, com manifest e SHA256SUMS. Backups anteriores preservados. Nenhuma instalação privilegiada foi necessária. Nenhum reinício, logout ou alteração em Linux Mint, partições, bootloader, kernel ou drivers.

Para Fish já aberto antes da instalação, execute uma vez `source ~/.config/fish/config.fish`. Neovim já aberto: `:source ~/.config/nvim/init.lua`. Novas instâncias carregam automaticamente. A recuperação de cache/estado do login foi testada sem encerrar a sessão; um login real permanece sem teste.

## Histórico das fases anteriores

As seções abaixo descrevem o estado anterior; a Fase 3 e sua documentação acima prevalecem.

# Rice minimal — integração testada

Aplicado em 2026-11-05. A continuação abaixo registra os testes na sessão; as seções posteriores preservam o histórico anterior e seus bloqueios, agora resolvidos.

## Continuação — sessão real em 2026-11-05

- Internet: GitHub respondeu HTTP 200; clone completo em `referencias/Super-upstream`, commit `08dc30982385446cd154e30e54749cf6f4d81824`. O `Supers` remoto é idêntico à referência local original. O launcher continua usando `super/Supers`, com as correções de segurança e `safe_io.py`; diferença auditável em `super/upstream-safety.patch`. Clone permanece intacto, sem push.
- Todos os pacotes necessários já estão instalados: Waybar 0.15.0, Waypaper 2.9, Hyprpaper 0.8.5, Neovim 0.12.6 e Kitty 0.49.2. Nenhuma instalação ou sudo foi necessário. VS Code Microsoft não foi encontrado, mas não é dependência desta integração.
- Hyprland: socket acessível, módulo de integração carregado e `configerrors` vazio após reload. Nenhum reinício, logout ou mudança no Linux Mint.
- Noctalia estava parado; foi iniciado e preservado como daemon de notificações, wallpaper, launcher e demais serviços. Apenas sua barra fica oculta quando a Waybar está pronta. O teste de encerramento do supervisor confirmou o retorno da barra original.
- Waybar ASCII: configuração e CSS existentes preservados. Barra de 1920 × 28 criada no HDMI-A-1, sem erros no log do teste. Supervisor `scripts/session.py` impede instâncias duplicadas e restaura a barra Noctalia ao terminar. Autostart XDG instalado em `~/.config/autostart/rice-minimal.desktop`; o próximo login ainda não foi testado, pois não reiniciamos a sessão.
- Waypaper: GUI abriu; seleção e `--restore` confirmados consultando o wallpaper efetivo no Noctalia. Configuração usa `backend = none` e `post_command = noctalia msg wallpaper-set $wallpaper`; a versão instalada do Waypaper escapa esse argumento com `shlex.quote`. Hyprpaper permanece instalado, sem iniciar um segundo renderizador. A escolha fica persistida pelo Noctalia, cujo autostart original foi mantido.
- Kitty: parser nativo confirmou fundo #111111, opacidade 0.85 e cursor sem piscar; janela com Super abriu na sessão. A edição de atalhos reais pela TUI não foi exercitada. Os três testes de segurança passaram e `--check` validou 52 atalhos estáticos.
- Neovim: `--headless +checkhealth` executado fora do sandbox de escrita; configuração, runtime e ferramentas básicas OK. Avisos apenas de provedores opcionais Node/Perl/Python/Ruby, dispensáveis para o init.lua sem plugins. Relatório em `diagnostico/nvim-health.txt`.
- Volume consultado pelo `wpctl`; clique/scroll de volume e cliques físicos dos atalhos não foram testados. Os atalhos foram conferidos na lista runtime, sem colisões antes da instalação.

Atalhos adicionais (todos com **Super+Ctrl+Alt**): **W** Waypaper, **B** iniciar Waybar supervisionada, **S** Kitty com Super, **N** Kitty com Neovim. Os atalhos anteriores permanecem.

Resultados dos testes reais: `VALIDACAO-SESSAO.json`. Estado final: `diagnostico/estado-final.json`. Os arquivos `VALIDACAO.json` e as seções seguintes são históricos da primeira execução.

Novo backup, sem alterar `backups/LATEST` nem os backups anteriores: `backups/20261105-214902-082254`. O SHA256SUMS do backup original foi verificado com sucesso. Para reverter apenas esta continuação, primeiro encerre o supervisor pelo PID registrado em `diagnostico/estado-final.json` (isso devolve a barra Noctalia), execute:

```sh
python3 ~/Projetos/rice-minimal/scripts/restore.py ~/Projetos/rice-minimal/backups/20261105-214902-082254 --apply
hyprctl reload config-only
```

A seleção do wallpaper é estado separado: use o seletor do Noctalia para escolher outra imagem. O backup original continua disponível para reverter a implementação anterior, após reverter esta continuação.

## Histórico da implementação anterior

## Aplicado

- Kitty: fonte monospace, fundo #111111, opacidade 0.85, cursor bloco sem piscar/trilha, padding 8. Parser nativo do Kitty confirmou os valores. Abra uma nova janela para usar.
- Fish: mantido o source CachyOS e o shell padrão; sobrescritos apenas greeting e prompts. Fastfetch deixa de executar na abertura. `fish -n` passou. Não foi executado um Fish interativo neste sandbox, para evitar efeitos colaterais do source do sistema.
- Neovim: criado ~/.config/nvim/init.lua independente, sem plugins. Nenhuma configuração anterior encontrada. Binário ausente: execução ainda não testada.
- Hyprland: módulo config.rice-minimal carregado ao final do arquivo principal, sem mudar monitores, jogos, UWSM ou atalhos. Desativa animações, blur, sombras e arredondamento. Lua validado com luac; reload não executado e validação na sessão pendente.
- Noctalia: preservado como shell completo; removido apenas o alvo de template Kitty para proteger suas cores. `noctalia config validate` passou. Barra e wallpaper originais permanecem ativos.
- ~/Imagens/Wallpapers criado com links para as três imagens já existentes em ~/Pictures/Wallpapers; imagens originais preservadas.
- `~/.local/bin/supers` executa a cópia de trabalho em super/Supers. Fish já inclui ~/.local/bin no PATH.

## Super

O clone solicitado foi tentado, mas Git falhou por DNS. referencias/Super-local/Supers é uma cópia de ~/Supers, não um clone e não foi autenticada contra o remoto. Nenhuma operação de push ou alteração remota foi feita.

Mantida a interface curses original. Melhorias: aspas escapadas no parser e nos comandos Lua, validação de combinação, detecção de conflitos entre atalhos estáticos, luac antes da escrita, escrita atômica, backups únicos, lock e rejeição de alterações concorrentes. Não executa comandos digitados durante a validação. Expressões dinâmicas, loops e digitCode ficam fora da edição para evitar quebrar múltiplos atalhos. Ações e opções existentes são preservadas.

`supers --check` validou 52 atalhos estáticos. Os três testes em super/test_safety.py passaram (backup/restauração, Lua inválido, edição concorrente, parser e entrada inválida). A TUI abriu e encerrou normalmente em PTY; edição interativa completa e teste no Kitty da sessão continuam pendentes. Os atalhos da sessão não foram alterados. Conflitos envolvendo includes externos, plugins ou binds criados dinamicamente não são verificáveis pelo parser estático; confira `hyprctl -j binds` na sessão antes de editar combinações.

Restaurar uma edição do Super:

```sh
supers --restore ~/.config/hypr/config/binds.lua.supers-TIMESTAMP.bak
```

## Preparado, ainda não ativado

- config/waybar/config.jsonc e style.css: workspaces, título limitado a 48 caracteres, CPU a cada 5s, RAM a cada 10s, volume e relógio. Sem scripts de polling, ícones externos ou animações. JSON validado; CSS/renderização dependem do Waybar instalado.
- config/waypaper/config.ini: backend hyprpaper, imagens existentes; ainda não copiado para a configuração ativa. Não inicia outro serviço de wallpaper.

## Bloqueios reais e próximos passos

Pacotes ausentes: VS Code Microsoft, neovim, waybar, waypaper, hyprpaper. `pacman -Si` confirmou neovim/waybar/hyprpaper nos repositórios configurados e waypaper no CachyOS. O pacote `code` disponível é Code OSS; `visual-studio-code-bin` não está nos repositórios configurados. Não instalei Code OSS como substituto.

Sudo falhou: no new privileges e propriedade de /etc/sudo.conf incompatível neste sandbox. A política deste ambiente também não permite solicitar elevação; não há aprovação que eu possa abrir aqui. Git falhou ao resolver github.com. hyprctl version/configerrors falharam ao acessar o socket. Variáveis da sessão existem, mas não provam acesso funcional.

Na sessão anfitriã, os pacotes de repositório podem ser instalados com:

```sh
sudo pacman -S --needed neovim waybar waypaper hyprpaper
```

Para VS Code Microsoft, revisar o PKGBUILD de visual-studio-code-bin no AUR e a origem/download Microsoft antes de construir/instalar, ou usar o arquivo Linux oficial. Não foi baixado nem revisado um PKGBUILD nesta execução. Fonte oficial: https://code.visualstudio.com/docs/setup/linux . A compatibilidade nominal do Waypaper com Hyprpaper consta em https://github.com/anufrievroman/waypaper ; funcionamento das versões instaladas continua pendente.

Após instalar, falta concluir em sessão acessível:

1. Clonar https://github.com/Lucas-dev4/Super para referencias/Super e comparar com a cópia local antes de portar o patch.
2. Testar `code --version`, `nvim --headless '+checkhealth' +qa`, Kitty e a interface Waypaper.
3. Testar a Waybar com `waybar -c ~/Projetos/rice-minimal/config/waybar/config.jsonc -s ~/Projetos/rice-minimal/config/waybar/style.css`; usar `noctalia msg bar-hide` para ocultar somente sua barra, preservando o daemon. `noctalia msg bar-show` restaura. Só persistir autostart após confirmar a barra funcionando.
4. Confirmar como desativar apenas o wallpaper do Noctalia na versão instalada antes de iniciar Hyprpaper. Copiar configuração do Waypaper com backup, testar seleção e `waypaper --restore`, conferir IPC da versão Hyprpaper 0.8.5 e somente então persistir o restore via UWSM/XDG autostart. Não executar dois backends.
5. Super+Return já abre Kitty. Super+T já abre outro editor. Preservá-los. Candidatos adicionais: Super+Ctrl+Alt+C (code), +W (Waypaper), +B (Waybar), +S (Kitty executando supers). Sem colisão literal no binds.lua inspecionado; validar binds em runtime antes de adicionar. Estes candidatos NÃO estão aplicados.
6. `hyprctl reload` seguido de `hyprctl configerrors`, sem reiniciar ou encerrar a sessão.

## Restaurar a implementação

Backups em backups/20261105-212603 com manifest.json. Para restaurar os arquivos alterados (preserva o estado atual em before-restore):

```sh
python3 ~/Projetos/rice-minimal/scripts/restore.py ~/Projetos/rice-minimal/backups/20261105-212603 --apply
```

Para apenas um arquivo, copie o correspondente de backups/20261105-212603/.config/ para ~/.config/. Restaure hyprland.lua junto ao módulo caso reverta o compositor. Neovim init.lua e módulo rice-minimal.lua eram novos e serão removidos pelo restaurador. O launcher supers também será removido. Links novos na pasta Wallpapers podem ser removidos individualmente; nenhum original foi movido ou apagado. Nenhum pacote foi instalado, portanto não há pacotes para remover. Backups são privados e ignorados pelo Git; não publicar diagnósticos sem revisar seu conteúdo.

Nenhuma alteração em partições, bootloader, kernel, drivers ou Linux Mint. Não houve reinício, logout, alteração de shell padrão ou desativação dos serviços do Noctalia.

## GUI

O LW é uma janela só (`gui/shell.qml`, Quickshell) com três seções na barra lateral: **SISTEMA** (wallpapers, atalhos, perfis, paleta, doctor, backups, bloqueio, greeter), **MÚSICA** (o cliamp) e **JOGOS** (biblioteca, backlog, sessões). `Super+BackSpace` (`lw gui`), `Super+M` (`lw music`) e `Super+G` (`lw games`) abrem a mesma janela na seção certa: fechada, abre lá; escondida, volta lá; aberta em outra seção, troca; na mesma, fecha. A seção aberta lista as telas dela; as fechadas mostram numa linha a faixa tocando ou o jogo em sessão, e o bloco de baixo da barra lateral muda com a seção (wallpaper atual; fontes, mini player e VOL; fontes e sessão). Fechar o LW não para a música nem a sessão de jogo: só grava a sessão do cliamp. O cliamp só é ligado ao entrar em MÚSICA, e o scan de jogos roda ao entrar em JOGOS. A janela não tem lógica própria: chama `lw ... --json` (`extras/cli.py`), os mesmos módulos da TUI (`lw` sem argumentos; `rice` continua funcionando como nome antigo).

Teclas: `Alt+1`/`2`/`3` trocam de seção, `1`…`n` escolhem a tela, `q`/`Esc` fecham; só as setas navegam (h/j/k/l saíram); onde dá para reordenar (fila de MÚSICA, backlog de JOGOS), `Shift`+setas leva o item. No EQUALIZER `←`/`→` escolhem a banda em vez de avançar a música. `Ctrl+J` esconde a janela sem fechar e o atalho Super a traz de volta. Enquanto SHORTCUTS grava uma combinação, `Ctrl+J` é gravado, não esconde.


Visual: segue `docs/lw-prototype.html`. Cores, fonte (JetBrains Mono) e tempos de animação ficam só em `gui/Theme.qml`, e todas as cores vêm da paleta do wallpaper. As animações (boot, glitch do logo, título decode, faixa deslizante) rodam em qualquer perfil; `RICE_GUI_MOTION=0 lw gui` desliga. A status bar mostra os atalhos da tela atual. Preferências só da GUI (favoritos, descrições de atalhos) ficam em `~/.local/state/rice-minimal/gui/`.

Na tela Wallpapers, `f` favorita e `F` filtra os favoritos; `/` busca, as setas navegam, e `Enter`, duplo clique ou `APPLY` aplicam. As miniaturas ficam em `~/.cache/rice-minimal/thumbs` e podem ser apagadas à vontade. Fechar a janela durante uma ação não a interrompe: o Quickshell mata seus processos filhos ao sair, então os comandos da GUI rodam por `setsid --fork`.

Na tela Palette ficam a paleta atual e a anterior com seus wallpapers; `RESTORE PREVIOUS` pede um segundo clique e só fica disponível quando as cores são diferentes. A tela Profiles alterna entre Minimal e Refined. Os chips de SCHEME regeneram com outro esquema do Matugen (`rice palette regenerate --scheme neutral|tonal-spot|vibrant|expressive`); a escolha fica em `~/.local/state/rice-minimal/theme/scheme` e vale para as próximas trocas de wallpaper. O modo é sempre dark. Profiles mostra só o que muda entre os perfis, lido dos arquivos que os aplicam (`rice profile get --json`, campo `differences`). Os comandos equivalentes são `rice palette show|regenerate|restore` e `rice profile get|set|restore`, todos com `--json`.

`SYNC ALL`, no rodapé, ou `rice sync`, reaplica tudo em ordem e sob uma única trava: wallpaper, paleta, candidato ou tema do bloqueio e greeter. Se a paleta estiver em cache, só recarrega os componentes, sem mexer no histórico. Cada passo vai para `~/.local/state/rice-minimal/theme/actions.jsonl`, exibido ao vivo pelo botão `LOG`, inclusive trocas feitas pelo Waypaper ou pela TUI.

A tela Greeter compara o que foi enviado com o tema atual (`rice greeter status`), envia na hora (`rice greeter sync`) e liga ou desliga o envio automático (`rice greeter auto on|off`). O envio automático depende do arquivo `greeter-sync` no estado do tema, removido por `scripts/restore_greeter.sh`.

A tela Shortcuts lista os atalhos de `binds.lua` e os do rice (somente leitura). Todos podem mudar de combinação; o comando só pode mudar quando a ação é um comando de texto, e dispatchers, funções e variáveis são preservados. Conflitos são checados no arquivo e nos binds ativos do Hyprland, e cada gravação guarda um backup. Cada atalho tem uma descrição legível gerada da ação (editável, guardada só na GUI). `r` grava uma combinação: a GUI entra no submap vazio `lw-record` (definido em `rice-integration.lua`), para que combinações com Super cheguem à janela; `Esc` sai, e a GUI reseta sozinha em 10 s. Toda combinação precisa de Super, porque `binds.lua` sempre a escreve como `mainMod .. ...`. Comandos: `rice shortcuts list|check|set|backups|restore`.

A tela Doctor usa `rice doctor --stream` (uma linha JSON por check) para mostrar o progresso real.

A tela Lock mostra uma prévia da candidata, ajusta o escurecimento (slider de 55 a 85%, `rice lock dim 55..85`) e atualiza a candidata, recapturando os monitores. `TRIAL LOCK` bloqueia de verdade e roda desacoplado da janela: fechar a GUI não interrompe o teste, e o resultado aparece no log. `ACTIVATE` só libera depois de um teste no layout atual de monitores; um layout novo invalida o teste. Senha e PAM nunca mudam. Comandos: `rice lock status|check|update|dim|trial|activate|restore`; `trial` e `activate` exigem `--confirm`. A recuperação pelo TTY continua sendo `rice lock-restore`.

A tela Backups lista cada backup com o tipo e o comando de restauração certo (`rice backups list`). Perfil e paleta anteriores restauram ali mesmo; a restauração completa e a do greeter ficam no terminal, porque substituem código em uso. `COPY COMMAND` copia o comando.

As cores vêm de `~/.config/noctalia/palettes/RiceMinimal.json`, trocado de forma atômica a cada mudança de paleta.

## Transparência do LW

O LW tem o fundo translúcido como o kitty (`background_opacity 0.85`): o fundo e os painéis deixam a área de trabalho aparecer, o texto, as capas e as bordas ficam sólidos. A opacidade fica em `Theme.alpha` (`Theme.base` é o fundo; `panel` e `raise` viram um véu sobre ele). `RICE_GUI_OPACITY=1 lw gui` deixa sólido; o que fica por cima de outra coisa (ficha do jogo, LOG, cartão arrastado) usa `Theme.sheet`, quase opaco; o blur do Hyprland está desligado no perfil, então não há desfoque atrás.

## LW: JOGOS

A seção JOGOS (`Super+G`, `lw games`; telas em `gui/arcade/`) é a biblioteca de jogos. Os dados ficam em `~/.local/share/lw/games.json` e só o `extras/games.py` escreve nele (trava + escrita atômica). O scan roda ao entrar em JOGOS, em segundo plano, e pelo `RESCAN`: Steam (todas as bibliotecas do `libraryfolders.vdf`, arte do `appcache/librarycache` nos dois formatos, horas do `userdata/*/config/localconfig.vdf`), Hydra Launcher (entradas que têm executável) e ROMs (`~/ROMs`, configurável em `~/.local/share/lw/games-config.json`, core do RetroArch pela extensão). Jogos do Wine entram por `+ JOGO` (executável, prefixo e nome). O scan só acrescenta e atualiza o que a fonte sabe; status, horas, notas e o resto nunca mudam, e o que some fica marcado como sumido. `games.py running` acha o jogo em execução pela variável `LW_GAME_ID`, que o LW põe no lançamento e todo processo filho herda (inclusive o `.exe` dentro do Wine), e pelo `SteamAppId` que a Steam põe nos jogos dela. Lançar (`▶ JOGAR`, `⏎`) mostra uma tela com os passos reais e inicia um vigia separado (`games.py watch`), que abre a sessão quando o processo do jogo aparece e a fecha quando ele some, ignorando os processos de sistema do Wine; a contagem continua com a janela fechada, e uma sessão interrompida por reboot fecha no último sinal de vida (a cada 30 s). Uma sessão por vez. Na Steam, `gamemoderun`/`mangohud` ficam nas opções de lançamento do próprio jogo (o LW não mexe na configuração da Steam).

## GRUB: tema LW

`python3 scripts/grub_theme.py` gera o tema em `~/.local/state/rice-minimal/grub/lw/`: o wallpaper atual desfocado sob o véu escuro (mais escuro à esquerda, atrás do menu), JetBrains Mono em `.pf2` (só latim, setas, molduras e ⏎), título `LW` e a entrada escolhida no accent, com a barra à esquerda. Ele não toca em `/boot` nem em `/etc`: imprime os comandos sudo. O tema não acompanha o wallpaper sozinho; depois de trocar o wallpaper, rode o script e o `install` de novo (o `grub-mkconfig` só é preciso na primeira vez).

Instalar (uma vez): copiar para `/boot/grub/themes/lw`, guardar `/etc/default/grub.bak-lw`, trocar `GRUB_THEME` e `GRUB_TIMEOUT` (2 s) e rodar `grub-mkconfig`. Voltar ao tema do CachyOS: `sudo cp /etc/default/grub.bak-lw /etc/default/grub && sudo grub-mkconfig -o /boot/grub/grub.cfg`.

## Neovim

`config/nvim/init.lua` é um arquivo único com lazy.nvim, pywal.nvim e lualine (versões fixadas em `config/nvim/lazy-lock.json`). O rice escreve as cores do terminal em `~/.cache/wal/colors-wal.vim` a cada troca de wallpaper, e o Neovim aberto recarrega na hora. Fundo transparente, números fixos, indentação com TAB real, `:Org` para reindentar, autosave (ao sair do modo inserção, trocar de buffer, editar no modo normal e 300 ms depois de parar de digitar), pares automáticos para `( [ { ' "`, seleção com `Shift+setas`, `Alt+↑/↓` para mover linhas e atalhos estilo VSCode. `Ctrl+R` salva, compila e roda o arquivo (C, C++, NASM, GAS/ARM, Python, Lua e shell) e mostra a saída num painel à direita, fechado com `q`. `Alt+I` abre ou fecha, acima da saída e maior que ela, a caixa de entrada do arquivo: o texto dela vai para o programa como teclado (stdin), fica guardado por arquivo em `~/.local/state/nvim/rice-run/` e o `Ctrl+R` também funciona de dentro dela. O compilador nunca recebe a entrada. Arquivos que o `Ctrl+R` roda já abrem com entrada e saída à direita, e trocar de arquivo troca a entrada mostrada. `Alt+←` vai para o código e `Alt+→` para a entrada; na coluna da direita, `Alt+↑`/`Alt+↓` alternam entre entrada e saída, e no código continuam movendo a linha. O Neovim abre no modo inserção, e voltar ao código ou à entrada também entra nele; a saída fica no modo normal e não aceita digitação. `Ctrl+T` abre um Kitty em `~/Vscode`. Não há terminal embutido.

## cliamp

Player de música no terminal (`bjarneo/cliamp`, MIT), instalado do binário oficial em `~/.local/bin/cliamp` depois de conferir o `checksums.txt` da release. `config/cliamp/config.toml` é a configuração inicial: tema `rice` e navegador de arquivos em `~/Músicas`. O rice gera `~/.config/cliamp/themes/rice.toml` com as cores vivas do terminal a cada troca de wallpaper, sem cor de fundo; o tema vale na próxima abertura. Atualize com `cliamp upgrade`.

### LW: MÚSICA

A seção MÚSICA (`Super+M`, `lw music`; telas em `gui/player/`) é o controle gráfico do cliamp. Segue `~/Downloads/lw-music.html`. Quem toca é sempre o cliamp: a janela só conversa com ele pelo IPC v2 (`cliamp remote`), num único módulo, `gui/Music.qml`. O estado chega pelo stream de eventos `runtime.state` (sem polling), cada comando roda assíncrono com 4 s de limite, e a janela reconecta sozinha se o cliamp cair. Entrar em MÚSICA liga o cliamp (`cliamp --daemon`, sem janela) se ele estiver desligado; fechar o LW deixa a música tocando e só grava a sessão (fila, faixa, segundo e volume do cliamp) em `~/.local/state/rice-minimal/gui/music-session.json`. Se o cliamp não estiver rodando (depois de um reboot, por exemplo), entrar em MÚSICA o liga pausado no mesmo ponto; sem sessão, abre `~/Músicas`. O daemon do cliamp não usa o próprio `resume.json`, por isso a sessão é guardada pelo LW. Para parar de vez, pause (`espaço`) ou clique direito no módulo da Waybar. `RICE_MUSIC_AUTOSTART=0` deixa o `START` manual.

- **NOW PLAYING**: visualizador em 4 modos (`v`: bars, ascii, mirror, wave; lembrado em `~/.local/state/rice-minimal/gui/music.json`), capa do MPRIS (`mpris:artUrl`, o cliamp extrai a embutida) ou gerada pelo título, formato via `ffprobe`, barra de progresso clicável, controles e as próximas 3 faixas (em shuffle a ordem é do cliamp e não aparece).
- **Visualizador**: o `cava` captura só o stream do cliamp no PipeWire (`alsa_playback.cliamp`), 56 bandas log 30 Hz–16 kHz a 60 fps, e só roda enquanto o cliamp toca. Outros sons do sistema não entram. O config fica em `$XDG_RUNTIME_DIR/lw-music-cava.conf`. Os modos não redesenham canvas por quadro (barras recortadas, texto fixo, `Shape`): na janela real, a 60 fps, ~6–11% de um núcleo conforme o modo, mais ~1% do cava; `RICE_MUSIC_FPS=30 rice music` corta pela metade.
- **PLAYLIST**: a fila ao vivo do cliamp. `↑`/`↓` andam, `Enter` toca, `Shift+↑`/`↓` mudam a posição, `d` tira da fila (o arquivo fica no disco), `/` filtra, `o` abre o seletor do sistema (zenity), e arrastar arquivos de áudio para a janela também adiciona. O `queue.move` do cliamp troca duas posições, por isso `Shift+↑`/`↓` andam uma por vez.
- **EQUALIZER**: as 10 bandas reais do cliamp (70, 180, 320, 600 Hz, 1, 3, 6, 12, 14, 16 kHz; Q 1.4; ±12 dB), ao vivo, com a curva de resposta calculada dos filtros. Presets do protótipo e os 16 do cliamp. O cliamp não tem pré-amplificador nem bypass: `BYPASS` guarda a curva (`music-eq.json`) e volta a ela. O cliamp grava o EQ na própria configuração ao fechar.
- **RADIO**: `extras/radio.py` busca no radio-browser.info (servidor tirado de `all.api.radio-browser.info`, só streams funcionando, mais votadas primeiro). `Enter` toca pelo cliamp (`url.load`), `a` salva em `~/.config/cliamp/radios.toml` (`[[station]]`, validado antes de gravar).

O VOL é o volume do sistema (a saída padrão do PipeWire), o mesmo de `Super+=`/`Super+-` e do aviso do Noctalia: a barra, a roda, `+`/`-` e `m` mexem nele, e mudanças feitas por fora aparecem na hora (`pactl subscribe`). O ganho interno do cliamp fica como está.

- **LIBRARY** (`5`): todos os arquivos de `~/Músicas` buscados pelas tags e pelas letras, agrupados por artista. A busca nativa do cliamp não olha dentro dos arquivos locais, então o índice vem de `extras/library.py scan` (ffprobe, com cache por data de modificação em `~/.cache/rice-minimal/music-library.json`). Texto solto procura em tudo; `artista:`, `álbum:`, `gênero:`, `ano:`, `título:` e `letra:` restringem a uma tag. `Enter` toca (da fila, ou adicionando), `a` põe na fila, `A` põe todos os resultados.
- **ONLINE** (`6`): busca música online. **YouTube** pelo `yt-dlp` (`ytsearch`, sem conta; `sudo pacman -S yt-dlp`) e **SoundCloud** pelo próprio cliamp (`provider.search`; ligado com `[soundcloud] enabled = true` no `config.toml` do cliamp, que o rice já põe). O provedor de YouTube do cliamp pede conta/cookies e fica de fora até ser configurado (aí aparece como "YouTube (conta)"). `/` busca, `Tab` troca a fonte, `Enter` toca agora (`track.play`, o cliamp resolve o link com o yt-dlp), `a` põe como próxima (`track.queue`). No SoundCloud, faixas oficiais de grandes selos vêm como prévia de 30 s (o resto pede assinatura); uploads comuns vêm inteiros. Rádio, arquivos locais e podcasts ficam nas próprias abas.
- **Tags que faltam**: `extras/library.py lookup --out plano.json` procura cada faixa na Deezer e, no que ela não achar, na iTunes Search (só artista e título são enviados) e propõe gênero (um por artista, pela maioria), ano e capa para quem não tem. `extras/library.py apply --plan plano.json` grava, mantendo as outras tags e as letras, e só troca o arquivo se o áudio continuar idêntico (hash); o antigo vai para a lixeira.

Teclas da seção: `1`–`6` telas, `espaço` play/pause (vale em qualquer seção), `n`/`p` próxima/anterior (`p` volta ao início depois de 3 s), `←`/`→` ±5 s, `+` (ou `=` no ABNT2)/`-` volume, `m` mute, `s` shuffle, `r` repeat, `R` rádio, `o` abrir arquivos. `scripts/music-check.sh` abre o LW em MÚSICA contra um cliamp real, isolado num `HOME` temporário, e testa a camada de controle.

### Waybar

O módulo `custom/lw` (`extras/lwbar.py`) mostra, à esquerda do CPU, o jogo em sessão (`● 0:12 título`) ou o que o cliamp toca (`▶`/`❚❚ faixa — artista`), e some quando nada roda. Clique abre o LW em JOGOS ou MÚSICA; clique direito pausa ou continua o cliamp.

## yazi

Gerenciador de arquivos no terminal, instalado pelo pacote `yazi` do Arch, com `7zip` e `zoxide`. `Super+E` abre o yazi num Kitty (classe `yazi`) no lugar do Dolphin; a variável `FILE_MANAGER` continua `dolphin` para quem a usa. `config/yazi/yazi.toml` põe pastas primeiro, ordenação natural, tamanho dos arquivos e abre texto no Neovim. O rice gera `~/.config/yazi/theme.toml` a cada troca de wallpaper: só os azuis fixos do tema padrão (seleção, pastas, modo, abas) passam para o tom do terminal; o resto usa as cores ANSI do Kitty. No Fish, `y` abre o yazi e, ao sair, deixa o terminal na pasta onde você estava; `config/fish/conf.d/zoxide.fish` liga o `z`.

## Instalar e restaurar

Depois de editar um arquivo gerenciado, rode `scripts/integrity.py` para atualizar `config/integrity.json` (a lista que o `rice doctor` confere); `scripts/integrity.py --check` só mostra o que mudou, e os testes falham se a lista estiver velha.


`python3 scripts/install.py` lista o que mudaria para deixar o sistema igual ao repositório (Hyprland, Fish, Kitty, Neovim, yazi, cliamp, Waypaper, atalhos de terminal e Qt); com `--apply`, valida cada arquivo, salva um backup em `backups/install-*` e grava tudo, desfazendo o que já tinha gravado se algo falhar. Os caminhos são gerados para o usuário e a pasta atuais. O doctor avisa quando um arquivo instalado se afasta do repositório. Pacotes e a tela de login (sudo) ficam de fora. Ele também fixa ícones e cursor no Adwaita (já incluso no sistema, quase monocromático) no ambiente da sessão, no GTK 3/4, no Qt 5/6, no XWayland e no gsettings; o cursor da sessão aberta troca na hora, e apps já abertos pegam os ícones ao reabrir.

`python3 scripts/restore.py backups/<nome>` mostra o que um backup restauraria; com `--apply`, confere o backup inteiro antes de mexer em qualquer coisa, salva o estado atual num backup de resgate (que o mesmo comando restaura) e volta tudo se algo falhar. O código do projeto nunca é restaurado por ele: isso é papel do git. A tela de login tem o próprio restaurador, `sudo sh /var/backups/rice-greeter/restore.sh`.

O perfil Minimal desliga todas as animações; nele a tela de login é sincronizada sem espera. A GUI usa renderização por software do Qt (menos memória e abertura mais rápida); defina `QT_QUICK_BACKEND` para trocar.

## Terminal: vim, bat, fzf e fastfetch

No Fish, `vim` abre o Neovim do rice. `bat` (e o `man`, que usa o bat) segue as cores ANSI do Kitty com `BAT_THEME=ansi`. O `fzf` recebe a paleta do wallpaper, fundo transparente e marcas em ASCII (`>`, `*`, `-`). O `fastfetch` usa `config/fastfetch/config.jsonc` (logo ASCII, chaves no formato `[ OS     ]`) e a função `fastfetch` do Fish passa o tom do wallpaper. Tudo é atualizado a cada troca de paleta pelo `colors.fish`.
