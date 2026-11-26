# Sessões do Claude Code — LW modular

Uma sessão por item. Entre uma e outra: `/clear`. Cole o prompt do item e deixe rodar.
Marque [x] quando terminar. Se uma sessão parar pedindo decisão, responda e deixe ela seguir.

---

## [ ] 0 — Baseline (rápida)
```
Rode a suíte de testes (python3 -m unittest discover -s tests -q) e crie docs/BASELINE.md listando cada teste que falha ou dá erro, com uma linha do motivo. Não conserte nada. Commit: "docs: baseline dos testes antes dos módulos".
```

## [ ] 1 — Contrato de módulo (só desenho, sem código)
```
Leia README.md, extras/cli.py, gui/shell.qml e gui/Theme.qml. Proponha em docs/modulos.md o contrato de um módulo do LW: o que ele declara (nome, descrição, dependências de pacote/comando, telas QML, subcomandos lw, chaves de config, atalhos), onde os arquivos ficam, como o shell.qml descobre os módulos ativos e como `lw doctor` lê as dependências. Mostre como SISTEMA, MÚSICA e JOGOS se encaixam. Mantenha simples: um manifesto TOML por módulo, sem sistema de plugins genérico. Pare e me mostre antes de commitar.
```

## [x] 2 — Tirar o que é pessoal do código
```
Siga docs/modulos.md. Crie a leitura de ~/.config/lw/config.toml (tomllib, padrão = valor atual quando o arquivo ou a chave não existir). Mova para lá os caminhos e listas pessoais (pastas de música, ROMs, emuladores, downloads, lista de jogos já jogados etc.). Liste antes o que vai mover e espere meu ok. Inclua também: config/fish/config.fish só faz source do cachyos-config.fish se o arquivo existir. Testes passando, commit.
```

## [x] 3 — Módulo SISTEMA
```
Extraia SISTEMA como módulo segundo docs/modulos.md (manifesto, telas, subcomandos). O comportamento visível não muda. README curto do módulo (o que faz, dependências, comandos). Testes passando, commit.
```

## [x] 4 — Módulo MÚSICA
```
Mesmo que a sessão 3, para MÚSICA (cliamp, rádio, online, biblioteca). Comportamento igual, README do módulo, testes, commit.
```

## [x] 5 — Módulo JOGOS
```
Mesmo que a sessão 3, para JOGOS (biblioteca, backlog, desempenho, emuladores, instalar). Comportamento igual, README do módulo, testes, commit.
```

## [ ] 6 — Escolher módulos + doctor
```
Implemente `lw modules list|enable|disable NOME` (estado em ~/.config/lw/config.toml) e faça o shell.qml mostrar só os módulos ativos. `lw doctor` passa a checar as dependências de cada módulo ativo e imprime o `sudo pacman -S …` do que falta. Testes novos em tests/, commit.
```

## [ ] 7 — `lw setup` e preparar o teste em sistema limpo
```
Parte A — `lw setup`: TUI em curses (biblioteca padrão, mesmo visual e teclas da TUI que já existe) para quem acabou de baixar o LW. Mostra os módulos (nome, descrição, ligado/desligado, SISTEMA fixo), e para o módulo selecionado as dependências obrigatórias e opcionais com o estado de cada uma (instalada/falta). Espaço liga/desliga o módulo, i instala o que falta. Antes de instalar, mostra o comando exato (sudo pacman -S --needed …) e só roda depois de confirmação explícita, em primeiro plano, para a pessoa digitar a senha. Pacotes do AUR: usa paru ou yay se existir; se não, mostra o que instalar e não instala. Toda a lógica fica em lw modules / lw doctor (--json); a TUI só desenha e chama. Testes com pacman/paru falsos no PATH; nunca rode o pacman real nem sudo. Plano primeiro e espere meu ok.

Parte B — docs/teste-vm.md: passo a passo para eu testar numa VM com CachyOS + Hyprland limpos, começando por `lw setup`. Procure no repo suposições da minha máquina que quebrariam lá e liste com arquivo:linha. Confira e inclua estas três: (1) "lucas" fixo no greeter; (2) ~/.local/bin no PATH, de onde o cliamp é chamado; (3) a biblioteca de JOGOS fica vazia numa máquina limpa até reabrir o LW (docs/pendencias.md). Corrija o 3 com teste; os outros só liste.

Testes, commits separados por parte, roteiro manual de 3 min do lw setup.
```
(Depois: rodar a VM você mesmo e trazer os erros numa sessão "corrija o que quebrou na VM: <erros>".)

## [ ] 8 — Módulo TERMINAL (tela nova)
```
Crie o módulo TERMINAL a partir de docs/prototipos/lw-terminal.html: abas KITTY, CORES, PROMPT, FASTFETCH, SAUDAÇÃO (com MODELOS: o usuário põe comando/arquivo) e, separadas, ANIMAÇÕES, JANELAS e INPUT do Hyprland. Primeiro o plano (subcomandos lw, onde grava cada coisa, como desfaz) e espere meu ok. Mudança ao vivo via kitty @ / hyprctl keyword; gravar só com 'w' e com backup. Dependências opcionais (pokemon-colorscripts, fortune, cowsay, cbonsai) no manifesto: o que faltar some da lista.
```

## [ ] 9 — Módulo DISPOSITIVOS (tela nova)
```
Crie o módulo DISPOSITIVOS a partir de docs/prototipos/lw-mecanicas.html: abas DISPOSITIVOS (impressora/CUPS, áudio/PipeWire, monitores, controle, pendrive), BLUETOOTH (reaproveite extras/bluetooth.py) e HARDWARE (testes rápidos com sysbench/fio/vkmark/iperf3, guardando o histórico). Não duplique o que o Noctalia já faz melhor: me diga o que sobrepõe antes de implementar. Plano primeiro.
```

## [ ] 10 — ENVIAR (tela nova)
```
A partir da tela ENVIAR de docs/prototipos/lw-servidor.html: arrastar arquivo e mandar para destinos configuráveis (pasta local/samba, celular via kdeconnect-cli, servidor via rsync se configurado). Entra em SISTEMA ou como módulo próprio, conforme docs/modulos.md. Plano primeiro.
```

## [ ] 11 — IA (tela nova, por último)
```
Módulo IA a partir de docs/prototipos/lw-ia.html: CHAT, PROCESSOS, MODELOS, PROMPTS sobre o ollama (API em localhost:11434). Os pedidos passam por uma fila do lw, e é ela que alimenta PROCESSOS; não invente dados que o ollama não dá. Plano primeiro.
```

## [ ] 12 — Documentação e 1.0
```
Reescreva o README.md: o que é o LW (5 linhas), print/protótipo, instalação rápida, lista de módulos com link para o README de cada um. Mova RICE-FINAL.md e PHASE4.md para docs/historico/. Remova o nome antigo `rice` das mensagens visíveis (mantenha o alias de comando). Commit e tag v1.0.0.
```

## [ ] 13 — Pacote (CachyOS e Arch)
```
Crie um PKGBUILD (lw-git) com as dependências obrigatórias e as opcionais por módulo (optdepends), seguindo docs/modulos.md. Teste com makepkg -si numa pasta temporária e me diga o que precisa de AUR.
```
