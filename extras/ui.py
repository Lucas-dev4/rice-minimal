"""Small ASCII curses helpers shared by the two menus."""
import curses

def setup(screen):
    curses.curs_set(0)
    screen.keypad(True)
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)

def text(screen, y, x, value, attr=0):
    height, width = screen.getmaxyx()
    if 0 <= y < height and 0 <= x < width-1:
        clean = ''.join(c if c.isprintable() else '?' for c in str(value))
        try:
            screen.addnstr(y, x, clean, width-x-1, attr)
        except curses.error:
            pass

def frame(screen, title):
    screen.erase()
    height, width = screen.getmaxyx()
    accent = curses.color_pair(1) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD
    text(screen, 0, 1, '+-- '+title+' '+'-'*width, accent)
    text(screen, height-3, 1, '+'+'-'*width, accent)
    return height, width

def external(screen, args):
    import subprocess
    curses.def_prog_mode()
    curses.endwin()
    try:
        return subprocess.run([str(a) for a in args], check=False).returncode
    finally:
        curses.reset_prog_mode()
        screen.refresh()

def page(screen, title, lines):
    offset = 0
    while True:
        height, _ = frame(screen, title)
        for row, line in enumerate(lines[offset:offset+max(0,height-5)], 2):
            text(screen, row, 2, line)
        text(screen, height-2, 2, 'j/k: scroll | q/Esc/Enter: back')
        screen.refresh()
        key = screen.getch()
        if key in (ord('q'),27,10,13):
            return
        if key in (ord('j'), curses.KEY_DOWN):
            offset = min(max(0,len(lines)-1), offset+1)
        if key in (ord('k'), curses.KEY_UP):
            offset = max(0, offset-1)
