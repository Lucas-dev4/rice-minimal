# RICE // Minimal Refined — Fase 4 Final

O bloqueador existente é o Noctalia 5.4.1, superfície segura Wayland; o atalho continua Super+L. Hyprlock não foi instalado. PAM, senha, impressão digital, grace period, bloqueio antes de suspensão e serviços de sessão não são alterados.

## Teste e recuperação do bloqueio

A configuração candidata é `~/.local/state/rice-minimal/theme/current/lockscreen.toml`. Preparar/validar a candidata não ativa nem bloqueia a sessão. O primeiro teste real exige confirmação explícita:

```sh
cd ~/Projetos/rice-minimal
rice lock-check
rice lock-trial --confirm
```

O teste aplica temporariamente os visuais e executa o bloqueio nativo. Desbloqueie com sua senha normal. Ao detectar o desbloqueio, ele restaura automaticamente os visuais anteriores. Não existe desbloqueio automático. O bloqueador permanece responsável por autenticação e feedback de senha; o rice nunca lê, armazena ou registra senhas.

Se o visual não funcionar, tente digitar a senha normalmente e Enter. Como alternativa, use Ctrl+Alt+F3, autentique-se no TTY com sua conta e execute:

```sh
cd ~/Projetos/rice-minimal
python3 extras/rice.py lock-restore
```

Isso restaura os visuais anteriores e recarrega o Noctalia; não contorna nem remove o bloqueio. Volte ao VT gráfico e desbloqueie normalmente. O snapshot da tentativa fica em `backups/lock-visual-*`; cada restauração preserva um resgate do estado atual.

A ativação permanente pelo menu só é liberada após um teste com desbloqueio confirmado: `rice` → Lock Screen Settings → Activate reviewed RICE // LOCKED. Sem aprovação para o teste real, o tema permanece candidato e o bloqueio atual continua ativo.

## Restaurar toda a configuração anterior a esta finalização

```sh
cd ~/Projetos/rice-minimal
python3 scripts/restore_refined.py backups/rice-final-20261105-231618
hyprctl configerrors
```

O backup inclui o projeto funcional anterior, configuração/overrides reais do Noctalia e toda a árvore de paletas. O restaurador salva um resgate antes de restaurar e não reinicia nem encerra a sessão. As notas e resultados completos serão registrados abaixo após a validação.

## Controle unificado

`rice` abre `RICE // CONTROL` com os sete módulos pedidos. Wallpapers e Super reutilizam o backend existente; `wallpapers` e `supers` continuam válidos como entradas alternativas. Toda a navegação integrada compartilha a mesma tela curses, renderer, seleção, tratamento de erros e escrita segura. O editor de atalhos mantém o parser Lua, detecção de conflito, validação com `luac`, escrita atômica e backups únicos do Super.

Setas/j/k, Enter, números e Q navegam. A alternância da seleção usa dois quadros finitos em 36 ms, `noutrefresh`/`doupdate` e nenhuma atualização periódica enquanto parado. `A` liga/desliga as animações; a escolha é persistida. Minimal desliga as animações; Refined as permite. `RICE_NO_ANIMATIONS=1 rice` força a desativação. O terminal é restaurado por `curses.wrapper`, inclusive em exceções e interrupções.

Color Palette oferece consulta, regeneração e restauração. Restore / Backups lista os snapshots, restaura perfil/paleta após confirmação e mostra o comando de recuperação completa. A restauração completa permanece um comando explícito de terminal, para não substituir arquivos da aplicação enquanto navega.

## Waybar e perfis

O formato continua `[ 1 ] [ 2 ] [ 3 ]` na configuração JSON. O ativo usa negrito, acento adaptativo e fundo/borda transparentes. A fonte DejaVu Sans Mono preserva o avanço dos caracteres: `[ 1 ]` normal e negrito mediram 40 px no Pango. As transições são somente de cor (150 ms no Refined, 0 ms no Minimal). CPU, RAM, volume, janela ativa, relógio e separadores ASCII permanecem.

Os perfis existentes e o adaptador IPC do supervisor foram preservados. Nenhum novo processo permanente foi acrescentado nesta finalização. Launcher/notificações continuam no Noctalia, com o tema Matugen compartilhado; Kitty permanece em 0.85, Fish minimalista e Neovim puro. Não foram alterados drivers, kernel, discos, boot, autenticação nem serviços essenciais.

## Tema nativo do bloqueio

A candidata usa widgets nativos `label`, `clock` e `login_box`: título RICE // LOCKED, hora central grande, data e campo compacto. Cada monitor detectado recebe seu layout com coordenadas lógicas. O wallpaper vem dos metadados da paleta atual; as cores usam os roles da paleta customizada do Noctalia. Os pontos de atualização existentes do Matugen geram também `lockscreen.toml`; quando o layout estiver aprovado e ativo, o reload publica o overlay `~/.config/noctalia/rice-lock.toml` atomicamente.

