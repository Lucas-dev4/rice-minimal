pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

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
    readonly property string title: !track ? "" : track.title || fileName(track.path)
    readonly property string artist: track ? track.artist || "" : ""
    readonly property string album: track ? track.album || "" : ""
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
    readonly property int volumePercent: Math.round(100 * Math.max(0, Math.min(1, (volumeDb - volumeMin) / (6 - volumeMin))))
    property real mutedFrom: NaN          // dB to go back to; NaN = not muted
    readonly property bool muted: !isNaN(mutedFrom)
    readonly property var eqFrequencies: [70, 180, 320, 600, 1000, 3000, 6000, 12000, 14000, 16000]

    // Per-file details cliamp does not give: {codec, rate, bitrate, channels, duration}.
    // Filled by ffprobe for local files, once per path.
    property var infos: ({})
    property var probing: ({})
    // At most 4 ffprobe at a time; the rest wait in line.
    property var infoQueue: []
    property int infoRunning: 0
    function requestInfo(path) {
        if (!path || sourceOf(path) !== "local" || infos[path] || probing[path]) return;
        probing[path] = true;
        infoQueue.push(path);
        pumpInfo();
    }
    function pumpInfo() {
        while (infoRunning < 4 && infoQueue.length) {
            infoRunning++;
            prober.createObject(root, { path: infoQueue.shift() }).running = true;
        }
    }
    // Cover art, only when cliamp's MPRIS metadata has one (mpris:artUrl).
    property string artUrl: ""

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
    function fileName(path) { return String(path || "").split("/").pop().replace(/\.[^.]+$/, ""); }

    // ---- commands -----------------------------------------------------------
    // op: a v2 operation; params: object. done(result) on success.
    function call(op, params, done) {
        const proc = caller.createObject(root, { op: op, params: params || {}, done: done || null });
        proc.start();
    }
    function toggle() { call("toggle"); }
    function next() { call("next"); }
    // Like most players: back to the start when past 3 s, otherwise the previous track.
    function previous() { position > 3 && seekable ? seekTo(0) : call("prev"); }
    function stop() { call("stop"); }
    function seekTo(seconds) {
        position = Math.max(0, Math.min(duration || seconds, seconds));
        call("seek.absolute", { value: position });
    }
    function seekBy(seconds) { if (seekable) seekTo(position + seconds); }
    function setVolumePercent(percent) {
        const p = Math.max(0, Math.min(100, percent));
        mutedFrom = NaN;
        call("volume", { value: Math.round((volumeMin + (6 - volumeMin) * p / 100) * 10) / 10 });
    }
    function volumeStep(percent) { setVolumePercent(volumePercent + percent); }
    // cliamp has no mute: remember the level and drop to the floor.
    function toggleMute() {
        if (muted) { const back = mutedFrom; mutedFrom = NaN; call("volume", { value: back }); }
        else { mutedFrom = volumeDb; call("volume", { value: volumeMin }); }
    }
    function setShuffle(on) { call("shuffle", { name: on ? "on" : "off" }); }
    function cycleRepeat() { call("repeat", { name: repeat === "off" ? "all" : repeat === "all" ? "one" : "off" }); }
    function playIndex(index) { call("queue.play", { index: index }); }
    function moveTrack(index, to) { call("queue.move", { index: index, to: to }, () => refreshPlaylist()); }
    function removeTrack(index) { call("queue.remove", { index: index }, () => refreshPlaylist()); }
    function addPath(path) { call("queue", { path: path }, () => refreshPlaylist()); }
    function playUrl(url) { call("url.load", { path: url, play: true }); }
    function setBand(band, dB) { call("eq", { band: band, value: Math.max(-12, Math.min(12, Math.round(dB))) }); }
    function setPreset(name) { call("eq", { name: name }); }

    // Starts cliamp headless; it resumes its last session on its own.
    function start() {
        if (online) return;
        Quickshell.execDetached(["setsid", "cliamp", "--daemon"]);
        connecting = true;
        retry.interval = 400;
        retry.restart();
    }
    function refreshPlaylist() {
        call("queue.list", { limit: 10000 }, r => {
            playlist = (r.tracks || []).map((t, i) => Object.assign({ index: i }, t));
            playlistLoaded = true;
        });
    }

    // ---- state stream -------------------------------------------------------
    property int playlistRevision: -1
    function accept(snap) {
        const wasOnline = online;
        const before = track ? track.path : "";
        snapshot = snap;
        online = true;
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
        command: ["cliamp", "remote", "events", "runtime.state"]
        running: true
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
            function start() {
                command = ["cliamp", "remote", "call", op, "--params", JSON.stringify(params), "--wait"];
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
                interval: 4000
                onTriggered: {
                    root.failed(proc.op, "cliamp did not answer in 4 s");
                    proc.signal(9);
                }
            }
        }
    }
}
