// Games.qml — singleton com a biblioteca de jogos para todas as telas de JOGOS.
// Lê ~/.local/share/lw/games.json e chama extras/games.py para qualquer mudança (nunca escreve o JSON direto).
// As telas usam: games (lista), column(status), launch(id), set(id, ...), scan(), meta()...
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
    readonly property var lw: ["/usr/bin/python3", Quickshell.shellDir + "/../extras/rice.py"]
    readonly property var statuses: ["want", "playing", "done", "dropped"]
    readonly property var statusLabel: ({ want: "quero jogar", playing: "jogando", done: "zerado", dropped: "largado" })

    property var games: []
    property var doc: ({})
    property bool loaded: false
    // Sessions live in games.json (written by the games.py watcher, even with LW closed).
    readonly property var session: doc.open_session || null
    readonly property var sessionGame: session ? byId(session.id) : null
    property double now: Date.now()
    readonly property int sessionSeconds: session ? Math.max(0, Math.floor(now / 1000 - session.start)) : 0
    // The launch in progress, for the launch screen: {id, title, wrappers, command, ok, error, detected}.
    property var launching: null
    signal sessionEnded(string title, real hours)
    property bool scanning: false
    property var lastScan: null              // {total, new, missing, errors, played_pending}
    // Desempenho no meu PC (lw compat check): título normalizado → {k: ok|lim|no|na, w: motivo}.
    // Só um aviso nas recomendações; jogo sem requisito conhecido não aparece aqui.
    property var compat: ({})

    signal failed(string message)
    signal changed(string message)

    // Cor de cada status: quero jogar (azul), jogando (destaque), zerado (verde), largado (apagado).
    function statusColor(status) {
        return status === "want" ? Theme.blue : status === "playing" ? Theme.accent : status === "done" ? Theme.ok : Theme.faint;
    }
    // O jogo com esse id, ou null.
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

    // Título normalizado para comparar nomes (minúsculas, só letras e números).
    function norm(t) { return String(t || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim(); }
    // Aviso de desempenho de um jogo pelo título: {k, w} se não roda bem, senão null.
    function warnOf(title) {
        const c = compat[norm(title)];
        return c && c.k !== "ok" ? c : null;
    }

    // ---- commands ------------------------------------------------------------------
    // base: o comando (games.py por padrão; lw para o compat).
    function run(args, done, base) {
        const proc = runner.createObject(root, { args: args, done: done || null, base: base || helper });
        proc.running = true;
    }
    // Lê o hardware e avalia os jogos com requisito conhecido (uma vez por abertura de JOGOS).
    function loadCompat() {
        run(["compat", "check", "--json"], (ok, data) => {
            if (!ok) return;
            const map = {};
            for (const g of data.data.games) map[norm(g.n)] = { k: g.k, w: g.w };
            compat = map;
        }, lw);
    }
    // quiet: the automatic scan on opening only speaks when something changed.
    function scan(quiet) {
        if (scanning) return;
        scanning = true;
        run(["scan"], (ok, data) => {
            scanning = false;
            if (!ok) { failed(data.error || "scan falhou"); return; }
            lastScan = data;
            // Then IGDB data for games never looked up (silent without a key).
            if (games.some(g => !g.igdb) || data.played_pending) meta(true);
            loadCompat();
            const broken = Object.keys(data.errors || {});
            if (quiet && !data.new && !broken.length) return;
            changed("scan: " + data.total + " jogos · " + data.new + " novos" + (data.missing ? " · " + data.missing + " sumiram" : "")
                    + (broken.length ? " · erro em " + broken.join(", ") : ""));
        });
    }
    // IGDB: cover and est_hours where empty, plus genres, times and similar games.
    property bool fetchingMeta: false
    // Busca capa/gêneros/duração no IGDB (para todos sem dados ou só para os ids dados).
    function meta(quiet, ids) {
        if (fetchingMeta) return;
        fetchingMeta = true;
        run(["meta"].concat(ids || []), (ok, data) => {
            fetchingMeta = false;
            if (!ok) { if (!quiet) failed(data.error || "IGDB falhou"); return; }
            const played = data.played || { matched: 0, missed: [] };
            if (quiet && !data.matched.length && !played.matched) return;
            changed("IGDB: " + data.matched.length + " jogo(s) com dados" + (data.missed.length ? " · sem par: " + data.missed.join(", ") : "")
                    + (played.matched ? " · " + played.matched + " já jogados" : "") + (played.missed.length ? " · sem par: " + played.missed.join(", ") : ""));
        });
    }
    // Muda campos de um jogo (ex.: ["status=done"]) e mostra a mensagem se der certo.
    function set(id, pairs, message) {
        run(["set", id].concat(pairs), (ok, data) => ok ? (message ? changed(message) : null) : failed(data.error));
    }
    // Adiciona um jogo à mão (executável, prefixo do Wine, nome).
    function add(exe, prefix, title) {
        const args = ["add", "--exe", exe];
        if (prefix) args.push("--prefix", prefix);
        if (title) args.push("--title", title);
        run(args, (ok, data) => ok ? changed("[ + ] " + data.added.title + " na biblioteca") : failed(data.error));
    }
    // Inicia o jogo (games.py launch) e abre a tela de lançamento.
    function launch(id) {
        const g = byId(id);
        if (!g) return;
        if (session && session.id !== id) { failed("já há uma sessão: " + (sessionGame ? sessionGame.title : session.id)); return; }
        if (session && session.id === id) { changed("● " + g.title + " já está rodando"); return; }
        launching = { id: id, title: g.title, source: g.source, gamemode: !!g.gamemode, mangohud: !!g.mangohud,
                      proton: !!g.proton, gamescope: !!g.gamescope, fsr: !!g.fsr,
                      command: "", ok: false, error: "", detected: false };
        run(["launch", id], (ok, data) => {
            if (!launching || launching.id !== id) return;
            launching = Object.assign({}, launching, ok ? { ok: true, command: data.command, tools: data.tools } : { error: data.error || "falha ao lançar" });
            if (!ok) failed(data.error || "falha ao lançar");
        });
    }
    // Pede para o jogo fechar.
    function stop(id) { run(["stop", id], (ok, data) => ok ? changed("■ parando " + ((byId(id) || {}).title || id)) : failed(data.error)); }
    // A session left open (LW closed, reboot): resumed if the game runs, closed otherwise.
    function recover() {
        run(["recover"], (ok, data) => {
            if (ok && data.session === "running") changed("● sessão retomada: " + ((byId(data.id) || {}).title || data.id));
        });
    }
    // Duração curta para mensagens: "+25 min" ou "+1.5 h".
    function hoursText(h) { return h < 0.1 ? "+" + Math.max(1, Math.round(h * 60)) + " min" : "+" + h.toFixed(1).replace(/\.0$/, "") + " h"; }

    // One backlog column in a single write: status and order 1..n for these ids.
    function arrange(status, ids, message) {
        run(["arrange", status].concat(ids), (ok, data) => ok ? (message ? changed(message) : null) : failed(data.error));
    }
    // Games of one status in backlog order (missing ones last).
    function column(status) {
        return games.filter(g => g.status === status)
                    .sort((a, b) => (a.missing - b.missing) || (a.order || 0) - (b.order || 0) || a.title.localeCompare(b.title, "pt"));
    }

    // ---- installers: setup.exe → Wine prefix → library ------------------------------
    // The list comes from `games.py installers`; each install's live state is in games.json.
    property var installers: []
    property var readyGames: []              // Hydra downloads not in the library yet
    property bool findingInstallers: false
    readonly property var installs: doc.installs || ({})
    // Procura instaladores e jogos prontos nas pastas de download.
    function findInstallers() {
        if (findingInstallers) return;
        findingInstallers = true;
        run(["installers"], (ok, data) => {
            findingInstallers = false;
            if (ok) { installers = data.installers; readyGames = data.ready || []; }
            else failed(data.error || "busca de instaladores falhou");
        });
    }
    // Começa a instalar um setup.exe num prefixo novo.
    function install(setup, name) {
        const args = ["install", setup];
        if (name) args.push("--name", name);
        run(args, (ok, data) => {
            if (!ok) { failed(data.error || "a instalação não começou"); return; }
            changed("[ .. ] instalando " + data.install.name + ": siga a janela do instalador");
        });
    }
    // Põe na biblioteca o .exe escolhido de uma instalação concluída.
    function installAdd(setup, exe) {
        run(["install-add", setup, exe], (ok, data) => ok ? changed("[ + ] " + data.added.title + " na biblioteca") : failed(data.error));
    }
    // A ready game: own prefix in ~/Games/<name>, Proton on when umu-run exists.
    function addReady(exe, name) {
        run(["add-ready", exe, "--name", name], (ok, data) => {
            if (!ok) { failed(data.error); return; }
            changed("[ + ] " + data.added.title + " na biblioteca" + (data.added.proton ? " · proton-ge ligado" : ""));
            findInstallers();
        });
    }
    // Apaga o registro de uma instalação (o prefixo fica no disco).
    function installForget(setup) {
        run(["install-forget", setup], (ok, data) => ok ? changed("[ - ] registro da instalação apagado (o prefixo continua)") : failed(data.error));
    }

    // Tira um jogo da biblioteca.
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
            let d = {};
            try { d = JSON.parse(text()); } catch (error) {}
            const before = root.doc;
            root.doc = d;
            root.games = d.games || [];
            // A session that just ended, a launch whose process never showed up.
            if (root.loaded && d.last_session && (!before.last_session || before.last_session.end !== d.last_session.end))
                root.sessionEnded(d.last_session.title, d.last_session.hours);
            if (root.launching) {
                if (d.open_session && d.open_session.id === root.launching.id)
                    root.launching = Object.assign({}, root.launching, { detected: true });
                else if (d.launch_error && d.launch_error.id === root.launching.id && (!before.launch_error || before.launch_error.at !== d.launch_error.at))
                    root.launching = Object.assign({}, root.launching, { error: d.launch_error.error });
            }
            root.loaded = true;
        }
        onLoadFailed: root.loaded = true
    }

    Timer { interval: 1000; repeat: true; running: root.session !== null; onTriggered: root.now = Date.now() }

    Component {
        id: runner
        Process {
            id: proc
            property var args: []
            property var done: null
            property var base: root.helper
            command: base.concat(args)
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
