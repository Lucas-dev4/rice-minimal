// Music.qml — singleton que conversa com o cliamp (o player de música de verdade).
// Todas as telas de MÚSICA usam só este arquivo: estado (faixa, posição, volume, fila) chega pelo stream de eventos
// do cliamp, e cada ação é um comando IPC (cliamp remote). Também guarda/retoma a sessão ao fechar e abrir o LW.
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import qs.components

// The one place that talks to cliamp (v2 IPC, `cliamp remote`). Everything that plays
// goes through cliamp; this only mirrors its state and sends it commands.
//   state   `remote events runtime.state` pushes a snapshot on every change; the position
//           is extrapolated between snapshots and resynced every few seconds.
//   calls   `remote call <op> --params JSON --wait`, one process each, killed after 4 s.
//   offline the event stream exits (no socket): retried with a growing delay.
Singleton {
    id: root

    // ---- observable state ---------------------------------------------------
    property bool online: false
    property bool connecting: true
    property var snapshot: ({})
    property var playlist: []            // [{title, artist, album, path, index}]
    property bool playlistLoaded: false
    property string lastError: ""
    readonly property string status: online ? (snapshot.state || "stopped") : "offline"
    readonly property bool playing: status === "playing"
    readonly property var track: snapshot.track || null
    readonly property string title: !track ? "" : clean(track.title) || fileName(track.path)
    readonly property string artist: track ? clean(track.artist) : ""
    readonly property string album: track ? clean(track.album) : ""
    // Some tags start with a byte-order mark or carry stray spaces.
    function clean(text) { return String(text || "").replace(/\uFEFF/g, "").trim(); }
    readonly property real duration: snapshot.duration || 0
    readonly property bool live: online && !!track && duration <= 0     // radio / stream
    readonly property bool seekable: snapshot.seekable === true
    property real position: 0
    readonly property bool shuffle: snapshot.shuffle === true
    readonly property string repeat: String(snapshot.repeat || "Off").toLowerCase()   // off | all | one
    readonly property var eqBands: snapshot.eq_bands || [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    readonly property string eqPreset: snapshot.eq_preset || ""
    readonly property int currentIndex: {
        if (!track) return -1;
        const at = playlist.findIndex(t => t.path === track.path);
        return at;
    }
    // Volume: dB from cliamp; percent uses cliamp's own bar formula.
    readonly property real volumeMin: -50
    readonly property real volumeDb: snapshot.volume === undefined ? 0 : snapshot.volume
    // VOL is the system output (PipeWire default sink), the same one Super+=/− and the
    // Noctalia OSD move, so every control shows one number. RICE_MUSIC_VOLUME=cliamp uses
    // cliamp's own gain instead (scripts/music-check.sh, so tests never touch the speakers).
    readonly property bool systemVolume: Quickshell.env("RICE_MUSIC_VOLUME") !== "cliamp"
    property real sinkVolume: 0
    property bool sinkMuted: false
    readonly property int cliampPercent: Math.round(100 * Math.max(0, Math.min(1, (volumeDb - volumeMin) / (6 - volumeMin))))
    readonly property int volumePercent: systemVolume ? Math.round(sinkVolume * 100) : cliampPercent
    property real mutedFrom: NaN          // dB to go back to; NaN = not muted
    readonly property bool muted: systemVolume ? sinkMuted : !isNaN(mutedFrom)
    readonly property var eqFrequencies: [70, 180, 320, 600, 1000, 3000, 6000, 12000, 14000, 16000]

    // Per-file details cliamp does not give: {codec, rate, bitrate, channels, duration}.
    // Filled by ffprobe for local files, once per path.
    property var infos: ({})
    property var probing: ({})
    // At most 4 ffprobe at a time; the rest wait in line.
    property var infoQueue: []
    property int infoRunning: 0
    // Pede as informações (tags/duração) de um arquivo local; entra na fila do ffprobe.
    function requestInfo(path) {
        if (!path || sourceOf(path) !== "local" || infos[path] || probing[path]) return;
        probing[path] = true;
        infoQueue.push(path);
        pumpInfo();
    }
    // Inicia os próximos ffprobe da fila (no máximo 4 ao mesmo tempo).
    function pumpInfo() {
        while (infoRunning < 4 && infoQueue.length) {
            infoRunning++;
            prober.createObject(root, { path: infoQueue.shift() }).running = true;
        }
    }
    // Cover art, only when cliamp's MPRIS metadata has one (mpris:artUrl).
    property string artUrl: ""

    // cliamp lives in ~/.local/bin, which Hyprland's PATH lacks: `rice music` adds it, and
    // RICE_CLIAMP can point somewhere else.
    readonly property string bin: Quickshell.env("RICE_CLIAMP") || "cliamp"

    signal changed()          // any new snapshot
    signal failed(string op, string message)

    // local | radio | stream. Plain http(s) is a radio stream unless it is a known
    // streaming site; provider ids (spotify:, ytmusic: …) are streaming.
    function sourceOf(path) {
        const p = String(path || "");
        if (p.startsWith("/") || p.startsWith("file:")) return "local";
        if (/^https?:/i.test(p)) return /youtube\.|youtu\.be|soundcloud\.|bandcamp\.|mixcloud\.|spotify\.|tidal\.|qobuz\./i.test(p) ? "stream" : "radio";
        return "stream";
    }
    // Nome do arquivo sem pasta e sem extensão.
    function fileName(path) { return String(path || "").split("/").pop().replace(/\.[^.]+$/, ""); }

    // A pasta das músicas (music.dir); dirShown é ela com "~".
    readonly property string dir: String(Modules.config("music", "dir") || "").replace(/(.)\/+$/, "$1")
    readonly property string dirShown: {
        const home = Quickshell.env("HOME");
        return dir.startsWith(home + "/") ? "~" + dir.slice(home.length) : dir;
    }

    // ---- commands -----------------------------------------------------------
    // op: a v2 operation; params: object. done(result) on success. limit: ms before giving
    // up (4 s; an online search through yt-dlp needs more).
    function call(op, params, done, limit) {
        const proc = caller.createObject(root, { op: op, params: params || {}, done: done || null, limit: limit || 4000 });
        proc.start();
    }
    // Play/pause.
    function toggle() { call("toggle"); }
    // Próxima faixa.
    function next() { call("next"); }
    // Like most players: back to the start when past 3 s, otherwise the previous track.
    function previous() { position > 3 && seekable ? seekTo(0) : call("prev"); }
    // Para a reprodução.
    function stop() { call("stop"); }
    // Pula para um segundo da faixa.
    function seekTo(seconds) {
        position = Math.max(0, Math.min(duration || seconds, seconds));
        call("seek.absolute", { value: position });
    }
    // Avança/volta alguns segundos.
    function seekBy(seconds) { if (seekable) seekTo(position + seconds); }
    // Volume em porcentagem (convertido para dB do cliamp).
    function setVolumePercent(percent) {
        const p = Math.max(0, Math.min(100, percent));
        if (systemVolume) {
            sinkVolume = p / 100;
            Quickshell.execDetached(["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", (p / 100).toFixed(2)]);
            return;
        }
        mutedFrom = NaN;
        call("volume", { value: Math.round((volumeMin + (6 - volumeMin) * p / 100) * 10) / 10 });
    }
    // Steps and mute use the very commands of Super+=/− (same step, same OSD).
    function volumeStep(percent) {
        if (systemVolume) Quickshell.execDetached(["noctalia", "msg", percent > 0 ? "volume-up" : "volume-down"]);
        else setVolumePercent(volumePercent + percent);
    }
    // cliamp has no mute: remember the level and drop to the floor.
    function toggleMute() {
        if (systemVolume) { Quickshell.execDetached(["noctalia", "msg", "volume-mute"]); return; }
        if (muted) { const back = mutedFrom; mutedFrom = NaN; call("volume", { value: back }); }
        else { mutedFrom = volumeDb; call("volume", { value: volumeMin }); }
    }
    // Liga/desliga o aleatório.
    function setShuffle(on) { call("shuffle", { name: on ? "on" : "off" }); }
    // Repetir: desligado → tudo → uma.
    function cycleRepeat() { call("repeat", { name: repeat === "off" ? "all" : repeat === "all" ? "one" : "off" }); }
    // Toca a faixa dessa posição da fila.
    function playIndex(index) { call("queue.play", { index: index }); }
    // Move uma faixa na fila.
    function moveTrack(index, to) { call("queue.move", { index: index, to: to }, () => refreshPlaylist()); }
    // Tira uma faixa da fila.
    function removeTrack(index) { call("queue.remove", { index: index }, () => refreshPlaylist()); }
    // Plays a file: from the queue when it is there, otherwise appended and played.
    function playPath(path) {
        const at = playlist.findIndex(t => t.path === path);
        if (at >= 0) { playIndex(at); return; }
        const end = playlist.length;
        call("queue", { path: path }, () => { call("queue.play", { index: end }); refreshPlaylist(); });
    }
    // Põe um arquivo/pasta no fim da fila.
    function addPath(path) { call("queue", { path: path }, () => refreshPlaylist()); }
    // Toca uma URL (rádio).
    function playUrl(url) { call("url.load", { path: url, play: true }); }
    // A track from provider.search (YouTube, SoundCloud…): play now or play next.
    function playTrack(track) { call("track.play", { track: track }, () => refreshPlaylist(), 30000); }
    // Põe uma faixa online como próxima.
    function queueTrack(track) { call("track.queue", { track: track }, () => refreshPlaylist(), 30000); }
    // Ajusta uma banda do equalizador (-12 a +12 dB).
    function setBand(band, dB) { call("eq", { band: band, value: Math.max(-12, Math.min(12, Math.round(dB))) }); }
    // Escolhe um preset do equalizador.
    function setPreset(name) { call("eq", { name: name }); }

    // Starts cliamp headless. With a saved session (see session()) it gets the same queue
    // and comes back paused at the same track and second; otherwise it opens the folder
    // given by `lw cliamp sync` (music.dir), without playing. cliamp's own
    // resume.json is not used by its daemon, hence our session.
    property var pendingResume: null
    // Enquanto o cliamp volta para a sessão salva (null fora disso): o estado dele ainda não é o da
    // pessoa, e o arquivo já é a sessão certa.
    property var resuming: null
    // Uma volta que falhou no meio acaba ali.
    onFailed: if (!pendingResume) resuming = null
    // O arquivo com o PID do cliamp que este LW ligou ("" se não foi ele).
    property string started: ""
    property int starts: 0
    // Fechado (closeSession): um START que ainda estava no meio não continua.
    property bool stopped: false
    // Liga o cliamp sem janela (daemon), com a sessão salva ou abrindo a pasta das músicas.
    function start(saved, folder) {
        if (online || stopped) return;
        const paths = saved && saved.paths ? saved.paths : [];
        pendingResume = paths.length ? saved : null;
        resuming = pendingResume;
        // O cliamp só escreve o cliamp.sock.pid quando responde; o exec mantém o PID anotado aqui.
        started = (Quickshell.env("XDG_RUNTIME_DIR") || "/tmp") + "/lw-cliamp-" + Quickshell.processId + "-" + (++starts) + ".pid";
        Quickshell.execDetached(["setsid", "sh", "-c", 'echo $$ > "$0"; exec "$@"', started, bin, "--daemon"]
            .concat(paths.length ? paths : folder ? [folder] : []));
        startWatch.restart();
        connecting = true;
        retry.interval = 400;
        retry.restart();
    }
    // cliamp answers at most 200 tracks per call: fetch page by page, then publish once.
    // ---- the window's session: closing stops cliamp, opening resumes it ------------
    // Saved in ~/.local/state/rice-minimal/gui/music-session.json; cliamp's daemon does not
    // read its own resume.json. RICE_MUSIC_AUTOSTART=0 keeps START manual.
    readonly property string sessionPath: Theme.guiStatePath + "/music-session.json"
    FileView {
        id: sessionFile
        path: root.sessionPath
        blockLoading: true
        blockWrites: true
        atomicWrites: true
        printErrors: false
    }
    // Sessão salva (fila, faixa, segundo, volume), ou null.
    function savedSession() {
        try { const s = JSON.parse(sessionFile.text()); return s.paths && s.paths.length ? s : null; } catch (error) { return null; }
    }
    // Liga o cliamp com a sessão salva. O cliamp não abre se um caminho da lista não existe
    // (música movida ou apagada), então os que sumiram ficam de fora antes.
    function startCliamp() {
        stopped = false;
        const saved = savedSession();
        if (pathCheck.running || folderSync.running) return;
        if (!saved) return syncFolder(null);
        pathCheck.saved = saved;
        pathCheck.command = ["sh", "-c", 'for p; do case "$p" in *://*) echo 1 ;; *) [ -e "$p" ] && echo 1 || echo 0 ;; esac; done',
                             "lw-music"].concat(saved.paths);
        pathCheck.running = true;
    }
    // A sessão só com os caminhos que ainda existem (flags: "1"/"0" por caminho); a faixa
    // atual é procurada de novo na lista menor. Sem nenhum, null (abre a pasta de música).
    function keepExisting(saved, flags) {
        const paths = saved.paths.filter((p, i) => flags[i] === "1");
        if (paths.length === saved.paths.length) return saved;
        if (!paths.length) return null;
        const index = paths.indexOf(saved.paths[saved.index || 0]);
        return { paths: paths, index: Math.max(0, index), position: index < 0 ? 0 : saved.position, volume: saved.volume };
    }
    Process {
        id: pathCheck
        property var saved: null
        stdout: StdioCollector { id: pathFlags }
        onExited: root.syncFolder(root.keepExisting(saved, pathFlags.text.split("\n")))
    }
    // Antes de ligar: o LW passa music.dir para o initial_directory do cliamp (lw cliamp sync)
    // e devolve a pasta. Com o cliamp parado, ele não regrava a config por cima.
    function syncFolder(saved) {
        folderSync.saved = saved;
        folderSync.call(["cliamp", "sync", "--json"]);
    }
    RiceCommand {
        id: folderSync
        property var saved: null
        program: Theme.lw
        onSucceeded: data => root.start(saved, data.exists ? data.dir : "")
        onFailed: message => {
            root.failed("pasta das músicas", message);
            root.start(saved, "");
        }
    }
    // Ao fechar o LW (active: em MÚSICA): salva a sessão e desliga o cliamp que o LW ligou (started),
    // mesmo antes de ele responder; um que já estava ligado só desliga em MÚSICA.
    function closeSession(active) {
        if (stopped) return;
        stopped = true;
        saveSession();
        if (started || (active && online && playlist.length)) shutdown(online && active);
    }
    // The LW window closes with cliamp still playing: only the session is written, so a
    // later start (after a reboot, say) comes back to the same place.
    function saveSession() {
        if (online && playlist.length && !resuming)
            sessionFile.setText(JSON.stringify(session()) + "\n");
    }
    // Starting cliamp by itself is up to the window: LW sets `wanted` when MÚSICA opens
    // (the separate player sets it at once), so opening LW for a wallpaper starts nothing.
    property bool wanted: false
    property bool autoStarted: false
    // Liga o cliamp sozinho quando a seção MÚSICA abre (se RICE_MUSIC_AUTOSTART não for 0).
    function autoStart() {
        if (wanted && !connecting && !online && !autoStarted && Quickshell.env("RICE_MUSIC_AUTOSTART") !== "0") {
            autoStarted = true;
            startCliamp();
        }
    }
    onConnectingChanged: autoStart()
    onWantedChanged: autoStart()

    // What to save when the window closes (closeSession writes it).
    function session() {
        return { paths: playlist.map(t => t.path), index: currentIndex, position: Math.floor(position), volume: volumeDb };
    }
    // Back to the saved track and second, paused. cliamp's own gain sits at the floor
    // while it gets there, so nothing is heard.
    function resumeNow(saved) {
        const index = Math.max(0, Math.min(playlist.length - 1, saved.index || 0));
        call("volume", { value: volumeMin }, () =>
            call("queue.play", { index: index }, () =>
                call("seek.absolute", { value: saved.position || 0 }, () =>
                    call("pause", {}, () => call("volume", { value: saved.volume === undefined ? 0 : saved.volume }, () => { resuming = null; })))));
    }
    // Closing the player switches cliamp off (SIGTERM: it saves its own state too).
    // O que o LW ligou, pelo PID anotado (espera um pouco por ele, se o START acabou de sair); se
    // esse já morreu e outro responde em MÚSICA, ou se não foi o LW, pelo cliamp.sock.pid.
    function shutdown(any) {
        Quickshell.execDetached(["sh", "-c",
            'if [ -n "$1" ]; then i=0; while [ ! -s "$1" ] && [ $i -lt 50 ]; do sleep 0.1; i=$((i+1)); done; '
            + 'p=$(cat "$1"); rm -f "$1"; grep -q -e --daemon "/proc/$p/cmdline" && kill -TERM "$p" && exit; fi; '
            + '[ -z "$2" ] || kill -TERM "$(cat "${XDG_CONFIG_HOME:-$HOME/.config}/cliamp/cliamp.sock.pid")"',
            "lw-music", started, any ? "1" : ""]);
        started = "";
    }
    // Relê a fila inteira do cliamp, 200 faixas por pedido.
    function refreshPlaylist() {
        const pages = [];
        const page = offset => call("queue.list", { offset: offset, limit: 200 }, r => {
            const got = (r.tracks || []).map((t, i) => ({ index: offset + i, path: t.path,
                title: clean(t.title), artist: clean(t.artist), album: clean(t.album) }));
            pages.push(...got);
            if (got.length && pages.length < (r.total || 0)) page(offset + got.length);
            else {
                playlist = pages;
                playlistLoaded = true;
                if (pendingResume) { const saved = pendingResume; pendingResume = null; resumeNow(saved); }
            }
        });
        page(0);
    }

    // ---- system volume --------------------------------------------------------
    // `pactl subscribe` reports every sink change (Super+=, the OSD, other apps):
    // re-read the default sink then, never on a timer.
    Process {
        id: sinkRead
        command: ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"]
        running: root.systemVolume
        stdout: StdioCollector {
            onStreamFinished: {
                const m = /Volume:\s*([\d.]+)(\s*\[MUTED\])?/.exec(text);
                if (m) { root.sinkVolume = parseFloat(m[1]); root.sinkMuted = !!m[2]; }
            }
        }
    }
    Process {
        id: sinkEvents
        command: ["pactl", "subscribe"]
        running: root.systemVolume
        stdout: SplitParser {
            onRead: line => { if (/ on (sink|server) #/.test(line)) sinkDebounce.restart(); }
        }
        onExited: sinkRestart.restart()
    }
    Timer { id: sinkDebounce; interval: 40; onTriggered: if (!sinkRead.running) sinkRead.running = true }
    Timer { id: sinkRestart; interval: 2000; onTriggered: if (root.systemVolume) { sinkEvents.running = true; sinkRead.running = true; } }

    // ---- state stream -------------------------------------------------------
    property int playlistRevision: -1
    // Recebe um novo estado do cliamp e atualiza todas as propriedades.
    function accept(snap) {
        const wasOnline = online;
        const before = track ? track.path : "";
        snapshot = snap;
        online = true;
        if (!wasOnline) stopped = false;
        connecting = false;
        lastError = "";
        position = snap.position || 0;
        stamp = Date.now();
        const now = snap.track ? snap.track.path : "";
        if (now !== before) {
            artUrl = "";
            if (now) { artDelay.restart(); requestInfo(now); }
        }
        if (snap.playlist_revision !== playlistRevision || !wasOnline) {
            playlistRevision = snap.playlist_revision;
            refreshPlaylist();
        }
        changed();
    }
    property double stamp: 0

    Process {
        id: events
        command: [root.bin, "remote", "events", "runtime.state"]
        running: true
        // A binary that cannot start never reports an exit: notice it here.
        onRunningChanged: if (!running && !root.online) notStarted.restart()
        stdout: SplitParser {
            onRead: line => {
                let event;
                try { event = JSON.parse(line); } catch (error) { return; }
                if (event.event === "runtime.state" && event.data) root.accept(event.data);
            }
        }
        stderr: StdioCollector { id: eventsErr }
        onExited: code => {
            root.online = false;
            root.connecting = false;
            root.lastError = eventsErr.text.trim() || "event stream exited (" + code + ")";
            retry.restart();
        }
    }
    Timer {
        id: notStarted
        interval: 300
        onTriggered: {
            if (events.running || retry.running) return;
            root.online = false;
            root.connecting = false;
            root.lastError = "comando cliamp não encontrado (" + root.bin + ")";
            retry.restart();
        }
    }
    // START gave cliamp a few seconds and it is still not answering.
    Timer {
        id: startWatch
        interval: 8000
        onTriggered: if (!root.online) root.failed("start", root.lastError || "o cliamp não respondeu")
    }
    // 0.4 s, then up to 5 s between attempts while cliamp is away.
    Timer {
        id: retry
        interval: 400
        onTriggered: {
            interval = Math.min(5000, interval * 2);
            events.running = true;
        }
    }
    onOnlineChanged: if (online) retry.interval = 400

    // The position moves on its own between snapshots.
    Timer {
        interval: 250
        repeat: true
        running: root.playing
        onTriggered: {
            const now = Date.now();
            root.position = Math.min(root.duration > 0 ? root.duration : Infinity, root.position + (now - root.stamp) / 1000 * (root.snapshot.speed || 1));
            root.stamp = now;
        }
    }
    // Events carry no position ticks: resync now and then.
    Timer {
        interval: 5000
        repeat: true
        running: root.online && root.playing
        onTriggered: root.call("runtime.snapshot", {}, r => { if (r && r.snapshot) root.accept(r.snapshot); })
    }

    Timer { id: artDelay; interval: 300; onTriggered: if (!art.running) art.running = true }
    Process {
        id: art
        command: ["playerctl", "-p", "cliamp", "metadata", "mpris:artUrl"]
        stdout: StdioCollector { onStreamFinished: root.artUrl = text.trim() }
    }

    Component {
        id: prober
        Process {
            id: probe
            property string path
            command: ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", "-select_streams", "a:0", path]
            stdout: StdioCollector { id: probed }
            onExited: {
                let d = {};
                try { d = JSON.parse(probed.text); } catch (error) {}
                const a = (d.streams || [])[0] || {}, f = d.format || {};
                const next = Object.assign({}, root.infos);
                next[probe.path] = {
                    codec: String(a.codec_name || "").toUpperCase(),
                    rate: parseInt(a.sample_rate) || 0,
                    bitrate: parseInt(a.bit_rate || f.bit_rate) || 0,
                    channels: parseInt(a.channels) || 0,
                    duration: parseFloat(f.duration || a.duration) || 0
                };
                root.infos = next;
                root.infoRunning--;
                root.pumpInfo();
                probe.destroy();
            }
        }
    }

    Component {
        id: caller
        Process {
            id: proc
            property string op
            property var params
            property var done
            property int limit: 4000
            function start() {
                command = [root.bin, "remote", "call", op, "--params", JSON.stringify(params), "--wait"];
                running = true;
                guard.start();
            }
            stdout: StdioCollector { id: out }
            stderr: StdioCollector { id: err }
            onExited: code => {
                guard.stop();
                let reply = null;
                try { reply = JSON.parse(out.text); } catch (error) {}
                const job = reply && reply.job;
                const ok = code === 0 && reply && reply.ok !== false && (!job || job.state === "succeeded");
                if (ok) {
                    if (proc.done) proc.done(job ? job.result || {} : reply.result || reply);
                } else {
                    const e = (job && job.error) || (reply && reply.error);
                    const message = (e && (e.message || e.code || (typeof e === "string" ? e : JSON.stringify(e))))
                        || err.text.trim() || op + " failed (" + code + ")";
                    root.lastError = String(message);
                    root.failed(op, String(message));
                }
                proc.destroy();
            }
            // Never wait on cliamp for long.
            property Timer guard: Timer {
                interval: proc.limit
                onTriggered: {
                    // Never started (binary missing) or hung: report it either way.
                    root.failed(proc.op, proc.running ? "o cliamp não respondeu em " + Math.round(proc.limit / 1000) + " s" : "comando cliamp não encontrado (" + root.bin + ")");
                    if (proc.running) proc.signal(9); else proc.destroy();
                }
            }
        }
    }
}
