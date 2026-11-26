# Teste do LW numa VM limpa

Roteiro para testar o LW numa VM com CachyOS + Hyprland recém-instalados, começando pelo `lw setup`. No fim estão as suposições da máquina do autor que podem quebrar lá, cada uma com arquivo:linha. Anote o que quebrar e traga numa sessão "corrija o que quebrou na VM: <erros>".

## 0. A VM

- CachyOS com a edição **Hyprland** no instalador. Usuário com outro nome que não `lucas` (ex.: `teste`), justamente para pegar o que está fixo.
- 4 GB de RAM ou mais, 3D ligado (virtio-gpu com OpenGL, ou virgl). Sem aceleração, o Quickshell abre devagar e o visualizador engasga.
- Tire um **snapshot** logo depois da primeira entrada no Hyprland. Cada rodada do teste começa dele.

## 1. Clonar

No terminal do Hyprland (kitty):

```sh
sudo pacman -S --needed git python
git clone <url do repositório> ~/Projetos/rice-minimal
cd ~/Projetos/rice-minimal
git switch modulos
```

## 2. `lw setup` (antes de qualquer outra coisa)

O `lw` ainda não está em `~/.local/bin`, então chame pelo arquivo:

```sh
python3 extras/rice.py setup
```

Ele só usa a biblioteca padrão do Python, então tem que abrir mesmo sem nenhum pacote do LW.

### Roteiro de 3 minutos

| Tempo | Faça | Tem que acontecer |
|---|---|---|
| 0:00 | abrir | moldura `LW SETUP`; à esquerda `MÓDULOS` com `[x] SISTEMA fixo`, `[x] MÚSICA`, `[x] JOGOS`; à direita as dependências de SISTEMA; embaixo o mapa das teclas |
| 0:15 | `Espaço` em SISTEMA | aviso `SISTEMA é fixo`, nada muda |
| 0:25 | `↓` até JOGOS, `Espaço` | vira `[ ] JOGOS` e aparece `vale na próxima abertura do LW`; `cat ~/.config/lw/config.toml` (noutro terminal) mostra `games = false` |
| 0:40 | `Espaço` de novo | volta `[x] JOGOS` |
| 0:50 | `↑` `↑` até SISTEMA, `Tab` | o foco passa para `DEPENDÊNCIAS`, o mapa das teclas muda; as obrigatórias que faltam já vêm com `[x]`, as opcionais com `[ ]`, as instaladas sem caixa |
| 1:05 | `Espaço` numa opcional que falta (ex.: `waybar`) | ganha `[x]`; a linha `Comando:` passa a incluir o pacote |
| 1:15 | `Espaço` de novo | desmarca; o comando volta ao que era |
| 1:20 | `i` | tela `CONFIRMAR INSTALAÇÃO` com o `sudo pacman -S --needed …` exato, e `Cancelar` selecionado |
| 1:30 | `Enter` (em Cancelar) | volta com `instalação cancelada · nada foi instalado`; nada rodou |
| 1:40 | `i`, `↓`, `Enter` (Confirmar) | sai do curses; o pacman roda no terminal e pede a senha; ao fim, `Enter volta ao lw setup` |
| 2:20 | `Enter` | de volta à TUI, `[ OK ] instalado`; o que foi instalado aparece como `OK` |
| 2:30 | `Tab`, `↓` até MÚSICA, `Tab` | `cliamp` aparece como `falta` **sem caixa**, com o caminho manual; `Espaço` nele mostra esse caminho em vez de marcar |
| 2:45 | `q` | sai sem erro, o terminal volta normal |

Anote também:

- se algum pacote do `sudo pacman -S` não existe no repositório do CachyOS (o pacman para e nada é instalado);
- se a tela cabe num terminal de 80×24.

Para ver o mesmo sem a TUI:

```sh
python3 extras/rice.py modules deps sistema
python3 extras/rice.py modules deps musica --optional
```

## 3. O que não é pacote

- **cliamp**: baixe o binário da página de releases (`modules/music/README.md`), confira o `checksums.txt` e ponha em `~/.local/bin/cliamp` com `chmod +x`.
- **Nemo** (atalho `Super+E`): `sudo pacman -S nemo nemo-fileroller cinnamon-translations`. O `install.py` só avisa.

## 4. Instalar as configs

```sh
python3 scripts/install.py            # mostra o que vai mudar
python3 scripts/install.py --apply    # instala, com backup antes
```

Confira:

- `~/.local/bin/lw` existe;
- `~/.config/hypr/config/rice-integration.lua` tem `/home/teste`, não `/home/lucas`;
- `~/.config/hypr/hyprland.lua` ganhou os `require("config.rice-…")`.

Depois saia da sessão e entre de novo.

## 5. O que rodar e observar

1. `lw doctor`: as checagens da sessão e as dependências por módulo. Anote cada `FAIL` e `WARN`.
2. `Super+BackSpace`: o LW abre em SISTEMA. Troque de wallpaper e veja as cores mudarem no kitty e na barra.
3. `Super+M`: MÚSICA abre e o cliamp liga. Ponha uma música em `~/Músicas` antes; numa VM em inglês, a pasta pode ser `~/Music`. `Super+N` passa a faixa.
4. `Super+G`: JOGOS abre. Com a pasta `~/.local/share/lw` ainda inexistente, a lista começa vazia. Adicione um jogo (`+ JOGO`, ou `lw game add --exe /usr/bin/true` noutro terminal): ele tem que aparecer **sem fechar o LW**.
5. `lw modules disable musica` e `Super+M`: aparece a notificação `módulo MÚSICA desligado`. Depois, `lw modules enable musica`.
6. Feche e abra o LW. Nada de erro no `~/.local/state/rice-minimal/` nem na notificação.

