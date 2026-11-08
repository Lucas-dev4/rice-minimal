> Histórico da primeira implementação Refined. A finalização atual está em [RICE-FINAL.md](RICE-FINAL.md), incluindo a Waybar sem fundo no ativo e o controle unificado.

# Fase 4 — Rice Minimal Refined

Implementada sobre a Fase 3 em `main`. Perfil ativo ao concluir: `refined`.

## Aparência e uso

Execute `rice`, selecione `[6] Appearance / Profiles`:

```text
[1] Minimal
[2] Refined
[3] Current Profile
[Q] Back
```

As setas/j/k e Enter também funcionam no menu principal e no submenu. O perfil ativo aparece na tela. `[7] Restore previous profile` retorna à última escolha bem-sucedida. Falhas durante a aplicação tentam restaurar o perfil, a geração de cores e os valores reais anteriores do Noctalia; falhas da própria restauração são reportadas explicitamente.

Também é possível usar:

```sh
python3 extras/theme/profiles.py current
python3 extras/theme/profiles.py minimal
python3 extras/theme/profiles.py refined
python3 extras/theme/profiles.py restore
```

| Componente | Minimal | Refined |
|---|---|---|
| Waybar | transparente, ASCII, destaque de texto | transparente, ativo com fundo/acento e texto contrastante |
| Workspaces | `[ 1 ] [ 2 ] [ 3 ]`, números reais | mesmo formato e mesmas dimensões |
| Transições de CSS | 0 ms | 150 ms, somente cores e borda |
| Hyprland | animações desligadas | 120–160 ms, curva sem overshoot, entrada 98%, fade e foco/borda |
| Noctalia | animações desligadas | animações nativas rápidas |
| Launcher/notificações | mesma infraestrutura e paleta | monospace, translúcidos, bordas de 1 px |
| Blur | desligado | desligado |

CPU, RAM, volume, janela ativa e relógio foram preservados. A opacidade do Kitty continua 0.85. Não foi necessário modificar sua configuração nem instalar Fish plugins ou uma distribuição de Neovim. Cursor/seleção do Kitty e sintaxe do Fish já eram adaptativos; o gerador foi estendido com bordas flutuantes, separadores, cursor e diagnósticos do Neovim. Menus usam as cores ANSI adaptativas do terminal, com seleção reversa e títulos ASCII. `wallpapers` e `supers` preservam seus comportamentos.

## Paleta única e persistência

O Matugen continua sendo a fonte. A troca pelo Waypaper ou `wallpapers` usa o hook existente, lock de geração e fingerprint de imagem; eventos repetidos usam o cache. O perfil é persistido em `~/.local/state/rice-minimal/theme/profile`, independentemente da paleta. Alternar perfis republica a mesma paleta sem executar Matugen. Restaurar uma paleta antiga também respeita o perfil atual.

Cada geração contém `colors.css`, `profile.css`, `kitty.conf`, `colors.fish`, `nvim.lua`, `hyprland.lua`, `noctalia.json` e os metadados `palette.json`. O Noctalia recebe uma cópia atômica em `~/.config/noctalia/palettes/RiceMinimal.json`; seu launcher e notificações usam `theme.source = custom`. O bloco `terminal` é obrigatório para o parser da versão instalada 5.4.1. Os templates já selecionados do Noctalia continuam habilitados. Sua barra de fallback é ocultada novamente após o reload, enquanto a Waybar está presente.

O login continua usando a paleta em cache e o supervisor existente, sem Matugen na inicialização. O include `config.rice-appearance` é carregado por último no Hyprland. Nenhuma sessão ou computador foi reiniciado.

Troque o wallpaper pela GUI (`Super+Backspace`), por `wallpapers` ou pelo Waypaper; todos passam pelo mesmo hook. O atalho do painel de wallpaper do Noctalia foi removido porque contornava o hook. Uma troca feita direto pelo IPC do Noctalia continua fora do hook; nesse caso use `SYNC ALL`.

## Compatibilidade Waybar 0.15 / Hyprland Lua

A Waybar instalada ainda envia `dispatch workspace N` ao clicar, sintaxe rejeitada pelo Hyprland 0.57.1. `scripts/waybar_ipc.py` adapta esses pedidos para `hl.dispatch(hl.dsp.focus(...))`, somente para o filho Waybar do supervisor. Queries passam intactas e os eventos usam o socket real do compositor. Uma thread bloqueante no supervisor atende as solicitações: sem polling, novo daemon, pacote substituído ou compilação local da Waybar.

Inicie a barra por `python3 scripts/session.py`, como já faz o autostart. Executar `/usr/bin/waybar` diretamente ignora essa adaptação. A configuração de clique continua `activate`; o volume mantém seus cliques e scroll. Não havia scroll de workspaces configurado na Fase 3.

## Arquivos

