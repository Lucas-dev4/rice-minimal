#!/usr/bin/env python3
"""LW // BLUETOOTH — a small curses manager over bluetoothctl.

↑↓ choose · Enter connect/disconnect · p pair · t trust · d forget · s scan · o power · q quit
"""
import curses
import re
import subprocess
import threading
import time

import ui

ICONS = {'audio-headset': 'fone', 'audio-headphones': 'fone', 'audio-card': 'som', 'input-gaming': 'controle',
         'input-keyboard': 'teclado', 'input-mouse': 'mouse', 'phone': 'celular', 'computer': 'pc'}


def ctl(*args, timeout=20):
    """Run bluetoothctl; (ok, output). Never raises."""
    try:
        r = subprocess.run(['bluetoothctl', *args], capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)


def parse_devices(text):
    """'Device AA:BB:… Name' lines → [(mac, name)]."""
    out = []
    for line in text.splitlines():
        m = re.match(r'\s*Device\s+([0-9A-F:]{17})\s*(.*)$', line, re.I)
        if m:
            out.append((m.group(1).upper(), m.group(2).strip()))
    return out


def parse_info(text):
    """`bluetoothctl info` → {'Name':…, 'Connected': True, 'Battery': 100, …}."""
    info = {}
    for line in text.splitlines():
        key, sep, value = line.strip().partition(': ')
        if not sep:
            continue
        if key in ('Paired', 'Trusted', 'Connected', 'Blocked', 'Powered', 'Discovering'):
            info[key] = value.strip() == 'yes'
        elif key == 'Battery Percentage':
            m = re.search(r'\((\d+)\)', value)
            info['Battery'] = int(m.group(1)) if m else None
        elif key in ('Name', 'Alias', 'Icon'):
            info[key] = value.strip()
    return info


def load():
    """Lê o adaptador e todos os aparelhos conhecidos, ordenados (conectados primeiro)."""
    ok, text = ctl('devices')
    devices = []
    for mac, name in parse_devices(text if ok else ''):
        info = parse_info(ctl('info', mac)[1])
        devices.append({'mac': mac, 'name': info.get('Alias') or name or mac, **info})
    # Connected first, then paired, then what a scan found.
    devices.sort(key=lambda d: (not d.get('Connected'), not d.get('Paired'), d['name'].lower()))
    adapter = parse_info(ctl('show')[1])
    return adapter, devices


def row(d):
    """Uma linha da tabela: nome, estado, tipo, bateria, confiável e MAC."""
    state = 'conectado' if d.get('Connected') else 'pareado' if d.get('Paired') else 'novo'
    kind = ICONS.get(d.get('Icon', ''), d.get('Icon', '') or '—')
    battery = f"{d['Battery']}%" if d.get('Battery') is not None else '—'
    trust = 'confiável' if d.get('Trusted') else ''
    return f"{d['name'][:26]:<26} {state:<10} {kind:<9} {battery:>5}  {trust:<9} {d['mac']}"


