# Contrato de módulo do LW

Um **módulo** é uma seção da barra lateral do LW que pode ser ligada ou desligada inteira: telas, subcomandos e dependências juntos. SISTEMA, MÚSICA e JOGOS são os três de hoje.

Não é um sistema de plugins. Todo módulo mora neste repositório, o conjunto de campos é fechado (campo desconhecido é erro) e não há instalação de módulo de terceiros.

## As peças

| Peça | Onde | Papel |
|---|---|---|
| Manifesto | `modules/<id>/module.toml` | declara tudo que o módulo tem |
| README | `modules/<id>/README.md` | o que faz, dependências, comandos |
| Telas | `gui/<pasta>/*.qml` | uma pasta por módulo |
| Gancho | `gui/<pasta>/<Nome>Module.qml` | o que o módulo põe na janela fora da tela (opcional) |
| Comandos | `extras/cmd_<id>.py` | subcomandos `lw` do módulo |
| Lógica | `extras/*.py` | como hoje; os `cmd_*` só chamam |
| Escolhas do usuário | `~/.config/lw/config.toml` | módulos ligados e valores de config |

As telas e a lógica existentes **não mudam de lugar**: `gui/screens`, `gui/player`, `gui/arcade` e `extras/*.py` ficam onde estão. Mover tudo para `modules/<id>/` quebraria os imports `qs.player`/`qs.arcade`, o `sys.path` dos testes e o histórico, sem ganho visível. Módulo novo usa `gui/<id>/`.

O **núcleo** é o que existe com qualquer módulo: `shell.qml`, `Theme.qml`, `Status.qml`, `gui/components/`, `extras/cli.py`, `rice.py`, `doctor.py`, `ui.py`, `theme/`, e os novos `extras/modules.py` (lê os manifestos), `extras/settings.py` (lê a config) e `gui/Modules.qml` (lista para o QML). `extras/lwbar.py` também é núcleo: só lê arquivos e mostra JOGOS e MÚSICA na Waybar.

## O manifesto

Exemplo completo, MÚSICA:

```toml
id = "music"                    # igual ao nome da pasta; é o nome no IPC e em `lw gui music`
name = "MÚSICA"                 # texto da barra lateral
description = "Toca, organiza e baixa músicas pelo cliamp."
order = 20                      # posição na barra lateral
default = true                  # ligado quando o usuário não escolheu
required = false                # true: não pode ser desligado

[gui]
folder = "player"               # gui/player
hook = "MusicModule.qml"        # opcional
screens = [
    { name = "NOW PLAYING", file = "NowScreen.qml" },
    { name = "PLAYLIST",    file = "PlaylistScreen.qml" },
    { name = "EQUALIZER",   file = "EqScreen.qml" },
    { name = "RADIO",       file = "RadioScreen.qml" },
    { name = "LIBRARY",     file = "LibraryScreen.qml" },
    { name = "ONLINE",      file = "OnlineScreen.qml" },
]

[commands]
handler = "cmd_music"           # extras/cmd_music.py
names = ["library", "organize", "radio", "download"]
open = "music"                  # `lw music` = `lw gui music` (opcional)

[[dependency]]
command = "cliamp"
manual = "fora dos repositórios; ver modules/music/README.md"
why = "é o player"

[[dependency]]
command = "yt-dlp"
package = "yt-dlp"
optional = true
why = "busca e download do YouTube na tela ONLINE"

[config.dir]
default = "~/Músicas"
description = "Pasta das músicas"

[[shortcut]]
keys = "SUPER + M"
command = "lw music"
description = "LW em MÚSICA"
```

### Dependências

Cada `[[dependency]]` tem **um** jeito de conferir e **um** jeito de resolver:

| Campo | Valor |
|---|---|
| `command` | executável no PATH (ou em `~/.local/bin`); lista = qualquer um serve (`["ppsspp", "PPSSPPSDL"]`) |
| `python` | módulo importável (`"PIL"`) |
| `font` | família conhecida pelo fontconfig |
| `package` | pacote do pacman |
| `aur` | pacote do AUR (não entra no `pacman -S`) |
| `manual` | frase curta, para o que não é pacote |
| `optional` | `true`: sem ele só some o que está em `why` |
| `why` | o que depende disso |

Drivers e kernel nunca são dependência declarada (ex.: `nvidia-smi`, que o `compat` usa se existir). Emulador em AppImage também não: quem o acha é o `lw emu list`, pelas pastas da config.

### Subcomandos

`names` são os primeiros argumentos de `lw` que pertencem ao módulo. Um nome só pode ter um dono. O handler tem uma função:

```python
def register(actions, common):
    """Cria os parsers deste módulo; cada um diz que função o executa."""
    p = actions.add_parser('radio').add_subparsers(dest='operation', required=True)
    p.add_parser('saved', parents=[common]).set_defaults(run=lambda args: radio.saved())
```

