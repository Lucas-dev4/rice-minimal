"""lw setup: escolher os módulos e instalar o que falta, para quem acabou de baixar o LW."""
# setup_tui.py — a TUI do "lw setup", em curses, com as peças de ui.py (mesma moldura e destaque do "lw").
# Painel principal: os módulos; Espaço liga/desliga (SISTEMA é fixo). Mini painel: as dependências do
# módulo selecionado; Espaço marca o que instalar. Embaixo, o comando exato e o mapa das teclas.
# Não tem lógica: tudo é "lw modules … --json". Instalar só roda depois de confirmar, fora do curses,
# para o sudo pedir a senha no terminal.
import curses
import json
from pathlib import Path
import subprocess
import sys
import ui

RICE = Path(__file__).resolve().parent/'rice.py'
KEYS = {'modules': 'Tab dependências  ↑↓ mover  Espaço liga/desliga  i instalar marcadas  q sair',
        'deps': 'Tab módulos  ↑↓ mover  Espaço marca/desmarca  i instalar marcadas  q sair'}


def call(*argv):
    """Roda lw <argv> --json e devolve o envelope."""
    p = subprocess.run([sys.executable, str(RICE), *argv, '--json'], capture_output=True, text=True)
    try:
        return json.loads(p.stdout)
    except ValueError:
        return {'ok': False, 'error': {'message': (p.stderr or p.stdout).strip() or f'lw saiu com {p.returncode}'}}


def execute(screen, argv):
    """Sai do curses, roda no terminal (o sudo pede a senha aqui), espera Enter e volta."""
    curses.def_prog_mode()
    curses.endwin()
    try:
        code = subprocess.run(argv).returncode
        try:
            input('\n' + ('[ OK ]' if code == 0 else f'[ FAIL ] saiu com {code}') + ' · Enter volta ao lw setup ')
        except EOFError:
            pass
        return code
    finally:
        curses.reset_prog_mode()
        ui.present(screen)


def picks(argv, marked):
    """Os --pick de cada pacote marcado."""
    return argv + [arg for key in sorted(marked) for arg in ('--pick', key)]