class App:
    """Estado da tela: lista de aparelhos, seleção, mensagem e ação em andamento."""
    def __init__(self):
        self.adapter, self.devices = {}, []
        self.index = 0
        self.message = 'carregando…'
        self.busy = None          # text of the running action
        self.scan_until = 0
        self.lock = threading.Lock()
        self.dirty = True

    def refresh(self):
        """Recarrega a lista (roda numa thread para não travar a tela)."""
        adapter, devices = load()
        with self.lock:
            self.adapter, self.devices = adapter, devices
            self.index = min(self.index, max(0, len(devices) - 1))
            self.dirty = True

    def run_bg(self, label, *args, timeout=25):
        """Executa um comando do bluetoothctl em segundo plano; uma ação por vez."""
        if self.busy:
            self.message = f'aguarde: {self.busy}'
            return
        self.busy = label

        def work():
            ok, out = ctl(*args, timeout=timeout)
            last = out.splitlines()[-1] if out else ''
            self.message = f"{label}: {'ok' if ok else 'falhou'}" + ('' if ok else f' — {last[:60]}')
            self.busy = None
            self.refresh()
        threading.Thread(target=work, daemon=True).start()

    def scan(self):
        """Procura aparelhos novos por 15 segundos."""
        if time.time() < self.scan_until:
            self.message = 'já procurando…'
            return
        self.scan_until = time.time() + 15
        self.message = 'procurando aparelhos por 15 s (deixe o aparelho em modo de pareamento)'

        def work():
            ctl('--timeout', '15', 'scan', 'on', timeout=25)
            self.message = 'busca terminada'
            self.refresh()
        threading.Thread(target=work, daemon=True).start()

    def current(self):
        """O aparelho selecionado (ou None)."""
        with self.lock:
            return self.devices[self.index] if self.devices else None

    def draw(self, screen):
        """Desenha a tela inteira."""
        h, w = ui.frame(screen, 'LW // BLUETOOTH')
        a = self.adapter
        power = 'ligado' if a.get('Powered') else 'desligado'
        scanning = '  · procurando…' if time.time() < self.scan_until else ''
        ui.text(screen, 1, 2, f"adaptador {a.get('Alias', '—')}: {power}{scanning}", curses.A_DIM)
        ui.text(screen, 2, 2, f"{'APARELHO':<26} {'ESTADO':<10} {'TIPO':<9} {'BAT':>5}  {'':<9} MAC", curses.A_BOLD)
        with self.lock:
            devices = list(self.devices)
        if not devices:
            ui.text(screen, 4, 2, 'nenhum aparelho — aperte s para procurar')
        visible = max(1, h - 8)
        offset = max(0, self.index - visible + 1)
        for pos, d in enumerate(devices[offset:offset + visible], offset):
            attr = ui.selected() if pos == self.index else (curses.A_BOLD if d.get('Connected') else 0)
            ui.text(screen, 3 + pos - offset, 2, ('> ' if pos == self.index else '  ') + row(d), attr)
        ui.text(screen, h - 4, 2, ('… ' + self.busy) if self.busy else self.message)
        ui.text(screen, h - 2, 2, '↑↓ escolher  Enter conectar/desconectar  p parear  t confiar  d esquecer  s procurar  o liga/desliga  q sair')
        ui.present(screen)

    def key(self, screen, k):
        """Trata uma tecla (Enter, p, t, d, s, o, r e as setas)."""
        d = self.current()
        if k in (curses.KEY_UP, ord('k')) and self.devices:
            self.index = (self.index - 1) % len(self.devices)
        elif k in (curses.KEY_DOWN, ord('j')) and self.devices:
            self.index = (self.index + 1) % len(self.devices)
        elif k in (10, 13, curses.KEY_ENTER) and d:
            if d.get('Connected'):
                self.run_bg(f"desconectando {d['name']}", 'disconnect', d['mac'])
            else:
                self.run_bg(f"conectando {d['name']}", 'connect', d['mac'])
        elif k == ord('p') and d:
            self.run_bg(f"pareando {d['name']}", 'pair', d['mac'], timeout=40)
        elif k == ord('t') and d:
            self.run_bg(f"{'removendo confiança de' if d.get('Trusted') else 'confiando em'} {d['name']}",
                        'untrust' if d.get('Trusted') else 'trust', d['mac'])
        elif k == ord('d') and d:
            if ui.confirm(screen, 'ESQUECER APARELHO', f"Esquecer {d['name']}? Vai precisar parear de novo."):
                self.run_bg(f"esquecendo {d['name']}", 'remove', d['mac'])
        elif k == ord('s'):
            self.scan()
        elif k == ord('o'):
            on = self.adapter.get('Powered')
            self.run_bg('desligando o bluetooth' if on else 'ligando o bluetooth', 'power', 'off' if on else 'on')
        elif k == ord('r'):
            threading.Thread(target=self.refresh, daemon=True).start()


def main(screen):
    """Laço principal: desenha, lê tecla (espera até 0,5 s) e atualiza a lista a cada 3 s."""
    ui.setup(screen)
    app = App()
    threading.Thread(target=app.refresh, daemon=True).start()
    screen.timeout(500)
    last = time.time()
    while True:
        app.draw(screen)
        k = screen.getch()
        if k in (ord('q'), ord('Q'), 27):
            return
        if k != -1:
            app.key(screen, k)
        if time.time() - last > 3 and not app.busy:     # follow changes made elsewhere
            last = time.time()
            threading.Thread(target=app.refresh, daemon=True).start()
        if app.message == 'carregando…' and app.devices:
            app.message = ''


def run():
    """Abre a TUI (usado por "lw bt")."""
    curses.wrapper(main)
    return 0


if __name__ == '__main__':
    run()
