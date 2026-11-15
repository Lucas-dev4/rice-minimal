"""Small ASCII curses helpers shared by the two menus."""
# ui.py — peças de curses usadas por todas as TUIs (lw, wallpapers, supers, lw bt):
# moldura, texto seguro, lista navegável, confirmação, campo de texto e página com rolagem.
import curses

def setup(screen):
    """Prepara a tela: esconde o cursor, liga as setas e a cor de destaque (par 1 = azul)."""
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    screen.keypad(True)
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_BLUE, -1)

def selected():
    """Estilo da linha selecionada (azul, invertido, negrito)."""
    return (curses.color_pair(1) if curses.has_colors() else 0) | curses.A_REVERSE | curses.A_BOLD

def text(screen, y, x, value, attr=0):
    """Escreve um texto sem nunca estourar a tela (corta no fim da linha e troca caracteres invisíveis por "?")."""
    height, width = screen.getmaxyx()
    if 0 <= y < height and 0 <= x < width-1:
        clean = ''.join(c if c.isprintable() else '?' for c in str(value))
        try:
            screen.addnstr(y, x, clean, width-x-1, attr)
        except curses.error:
            pass

def frame(screen, title):
    """Limpa a tela e desenha a moldura com o título; devolve (altura, largura)."""
    screen.erase()
    height, width = screen.getmaxyx()
    accent = curses.color_pair(1) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD
    text(screen, 0, 1, '+-- '+title+' '+'-'*width, accent)
    text(screen, height-3, 1, '+'+'-'*width, accent)
    return height, width

def external(screen, args):
    """Sai do curses, roda um programa externo no terminal e volta para a TUI."""
    import subprocess
    curses.def_prog_mode()
    curses.endwin()
    try:
        return subprocess.run([str(a) for a in args], check=False).returncode
    finally:
        curses.reset_prog_mode()
        present(screen)

def page(screen, title, lines):
    """Mostra uma lista de linhas só para leitura, com rolagem (j/k)."""
    offset = 0
    while True:
        height, _ = frame(screen, title)
        for row, line in enumerate(lines[offset:offset+max(0,height-5)], 2):
            text(screen, row, 2, line)
        text(screen, height-2, 2, 'j/k: scroll | q/Esc/Enter: back')
        present(screen)
        key = screen.getch()
        if key in (ord('q'),27,10,13):
            return
        if key in (ord('j'), curses.KEY_DOWN):
            offset = min(max(0,len(lines)-1), offset+1)
        if key in (ord('k'), curses.KEY_UP):
            offset = max(0, offset-1)

# Event-driven rendering: terminal diff updates; sleeps only during user actions.
import os
import time
from pathlib import Path

_animations = None
_last_title = None

def animations_enabled():
    """As animações da TUI só rodam no perfil Refined e se não foram desligadas."""
    if os.environ.get('RICE_NO_ANIMATIONS') == '1':
        return False
    if _animations is not None:
        return _animations
    try:
        root = Path(os.environ.get('RICE_THEME_STATE', Path.home()/'.local/state/rice-minimal/theme'))
        return (root/'profile').read_text().strip() == 'refined' and not (root/'no-tui-animation').exists()
    except OSError:
        return False

def toggle_animations():
    """Liga/desliga as animações e grava a escolha (arquivo no-tui-animation)."""
    global _animations
    _animations = not animations_enabled()
    root = Path(os.environ.get('RICE_THEME_STATE', Path.home()/'.local/state/rice-minimal/theme'))
    root.mkdir(parents=True,exist_ok=True)
    marker = root/'no-tui-animation'
    if _animations:
        marker.unlink(missing_ok=True)
    else:
        marker.write_text('disabled\n')
    return _animations

def present(screen):
    """Envia para o terminal só o que mudou na tela."""
    screen.noutrefresh()
    curses.doupdate()

def choose(screen, title, entries, message='', initial=0):
    """One shared navigation loop. Returns an index or None; never starts curses."""
    index = min(initial,max(0,len(entries)-1))
    animate = True
    while True:
        h,w = frame(screen,title)
        visible = max(1,h-6)
        offset = max(0,index-visible+1)
        for pos,value in enumerate(entries[offset:offset+visible],offset):
            text(screen,2+pos-offset,2,('> ' if pos == index else '  ')+f'{pos+1:02d}  '+value,
                 selected() if pos == index else 0)
        text(screen,h-4,2,message)
        text(screen,h-2,2,'↑↓ Navigate  Enter Select  Q Back  A Animations')
        if animate and animations_enabled():
            y=2+index-offset
            # Two finite highlight frames, 36 ms total; no idle timer.
            for attr in (curses.A_BOLD,curses.A_BOLD|curses.A_UNDERLINE):
                text(screen,y,2,'> '+f'{index+1:02d}  '+entries[index],attr)
                present(screen)
                curses.napms(18)
            text(screen,y,2,'> '+f'{index+1:02d}  '+entries[index],selected())
        present(screen)
        animate = False
        key = screen.getch()
        if key in (ord('q'),ord('Q'),27):
            return None
        if key in (curses.KEY_UP,ord('k')):
            index = (index-1)%len(entries)
            animate = True
        elif key in (curses.KEY_DOWN,ord('j')):
            index = (index+1)%len(entries)
            animate = True
        elif key in (10,13,curses.KEY_ENTER):
            return index
        elif ord('1') <= key <= ord('9') and key-ord('1') < len(entries):
            return key-ord('1')
        elif key in (ord('a'),ord('A')):
            message = 'Animations: '+('on' if toggle_animations() else 'off')
        elif key == curses.KEY_RESIZE:
            screen.erase()

def confirm(screen, title, details):
    """Pergunta Cancel/Confirm; True só se confirmar."""
    return choose(screen,title,['Cancel','Confirm'],details) == 1

def input_text(screen,title,prompt):
    """Campo de texto de uma linha; Enter aceita, Esc cancela (None)."""
    value = ''
    while True:
        h,w=frame(screen,title)
        text(screen,2,2,prompt)
        text(screen,4,2,'> '+value)
        text(screen,h-2,2,'Enter Accept  Esc Cancel')
        present(screen)
        key=screen.get_wch()
        if key == '\x1b':
            return None
        if key in ('\n','\r'):
            return value.strip()
        if key in ('\b','\x7f',curses.KEY_BACKSPACE):
            value=value[:-1]
        elif isinstance(key,str) and key.isprintable() and len(value)<512:
            value+=key
