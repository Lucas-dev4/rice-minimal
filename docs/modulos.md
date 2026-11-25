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
names = ["library", "organize", "radio", "online", "download", "cliamp"]
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
description = "Pasta das músicas; o initial_directory do cliamp é escrito a partir dela"

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
- **Fluxo** (várias linhas JSON, sem envelope): `set_defaults(run=..., stream=True)`; a função imprime e devolve o código de saída. Já são assim `wallpaper thumbs`, `emu pad-watch`, `doctor --stream`, `bt` e `download`.
- `cli.py` importa só o handler dono do comando pedido. `cli.COMMANDS` vem dos manifestos: os `names` e o `open`, que também só pode ter um dono.
- Na GUI, `RiceCommand` roda com `Theme.rice` (`setsid --fork --wait`): a ação termina mesmo se o LW fechar, mas um sinal não chega nela. O que precisa parar (download, buscas) usa `program: Theme.lw`, sem o `setsid`.
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

- O padrão existe só no manifesto. Arquivo ou chave ausente = padrão. O tipo é o do padrão (lista e tabela são de textos; texto vazio não vale), e `~/` no começo vira a pasta pessoal (também em listas).
- `settings.get('music', 'dir')` no Python; `Modules.config("music", "dir")` no QML.
- Arquivo quebrado ou tipo errado: vale o padrão e o `lw doctor` mostra FAIL. O LW sempre abre.
- `lw modules enable|disable` muda só a linha do módulo em `[modules]`: backup, temp + rename, e o resultado precisa passar no `tomllib` antes de substituir.
- **Segredo não entra aqui** (a config é entregue ao QML por variável de ambiente). `~/.config/lw/igdb.json` continua à parte.
- JOGOS já aceita `~/.local/share/lw/games-config.json`. Ordem: `config.toml`, depois esse arquivo, depois o padrão.

### Atalhos

`[[shortcut]]` documenta o atalho **padrão** do Hyprland. Quem cria o atalho continua sendo `config/hypr/rice-integration.lua`, editável em SHORTCUTS; por isso o doctor não cobra a tecla instalada, e um teste confere só que o atalho declarado existe no `.lua` do repositório. Teclas de dentro da janela não são declaradas: ficam nos `hints` da tela ou do gancho.

## Como o shell.qml descobre os módulos

1. `lw gui` lê os manifestos e a config e abre o Quickshell com `LW_MODULES`: o mesmo JSON do `data` de `lw modules list --json` (id, nome, pasta, gancho, telas e config já resolvida), na ordem da barra lateral.
2. `gui/Modules.qml` lê a variável ao nascer. Sem ela (`qs -p gui`, como no `scripts/music-check.sh`), `Modules.active` começa com SISTEMA, que é obrigatório, e os outros entram quando `lw modules list --json` responde; a lista nunca fica vazia. A cópia de SISTEMA no `Modules.qml` é igual ao manifesto, e um teste confere.
3. `shell.qml` troca a lista fixa `groups` por `Modules.active`; `lastScreen` vira um mapa por id; `Alt+1…9` segue a posição.
4. Para cada módulo ativo com `hook`, um `Loader` carrega o gancho.

Usar a variável evita abrir a janela vazia: o `lw gui` já é Python e já passa `LW_START_GROUP` assim. Ligar ou desligar um módulo vale na **próxima abertura** do LW.

`lw gui <id>` ou `lw music` de módulo desligado não abre nada e sai com o erro acima.

**A única linha que um módulo novo acrescenta ao núcleo** é `import qs.<pasta>` no `shell.qml`. O Quickshell só indexa pastas importadas de forma estática: testei carregar uma tela por caminho sem esse import e ela falha (`Vizinho is not a type`); pôr o import só na própria tela também falha (`module is not installed`). Import não executa nada: no mesmo teste, um singleton nunca usado não foi criado. Logo, com JOGOS desligado, `Games` não nasce, desde que só o módulo fale com ele.

## O gancho: o que sai do shell.qml

Hoje o `shell.qml` cita `Music` e `Games` em toda parte. Filtrar `groups` esconderia as telas, mas ligaria o cliamp e o scan do mesmo jeito. O gancho tira isso de lá. O tipo base `gui/components/LwModule.qml` tem todos os campos com um padrão neutro; cada módulo preenche o que usa:

