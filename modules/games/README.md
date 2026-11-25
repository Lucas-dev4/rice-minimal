# JOGOS

Biblioteca, backlog e tempo de jogo: Steam, jogos de Windows (Wine ou Proton-GE), Hydra e emuladores.

Abre com `Super+G` ou `lw games`.

## Telas

| Tela | Para quê |
|---|---|
| BIBLIOTECA | a grade de capas: buscar, filtrar, abrir a ficha, adicionar (`a`), instalar (`i`), procurar de novo (`r`) |
| BACKLOG | quero jogar, jogando, zerado e largado; arrastar ou `Shift+setas` muda a coluna e a prioridade |
| DESEMPENHO | horas, semanas, mais jogados, zerados e recomendações |
| EMULADORES | resolução, tela cheia, vsync, FPS e o controle de cada emulador |

A ficha do jogo, INSTALAR e a tela de lançamento abrem por cima da janela. Na barra lateral ficam as fontes e a sessão de agora. Entrar em JOGOS procura jogos uma vez por janela.

## Sessão

Ao lançar, o LW põe `LW_GAME_ID` no ambiente do jogo e inicia um vigia separado (`games.py watch`). A sessão abre quando um processo com essa variável aparece e fecha quando o último some. A contagem segue com o LW fechado; se o vigia morrer, a sessão volta ou fecha na próxima abertura. Uma sessão por vez. Não há tempo mínimo; o fim tem até 2 s de erro. Abaixo de 1 h a ficha, a BIBLIOTECA e o DESEMPENHO mostram minutos, e uma sessão que termina com o LW fechado é avisada quando ele abre.

Jogo da Steam é lançado sem o `LW_GAME_ID`, porque uma Steam fechada abre por esse comando, o herdaria e ficaria aberta depois do jogo. A sessão dele vive enquanto existir o `reaper SteamLaunch AppId=<ID>` que a Steam põe na frente do jogo, ou um processo com o `SteamAppId`; o PARAR nunca alcança o cliente.

Emulador que esconde o próprio ambiente (o Ryujinx) conta pelo `sh` que o LW deixa na frente dele com o `LW_GAME_ID`; o PARAR alcança os processos escondidos da sessão que o LW criou para aquele jogo, e só dela.

## Dependências

Nenhuma é obrigatória: sem elas a lista abre, e só some o que está ao lado.

```
sudo pacman -S --needed wine umu-launcher steam gamemode mangohud gamescope retroarch dolphin-emu ppsspp ryujinx pciutils zenity
```

`wine` (instalar e rodar sem Proton), `umu-launcher` (Proton-GE), `steam`, `gamemode`/`mangohud`/`gamescope` (opções da ficha), `retroarch` (NES a PS1), `dolphin-emu` (GameCube e Wii), `ppsspp` (PSP), `ryujinx` (Switch), `pciutils` (placa de vídeo no `lw compat`), `zenity` (escolher arquivos).

O `ryujinx` está no repositório do CachyOS; no Arch puro ele vem do AUR. PCSX2, Azahar e shadPS4 entram como AppImage em `emulator_dirs`.

## Comandos

Todos aceitam `--json`, menos `emu pad-watch`, que imprime uma linha JSON por evento.

| Comando | O que faz |
|---|---|
| `lw games` | abre o LW em JOGOS |
| `lw game scan` · `list` · `running` | procura jogos em todas as fontes; a biblioteca; o que está rodando |
| `lw game add --exe ARQUIVO [--prefix PASTA] [--title NOME] [--args TEXTO]` · `remove ID` | um jogo à mão |
| `lw game set ID CAMPO=VALOR…` · `arrange STATUS ID…` | muda campos; a ordem de uma coluna do backlog |
| `lw game launch ID` · `stop ID` · `recover` · `seen FIM` | inicia, pede para fechar, retoma ou fecha a sessão que ficou aberta (e diz a que terminou sem ninguém ver), marca como avisada |
| `lw game installers` · `install SETUP [--name NOME]` · `install-add SETUP EXE` · `install-forget SETUP` | instaladores de Windows |
| `lw game add-ready EXE --name NOME` | um jogo que veio pronto (download do Hydra) |
| `lw game meta [--all] [ID…]` · `played-add IGDB` · `rec-hide IGDB\|--clear` | IGDB e recomendações |
| `lw game tools` · `prefixes` | o que há para lançar (gamemode, mangohud, Proton, gamescope); prefixos do Wine |
| `lw compat scan` · `check` | o hardware; os jogos da lista contra ele |
| `lw emu list` · `set EMULADOR CHAVE VALOR` · `apply-pad EMULADOR` | ajustes dos emuladores, com backup |
| `lw emu pads` · `pad-watch EVENTO` · `pad-save GUID NOME BOTÃO=VALOR…` | o controle |

## Config

Em `~/.config/lw/config.toml` (estes são os padrões):

```toml
[games]
rom_dirs = ["~/ROMs", "~/Jogos/ROMs"]          # uma subpasta por console (ps2, snes…)
ready_dirs = ["~/Downloads/hydra_Jogos"]       # jogos que vêm prontos
emulator_dirs = ["~/Jogos/Emuladores"]         # AppImages
download_dirs = ["~/Downloads"]                # onde procurar instaladores
prefix_dir = "~/Games"                         # prefixos do Wine que o LW cria
retroarch = "retroarch"
cores_dir = "/usr/lib/libretro"
emulators = {}                                 # comando por extensão: ".xyz" = "emu {rom}"
compat_list = "extras/games-list.json"         # jogos já jogados e mistério
```

BIOS e saves são de cada emulador: o LW não mexe neles. A chave do IGDB fica à parte, em `~/.config/lw/igdb.json`.

## Onde fica

- Telas e gancho: `gui/arcade/` (`GamesModule.qml`); `gui/Games.qml` (a biblioteca na janela)
- Comandos: `extras/cmd_games.py`; a lógica continua em `extras/games.py`, `compat.py` e `emulators.py`
- Dados: `~/.local/share/lw/` (`games.json`, `covers/`, `controllers.txt`, `last-launch.log`); backups dos emuladores em `~/.local/state/rice-minimal/emulators/`