class Setup:
    def __init__(self, screen, run=call, launch=execute):
        self.screen, self.run, self.launch = screen, run, launch
        self.focus, self.index, self.row, self.offset = 'modules', 0, 0, 0
        self.message = ''
        self.deps, self.marks, self.plans = {}, {}, {}
        self.load()

    # Dados, sempre do lw.
    def load(self):
        """Lê a lista de módulos; sem ela não há o que mostrar."""
        result = self.run('modules', 'list')
        if not result.get('ok'):
            raise RuntimeError(result['error']['message'])
        self.modules = result['data']

    def module(self):
        return self.modules[self.index]

    def dependencies(self, refresh=False):
        """As dependências do módulo selecionado; as obrigatórias que faltam já vêm marcadas."""
        mid = self.module()['id']
        if refresh or mid not in self.deps:
            result = self.run('modules', 'deps', mid)
            if not result.get('ok'):
                self.message = '[ FAIL ] ' + result['error']['message']
                return []
            self.deps[mid] = result['data']['dependencies']
            self.marks[mid] = {d['key'] for d in self.deps[mid] if self.markable(d) and not d['optional']}
            self.plans = {k: v for k, v in self.plans.items() if k[0] != mid}
        return self.deps[mid]

    @staticmethod
    def markable(dep):
        """Só o que falta, tem pacote (pacman ou AUR) e não tem conflito pode ser marcado."""
        return not dep['found'] and bool(dep['key']) and not dep.get('conflict')

    def plan(self):
        """O plano do lw para o que está marcado (None se nada marcado)."""
        mid = self.module()['id']
        marked = self.marks.get(mid, set())
        if not marked:
            return None
        key = (mid, tuple(sorted(marked)))
        if key not in self.plans:
            result = self.run(*picks(['modules', 'deps', mid], marked))
            self.plans[key] = result['data']['install'] if result.get('ok') else {'commands': [], 'blocked': [result['error']['message']]}
        return self.plans[key]

    # Ações.
    def toggle_module(self):
        m = self.module()
        if m['required']:
            self.message = f'{m["name"]} é fixo: sem ele o LW não abre'
            return
        result = self.run('modules', 'disable' if m['enabled'] else 'enable', m['id'])
        if not result.get('ok'):
            self.message = '[ FAIL ] ' + result['error']['message']
            return
        m['enabled'] = result['data']['enabled']
        self.message = f'[ OK ] {m["name"]} ' + ('ligado' if m['enabled'] else 'desligado') + ' · vale na próxima abertura do LW'

    def toggle_mark(self):
        deps = self.dependencies()
        if not deps:
            return
        dep = deps[self.row]
        marked = self.marks[self.module()['id']]
        if dep.get('conflict'):
            self.message = dep['name'] + ': ' + dep['conflict']
        elif dep['found']:
            self.message = dep['name'] + ' já está instalada'
        elif not dep['key']:
            self.message = dep['name'] + ': ' + dep['manual']
        else:
            marked.symmetric_difference_update({dep['key']})
            self.message = ''

    def install(self):
        """Mostra os comandos exatos e só roda com Confirmar."""
        plan = self.plan()
        if plan is None:
            self.message = 'nada marcado · Tab e Espaço para marcar'
            return
        if not plan['commands']:
            self.message = ' · '.join(plan['blocked']) or 'nada a instalar'
            return
        if not self.confirm(plan):
            self.message = 'instalação cancelada · nada foi instalado'
            return
        mid = self.module()['id']
        code = self.launch(self.screen, picks([sys.executable, str(RICE), 'modules', 'install', mid],
                                               self.marks[mid]) + ['--yes'])
        self.dependencies(refresh=True)
        self.message = '[ OK ] instalado' if code == 0 else f'[ FAIL ] a instalação saiu com {code}; nada mais foi rodado'

    def confirm(self, plan):
        """Cancelar vem selecionado; Enter em Confirmar é o único jeito de seguir."""
        choice = 0
        while True:
            h, _ = ui.frame(self.screen, 'CONFIRMAR INSTALAÇÃO')
            lines = ['Vai rodar no terminal, nesta ordem:', ''] + ['  ' + ' '.join(c) for c in plan['commands']]
            lines += [''] + [f'não instala: {b}' for b in plan['blocked']] + ([''] if plan['blocked'] else [])
            lines += ['O sudo pede a sua senha. O resto do LW não muda.']
            for row, line in enumerate(lines, 2):
                ui.text(self.screen, row, 2, line)
            for pos, label in enumerate(('Cancelar', 'Confirmar')):
                ui.text(self.screen, len(lines) + 3 + pos, 2, ('> ' if pos == choice else '  ') + label,
                        ui.selected() if pos == choice else 0)
            ui.text(self.screen, h - 2, 2, '↑↓ escolher  Enter seguir  q/Esc cancelar')
            ui.present(self.screen)
            key = self.screen.getch()
            if key in (ord('q'), ord('Q'), 27):
                return False
            if key in (curses.KEY_UP, curses.KEY_DOWN, ord('j'), ord('k')):
                choice = 1 - choice
            elif key in (10, 13, curses.KEY_ENTER):
                return choice == 1

    # Desenho.
    def draw(self):
        h, w = ui.frame(self.screen, 'LW SETUP')
        left = max(24, min(40, w // 3))
        accent = lambda focus: ui.selected() if self.focus == focus else curses.A_BOLD
        ui.text(self.screen, 2, 2, 'MÓDULOS', accent('modules'))
        for pos, m in enumerate(self.modules):
            line = f'[{"x" if m["enabled"] else " "}] {m["name"]:<9} {"fixo" if m["required"] else ""}'
            here = pos == self.index
            ui.text(self.screen, 3 + pos, 2, ('> ' if here else '  ') + line,
                    ui.selected() if here and self.focus == 'modules' else curses.A_BOLD if here else 0)
        m = self.module()
        x = left + 3
        ui.text(self.screen, 2, x, 'DEPENDÊNCIAS', accent('deps'))
        ui.text(self.screen, 3, x, m['name'] + (' — ' + m['description'] if m.get('description') else ''))
        deps = self.dependencies()
        marked = self.marks.get(m['id'], set())
        visible = max(1, h - 12)
        self.offset = min(self.offset, self.row)
        if self.row >= self.offset + visible:
            self.offset = self.row - visible + 1
        for pos, d in enumerate(deps[self.offset:self.offset + visible], self.offset):
            box = ('[x]' if d['key'] in marked else '[ ]') if self.markable(d) else '   '
            state = 'conflito' if d.get('conflict') else 'OK   ' if d['found'] else 'falta'
            extra = ' · opcional' if d['optional'] else ''
            extra += ' · ' + d['conflict'] if d.get('conflict') else ' · ' + d['why'] if not d['found'] else ''
            extra += ' · ' + d['manual'] if d['manual'] and not d['found'] else ''
            here = pos == self.row and self.focus == 'deps'
            ui.text(self.screen, 5 + pos - self.offset, x, ('> ' if here else '  ') + f'{box} {state} {d["name"]}{extra}',
                    ui.selected() if here else 0)
        if len(deps) > visible:
            ui.text(self.screen, 5 + visible, x, f'{self.offset + 1}–{min(len(deps), self.offset + visible)} de {len(deps)}')
        plan = self.plan()
        commands = plan['commands'] if plan else []
        ui.text(self.screen, h - 6, 2, 'Comando: ' + ('  ;  '.join(' '.join(c) for c in commands) if commands
                                                     else 'nada marcado' if plan is None else 'nenhum'))
        if plan and plan['blocked']:
            ui.text(self.screen, h - 5, 2, 'Não instala: ' + ' · '.join(plan['blocked']))
        ui.text(self.screen, h - 4, 2, self.message)
        ui.text(self.screen, h - 2, 2, KEYS[self.focus])
        ui.present(self.screen)

    def loop(self):
        while True:
            self.draw()
            key = self.screen.getch()
            count = len(self.modules) if self.focus == 'modules' else len(self.dependencies())
            if key in (ord('q'), ord('Q'), 27):
                return 0
            if key == 9:
                self.focus = 'deps' if self.focus == 'modules' else 'modules'
            elif key in (curses.KEY_UP, ord('k'), curses.KEY_DOWN, ord('j')) and count:
                step = -1 if key in (curses.KEY_UP, ord('k')) else 1
                if self.focus == 'modules':
                    self.index, self.row, self.offset = (self.index + step) % count, 0, 0
                    self.message = ''
                else:
                    self.row = (self.row + step) % count
            elif key == ord(' '):
                self.toggle_module() if self.focus == 'modules' else self.toggle_mark()
            elif key in (ord('i'), ord('I')):
                self.install()
            elif key == curses.KEY_RESIZE:
                self.screen.erase()


def main():
    """Abre a TUI do lw setup."""
    def start(screen):
        ui.setup(screen)
        return Setup(screen).loop()
    return curses.wrapper(start)
