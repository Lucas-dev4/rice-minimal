# Tema adaptativo

Dependência instalada: Matugen **4.2.0-1.1**, igual ao pacote disponível no CachyOS. Nenhum pacote foi instalado. A sintaxe da linha de comando foi conferida com o binário instalado e exercitada com imagens reais:

```sh
matugen image IMAGEM --config extras/theme/matugen.toml --dry-run --json hex --mode dark --type ESQUEMA --source-color-index 0 --quiet
```

O `ESQUEMA` fica em `~/.local/state/rice-minimal/theme/scheme` (padrão `scheme-neutral`; também
`scheme-tonal-spot`, `scheme-vibrant`, `scheme-expressive`). `rice palette regenerate --scheme vibrant`
troca o esquema, e as trocas de wallpaper seguintes o mantêm. Restaurar uma paleta restaura o esquema dela.

O TOML isolado tem templates vazios. O Matugen nunca aplica wallpaper, nunca roda ganchos do usuário e nunca sobrescreve temas globais de aplicativos. As cores neutras escuras dele são dessaturadas ainda mais; as cores ANSI mantêm diferenças discretas. O contraste básico entre texto e fundo do terminal é conferido. Com transparência, o contraste real depende da imagem atrás da janela.

## Fluxo dos eventos

Waypaper (janela) ou `wallpapers` → grava a escolha pelo Waypaper → gancho comum `theme.py wallpaper` → o Noctalia aplica a imagem → o Matugen extrai as cores uma vez → os arquivos gerados são validados → um link simbólico atômico publica a geração → os componentes abertos são atualizados → pede ao Noctalia para sincronizar a tela de login (só quando a paleta mudou; uma falha aí não faz falhar a troca de wallpaper).

O gancho pega um `flock` exclusivo que cobre aplicar o wallpaper, gerar e recarregar. Ele lê a última escolha gravada no Waypaper depois de pegar a trava; eventos repetidos na fila reaproveitam a paleta pela impressão digital. A impressão digital inclui o caminho resolvido da imagem, o tamanho, a data de modificação e a versão do algoritmo do tema. A opção 4 do menu força a geração de propósito. Não há polling, vigia nem daemon novo.

O estado fica em `~/.local/state/rice-minimal/theme/`:

- `current` e `previous`: links simbólicos para pastas de paleta que não mudam.
- Cada pasta tem `palette.json`, `colors.css`, `kitty.conf`, `hyprland.lua`, `colors.fish` e `nvim.lua`.
- `status.json`: o último resultado do gancho e os erros do gerador, se houver.
- `generation.lock`: a trava do processo, que o sistema solta quando o processo termina.

Uma falha na geração mantém a última paleta que funcionava. Na primeira vez, ou com os arquivos do cache faltando ou corrompidos, vale a paleta de emergência fixa embutida. As gerações ficam guardadas para recuperação e não são tratadas como backups descartáveis.

Numa troca de wallpaper de verdade, o gancho primeiro abre o `gui/reveal` (Quickshell, camada overlay, cliques passam através, sem teclado): ele cobre a tela, monta a imagem nova com blocos de 4 px das próprias cores sobre preto puro (um shader na GPU, então `RICE_REVEAL_BLOCK=1` custa o mesmo), do meio para fora, devagar no começo e acelerando, depois se dissolve no wallpaper real e sai (~3,5 s, limite de 9 s). O gancho espera até 1,5 s pela cobertura antes de trocar a imagem por baixo. Escolher de novo a imagem atual pula a animação. `touch ~/.local/state/rice-minimal/theme/reveal-off` desliga; uma falha nunca faz falhar a troca de wallpaper.

## Integração com os componentes

| Componente | Integração | Atualização |
| --- | --- | --- |
| Waybar | O CSS existente importa as cores geradas; fundos de contêiner, módulo e hover transparentes | SIGUSR2 recarrega o processo aberto |
| Kitty | Um include só de cores no fim da config existente | SIGUSR1 recarrega os Kitty abertos do usuário |
| Hyprland | Um include `config.rice-adaptive`, com `general.col.active_border` / `inactive_border` | `hyprctl eval` aplica só as bordas geradas |
| Fish | Um ajudante pequeno em conf.d; o formato do prompt e o código de erro continuam | As atribuições geradas são lidas no próximo prompt |
| Neovim | Um include Lua pequeno, sem plugins | FocusGained / BufEnter / VimResume recarregam se a geração mudou; `:RiceTheme` força |

O `background_opacity 0.85` do Kitty, o padding e as outras opções ficam intactos. O compositor mantém blur, sombras, cantos arredondados e animações desligados; as bordas têm 1 px. Os menus usam moldura ASCII e a transparência e as cores ANSI que o terminal já tem.

Fish abertos antes da instalação precisam de `source ~/.config/fish/config.fish` uma vez para carregar o gancho novo do prompt. Neovim abertos antes da instalação precisam de `:source ~/.config/nvim/init.lua` uma vez. Instâncias novas carregam sozinhas. Nada injeta comandos num shell ou editor já aberto.

O texto da Waybar é escolhido entre tons claros, escuros e intermediários discretos a partir de uma amostra da faixa de cima da imagem, supondo a imagem centralizada cobrindo a tela. Cores separadas por módulo dão conta de partes claras e escuras da mesma imagem. O texto da área de trabalho ativa mantém um destaque do wallpaper ajustado para contraste. O `palette.json` registra o contraste medido por módulo. Os limites de cada módulo são estimativas para o layout monoespaçado de 13 px de hoje e o monitor em foco; imagens muito heterogêneas, outra escala, vários monitores ou larguras variáveis de área de trabalho e título podem reduzir o contraste local. A implementação ajusta só o texto e não acrescenta caixas de fundo nem blur. Rode a opção 4 do menu depois de mudar a geometria do monitor. É uma heurística medida, não uma garantia de contraste em cada pixel.

