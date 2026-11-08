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
python3 ~/Projetos/rice-minimal/restore.py ~/Projetos/rice-minimal/backups/20261105-214902-082254
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
python ~/Projetos/rice-minimal/restore.py ~/Projetos/rice-minimal/backups/20261105-212603
```

Para apenas um arquivo, copie o correspondente de backups/20261105-212603/.config/ para ~/.config/. Restaure hyprland.lua junto ao módulo caso reverta o compositor. Neovim init.lua e módulo rice-minimal.lua eram novos e serão removidos pelo restaurador. O launcher supers também será removido. Links novos na pasta Wallpapers podem ser removidos individualmente; nenhum original foi movido ou apagado. Nenhum pacote foi instalado, portanto não há pacotes para remover. Backups são privados e ignorados pelo Git; não publicar diagnósticos sem revisar seu conteúdo.

Nenhuma alteração em partições, bootloader, kernel, drivers ou Linux Mint. Não houve reinício, logout, alteração de shell padrão ou desativação dos serviços do Noctalia.

## GUI

`Super+Backspace` (ou `rice gui`) abre e fecha o `RICE // CONTROL` gráfico. Ele é feito em Quickshell, só existe enquanto a janela está aberta e não tem lógica própria: chama comandos `rice ... --json` (`extras/cli.py`), os mesmos módulos usados pela TUI. A TUI (`rice`) continua disponível como reserva.

Na tela Wallpapers, `/` busca, setas ou `h`/`j`/`k`/`l` navegam, e `Enter`, duplo clique ou `APPLY` aplicam. As miniaturas ficam em `~/.cache/rice-minimal/thumbs` e podem ser apagadas à vontade. Fechar a janela durante uma ação não a interrompe: o Quickshell mata seus processos filhos ao sair, então os comandos da GUI rodam por `setsid --fork`.

Na tela Palette ficam a paleta atual e a anterior com seus wallpapers; `RESTORE PREVIOUS` pede um segundo clique e só fica disponível quando as cores são diferentes. A tela Profiles alterna entre Minimal e Refined. Os comandos equivalentes são `rice palette show|regenerate|restore` e `rice profile get|set|restore`, todos com `--json`.

`SYNC ALL`, no rodapé, ou `rice sync`, reaplica tudo em ordem e sob uma única trava: wallpaper, paleta, candidato ou tema do bloqueio e greeter. Se a paleta estiver em cache, só recarrega os componentes, sem mexer no histórico. Cada passo vai para `~/.local/state/rice-minimal/theme/actions.jsonl`, exibido ao vivo pelo botão `LOG`, inclusive trocas feitas pelo Waypaper ou pela TUI.

A tela Greeter compara o que foi enviado com o tema atual (`rice greeter status`), envia na hora (`rice greeter sync`) e liga ou desliga o envio automático (`rice greeter auto on|off`). O envio automático depende do arquivo `greeter-sync` no estado do tema, removido por `scripts/restore_greeter.sh`.

A tela Shortcuts lista os atalhos de `binds.lua` e os do rice (somente leitura). Todos podem mudar de combinação; o comando só pode mudar quando a ação é um comando de texto, e dispatchers, funções e variáveis são preservados. Conflitos são checados no arquivo e nos binds ativos do Hyprland, e cada gravação guarda um backup. Comandos: `rice shortcuts list|check|set|backups|restore`.

A tela Lock mostra uma prévia da candidata, ajusta o escurecimento e atualiza a candidata, recapturando os monitores. `TRIAL LOCK` bloqueia de verdade e roda desacoplado da janela: fechar a GUI não interrompe o teste, e o resultado aparece no log. `ACTIVATE` só libera depois de um teste no layout atual de monitores; um layout novo invalida o teste. Senha e PAM nunca mudam. Comandos: `rice lock status|check|update|dim|trial|activate|restore`; `trial` e `activate` exigem `--confirm`. A recuperação pelo TTY continua sendo `rice lock-restore`.

A tela Backups lista cada backup com o tipo e o comando de restauração certo (`rice backups list`). Perfil e paleta anteriores restauram ali mesmo; a restauração completa e a do greeter ficam no terminal, porque substituem código em uso. `COPY COMMAND` copia o comando.

As cores vêm de `~/.config/noctalia/palettes/RiceMinimal.json`, trocado de forma atômica a cada mudança de paleta.
