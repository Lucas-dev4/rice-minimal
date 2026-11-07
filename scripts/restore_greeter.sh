#!/bin/sh
# Restaura a tela de login ao estado do backup pre-rice.tar.
# Uso, pelo TTY e com a sessao grafica fechada:
#   sudo sh /var/backups/rice-greeter/restore.sh
# Com --force, roda mesmo com o Hyprland aberto (encerra a sessao grafica).
set -u

BACKUP=/var/backups/rice-greeter/pre-rice.tar
FLAG=/home/lucas/.local/state/rice-minimal/theme/greeter-sync
STATE=/var/lib/noctalia-greeter

fail() {
    echo "restore_greeter: $1" >&2
    exit 1
}

# Tudo aqui acontece antes de qualquer alteracao.
[ "$(id -u)" -eq 0 ] || fail 'rode com sudo'
[ -s "$BACKUP" ] || fail "backup ausente ou vazio: $BACKUP (nada foi alterado)"
tar -tf "$BACKUP" etc/greetd var/lib/noctalia-greeter >/dev/null 2>&1 \
    || fail "backup invalido ou incompleto: $BACKUP (nada foi alterado)"
if pgrep -x Hyprland >/dev/null 2>&1 && [ "${1:-}" != --force ]; then
    fail 'Hyprland aberto: reiniciar o greetd encerraria a sessao. Feche a sessao ou use --force (nada foi alterado)'
fi

rm -f "$FLAG"
noctalia-greeter passwordless-sync disable lucas \
    || echo 'restore_greeter: aviso: regra do polkit nao removida; confira com: sudo noctalia-greeter passwordless-sync status' >&2

find "$STATE" -mindepth 1 -delete || fail "falha ao limpar $STATE"
tar -xpf "$BACKUP" -C / || fail 'falha ao extrair o backup; greetd nao foi reiniciado'

systemctl restart greetd || fail 'arquivos restaurados, mas o greetd nao reiniciou'
echo 'restore_greeter: concluido'
