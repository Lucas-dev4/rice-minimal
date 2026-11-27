# SISTEMA

A base do LW: wallpaper, paleta, atalhos, perfil, bloqueio, tela de login, backups e diagnóstico. É obrigatório, não pode ser desligado.

Abre com `Super+BackSpace` ou `lw gui`.

## Telas

| Tela | Para quê |
|---|---|
| WALLPAPERS | escolher e aplicar o wallpaper (a paleta vem junto) |
| SHORTCUTS | ver, gravar e apagar atalhos do Hyprland |
| PROFILES | trocar entre Minimal e Refined |
| PALETTE | ver, gerar de novo e restaurar a paleta |
| DOCTOR | conferir a sessão, os programas e os arquivos |
| BACKUPS | listar backups e o comando que restaura cada um |
| LOCK | aparência da tela de bloqueio (senha e PAM nunca mudam) |
| GREETER | enviar o tema para a tela de login |

Na barra lateral fica o CURRENT (wallpaper, paleta e perfil de agora); no rodapé, SYNC ALL e LOG.

## Dependências

Obrigatórias (valem também para o núcleo do LW):

```
sudo pacman -S --needed quickshell hyprland noctalia matugen waypaper kitty fish neovim lua python-pillow ttf-jetbrains-mono-nerd
```

Opcionais: `waybar` (a barra), `wireplumber` (checagem de áudio do doctor), `wl-clipboard` (copiar em PALETTE e BACKUPS), `bluez-utils` (`lw bt`).

O `waypaper` está no repositório do CachyOS; no Arch puro ele vem do AUR.

**Noctalia e Quickshell:** o LW usa o `noctalia` do extra (shell próprio, sem Quickshell; é quem responde ao `noctalia msg`) e o `quickshell` do extra, para a janela. O `noctalia-shell` (repositório cachyos e AUR) é outro programa: depende do `noctalia-qs`, um fork do Quickshell que conflita com o `quickshell`. Com o `noctalia-qs` ou o `noctalia-shell` instalados, o `lw doctor` mostra o conflito e o `lw setup` não pede nem `quickshell` nem `noctalia`: a troca é à mão.

`lw setup` mostra o que falta de cada módulo e instala depois de confirmar; `lw modules deps sistema` mostra o mesmo no terminal.

## Comandos

Todos aceitam `--json`, menos `bt` e `wallpaper thumbs`.

| Comando | O que faz |
|---|---|
| `lw status` | resumo: perfil, paleta, wallpaper, bloqueio |
| `lw wallpaper list` · `apply ARQUIVO` · `thumbs` | lista, aplica, gera miniaturas (uma linha JSON por imagem) |
| `lw palette show` · `regenerate [--scheme NOME]` · `restore` | paleta atual, gerar de novo, voltar a anterior |
| `lw profile get` · `set minimal\|refined` · `restore` | perfil de aparência |
| `lw greeter status` · `sync` · `auto on\|off` | tema na tela de login |
| `lw sync` | reaplica tudo em ordem (o SYNC ALL) |
| `lw shortcuts list` · `check` · `backups` · `set` · `delete` · `restore` | atalhos do Hyprland, com backup |
| `lw backups list` | backups e como restaurar cada um |
| `lw lock status` · `check` · `update` · `dim NÍVEL` · `restore` | aparência do bloqueio |
| `lw lock trial --confirm` · `activate --confirm` | teste real e ativação (o `trial` bloqueia a tela) |
| `lw bt` | menu de Bluetooth no terminal |

## Onde fica

- Telas e gancho: `gui/screens/` (`SystemModule.qml`)
- Comandos: `extras/cmd_system.py`; a lógica continua em `extras/theme/`, `shortcuts.py`, `lockscreen.py`, `backups.py` e `bluetooth.py`
- Config, em `~/.config/lw/config.toml` (vale na próxima abertura do LW):

```toml
[system]
fullscreen = true     # o padrão; false abre a janela flutuante
```
