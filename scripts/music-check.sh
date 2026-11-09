#!/bin/bash
# LW // MUSIC control layer check: drives gui/Music.qml against a real cliamp through
# the `music` IPC hooks of gui/music.qml. Isolated: generated tracks and a temporary
# HOME, so the real ~/.config/cliamp (history, resume, socket) is never touched.
# Needs cliamp, ffmpeg and qs. Plays quietly (-30 dB).
set -u
REPO=$(cd "$(dirname "$0")/.." && pwd)
WORK=$(mktemp -d)
trap 'kill $QS $CL 2>/dev/null; rm -rf "$WORK"' EXIT
export HOME=$WORK/home XDG_CONFIG_HOME=$WORK/home/.config XDG_STATE_HOME=$WORK/home/.local/state
mkdir -p "$HOME" "$WORK/music"
cd "$WORK/music"
ffmpeg -loglevel error -f lavfi -i "sine=f=220:d=60,volume=0.3" -metadata title="Grave" -metadata artist="LW Lab" -metadata album="Sinais" a.mp3
ffmpeg -loglevel error -f lavfi -i "sine=f=330:d=60,volume=0.3" -metadata title="Médio" -metadata artist="LW Lab" b.flac
ffmpeg -loglevel error -f lavfi -i "sine=f=440:d=60,volume=0.3" c.ogg
ffmpeg -loglevel error -f lavfi -i "sine=f=550:d=20,volume=0.3" sem-tags.mp3
cd "$REPO"
fails=0
QT_QPA_PLATFORM=offscreen setsid qs -p gui/music.qml > "$WORK/qs.log" 2>&1 & QS=$!
m() { qs ipc --pid $QS call music "$@"; }
get() { m state | python3 -c "import json,sys;d=json.load(sys.stdin);print(d[sys.argv[1]])" "$1"; }
check() { # name field expected
    local got; got=$(get "$2")
    if [ "$got" = "$3" ]; then echo "[ OK ] $1"; else echo "[FAIL] $1: $2=$got, esperado $3"; fails=$((fails+1)); fi
}
sleep 1.5
check "offline sem cliamp" status offline
setsid cliamp -d --vol -30 --auto-play "$WORK"/music/a.mp3 "$WORK"/music/b.flac "$WORK"/music/c.ogg > "$WORK/cl.log" 2>&1 & CL=$!
sleep 3
check "reconecta sozinho" status playing
check "metadados" title Grave
m act toggle - >/dev/null; sleep 0.6; check "pausa" status paused
m act toggle - >/dev/null; sleep 0.6; check "volta a tocar" status playing
m act seek 30 >/dev/null; sleep 0.8; p=$(get position); python3 -c "import sys;sys.exit(0 if 29<=float(sys.argv[1])<=32 else 1)" "$p" && echo "[ OK ] seek ($p s)" || { echo "[FAIL] seek: $p"; fails=$((fails+1)); }
m act volume 20 >/dev/null; sleep 0.6; check "volume 20%" volume 20
m act mute - >/dev/null; sleep 0.6; check "mute" volume 0
m act mute - >/dev/null; sleep 0.6; check "unmute" volume 20
m act shuffle - >/dev/null; sleep 0.6; check "shuffle" shuffle True
m act shuffle - >/dev/null; sleep 0.6
m act repeat - >/dev/null; sleep 0.5; check "repeat all" repeat all
m act repeat - >/dev/null; sleep 0.5; check "repeat one" repeat one
m act repeat - >/dev/null; sleep 0.5; check "repeat off" repeat off
m act next - >/dev/null; sleep 0.8; check "próxima" index 1
m act prev - >/dev/null; sleep 0.8; check "anterior" index 0
m act add "$WORK/music/sem-tags.mp3" >/dev/null; sleep 1
m act play 3 >/dev/null; sleep 0.8; check "sem tags usa o nome do arquivo" title sem-tags
# queue.move swaps the two positions (sem-tags <-> Grave); J/K moves one step, where it is the same.
m act move 3,0 >/dev/null; sleep 1; check "mover faixa" index 0
m act remove 0 >/dev/null; sleep 1; check "remover faixa" playlist "['Médio', 'c', 'Grave']"
m act band 0,4 >/dev/null; sleep 0.6; check "EQ banda" eq "[4, 0, 0, 0, 0, 0, 0, 0, 0, 0]"
m act preset Flat >/dev/null; sleep 0.6; check "EQ preset" eq "[0, 0, 0, 0, 0, 0, 0, 0, 0, 0]"
m act bad - >/dev/null; sleep 1; check "erro com motivo" error "job failed (invalid_params): invalid parameters"
kill $CL; sleep 1.5; check "cliamp morre: offline" status offline
start=$(date +%s%N); m state >/dev/null; ms=$(( ($(date +%s%N)-start)/1000000 ))
[ $ms -lt 500 ] && echo "[ OK ] responde sem travar (${ms} ms)" || { echo "[FAIL] demorou ${ms} ms"; fails=$((fails+1)); }
m act quit - >/dev/null; sleep 1
pgrep -f "^cliamp remote events" -u "$(id -u)" -a | grep -q "$WORK" && { echo "[FAIL] processo de eventos sobrou"; fails=$((fails+1)); } || echo "[ OK ] fecha sem deixar processos"
echo; [ $fails -eq 0 ] && echo "music-check: tudo OK" || echo "music-check: $fails falha(s)"
exit $fails