- `run(args)` devolve `data` ou `(data, warnings)`. Quem monta o envelope e trata o erro é o `cli.py`.
- **Fluxo** (várias linhas JSON, sem envelope): `set_defaults(run=..., stream=True)`; a função imprime e devolve o código de saída. Já são assim `wallpaper thumbs`, `emu pad-watch` e `doctor --stream`.
- `cli.py` importa só o handler dono do comando pedido. `cli.COMMANDS` passa a vir dos manifestos.
- Comando de módulo desligado: `{"ok": false}`, código `invalid`, mensagem `módulo JOGOS desligado; ligue com: lw modules enable games`. O vigia de sessão (`games.py watch`) roda direto, então não morre se JOGOS for desligado no meio.
- Do núcleo, sempre disponíveis: `gui`, `doctor`, `modules` e os `lock-*` antigos do `rice.py`.

### Config

`~/.config/lw/config.toml`, uma tabela por módulo:

```toml
[modules]
games = false          # ausente = o `default` do manifesto

[music]
dir = "~/Áudio"
```

- O padrão existe só no manifesto. Arquivo ou chave ausente = padrão. O tipo é o do padrão, e `~/` no começo vira a pasta pessoal (também em listas).
- `settings.get('music', 'dir')` no Python; `Modules.config("music", "dir")` no QML.
- Arquivo quebrado ou tipo errado: vale o padrão e o `lw doctor` mostra FAIL. O LW sempre abre.
- `lw modules enable|disable` muda só a linha do módulo em `[modules]`: backup, temp + rename, e o resultado precisa passar no `tomllib` antes de substituir.
- **Segredo não entra aqui** (a config é entregue ao QML por variável de ambiente). `~/.config/lw/igdb.json` continua à parte.
- JOGOS já aceita `~/.local/share/lw/games-config.json`. Ordem: `config.toml`, depois esse arquivo, depois o padrão.

### Atalhos

`[[shortcut]]` documenta o atalho **padrão** do Hyprland. Quem cria o atalho continua sendo `config/hypr/rice-integration.lua`, editável em SHORTCUTS; por isso o doctor não cobra a tecla instalada, e um teste confere só que o atalho declarado existe no `.lua` do repositório. Teclas de dentro da janela não são declaradas: ficam nos `hints` da tela ou do gancho.

## Como o shell.qml descobre os módulos

1. `lw gui` lê os manifestos e a config e abre o Quickshell com `LW_MODULES`: o mesmo JSON do `data` de `lw modules list --json` (id, nome, pasta, gancho, telas e config já resolvida), na ordem da barra lateral.
2. `gui/Modules.qml` lê a variável ao nascer. Sem ela (`qs -p gui`, como no `scripts/music-check.sh`), chama `lw modules list --json`.
3. `shell.qml` troca a lista fixa `groups` por `Modules.active`; `lastScreen` vira um mapa por id; `Alt+1…9` segue a posição.
4. Para cada módulo ativo com `hook`, um `Loader` carrega o gancho.

Usar a variável evita abrir a janela vazia: o `lw gui` já é Python e já passa `LW_START_GROUP` assim. Ligar ou desligar um módulo vale na **próxima abertura** do LW.

`lw gui <id>` ou `lw music` de módulo desligado não abre nada e sai com o erro acima.

**A única linha que um módulo novo acrescenta ao núcleo** é `import qs.<pasta>` no `shell.qml`. O Quickshell só indexa pastas importadas de forma estática: testei carregar uma tela por caminho sem esse import e ela falha (`Vizinho is not a type`); pôr o import só na própria tela também falha (`module is not installed`). Import não executa nada: no mesmo teste, um singleton nunca usado não foi criado. Logo, com JOGOS desligado, `Games` não nasce, desde que só o módulo fale com ele.

## O gancho: o que sai do shell.qml

Hoje o `shell.qml` cita `Music` e `Games` em toda parte. Filtrar `groups` esconderia as telas, mas ligaria o cliamp e o scan do mesmo jeito. O gancho tira isso de lá. O tipo base `gui/components/LwModule.qml` tem todos os campos com um padrão neutro; cada módulo preenche o que usa:

| Campo | Para quê | Hoje no shell.qml |
|---|---|---|
| `summary` | linha da seção fechada | faixa tocando; jogo em sessão |
| `sidebar` (Component) | bloco de baixo da barra lateral | CURRENT; mini player e VOL; fontes e SESSÃO |
| `header` (Component) | cabeçalho comum das telas | `musicHeader` |
| `ready`, `gate` (Component) | o que mostrar no lugar da tela | cliamp offline / START |
| `overlay` (Component) | camada sobre a janela | `GameSheet`, `InstallSheet`, `LaunchScreen`, `DropArea` |
| `footerLeft` (Component), `context`, `contextClicked()` | rodapé | SYNC ALL; saída do cliamp; último scan; LOG |
| `idleText`, `hints` | mensagem e dicas padrão | `typed.full`, `globalHints` |
| `bootStep` | linha do boot | `BootScreen.steps` |
| `started()` | janela abriu | `Games.recover()` |
| `entered()`, `left()` | entrou/saiu da seção | `enterGroup()`, fechar as fichas |
| `closing(active)` | janela fechando | `quit()`: parar ou só salvar a sessão |
| `screenLoaded(item)` | tela pronta | `levels` do espectro; sinais `open`/`launch`/`installer` |
| `overlayKey(event)` | tecla antes da tela | fichas abertas; `Enter` no START |
| `key(event)` | tecla da seção aberta, depois da tela | `n`, `p`, setas, volume… |
| `backgroundKey(event)` | tecla quando outra seção está aberta | `Espaço` toca/pausa em qualquer lugar |
| `state()`, `act(op, arg)` | IPC dos testes | `state`, `act`, `openSheet`, `installer` |

Ordem das teclas, igual à de hoje: `Ctrl+J` → boot → `overlayKey` → `Alt+n` → tela → `key` → `1…n`, `q`/`Esc`, `↑↓` → `backgroundKey`. Os nomes do IPC não mudam; `state` continua um objeto plano (soma dos módulos), para o `music-check.sh` seguir funcionando.

Regra: **depois da sessão 5, `shell.qml` não cita `Music`, `Games`, `Spectrum` nem `Downloads`**, e um teste confere isso.

## Como o `lw doctor` lê as dependências

Depois das checagens de sessão, para cada módulo **ativo** e cada `[[dependency]]`:

| Situação | Status |
|---|---|
| encontrada | `OK`, com o caminho |
| obrigatória ausente | `FAIL` |
| opcional ausente | `INFO`, com o `why` (não conta como problema) |
| manifesto inválido | `FAIL`; o módulo não aparece, o resto do LW abre |

- Cada item mantém `status`, `name`, `detail` e ganha `module`. A tela DOCTOR agrupa por `module` quando ele vier; `INFO` fica apagado e fora de ATTENTION.
- No fim, até dois itens, com os pacotes de todos os módulos sem repetição, obrigatórios e opcionais separados: `sudo pacman -S --needed …`. AUR e manual saem cada um com sua frase. O LW só escreve o comando, nunca roda.
- Formato de saída inalterado: lista JSON pura, `--stream` linha a linha, código 1 se houver FAIL.
- A lista fixa `('matugen','waypaper','kitty','fish','nvim','qs')` do `doctor.py` vai para o manifesto de SISTEMA, que como obrigatório também guarda as dependências do núcleo.

## Os três módulos de hoje

### SISTEMA: `modules/system/`

- `required = true`, `order = 10`. Wallpaper, paleta, atalhos e doctor são a base do resto.
- **Telas** (`gui/screens`): WALLPAPERS, SHORTCUTS, PROFILES, PALETTE, DOCTOR, BACKUPS, LOCK, GREETER.
- **Comandos** (`cmd_system`): `status`, `wallpaper`, `palette`, `profile`, `greeter`, `sync`, `shortcuts`, `backups`, `lock`, `bt` (o `bt` passa para DISPOSITIVOS na sessão 9).
- **Gancho**: `sidebar` (CURRENT), `footerLeft` (SYNC ALL), `context` (LOG), `idleText`.
- **Obrigatórias**: `qs` quickshell · `hyprctl` hyprland · `noctalia` · `matugen` · `waypaper` · `kitty` · `fish` · `nvim` neovim · `luac` lua · `PIL` python-pillow · fonte ttf-jetbrains-mono-nerd.
- **Opcionais**: `waybar` · `wpctl` wireplumber · `wl-copy` wl-clipboard · `bluetoothctl` bluez-utils.
- **Config**: nada no começo.
- **Atalhos**: `SUPER + BackSpace` (`lw gui`).

### MÚSICA: `modules/music/`

- `order = 20`. Telas e manifesto no exemplo acima.
- **Comandos** (`cmd_music`), hoje scripts que a GUI chama direto: `library scan|lookup|apply`, `organize plan|apply|move`, `radio search|saved|add`, `download` (fluxo, `ytdl.py`).
- **Gancho**: `summary`, `sidebar`, `header`, `ready`/`gate`, `overlay` (soltar arquivos), `context`, `bootStep`, `entered`, `closing`, `key`, `backgroundKey`, `screenLoaded`, `act`.
- **Singletons**: `Music`, `Spectrum`, `Downloads` (continuam em `gui/`).
- **Obrigatórias**: `cliamp` (manual) · `wpctl` wireplumber · `pactl` libpulse.
- **Opcionais**: `cava` (visualizador) · `ffmpeg`/`ffprobe` ffmpeg (LIBRARY, detalhes, download) · `yt-dlp` (ONLINE) · `playerctl` (capa) · `zenity` (escolher arquivos) · `gio` glib2 (lixeira).
- **Config**: `dir`.

