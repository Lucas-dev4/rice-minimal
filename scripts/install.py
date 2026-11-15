#!/usr/bin/env python3
"""Install every part of the rice from this repository, transactionally.

Without --apply it only lists what would change. With --apply it validates every
new file, saves a backup that scripts/restore.py can undo, writes everything,
and rolls back on any failure. Paths are rendered for the current user and
checkout, so the repository never needs /home/lucas to exist.
"""
# install.py — instala o rice a partir deste repositório (python3 scripts/install.py [--apply|--check]).
# Sem --apply só mostra o que mudaria. Com --apply: valida cada arquivo, faz backup em backups/install-*,
# grava tudo e desfaz se algo falhar. Pacotes do sistema e a tela de login (sudo) ficam de fora.
import argparse
import configparser
import datetime
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
STATE = HOME/'.local/state/rice-minimal/theme'

# Repository file -> installed path (relative to HOME). Copied as they are.
FILES = [
    ('config/hypr/rice-minimal.lua', '.config/hypr/config/rice-minimal.lua'),
    ('config/hypr/rice-integration.lua', '.config/hypr/config/rice-integration.lua'),
    ('config/hypr/rice-appearance.lua', '.config/hypr/config/rice-appearance.lua'),
    ('extras/theme/rice-adaptive-hypr.lua', '.config/hypr/config/rice-adaptive.lua'),
    ('config/fish/config.fish', '.config/fish/config.fish'),
    ('extras/theme/rice-adaptive.fish', '.config/fish/conf.d/rice-adaptive.fish'),
    ('config/fish/conf.d/zoxide.fish', '.config/fish/conf.d/zoxide.fish'),
    ('config/fish/functions/y.fish', '.config/fish/functions/y.fish'),
    ('config/fish/functions/vim.fish', '.config/fish/functions/vim.fish'),
    ('config/fish/functions/fastfetch.fish', '.config/fish/functions/fastfetch.fish'),
    ('config/fastfetch/config.jsonc', '.config/fastfetch/config.jsonc'),
    ('config/nvim/init.lua', '.config/nvim/init.lua'),
    ('config/nvim/lazy-lock.json', '.config/nvim/lazy-lock.json'),
    ('config/yazi/yazi.toml', '.config/yazi/yazi.toml'),
    ('config/autostart/rice-minimal.desktop', '.config/autostart/rice-minimal.desktop'),
]
# Written once; the program rewrites them with the user's own preferences.
SEEDS = [('config/cliamp/config.toml', '.config/cliamp/config.toml')]
# `lw` is the name; `rice` stays so shortcuts and scripts keep working.
LAUNCHERS = [('lw', 'extras/rice.py'), ('rice', 'extras/rice.py'), ('supers', 'extras/supers/Supers'),
             ('wallpapers', 'extras/wallpapers/wallpaper_tui.py')]
HYPR_MODULES = ['rice-minimal', 'rice-integration', 'rice-adaptive', 'rice-appearance']
# Minimal, nearly monochrome themes that ship with the system (adwaita-icon-theme).
ICON_THEME = 'Adwaita'
CURSOR_THEME = 'Adwaita'
# Existing files where the themes are named: (file, [(pattern, replacement)]).
THEME_KEYS = [
    ('.config/uwsm/env', [(r'^export HYPRCURSOR_THEME=.*$', f'export HYPRCURSOR_THEME="{CURSOR_THEME}"'),
                          (r'^export XCURSOR_THEME=.*$', f'export XCURSOR_THEME="{CURSOR_THEME}"')]),
    ('.icons/default/index.theme', [(r'^Inherits=.*$', f'Inherits={CURSOR_THEME}')]),
    ('.local/share/icons/default/index.theme', [(r'^Inherits=.*$', f'Inherits={CURSOR_THEME}')]),
    ('.config/gtk-3.0/settings.ini', [(r'^gtk-icon-theme-name=.*$', f'gtk-icon-theme-name={ICON_THEME}'),
                                      (r'^gtk-cursor-theme-name=.*$', f'gtk-cursor-theme-name={CURSOR_THEME}')]),
    ('.config/gtk-4.0/settings.ini', [(r'^gtk-icon-theme-name=.*$', f'gtk-icon-theme-name={ICON_THEME}'),
                                      (r'^gtk-cursor-theme-name=.*$', f'gtk-cursor-theme-name={CURSOR_THEME}')]),
    ('.config/qt5ct/qt5ct.conf', [(r'^icon_theme=.*$', f'icon_theme={ICON_THEME}')]),
    ('.config/qt6ct/qt6ct.conf', [(r'^icon_theme=.*$', f'icon_theme={ICON_THEME}')]),
]


