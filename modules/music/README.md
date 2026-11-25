# MÚSICA

Toca, organiza e baixa músicas. Quem toca é sempre o [cliamp](https://github.com/bjarneo/cliamp); o LW só conversa com ele.

Abre com `Super+M` ou `lw music`.

## Telas

| Tela | Para quê |
|---|---|
| NOW PLAYING | faixa, capa, visualizador e controles |
| PLAYLIST | a fila: reordenar, tirar, adicionar arquivos (`o` ou arrastando) |
| EQUALIZER | as 10 bandas do cliamp e os presets |
| RADIO | buscar estações no radio-browser.info e salvar |
| LIBRARY | todas as músicas da pasta, buscadas por tag e letra |
| ONLINE | buscar no YouTube e no SoundCloud, baixar e organizar |

Na barra lateral ficam as fontes da fila, o mini player e o VOL (o volume do sistema). Entrar em MÚSICA liga o cliamp; fechar o LW em MÚSICA desliga (mesmo antes de ele responder) e guarda a sessão, que volta pausada no mesmo ponto; fechar de outra seção deixa tocar. `Espaço` toca e pausa em qualquer seção.

## Dependências

Obrigatórias:

```
sudo pacman -S --needed wireplumber libpulse
```

O `cliamp` não está nos repositórios: baixe o binário da [página de releases](https://github.com/bjarneo/cliamp/releases), confira o `checksums.txt` e ponha em `~/.local/bin/cliamp`.

Opcionais (sem elas só some o que está ao lado):

```
sudo pacman -S --needed cava ffmpeg yt-dlp playerctl zenity glib2
```

`cava` (visualizador), `ffmpeg` (LIBRARY, formato da faixa, download e tags), `yt-dlp` (YouTube em ONLINE), `playerctl` (capa), `zenity` (escolher arquivos), `glib2` (o arquivo antigo vai para a lixeira ao gravar tags).

## Comandos

Todos aceitam `--json`, menos `download`, que imprime uma linha JSON por evento.

| Comando | O que faz |
|---|---|
| `lw music` | abre o LW em MÚSICA |
| `lw library scan` | as músicas da pasta com as tags |
| `lw library lookup --out PLANO` · `apply --plan PLANO` | procura gênero, ano e capa na internet; grava o plano |
| `lw organize plan` · `apply` · `move ARQUIVO PASTA` | tira as músicas de `Downloads` e põe na pasta do artista |
| `lw radio search [--name TEXTO] [--tag TAG]` · `saved` · `add --name NOME --url URL` | estações |
| `lw online status` · `search TEXTO\|LINK` | se há yt-dlp; busca no YouTube ou o que tem num link |
| `lw download URL [--playlist]` | baixa em MP3 com tags e capa |
| `lw cliamp sync` | escreve a pasta das músicas na config do cliamp |

`library scan|lookup`, `organize` e `download` aceitam `--root PASTA`.

## Config

Em `~/.config/lw/config.toml`:

```toml
[music]
dir = "~/Músicas"     # o padrão
```

É a única fonte: o `initial_directory` do cliamp é escrito a partir dela.

## Onde fica

- Telas e gancho: `gui/player/` (`MusicModule.qml`); `gui/Music.qml` (cliamp), `gui/Spectrum.qml` (cava) e `gui/Downloads.qml`
- Comandos: `extras/cmd_music.py`; a lógica continua em `extras/library.py`, `organize.py`, `radio.py`, `ytdl.py` e `cliamp.py`
- Estado: `~/.local/state/rice-minimal/gui/music-session.json` (sessão), `~/.cache/rice-minimal/music-library.json` (tags), `~/.local/share/lw/yt-dlp-archive.txt` (já baixados)