## Suposições da máquina do autor

O que está fixo e pode quebrar numa máquina limpa. Corrigido nesta sessão: só o item 3.

### 1. Usuário `lucas` fixo no greeter

- `config/greeter/greeter.toml:20`: `default = "lucas"` em `[user]`. O `install.py` não instala esse arquivo (`scripts/install.py:269` diz para fazer à mão com sudo). Copiado como está, o greeter sugere um usuário que não existe na VM.
- `scripts/restore_greeter.sh:9`: `FLAG=/home/lucas/.local/state/…`, caminho fixo.
- `scripts/restore_greeter.sh:27`: `passwordless-sync disable lucas`, usuário fixo.

### 2. `~/.local/bin` no PATH, de onde vêm o `lw` e o `cliamp`

- `config/hypr/rice-integration.lua:10-16` e `config/waybar/config.jsonc:38` chamam `/home/lucas/.local/bin/lw` e `/home/lucas/.local/bin/cliamp` pelo caminho absoluto. O `install.py` troca `/home/lucas` pelo HOME (`scripts/install.py:77-80`), mas o `cliamp` precisa ter sido posto lá à mão.
- `extras/cli.py:117`: o `lw gui` acrescenta `~/.local/bin` ao PATH só da janela, porque o PATH do Hyprland não tem essa pasta (comentário em `gui/Music.qml:86`).
- `extras/doctor.py:27`: o doctor também procura em `~/.local/bin`. Por isso ele dá `OK` para o cliamp mesmo quando o terminal não acha o programa.
- No terminal, quem põe `~/.local/bin` no PATH é o `/usr/share/cachyos-fish-config/cachyos-config.fish` (`fish_add_path ~/.local/bin`, linha 25 na minha máquina), carregado por `config/fish/config.fish:3`. No CachyOS isso funciona. Sem esse arquivo (Arch puro), `lw` e `cliamp` digitados no fish não são achados.

### 3. Biblioteca de JOGOS vazia na primeira vez (corrigido)

- `gui/Games.qml`, no `FileView` do `games.json`: se `~/.local/share/lw` não existia quando a janela abriu, o `FileView` não acompanhava o arquivo, e a biblioteca ficava vazia até reabrir o LW. Agora, quando o primeiro scan termina sem que o arquivo tenha sido lido (`fileSeen`), ele relê (`gui/Games.qml:107`) e passa a acompanhar. O teste é `tests/test_gui.py`, `test_a_clean_machine_sees_the_library_without_reopening`.

### 4. Outros caminhos e arquivos da minha máquina

- `config/waybar/config.jsonc:34,37,38` e `config/waybar/style.css:1,52`: `/home/lucas/...` fixo. O `install.py` **não instala** a Waybar (não está em `FILES`, `scripts/install.py:32`). Copiada à mão, a barra chama o `lwbar.py` num caminho que não existe.
- `config/waypaper/config.ini:2,4`: pasta `~/Imagens/Wallpapers` e `default-wallpaper.png`. O caminho é trocado pelo do usuário, mas o nome da pasta é o da instalação em português, e a imagem precisa existir. Sem ela, o doctor dá `FAIL` em "Wallpaper reference".
- `config/autostart/rice-minimal.desktop:5`: o repositório precisa estar em `~/Projetos/rice-minimal` ou ser instalado pelo `install.py`, que troca o caminho.
- `scripts/install.py:135`: os `require("config.rice-…")` só entram se `~/.config/hypr/hyprland.lua` existir. Se o Hyprland da VM vier com `hyprland.conf` (sem Lua), nada do rice é carregado e o `install.py` não avisa. O doctor mostra `FAIL` em "Lua appearance include".
- `config/greeter/greeter.toml:17`: a sessão `Hyprland (uwsm-managed)`, que precisa existir com esse nome.
- `scripts/test_adaptive_session.py:96`: `/home/lucas/.config/kitty/kitty.conf` fixo (é teste de sessão real; não roda na suíte).

### 5. Programas que o LW usa e os manifestos não declaram

- `noctalia-greeter` e `greetd`: a tela GREETER e o `scripts/restore_greeter.sh:10,20`.
- `nemo`: `config/hypr/rice-integration.lua:20`. `dconf`: `scripts/install.py:235` (`dconf load /org/nemo/`).
- `yazi`: `config/fish/functions/y.fish:4` e `Super+Shift+E`.
- `fastfetch`: `config/fish/functions/fastfetch.fish:4`. Só embrulha o programa; sem ele, dá erro ao chamar.
- `zoxide`: `config/fish/conf.d/zoxide.fish:2`, já protegido por `command -q`.
- `git`: o `lazy.nvim` se baixa sozinho no primeiro `nvim` (`config/nvim/init.lua:65`), e sem rede o nvim abre sem tema.
- `pcsx2-qt`: `extras/emulators.py:139` e `extras/games.py:330`. Fica fora de JOGOS como os AppImages, mas é procurado também no PATH.
- `fc-list` (fontconfig), `pgrep`/`pkill` (procps-ng), `setsid` (util-linux): vêm com a base. Ficam listados para o caso de um Arch mínimo.

### 6. Pacotes que talvez não existam com esse nome

Não confirmei; o `lw setup` mostra na hora, porque o `pacman` falha e não instala nada.

- `noctalia`, `quickshell`, `matugen` e `waypaper` (`modules/system/module.toml`): confira se estão no repositório do CachyOS ou só no AUR. Se estiverem só no AUR, o manifesto precisa de `aur =` no lugar de `package =`.
- `waypaper` e `ryujinx` estão no CachyOS mas não no Arch (`docs/pendencias.md`, sessão 6).