def render(text):
    # The repository records the author's paths; install them for this user and checkout.
    # A placeholder keeps the checkout path from being rewritten twice.
    """Troca os caminhos do autor (/home/lucas/...) pelos do usuário e da pasta atuais."""
    marker = '\0ROOT\0'
    return (text.replace('/home/lucas/Projetos/rice-minimal', marker)
            .replace('/home/lucas', str(HOME)).replace(marker, str(ROOT)))


def read(path):
    """Conteúdo do arquivo, ou None se não existir."""
    return path.read_text() if path.exists() else None


def hook_installed(command):
    """True se o post_command do Waypaper já é o gancho do tema."""
    return 'extras/theme/theme.py' in command and command.rstrip().endswith(' wallpaper')


def waypaper(target):
    """Only the hook belongs to the rice; every other Waypaper value is the user's."""
    source = render((ROOT/'config/waypaper/config.ini').read_text())
    if not target.exists():
        return source
    expected, current = (configparser.ConfigParser(interpolation=None) for _ in range(2))
    for parser in (expected, current):
        parser.optionxform = str
    expected.read_string(source)
    current.read(target)
    changed = False
    for section in expected.sections():
        if not current.has_section(section):
            current.add_section(section)
        for key, value in expected.items(section):
            actual = current.get(section, key, fallback=None)
            if actual is None or (key == 'post_command' and not hook_installed(actual)):
                current.set(section, key, value)
                changed = True
    if not changed:
        return None
    text = io.StringIO()
    current.write(text)
    return text.getvalue()


def plan():
    """Every pending change as {target: (text, mode)}; empty when installed."""
    files = {}
    for source, target in FILES:
        files[HOME/target] = (render((ROOT/source).read_text()), 0o644)
    for source, target in SEEDS:
        if not (HOME/target).exists():
            files[HOME/target] = ((ROOT/source).read_text(), 0o644)
    kitty = render((ROOT/'config/kitty/kitty.conf').read_text()).rstrip('\n')
    files[HOME/'.config/kitty/kitty.conf'] = (kitty+f'\n\ninclude {STATE}/current/kitty.conf\n', 0o644)
    text = waypaper(HOME/'.config/waypaper/config.ini')
    if text is not None:
        files[HOME/'.config/waypaper/config.ini'] = (text, 0o644)
    for name, entry in LAUNCHERS:
        files[HOME/'.local/bin'/name] = ('#!/bin/sh\nexec /usr/bin/python3 '+shlex.quote(str(ROOT/entry))+' "$@"\n', 0o755)
    hypr = HOME/'.config/hypr/hyprland.lua'
    if hypr.exists():
        text = hypr.read_text()
        for module in HYPR_MODULES:
            line = f'require("config.{module}")'
            if line not in text:
                text = text.rstrip('\n')+f'\n\n{line}\n'
        files[hypr] = (text, 0o644)
    for qt in ('qt5ct', 'qt6ct'):
        path = HOME/f'.config/{qt}/{qt}.conf'
        if path.exists():
            # Noctalia regenerates this palette on every theme change.
            text = re.sub(r'^color_scheme_path=.*$', f'color_scheme_path={HOME}/.config/{qt}/colors/noctalia.conf',
                          path.read_text(), flags=re.M)
            files[path] = (text, 0o644)
    for relative, rules in THEME_KEYS:
        path = HOME/relative
        if path.exists():
            text = files[path][0] if path in files else path.read_text()
            for pattern, replacement in rules:
                text = re.sub(pattern, lambda _: replacement, text, flags=re.M)
            files[path] = (text, path.stat().st_mode & 0o777)
    return {path: (text, mode) for path, (text, mode) in files.items()
            if read(path) != text or (path.stat().st_mode & 0o777) != mode}