**Nenhum campo é obrigatório.** O gancho em si é opcional, e um módulo simples pode ter o `LwModule` vazio (ou nem ter gancho): a seção abre as telas do manifesto e o resto fica neutro. Os únicos que andam juntos estão na coluna "se usar".

Preenchidos pelo `shell.qml`; o módulo só lê, nunca escreve:

| Campo | Valor |
|---|---|
| `active` | a seção deste módulo está aberta |
| `current` | a tela dele, pela ordem do manifesto (cada seção lembra a sua) |
| `parked` | janela escondida (`Ctrl+J`) |
| `keyTarget` | quem recebe o foco do teclado depois de um clique |

Opcionais, com o padrão neutro:

| Campo | Para quê | Padrão neutro | Se usar |
|---|---|---|---|
| `summary` | linha da seção fechada | `""`: sem linha | |
| `sidebar` (Component) | bloco de baixo da barra lateral | `null`: vazio | |
| `header` (Component) | cabeçalho comum das telas | `null`: cada tela desenha o seu | a raiz precisa ter `height` |
| `ready` | falso: esconde a tela e mostra o `gate` | `true` | preencha `gate` |
| `gate` (Component) | o que mostrar no lugar da tela | `null` | preencha `ready` |
| `overlay` (Component) | camada sobre a janela | `null` | |
| `footerLeft` (Component) | bloco à esquerda do rodapé | `null` | |
| `context` | ponta direita do rodapé | `"—"` | |
| `contextClickable`, `contextClicked()` | clique nessa ponta | `false`, não faz nada | os dois juntos |
| `idleText` | mensagem quando nada acontece | `""` | |
| `hints` | dicas padrão da seção | `[]`: as dicas da janela | |
| `bootStep` | linha do boot, `{ label, done }` | `null`: "reading profile" | `done` precisa virar `true` |
| `openScreen(index)` (sinal) | o módulo pede uma tela da própria seção | ninguém emite | só vale com a seção aberta |
| `started()` | janela abriu | não faz nada | o shell passa a chamar na sessão 5 |
| `entered()`, `exited()` | entrou/saiu da seção | não fazem nada | |
| `closing(active)` | janela fechando (`active`: nesta seção) | não faz nada | |
| `screenLoaded(item)` | tela do módulo pronta | não faz nada | |
| `overlayKey(event)` | tecla antes da tela | `false`: não usou | confira `active` |
| `key(event)` | tecla da seção aberta, depois da tela | `false` | |
| `backgroundKey(event)` | tecla quando ninguém mais usou | `false` | |
| `state()`, `act(op, arg)` | IPC dos testes | `{}`, `false`: não conhece a ação | |

Quem recebe o quê: `overlayKey`, `backgroundKey`, `closing`, `state` e `act` vão a **todos** os ganchos, na ordem da barra lateral (o primeiro que responde `true` encerra); `key`, `screenLoaded`, `entered` e `exited`, só ao da seção. O gancho que carrega depois da janela recebe `entered` e `screenLoaded` ao chegar. `exited` não se chama `left` porque esse nome já é uma âncora do `Item` e a chamada falha.

O gancho não enxerga o `shell.qml`. O que os dois precisam ver passa pelo `Status.qml`: `logOpen` (painel LOG aberto) e `logLine` (última linha do log), `wallpaper` e `profile` (do `lw status`, que o shell chama porque o boot e as cores do terminal dependem dele) e `error`, uma falha que fica no rodapé, acima de qualquer mensagem, até a ação rodar de novo (SYNC ALL).

O gancho nasce com a janela e vive até ela fechar; `sidebar` e `footerLeft` também, só alternando `visible`. O `bootStep` neutro é "reading profile".

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
- **Comandos** (`cmd_music`): `library scan|lookup|apply`, `organize plan|apply|move`, `radio search|saved|add`, `online status|search` (yt-dlp), `download` (fluxo, `ytdl.py`) e `cliamp sync`; `open = "music"`.
- **Gancho**: `summary`, `sidebar`, `header`, `ready`/`gate`, `overlay` (soltar arquivos), `context`, `idleText`, `hints`, `bootStep`, `entered`, `closing`, `screenLoaded`, `overlayKey` (START), `key`, `backgroundKey`, `state`, `act`.
- **Singletons**: `Music`, `Spectrum`, `Downloads` (continuam em `gui/`).
- **Obrigatórias**: `cliamp` (manual) · `wpctl` wireplumber · `pactl` libpulse.
- **Opcionais**: `cava` (visualizador) · `ffmpeg`/`ffprobe` ffmpeg (LIBRARY, detalhes, download) · `yt-dlp` (ONLINE) · `playerctl` (capa) · `zenity` (escolher arquivos) · `gio` glib2 (lixeira).
- **Config**: `dir`. É a fonte de verdade: `lw cliamp sync` escreve o `initial_directory` de `~/.config/cliamp/config.toml` a partir dela (com backup), nunca o contrário. O `Music.qml` chama antes de ligar o cliamp.