- `config/waybar/config.jsonc`, `config/waybar/style.css`: layout ASCII e destaque com geometria estável.
- `config/hypr/rice-appearance.lua`: módulo Lua compartilhado dos perfis.
- `extras/theme/theme.py`: geração integrada, Noctalia, cores de Neovim, migração do cache e preservação do perfil na restauração.
- `extras/theme/profiles.py`: transação dos perfis, estado anterior e CLI.
- `extras/rice.py`, `extras/ui.py`: submenu, estado ativo e navegação/seleção.
- `scripts/session.py`, `scripts/waybar_ipc.py`: supervisor e compatibilidade de cliques com Lua.
- `scripts/install_refined.py`, `scripts/restore_refined.py`: instalação com snapshot e restauração com resgate.
- `scripts/test_refined_session.py`: aceitação real reproduzível.
- `tests/test_profiles.py`, `tests/test_waybar_ipc.py`, `tests/test_restore_refined.py`: testes de falha, persistência, compatibilidade e restauração.
- `.gitignore`, `README.md`, `PHASE4.md`: documentação e exclusão do marcador de backup.
- `VALIDACAO-FASE3.json` foi atualizado pela suíte existente; `VALIDACAO-FASE4.json` registra a aceitação da nova fase.

Arquivos reais instalados: `~/.config/hypr/hyprland.lua` (include), `~/.config/hypr/config/rice-appearance.lua`, `~/.config/noctalia/palettes/RiceMinimal.json`, overrides em `~/.local/state/noctalia/settings.toml`, gerações/estado do tema. Os demais programas continuam usando os includes da Fase 3.

## Validação executada

- `python3 -m unittest discover -s tests -v`: 18 testes, incluindo falha parcial de IPC, rollback, cache antigo, restauração de arquivos/symlinks em HOME temporário e paleta anterior em outro perfil.
- `python3 extras/supers/test_safety.py`: 3 testes.
- `python3 tests/tui_smoke.py`: três interfaces reais em PTY, saída normal.
- `python3 scripts/test_adaptive_session.py`, em Minimal: aceitação da Fase 3 aprovada, incluindo troca/restauração de imagens, hook, cache, Kitty 0.85, Fish, Neovim, Super e erros do compositor.
- `python3 scripts/test_refined_session.py`: ambos os perfis após reload real; wallpaper/Matugen preservando Refined; paleta compartilhada; barra única; launcher aberto e pesquisa via teclado virtual; notificação; janela flutuante; troca e retorno de workspace; mensagem real de clique da Waybar através do adaptador; submenu e persistência em cache.
- CSS completo lido pelo parser GTK3; `noctalia config validate` aprovado; `hyprctl configerrors` vazio.
- Capturas reais de Waybar, launcher e notificações inspecionadas. Capturas finais locais: `/tmp/rice-phase4-launcher-final.png` e `/tmp/rice-phase4-notification-final.png`.

Os dispatchers e estados de animação foram exercitados no compositor real; capturas estáticas não comprovam fluidez temporal. Não houve benchmark de FPS/latência/Steam/Proton nem novo login real. Persistência foi validada por arquivos, cache e reload sem encerrar a sessão. O teste de clique usa a mesma mensagem IPC da Waybar; não simula um mouse físico. Em uma sessão normal, repita a suíte acima e avalie visualmente foco/abertura e cliques de workspace. Não é necessário reboot.

O antigo `scripts/test_session.py` inicia outro supervisor e espera assumir a barra; não é apropriado executá-lo com o supervisor da sessão já ativo. A suíte adaptativa existente e a nova suíte foram usadas para a aceitação ao vivo.

## Checkpoint, backup e restauração

Branch de checkpoint: `checkpoint/phase3-before-refined` no commit original `6e57130`. A branch não inclui arquivos locais não rastreados. O snapshot em disco guarda as configurações do projeto da Fase 3, além dos arquivos reais e de toda a árvore de gerações do tema antes da instalação:

```text
backups/phase4-20261105-224647/
  project/
  home/
  theme/
  manifest.json
  git-status.txt
```

Backups antigos não foram removidos. O marcador `.phase4-backup` identifica esse snapshot. Para restaurar a configuração anterior, no terminal normal:

```sh
cd ~/Projetos/rice-minimal
python3 scripts/restore_refined.py backups/phase4-20261105-224647
hyprctl configerrors
```

O restaurador guarda o estado atual em `before-restore-*` dentro do backup, restaura os includes reais, overrides do Noctalia, gerações e arquivos anteriores do projeto, e recarrega configurações/cores sem logout. Arquivos novos sem include ativo podem permanecer no projeto. A compatibilidade IPC já carregada no supervisor permanece inofensiva até sua próxima inicialização; não exige reiniciar a sessão.

Para somente desfazer a escolha de aparência, use `rice` → `[7] Restore previous profile` ou `profiles.py restore`; não restaure toda a Fase 3.

Instalações futuras: `python3 scripts/install_refined.py` mostra os destinos; `--apply` instala com backup e ativa Refined. Se o supervisor já estava rodando antes da instalação, reinicie apenas `scripts/session.py` para carregar o adaptador; o autostart do próximo login já o utiliza. A instalação não sobrescreve o backup original ao ser repetida.

Referências consultadas: [animações Lua do Hyprland](https://wiki.hypr.land/configuring/core/animations/), [Noctalia v5.4.1 — parser de paletas](https://github.com/noctalia-dev/noctalia/blob/v5.4.1/src/theme/theme_service.cpp), [Waybar 0.15 — cliques de workspace](https://github.com/Alexays/Waybar/blob/0.15.0/src/modules/hyprland/workspace.cpp). A API foi conferida também nos módulos e stubs instalados.