def validate(path, text):
    """Reject a broken file before anything is written."""
    suffix = path.suffix
    if suffix == '.toml':
        tomllib.loads(text)
    elif suffix == '.json':
        json.loads(text)
    elif suffix == '.ini':
        configparser.ConfigParser(interpolation=None).read_string(text)
    elif suffix in ('.lua', '.fish'):
        with tempfile.NamedTemporaryFile('w', suffix=suffix) as stream:
            stream.write(text)
            stream.flush()
            subprocess.run(['luac', '-p', stream.name] if suffix == '.lua' else ['fish', '-n', stream.name],
                           check=True, capture_output=True, text=True)


def apply(changes, backups=ROOT/'backups'):
    """Valida tudo, faz o backup e grava; em caso de erro devolve os arquivos originais."""
    for path, (text, _) in changes.items():
        validate(path, text)
    backup = backups/('install-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(parents=True)
    manifest = []
    for path in changes:
        saved = None
        if path.exists():
            saved = backup/'home'/path.relative_to(HOME)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, saved, follow_symlinks=False)
        manifest.append({'path': str(path), 'backup': str(saved) if saved else None})
    # The manifest exists before the first write, so a crash is always restorable.
    (backup/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    written = []
    try:
        for path, (text, mode) in changes.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            handle, temporary = tempfile.mkstemp(prefix='.rice-', dir=path.parent)
            try:
                with os.fdopen(handle, 'w') as stream:
                    stream.write(text)
                os.chmod(temporary, mode)
                os.replace(temporary, path)
            finally:
                Path(temporary).unlink(missing_ok=True)
            written.append(path)
    except Exception:
        for item in manifest:
            path = Path(item['path'])
            if path in written:
                if item['backup']:
                    shutil.copy2(item['backup'], path, follow_symlinks=False)
                else:
                    path.unlink(missing_ok=True)
        raise
    return backup


def post_install():
    """Publish the palette and bring the running session up to date (best effort)."""
    steps = []
    def run(label, args):
        """Roda um passo pós-instalação e anota OK/WARN."""
        result = subprocess.run(args, capture_output=True, text=True, cwd=ROOT)
        steps.append(f"{'OK' if result.returncode == 0 else 'WARN'}  {label}")
    run('theme files', [sys.executable, str(ROOT/'extras/theme/theme.py'), 'cached'])
    palette = HOME/'.config/noctalia/palettes/RiceMinimal.json'
    if not palette.exists() and (STATE/'current/noctalia.json').exists():
        palette.parent.mkdir(parents=True, exist_ok=True)
        palette.write_text((STATE/'current/noctalia.json').read_text())
        steps.append('OK  Noctalia palette RiceMinimal')
    run('GNOME/GTK4 icon theme', ['gsettings', 'set', 'org.gnome.desktop.interface', 'icon-theme', ICON_THEME])
    run('GNOME/GTK4 cursor theme', ['gsettings', 'set', 'org.gnome.desktop.interface', 'cursor-theme', CURSOR_THEME])
    if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
        run('cursor in this session', ['hyprctl', 'setcursor', CURSOR_THEME, os.environ.get('XCURSOR_SIZE', '24')])
        run('sync running session', [sys.executable, str(ROOT/'extras/rice.py'), 'sync', '--json'])
    return steps


def main():
    """Mostra o plano; com --apply instala, com --check só diz se falta algo (código de saída 1)."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='write the changes (otherwise only list them)')
    parser.add_argument('--check', action='store_true', help='exit 1 when anything is not installed')
    args = parser.parse_args()
    changes = plan()
    for path in changes:
        print(('new      ' if not path.exists() else 'changed  ')+str(path).replace(str(HOME), '~'))
    if not changes:
        print('Everything is installed; nothing to change.')
    if args.check:
        return 1 if changes else 0
    if not args.apply:
        if changes:
            print('\nRun again with --apply to install. A backup is saved first.')
        return 0
    if changes:
        backup = apply(changes)
        print('\nBackup:', backup.relative_to(ROOT))
        print('Undo with: python3 scripts/restore.py', backup.relative_to(ROOT), '--apply')
    for line in post_install():
        print(line)
    print('\nNot handled here (needs sudo): packages, the login screen (config/greeter/greeter.toml).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
