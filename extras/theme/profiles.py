#!/usr/bin/env python3
"""Transactional appearance changes; no palette generation and no session restart."""
# profiles.py — troca o perfil de aparência (minimal/refined) de forma transacional.
# Muda o Noctalia (via "noctalia msg config-set"), o Hyprland (rice-appearance.lua) e os arquivos do tema;
# se algo falhar no meio, devolve tudo como estava.
import argparse
import json
from pathlib import Path
import sys

if __package__:
    from . import theme
else:
    directory = Path(__file__).resolve().parent
    sys.path[:] = [p for p in sys.path if Path(p or '.').resolve() != directory]
    sys.path.insert(0,str(directory.parent))
    from theme import theme


def settings(profile):
    """As opções do Noctalia para cada perfil (Refined liga as animações; o resto é igual)."""
    refined = profile == 'refined'
    return {
        'theme.source':'custom', 'theme.custom_palette':'RiceMinimal', 'theme.mode':'dark',
        'shell.font_family':'DejaVu Sans Mono', 'shell.corner_radius_scale':0.0,
        'shell.animation.enabled':refined, 'shell.animation.speed':1.5,
        'shell.panel.transparency_mode':'soft', 'shell.panel.borders':True,
        'shell.panel.border_width':1.0, 'shell.panel.border_color':'outline_variant',
        'shell.panel.shadow':False, 'shell.popup_shadows':False,
        'shell.launcher.layout':'simple', 'shell.launcher.compact':True,
        'shell.launcher.categories':False, 'shell.launcher.show_icons':False,
        'notification.background_opacity':.94, 'notification.border':True,
        'notification.border_width':1.0, 'notification.border_color':'outline_variant',
        'notification.offset_y':36, 'notification.width':360,
        # No click when the volume changes (Super+=/-, the bar's wheel).
        'audio.enable_volume_sounds':False,
    }


def atomic(path, value):
    """Grava um arquivo pequeno de uma vez (arquivo temporário + rename)."""
    temporary = path.with_name('.'+path.name+'.tmp')
    temporary.write_text(value)
    temporary.replace(path)


def apply_hypr():
    """Recarrega a aparência do Hyprland na sessão aberta e falha se o Hyprland apontar erro."""
    if theme.os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
        theme.command(['hyprctl','eval','dofile('+json.dumps(str(theme.ROOT/'config/hypr/rice-appearance.lua'))+')'])
        errors = theme.command(['hyprctl','configerrors'])
        if errors.strip():
            raise RuntimeError(errors)


def same(printed, value):
    """config-get prints TOML values ('monospace', true, 0.25); compare them as data."""
    import tomllib
    try:
        return tomllib.loads('v = '+printed)['v'] == value
    except (tomllib.TOMLDecodeError, TypeError):
        return False


def switch(profile):
    """Troca o perfil: lê os valores atuais, aplica só o que muda e, em caso de erro, desfaz tudo."""
    if profile not in ('minimal','refined'):
        raise ValueError('Unknown profile: '+profile)
    with theme.locked():
        before = theme.current_profile()
        previous_generation = (theme.STATE/'current').resolve()
        # Read every key first so a partial IPC failure can restore its actual value.
        keys = settings(profile)
        # Reads are independent IPC calls; in parallel they take ~0.1 s instead of ~0.55 s.
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(8) as pool:
            old = dict(zip(keys, pool.map(lambda key: theme.command(['noctalia','msg','config-get',key]), keys)))
        changed = []
        try:
            atomic(theme.STATE/'profile', profile+'\n')
            theme.publish(theme.read_palette())
            apply_hypr()
            for key,value in keys.items():
                # Only send what differs: one IPC round trip each, and most keys never change.
                if same(old[key], value):
                    continue
                changed.append(key)
                theme.command(['noctalia','msg','config-set',key,json.dumps(value)])
            theme.reload_components()
        except Exception as exc:
            atomic(theme.STATE/'profile',before+'\n')
            theme.link('current',previous_generation.name)
            failures = []
            for key in reversed(changed):
                try:
                    theme.command(['noctalia','msg','config-set',key,old[key]])
                except Exception as error:
                    failures.append(str(error))
            try:
                apply_hypr()
                theme.reload_components()
            except Exception as error:
                failures.append(str(error))
            if failures:
                raise RuntimeError(f'{exc}; rollback incomplete: {failures}') from exc
            raise
        atomic(theme.STATE/'previous-profile',before+'\n')
        return profile


def previous():
    """Volta para o perfil usado antes do atual."""
    return switch((theme.STATE/'previous-profile').read_text().strip())


def main():
    """Linha de comando: minimal | refined | current | restore."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile',choices=['minimal','refined','current','restore'])
    args = parser.parse_args()
    print(theme.current_profile() if args.profile == 'current' else
          previous() if args.profile == 'restore' else switch(args.profile))

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'rice-profile: {exc}',file=sys.stderr)
        sys.exit(1)