O renderizador, as notificações, o lançador e os atalhos do Noctalia ficam intactos. Os templates que ele já tinha e o comportamento visual próprio continuam sendo dele. GTK, Qt e btop seguem os templates do próprio Noctalia. Firefox, VS Code, jogos e outros temas de aplicativo não são sincronizados. O atalho do painel de wallpaper do Noctalia foi tirado porque passava por fora do gancho; uma troca feita direto pelo IPC do Noctalia ainda passa, e o `SYNC ALL` (ou `rice sync`) conserta.

## Login

O autostart XDG de sempre ainda abre o `scripts/session.py`. Ele espera o Noctalia, valida e reaproveita o `current`, restaura pelo Noctalia o wallpaper gravado no Waypaper e abre a Waybar. **O Matugen nunca roda no login.** Se a Waybar parar, o supervisor mostra de novo a barra do Noctalia. Fish, Kitty e Neovim novos leem os arquivos do cache; o Hyprland carrega o módulo gerado ao ler a configuração normal.

A função de início e restauração pelo cache foi testada na sessão aberta, conferindo que ela não trocava a geração da paleta. Um logout/login de verdade não foi feito, de propósito.

## Comandos e recuperação

O `rice` oferece Wallpapers, Super, ver a paleta, forçar a geração e restaurar o tema anterior. Ele sai por inteiro ao fechar. `Restore previous theme` troca as duas gerações guardadas e recarrega os componentes, sem mudar o wallpaper escolhido. Rodar de novo volta para a outra geração.

Comandos equivalentes, da pasta do projeto:

```sh
python3 extras/theme/theme.py show
python3 extras/theme/theme.py regenerate
python3 extras/theme/theme.py restore
```

Para desfazer **toda a integração da Fase 3**, o backup preparado é:

```sh
python3 ~/Projetos/rice-minimal/scripts/restore.py ~/Projetos/rice-minimal/backups/phase3-20261105-220201-094267 --apply
hyprctl reload config-only
pkill -USR1 -u "$USER" -x kitty
pkill -USR2 -u "$USER" -x waybar
```

O restaurador guarda os arquivos atuais antes de restaurar os originais, tira os lançadores e includes novos registrados no manifesto e não reinicia a sessão gráfica. Abra um Fish novo depois. Num Neovim já aberto, tire os autocmds adaptativos antigos com `:lua pcall(vim.api.nvim_del_augroup_by_name, 'RiceAdaptive')` e use `:colorscheme default`. O histórico de paletas e os arquivos novos em `extras/` continuam no disco, mas deixam de ser carregados. Os backups anteriores e o `backups/LATEST` não foram substituídos.

## Validação

- Nove testes de unidade: falha na geração, tema de emergência na primeira vez, cache corrompido, cache de eventos repetidos, trava exclusiva, desfazer, recusa de cor insegura, nomes especiais e contraste em wallpaper claro, escuro e misto.
- Os testes de segurança originais do Super passam tanto pelo caminho canônico quanto pelo de compatibilidade; 52 atalhos fixos validam.
- PTYs de curses reais exercitaram busca, movimento, escolha aleatória, navegação no menu e saída, sem trocar imagem.
- Sessão real: o Enter da TUI trocou uma imagem existente, o Waypaper a reconheceu, o gancho gerou as cores, a escolha pela linha de comando equivalente à janela e o `--restore` funcionaram, e a imagem original voltou.
- A sintaxe do Lua e do Fish gerados e o CSS do GTK passam; o parser do Kitty confirma a opacidade; o Neovim sem tela confirma realces e opções; checagens no Hyprland em execução confirmam o tamanho da borda, sem blur, cantos retos e sem animações.
- O `VALIDACAO-FASE3.json` tem os resultados da sessão. Partições, bootloader, kernel, drivers e o Linux Mint não foram modificados.

Referências principais, conferidas junto com a ajuda instalada e o `/usr/share/hypr/stubs/hl.meta.lua`: [uso do Matugen](https://github.com/InioX/matugen/wiki/Usage), [configuração Lua do Hyprland](https://wiki.hypr.land/configuring/core/config-options/), [includes e recarga do Kitty](https://sw.kovidgoyal.net/kitty/conf/).

O texto do terminal é a única exceção à paleta discreta: as cores ANSI do Kitty, o realce do Fish e o `LS_COLORS`/`EZA_COLORS` usam `vivid()`, que mantém o matiz de cada cor mas sobe a saturação, e a luminosidade só até onde um contraste de 4,5:1 precisa. Fish abertos pegam essas cores no próximo prompt. As barras e o Noctalia mantêm as cores discretas.

O destaque do terminal vem do matiz mais presente na imagem (`image_hue`), não da escolha do Matugen, que pode não ter nada a ver com o que a imagem parece. Matizes perto do vermelho são desviados para que comandos nunca pareçam erro, e imagens quase cinza ganham um destaque mais suave. Paletas geradas antes disso continuam funcionando pelo destaque do Matugen.

Cada módulo da Waybar mantém um matiz (CPU verde, RAM amarelo, VOL ciano, relógio e área de trabalho ativa no destaque do terminal). O `bar_contrast` escurece ou clareia cada um só até onde a própria faixa do wallpaper precisa para 4,5:1, então um módulo nunca fica menos legível do que branco ou preto puros seriam. Onde nenhuma cor sozinha chega lá, um halo leve liga só naquele módulo. Os separadores são desenhados com 40% de opacidade, com marcação Pango.