### JOGOS: `modules/games/`

- `order = 30`.
- **Telas** (`gui/arcade`): BIBLIOTECA, BACKLOG, DESEMPENHO, EMULADORES.
- **Comandos** (`cmd_games`): `compat`, `emu` (já existem) e `game` (hoje `games.py` direto): `scan`, `list`, `add`, `set`, `launch`, `stop`, `arrange`, `meta`, `installers`, `install`…; `open = "games"`.
- **Gancho**: `summary`, `sidebar`, `overlay` (fichas e tela de lançamento), `context`, `bootStep`, `started`, `entered`, `exited`, `overlayKey`, `screenLoaded`, `act`.
- **Singleton**: `Games`.
- **Obrigatórias**: nenhuma; a lista abre vazia.
- **Opcionais**: `wine` · `umu-run` umu-launcher (Proton) · `gamemoderun` gamemode · `mangohud` · `gamescope` · `steam` · `retroarch` · `dolphin-emu` · `ppsspp` · `ryujinx` · `lspci` pciutils · `zenity`.
- **Config**: `rom_dirs`, `ready_dirs`, `emulator_dirs`, `download_dirs`, `retroarch`, `cores_dir`, `emulators`, `compat_list` (caminho do JSON com a lista de jogos; lista longa não vai dentro do `config.toml`; caminho relativo conta a partir do repositório).
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
- **3**: cria o gancho base, `Modules.qml`, `LW_MODULES` e `cmd_system`. As funções de SISTEMA saem de `cli.py`; em `tests/test_cli_json.py` mudam só os alvos dos mocks (`cli.thumb_path` → `cmd_system.thumb_path`), nunca o que é verificado. Nasce também o `lw modules list`, que o `Modules.qml` usa, e MÚSICA e JOGOS ganham `order`, `default` e `[gui]` sem `hook`; comandos e dependências deles ficam para a 4 e a 5. O `shell.qml` lê do gancho só o que SISTEMA usa (`sidebar`, `footerLeft`, `context*`, `idleText`, `hints`, `bootStep`); os outros campos já existem na base. Até a 5, MÚSICA e JOGOS ainda citados no `shell.qml` são esperados.
- **4 e 5**: os scripts chamados direto pela GUI (`library.py`, `organize.py`, `radio.py`, `ytdl.py`, `games.py`) passam para `lw`. O JSON deles é plano (`{"ok", …campos}`) e o do `lw` tem `data`, então `Games.qml`, `Downloads.qml` e as telas mudam a leitura. Vão junto os `sh -c` de lógica: `command -v` em `OnlineScreen.qml` e `GameSheet.qml`, e a busca de prefixos em `LibraryView.qml`.
- **6**: `lw modules enable|disable`, filtro de ativos e o novo doctor.

## Exceções à regra "a GUI não tem lógica"

O código de hoje não cumpre a regra ao pé da letra. O contrato aceita só estas exceções, sempre com o comando declarado em `[[dependency]]`:

- **Fluxo ao vivo do player e do áudio**: `cliamp`, `cava`, `pactl`, `wpctl`, `noctalia` (volume), `playerctl`, `ffprobe` em `Music.qml`, `Spectrum.qml` e no formato da saída (`MusicModule.qml`). Passar cada evento pelo Python atrasaria a tela.
- **Ligar e desligar o cliamp** (`sh -c` em `Music.qml`): quais arquivos da sessão ainda existem, e o SIGTERM pelo `cliamp.sock.pid`, que sai enquanto a janela fecha.
- **Diálogo e área de transferência**: `zenity`, `wl-copy`.
- **Gravar atalho**: o submapa do `hyprctl` em SHORTCUTS.
- **Preferências só visuais** em `~/.local/state/rice-minimal/gui/`.

Módulo novo não acrescenta exceção sem antes mudar esta lista.
