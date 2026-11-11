pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// The LW // GAMES data: ~/.local/share/lw/games.json, read here and written only through
// extras/games.py (one lock, atomic writes), so the window and the helper never race.
Singleton {
    id: root

    readonly property string dataPath: (Quickshell.env("XDG_DATA_HOME") || Quickshell.env("HOME") + "/.local/share") + "/lw/games.json"
    readonly property var helper: ["/usr/bin/python3", Quickshell.shellDir + "/../extras/games.py"]
    readonly property var statuses: ["want", "playing", "done", "dropped"]
    readonly property var statusLabel: ({ want: "quero jogar", playing: "jogando", done: "zerado", dropped: "largado" })

    property var games: []
    property bool loaded: false
    property bool scanning: false
    property var lastScan: null              // {total, new, missing, errors}

    signal failed(string message)
    signal changed(string message)

    function statusColor(status) {
        return status === "want" ? Theme.blue : status === "playing" ? Theme.accent : status === "done" ? Theme.ok : Theme.faint;
    }
    function byId(id) { return games.find(g => g.id === id) || null; }

    // ---- numbers --------------------------------------------------------------
    // Steam keeps its own playtime; the larger of the two counts, never both.
    function hoursOf(g) { return Math.max(g.hours || 0, g.hours_source || 0); }
    readonly property real totalHours: games.reduce((sum, g) => sum + hoursOf(g), 0)
    readonly property int doneCount: games.filter(g => g.status === "done").length
    // Weekly pace: my session hours of the last four weeks, divided by four.
    readonly property real weeklyPace: {
        const since = Date.now() / 1000 - 28 * 86400;
        let hours = 0;
        for (const g of games) for (const s of g.sessions || []) if (s.end && s.start >= since) hours += (s.end - s.start) / 3600;
        return hours / 4;
    }
    readonly property real queueHours: games.filter(g => g.status === "want" && !g.missing).reduce((sum, g) => sum + (g.est_hours || 0), 0)
    readonly property string queueWeeks: weeklyPace > 0 && queueHours > 0 ? String(Math.ceil(queueHours / weeklyPace)) : "—"
    // CONTINUE: the "playing" game played most recently.
    readonly property var continueGame: games.filter(g => g.status === "playing" && !g.missing)
                                             .sort((a, b) => (b.last_played || 0) - (a.last_played || 0))[0] || null

    // ---- commands ------------------------------------------------------------------
    function run(args, done) {
        const proc = runner.createObject(root, { args: args, done: done || null });
        proc.running = true;
    }
    function scan() {
        if (scanning) return;
        scanning = true;
        run(["scan"], (ok, data) => {
            scanning = false;
            if (!ok) { failed(data.error || "scan falhou"); return; }
            lastScan = data;
            const broken = Object.keys(data.errors || {});
            changed("scan: " + data.total + " jogos · " + data.new + " novos" + (data.missing ? " · " + data.missing + " sumiram" : "")
                    + (broken.length ? " · erro em " + broken.join(", ") : ""));
        });
    }
    function set(id, pairs, message) {
        run(["set", id].concat(pairs), (ok, data) => ok ? (message ? changed(message) : null) : failed(data.error));
    }
    function add(exe, prefix, title) {
        const args = ["add", "--exe", exe];
        if (prefix) args.push("--prefix", prefix);
        if (title) args.push("--title", title);
        run(args, (ok, data) => ok ? changed("[ + ] " + data.added.title + " na biblioteca") : failed(data.error));
    }
    function remove(id) {
        const g = byId(id);
        run(["remove", id], (ok, data) => ok ? changed("[ - ] " + (g ? g.title : id) + " removido") : failed(data.error));
    }

    // The file is replaced atomically by the helper: reload on every change.
    FileView {
        id: file
        path: root.dataPath
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            try { root.games = JSON.parse(text()).games || []; } catch (error) { root.games = []; }
            root.loaded = true;
        }
        onLoadFailed: root.loaded = true
    }

    Component {
        id: runner
        Process {
            id: proc
            property var args: []
            property var done: null
            command: root.helper.concat(args)
            stdout: StdioCollector { id: out }
            onExited: code => {
                let data = {};
                try { data = JSON.parse(out.text); } catch (error) { data = { error: "resposta inválida do games.py" }; }
                if (proc.done) proc.done(code === 0 && data.ok, data);
                proc.destroy();
            }
        }
    }
}