### JOGOS: `modules/games/`

- `order = 30`.
- **Telas** (`gui/arcade`): BIBLIOTECA, BACKLOG, DESEMPENHO, EMULADORES.
- **Comandos** (`cmd_games`): `compat`, `emu` (já existem) e `game` (hoje `games.py` direto): `scan`, `list`, `add`, `set`, `launch`, `stop`, `arrange`, `meta`, `installers`, `install`…; `open = "games"`.
- **Gancho**: `summary`, `sidebar`, `overlay` (fichas e tela de lançamento), `context`, `bootStep`, `started`, `entered`, `left`, `overlayKey`, `screenLoaded`, `act`.
- **Singleton**: `Games`.
- **Obrigatórias**: nenhuma; a lista abre vazia.
- **Opcionais**: `wine` · `umu-run` umu-launcher (Proton) · `gamemoderun` gamemode · `mangohud` · `gamescope` · `steam` · `retroarch` · `dolphin-emu` · `ppsspp` · `ryujinx` · `lspci` pciutils · `zenity`.
- **Config**: `rom_dirs`, `ready_dirs`, `emulator_dirs`, `download_dirs`, `retroarch`, `cores_dir`, `emulators`, `compat_list` (caminho do JSON com a lista de jogos; lista longa não vai dentro do `config.toml`).
- **Atalhos**: `SUPER + G` (`lw games`).

## Módulo novo, passo a passo

1. `modules/<id>/module.toml` e `README.md`.
2. Telas em `gui/<id>/`, seguindo o protótipo; gancho se precisar.
3. `extras/cmd_<id>.py` e testes em `tests/test_cli_json.py`.
4. `import qs.<id>` no `shell.qml`.
5. `python3 scripts/integrity.py`.

É módulo se tem dependências próprias **e** faz sentido desligar sozinho; senão é tela de um módulo existente. Por essa regra TERMINAL, DISPOSITIVOS, ENVIAR (kdeconnect, rsync, samba) e IA são módulos: `terminal`, `devices`, `send`, `ai`. O `id` é em inglês como os de hoje; o nome na tela, em português.

## Testes do contrato

`tests/test_modules.py`: todo manifesto só tem campos conhecidos; `id` igual à pasta; QML e handler existem; o handler registra exatamente os `names`; nenhum comando repetido; a pasta está importada no `shell.qml`; os atalhos estão no `.lua`; config ausente, parcial e quebrada; módulo desligado recusa comandos. `scripts/integrity.py` passa a incluir `modules/*/module.toml`.

## O que muda nas sessões

- **2**: nasce com `extras/settings.py`, `extras/modules.py` e os três `module.toml` só com `id`, `name` e `[config]`, porque os padrões moram no manifesto.
- **3**: cria o gancho base, `Modules.qml`, `LW_MODULES` e `cmd_system`. As funções de SISTEMA saem de `cli.py`; em `tests/test_cli_json.py` mudam só os alvos dos mocks (`cli.thumb_path` → `cmd_system.thumb_path`), nunca o que é verificado. Até a 5, MÚSICA e JOGOS ainda citados no `shell.qml` são esperados.
- **4 e 5**: os scripts chamados direto pela GUI (`library.py`, `organize.py`, `radio.py`, `ytdl.py`, `games.py`) passam para `lw`. O JSON deles é plano (`{"ok", …campos}`) e o do `lw` tem `data`, então `Games.qml`, `Downloads.qml` e as telas mudam a leitura. Vão junto os `sh -c` de lógica: `command -v` em `OnlineScreen.qml` e `GameSheet.qml`, e a busca de prefixos em `LibraryView.qml`.
- **6**: `lw modules`, filtro de ativos e o novo doctor.

## Exceções à regra "a GUI não tem lógica"

O código de hoje não cumpre a regra ao pé da letra. O contrato aceita só estas exceções, sempre com o comando declarado em `[[dependency]]`:

- **Fluxo ao vivo do player e do áudio**: `cliamp`, `cava`, `pactl`, `wpctl`, `noctalia` (volume), `playerctl`, `ffprobe` em `Music.qml`, `Spectrum.qml` e no painel de saída. Passar cada evento pelo Python atrasaria a tela.
- **Diálogo e área de transferência**: `zenity`, `wl-copy`.
- **Gravar atalho**: o submapa do `hyprctl` em SHORTCUTS.
- **Preferências só visuais** em `~/.local/state/rice-minimal/gui/`.

Módulo novo não acrescenta exceção sem antes mudar esta lista.
