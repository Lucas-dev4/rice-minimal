# Wallpapers

`wallpapers` abre o seletor em curses, só com a biblioteca padrão. Para navegar não precisa de miniaturas, toolkit gráfico nem daemon. Para aplicar, precisa da sessão Wayland/Noctalia aberta.

- `j`/Baixo e `k`/Cima movem; `/` filtra pelo nome, Enter termina a busca.
- Enter fora da busca aplica; `r` escolhe um ao acaso; `q`/Esc sai.
- `*` marca o wallpaper em uso, comparando os caminhos resolvidos, para os links simbólicos que já existem funcionarem.
- `wallpapers --list` imprime a pasta, a escolha atual e os caminhos das imagens, sem mudar nada.
- `wallpapers --apply '/caminho/com espaços/imagem.png'` usa a mesma função de aplicar do Enter.

A pasta vem do `~/.config/waypaper/config.ini`: hoje, `~/Imagens/Wallpapers`. Os links que já existem apontam para `~/Pictures/Wallpapers`; um JPG que já existia também fica direto na pasta configurada. Nenhuma biblioteca de imagens foi criada ou copiada. A busca em subpastas segue as opções do Waypaper.

O seletor chama o Waypaper com uma lista de argumentos e `--no-post-command`, depois roda o gancho comum do tema na hora. O Waypaper grava a escolha na própria configuração; o seletor não tem estado à parte. A janela chama o mesmo gancho, sem esperar. O gancho configurado lê a escolha gravada no Waypaper em vez de pôr nomes de arquivo num texto de shell. Espaços, aspas, ponto e vírgula e expressões com cifrão foram exercitados pelo comando real do Waypaper.

O Noctalia continua sendo o único que desenha o wallpaper (`backend = none` no Waypaper). O Hyprpaper continua instalado, mas não é aberto. Veja [o comportamento e a recuperação do tema](../theme/README.md).