Os níveis de escurecimento selecionam mínimos de 35%, 55% e 75%. A amostra central do wallpaper pode elevar esse mínimo para preservar contraste de texto; não há blur. Refined usa somente fade nativo de 150 ms; Minimal mantém as animações globais do shell desligadas. Indicadores de digitação e autenticação continuam sendo os do campo seguro nativo.

O instalador visual valida a candidata e a configuração completa mesclada antes de escrever. Remove apenas overrides visuais conflitantes; nunca modifica `allow_empty_password`, fingerprint, grace period, lock-before-suspend ou PAM. A restauração do tema de bloqueio preserva escolhas posteriores não relacionadas ao bloqueio (perfil, launcher e demais opções), em vez de sobrescrever todos os overrides do Noctalia.

Se mudar a disposição ou os monitores, prepare novamente o layout antes de testá-lo. O caminho de cores permanece Waypaper/`wallpapers`; alterações diretas por outros painéis do Noctalia continuam exigindo Color Palette → Update adaptive colors.

## System Doctor

```sh
rice doctor
rice doctor --json
```

Diagnóstico somente leitura, com `[ OK ]`, `[ WARN ]` e `[ FAIL ]`: versão/configuração Lua do Hyprland, Waybar, Noctalia, lockscreen, imagem/paleta, hook Waypaper/Matugen, Kitty/0.85, sintaxe Fish/Neovim/Super, perfil persistente, áudio, NetworkManager, portais, sessão gráfica UWSM e hashes dos arquivos gerenciados. Nenhuma correção, reload, bloqueio ou geração de cores é executada. WARN não torna a saída um erro; FAIL retorna código 1.

`config/integrity.json` contém hashes SHA-256 dos arquivos gerenciados de configuração/código/testes. Edições deliberadas posteriores exigem atualizar esse inventário; o Doctor somente informa a diferença, sem sobrescrever o arquivo editado.

## Arquivos desta finalização

- `config/waybar/style.css`, `extras/theme/theme.py`: destaque discreto e nova saída de lockscreen.
- `extras/rice.py`, `extras/ui.py`: centro modular e animações finitas.
- `extras/shortcuts.py`, `extras/supers/Supers`, `extras/wallpapers/wallpaper_tui.py`: entradas compartilhadas, backend preservado.
- `extras/doctor.py`, `config/integrity.json`: diagnóstico e integridade.
- `extras/lockscreen.py`: layout, contraste, candidata, validação, teste consentido, instalação e restauração visual.
- `extras/theme/profiles.py`: importação consistente no uso como CLI e como módulo.
- `scripts/restore_refined.py`: restauração também remove um overlay criado após o snapshot.
- `scripts/test_control_tui.py`, `tests/test_rice_final.py`, `tests/tui_smoke.py`: navegação integrada, resize, segurança e regressões.
- `scripts/test_adaptive_session.py`, `scripts/test_refined_session.py`: caminhos de navegação atualizados para o novo centro.
- `README.md`, `RICE-FINAL.md`, `.gitignore`: documentação e marcador de snapshot.

O commit final inclui também os arquivos da implementação Refined anterior que ainda não tinham sido commitados. Arquivos locais anteriores de diagnóstico, propostas e o repositório `super/` não são incorporados por engano.

## Validação e limites

- 27 testes de unidade/regressão passaram; 3 testes de segurança do Super passaram.
- Os três comandos curses foram exercitados em PTY. A travessia integrada abre todos os módulos de configuração sem criar outra sessão curses; o Doctor também foi executado separadamente na sessão real.
- Resize durante o submenu Super: 12×44 → 6×24 → 28×110, sem crash e com saída normal.
- Suíte real da Fase 3 aprovada após a atualização dos menus; wallpaper inicial preservado e Refined restaurado.
- Suíte real Refined aprovada: perfis após reload, paleta/wallpapers, barra única, launcher e teclado, notificação, janela flutuante e IPC de cliques de workspace.
- CSS validado pelo GTK3; candidata do bloqueio validada pelo Noctalia; `hyprctl configerrors` vazio. Captura real da Waybar inspecionada em `/tmp/rice-final-waybar.png`.
- O bloqueio real não é acionado sem a resposta à solicitação explícita de confirmação. Até esse teste, tanto o visual final quanto o desbloqueio na nova disposição são pendências; validar TOML não demonstra autenticação nem composição gráfica do lockscreen.
- Não foi feito benchmark de FPS/latência nem logout/login real. A persistência foi verificada por arquivos, cache e reload da configuração na mesma sessão. Steam/Proton e drivers não foram modificados.

Evidências consolidadas: `VALIDACAO-RICE-FINAL.json`; detalhes da suíte gráfica: `VALIDACAO-FASE4.json`.
