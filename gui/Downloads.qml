// Downloads.qml — singleton dos downloads de música (yt-dlp) da aba ONLINE.
// Fica fora da tela para o download continuar quando você troca de aba; um de cada vez, o resto
// espera na fila. Quem baixa é extras/ytdl.py (MP3 com tags e capa em ~/Músicas/Downloads).
// Depois de cada download, extras/organize.py manda as músicas para a pasta de gênero do
// artista; as de artista novo ficam em `unknown` até você escolher a pasta (moveTo).
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// One download at a time through extras/ytdl.py, which streams JSON events; the rest wait.
Singleton {
    id: root

    property var queue: []                 // [{url, playlist, label}] waiting
    property var job: null                 // the one running
    property string title: ""              // song being downloaded now
    property int index: 0
    property int total: 0
    property real percent: 0
    property int finished: 0               // since the LW opened, for the footer
    readonly property bool active: job !== null
    readonly property string dest: "~/Músicas/Downloads"
    signal ended(bool ok)                  // a job ended (the library may rescan)
    // Organização: músicas em Downloads sem pasta conhecida e as pastas de gênero.
    property var unknown: []               // [{file, artist, title, name}]
    property var folders: []
    property string summary: ""            // resumo do download, completado pela organização
    readonly property string organizer: Quickshell.shellDir + "/../extras/organize.py"

    // Põe um download na fila (link de música ou de playlist).
    function add(url, playlist, label) {
        if (!url) return;
        const same = j => j && j.url === url && j.playlist === !!playlist;
        if (same(job) || queue.some(same)) { Status.say("[ -- ] já está na fila: " + label, Theme.dim); return; }
        queue = queue.concat([{ url: url, playlist: !!playlist, label: label || url }]);
        Status.say("[ ↓ ] na fila: " + (label || url), Theme.accent);
        next();
    }
    // Cancela o download atual (a fila segue).
    function cancel() {
        if (proc.running) proc.signal(15);
    }
    // Começa o próximo da fila.
    function next() {
        if (job || !queue.length || organizeProc.running) return;
        job = queue[0];
        queue = queue.slice(1);
        title = job.label;
        index = 0; total = 0; percent = 0;
        proc.command = ["/usr/bin/python3", Quickshell.shellDir + "/../extras/ytdl.py", "download", job.url]
            .concat(job.playlist ? ["--playlist"] : []);
        proc.running = true;
    }
    // Um evento do ytdl.py.
    function onEvent(e) {
        if (e.event === "item") { title = e.title; index = e.index; total = e.total; percent = 0; }
        else if (e.event === "progress") percent = e.percent;
        else if (e.event === "done") finished++;
        else if (e.event === "end") {
            const label = job ? job.label : "";
            const parts = [];
            if (e.done) parts.push(e.done + (e.done === 1 ? " baixada" : " baixadas"));
            if (e.skipped) parts.push(e.skipped + " já tinha");
            if (e.errors) parts.push(e.errors + (e.errors === 1 ? " erro" : " erros"));
            if (e.cancelled) Status.say("[ -- ] download cancelado: " + label, Theme.dim);
            else if (!e.ok) Status.say("[ !! ] " + (parts.length ? parts.join(" · ") + " — " : "") + (e.message || "falhou"), Theme.red);
            root.ended(!!e.ok);
            // O que baixou vai para a pasta do artista (o resumo sai quando a organização termina).
            if (e.done) organize(e.ok ? parts.join(" · ") : "");
            else if (e.ok) Status.say("[ ↓ ] " + (parts.join(" · ") || "nada novo"), Theme.ok);
        }
    }
    // Manda o que está em Downloads para as pastas de gênero (artistas conhecidos).
    // Sem resumo, é a checagem silenciosa (aba ONLINE abrindo, depois de mover uma música):
    // essa espera o download acabar, para não mexer num arquivo que o yt-dlp ainda escreve.
    function organize(summaryText) {
        if (organizeProc.running || (active && summaryText === undefined)) return;
        summary = summaryText || "";
        organizeProc.running = true;
    }
    // Move uma música de artista novo para a pasta escolhida; dali em diante o artista é conhecido.
    function moveTo(file, folder) {
        if (moveProc.running) return;
        moveProc.command = ["/usr/bin/python3", organizer, "move", file, folder];
        moveProc.running = true;
    }
    // Junta as músicas movidas por pasta: "2 → K-Pop · 1 → Funk".
    function byFolder(moved) {
        const count = {};
        for (const m of moved) count[m.folder] = (count[m.folder] || 0) + 1;
        return Object.keys(count).map(f => count[f] + " → " + f).join(" · ");
    }

    Process {
        id: organizeProc
        command: ["/usr/bin/python3", root.organizer, "apply"]
        // O próximo download da fila espera a organização terminar.
        onExited: root.next()
        stdout: StdioCollector {
            onStreamFinished: {
                let r = null;
                try { r = JSON.parse(text); } catch (error) {}
                if (!r || !r.ok) { if (root.summary) Status.say("[ !! ] organizar: " + (r && r.error || "falhou"), Theme.red); return; }
                root.unknown = r.unknown;
                root.folders = r.folders;
                const parts = [];
                if (r.moved.length) parts.push(root.byFolder(r.moved));
                if (r.skipped.length) parts.push(r.skipped.length + " repetida(s) ficaram em Downloads");
                if (r.unknown.length) parts.push(r.unknown.length + " de artista novo: g escolhe a pasta");
                if (root.summary || r.moved.length)
                    Status.say("[ ↓ ] " + [root.summary].concat(parts).filter(x => x).join(" · "), r.unknown.length ? Theme.accent : Theme.ok);
                root.summary = "";
            }
        }
    }
    Process {
        id: moveProc
        stdout: StdioCollector {
            onStreamFinished: {
                let r = null;
                try { r = JSON.parse(text); } catch (error) {}
                if (!r || !r.ok) { Status.say("[ !! ] não moveu: " + (r && r.error || "falhou"), Theme.red); return; }
                const m = r.moved[0];
                Status.say("[ → ] " + m.name + " → " + m.folder, Theme.ok);
                // Outras músicas do mesmo artista agora têm pasta: organiza de novo.
                root.organize();
            }
        }
    }
    Process {
        id: proc
        stdout: SplitParser { onRead: line => { try { root.onEvent(JSON.parse(line)); } catch (error) {} } }
        onExited: {
            root.job = null;
            root.title = "";
            if (!organizeProc.running) root.next();
        }
    }
}
