// OnlineScreen.qml — tela ONLINE (MÚSICA): busca no YouTube (yt-dlp) e no SoundCloud (cliamp).
// / busca, Tab troca a fonte, Enter toca agora, a põe como próxima.
import QtQuick
import Quickshell.Io
import qs
import qs.components

// LW // ONLINE: YouTube through yt-dlp (`ytsearch`, no account) plus cliamp's own
// searchable online providers (SoundCloud with `[soundcloud] enabled = true`, YouTube with
// an account…, whatever `provider.list` says) through its v2 IPC. ⏎ plays the result now,
// `a` puts it next in the queue; cliamp resolves YouTube links with yt-dlp itself.
Item {
    id: root

    property Item keyTarget: null
    property string title: ""
    readonly property var hints: [["/", "buscar"], ["tab", "fonte"], ["↑↓", "move"], ["⏎", "tocar"], ["a", "próxima"]]

    // Local files and radio have their own tabs; "cliamp" is its own radio; podcast results
    // are whole shows, not tracks.
    readonly property var skip: ["local", "radio", "cliamp", "podcast"]
    readonly property var order: ["ytdlp", "soundcloud", "ytmusic", "yt", "youtube", "bandcamp", "mixcloud"]
    readonly property var names: ({ ytdlp: "YouTube", yt: "YouTube (conta)", youtube: "YouTube (conta)", ytmusic: "YT Music", soundcloud: "SoundCloud" })
    // YouTube without cliamp's account-based provider: yt-dlp searches, cliamp plays the link.
    property bool hasYtdlp: false
    property var providers: []
    property string provider: ""
    property bool listed: false

    property var results: []
    property bool searching: false
    property string error: ""
    property string lastQuery: ""
    property int seq: 0
    property int cursor: 0
    readonly property var selected: results[cursor] || null

    // Ordem das fontes na lista.
    function rank(key) { const i = order.indexOf(key); return i < 0 ? order.length : i; }
    // Pergunta ao cliamp quais fontes online existem.
    function loadProviders() {
        if (!Music.online) return;
        Music.call("provider.list", {}, result => {
            const list = (result.providers || []).filter(p => p.searchable && skip.indexOf(p.key) < 0)
                .concat(hasYtdlp ? [{ key: "ytdlp", name: "YouTube" }] : [])
                .sort((a, b) => rank(a.key) - rank(b.key));
            providers = list;
            listed = true;
            if (!list.some(p => p.key === provider)) provider = list.length ? list[0].key : "";
        });
    }
    // Faz a busca na fonte escolhida.
    function search() {
        const query = box.text.trim();
        if (!query || !provider) return;
        error = "";
        searching = true;
        lastQuery = query;
        results = [];             // never show one source's results under another's name
        const mine = ++seq;
        if (provider === "ytdlp") {
            ytSearch.mine = mine;
            ytSearch.command = ["yt-dlp", "--flat-playlist", "--no-warnings", "-J", "ytsearch25:" + query];
            ytSearch.running = true;
            ytGuard.restart();
            return;
        }
        Music.call("provider.search", { provider: provider, query: query, limit: 30 }, result => {
            if (mine !== seq) return;          // a newer search replaced this one
            searching = false;
            results = result.tracks || [];
            cursor = 0;
            view.positionViewAtBeginning();
        }, 30000);
    }
    // Passa para a próxima fonte (Tab).
    function cycleProvider() {
        if (providers.length < 2) return;
        const i = providers.findIndex(p => p.key === provider);
        provider = providers[(i + 1) % providers.length].key;
        if (lastQuery) search();
    }
    // "Artista — Título" de um resultado.
    function label(track) { return [track.artist, track.title].filter(x => x).join(" — ") || track.path; }
    // Toca um resultado agora.
    function play(track) {
        if (!track) return;
        Music.playTrack(track);
        Status.say("[ ▶ ] " + label(track), Theme.ok);
    }
    // Põe um resultado como próxima faixa.
    function queueNext(track) {
        if (!track) return;
        Music.queueTrack(track);
        Status.say("[ + ] próxima: " + label(track), Theme.accent);
    }
    // Segundos → "m:ss".
    function duration(seconds) {
        const s = Math.round(Number(seconds) || 0);
        if (s <= 0) return "—";
        return (s >= 3600 ? Math.floor(s / 3600) + ":" + String(Math.floor(s / 60) % 60).padStart(2, "0") : Math.floor(s / 60)) + ":" + String(s % 60).padStart(2, "0");
    }
    // Move a seleção.
    function moveCursor(step) {
        if (!results.length) return;
        cursor = Math.max(0, Math.min(results.length - 1, cursor + step));
        view.positionViewAtIndex(cursor, ListView.Contain);
    }
    // Teclas da tela.
    function handleKey(event) {
        const t = event.text;
        if (event.key === Qt.Key_Slash) { box.focusInput(); return true; }
        if (event.key === Qt.Key_Tab) { cycleProvider(); return true; }
        if (event.key === Qt.Key_Down) { moveCursor(1); return true; }
        if (event.key === Qt.Key_Up) { moveCursor(-1); return true; }
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { play(selected); return true; }
        if (t === "a") { queueNext(selected); return true; }
        return false;
    }
    // Test hook (music IPC `query`).
    function query(text) { box.text = text; search(); }

    Process {
        id: ytCheck
        command: ["sh", "-c", "command -v yt-dlp"]
        running: true
        onExited: code => { root.hasYtdlp = code === 0; root.listed = false; root.loadProviders(); }
    }
    Process {
        id: ytSearch
        property int mine: 0
        stdout: StdioCollector { id: ytOut }
        stderr: StdioCollector { id: ytErr }
        onExited: code => {
            ytGuard.stop();
            if (mine !== root.seq) return;
            root.searching = false;
            let data = null;
            try { data = JSON.parse(ytOut.text); } catch (error) {}
            if (code !== 0 || !data) {
                root.error = (ytErr.text.trim().split("\n").pop() || "yt-dlp falhou (" + code + ")");
                root.results = [];
                return;
            }
            root.results = (data.entries || []).filter(e => e && e.url).map(e => ({
                title: e.title || e.url, artist: e.channel || e.uploader || "",
                path: e.url, duration_secs: e.duration || 0, stream: true }));
            root.cursor = 0;
            view.positionViewAtBeginning();
        }
    }
    Timer {
        id: ytGuard
        interval: 30000
        onTriggered: if (ytSearch.running) { ytSearch.signal(15); root.searching = false; root.error = "o YouTube não respondeu em 30 s"; }
    }
    Component.onCompleted: loadProviders()
    Connections {
        target: Music
        function onOnlineChanged() { if (Music.online && !root.listed) root.loadProviders(); }
        function onFailed(op, message) {
            if (op !== "provider.search") return;
            root.searching = false;
            root.error = message;
            root.results = [];
        }
    }

    // ================= SEARCH =================
    Row {
        id: top
        width: parent.width
        spacing: 10
        SearchBox {
            id: box
            width: parent.width - goButton.width - 10
            placeholder: "buscar música online"
            keyTarget: root.keyTarget
            onAccepted: root.search()
        }
        AccentButton { id: goButton; label: root.searching ? "BUSCANDO…" : "SEARCH ⏎"; enabledState: !!root.provider; onClicked: root.search() }
    }
    Flow {
        id: chips
        anchors.top: top.bottom
        anchors.topMargin: 10
        width: parent.width
        spacing: 6
        Repeater {
            model: root.providers
            Chip {
                required property var modelData
                label: root.names[modelData.key] || modelData.name
                on: root.provider === modelData.key
                onClicked: { root.provider = modelData.key; if (root.lastQuery) root.search(); root.keyTarget.forceActiveFocus(); }
            }
        }
    }

    // ================= RESULTS =================
    Rectangle {
        id: table
        anchors.top: chips.bottom
        anchors.topMargin: 10
        anchors.bottom: foot.top
        anchors.bottomMargin: 10
        width: parent.width
        color: "transparent"
        border.width: 1
        border.color: Theme.line
        clip: true

        component Line: Item {
            id: line
            property bool head: false
            property var t: null
            width: parent ? parent.width : 0
            height: 26
            readonly property int artistW: Math.min(260, width * 0.28)
            RiceText {
                x: 10
                width: parent.width - 10 - line.artistW - 70 - 30
                anchors.verticalCenter: parent.verticalCenter
                elide: Text.ElideRight
                text: line.head ? "TÍTULO" : line.t.title || line.t.path
                color: line.head ? Theme.faint : Theme.fg
                font.pixelSize: line.head ? Theme.small : Theme.fontSize
                font.letterSpacing: line.head ? 1.5 : 0
            }
            RiceText {
                x: parent.width - line.artistW - 70 - 20
                width: line.artistW
                anchors.verticalCenter: parent.verticalCenter
                elide: Text.ElideRight
                text: line.head ? "ARTISTA" : line.t.artist || "—"
                color: line.head ? Theme.faint : Theme.dim
                font.pixelSize: line.head ? Theme.small : Theme.fontSize
                font.letterSpacing: line.head ? 1.5 : 0
            }
            RiceText {
                x: parent.width - 70 - 10
                width: 70
                anchors.verticalCenter: parent.verticalCenter
                horizontalAlignment: Text.AlignRight
                text: line.head ? "DURAÇÃO" : root.duration(line.t.duration_secs || line.t.duration)
                color: Theme.faint
                font.pixelSize: line.head ? Theme.small : Theme.fontSize
                font.letterSpacing: line.head ? 1.5 : 0
            }
        }

        ListView {
            id: view
            anchors.fill: parent
            anchors.margins: 1
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: root.results
            headerPositioning: ListView.OverlayHeader
            header: Rectangle {
                width: view.width
                height: 26
                z: 2
                color: Theme.base
                Line { head: true }
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
            }
            delegate: Item {
                id: row
                required property var modelData
                required property int index
                readonly property bool chosen: index === root.cursor
                readonly property bool playing: Music.track !== null && Music.track.path === modelData.path
                width: view.width
                height: 26
                Rectangle {
                    anchors.fill: parent
                    color: row.playing ? Theme.accentA : row.chosen ? Qt.alpha(Theme.fg, 0.04) : rowMouse.containsMouse ? Qt.alpha(Theme.fg, 0.025) : "transparent"
                    Rectangle { width: 2; height: parent.height; color: row.playing ? Theme.accent : row.chosen ? Theme.line2 : "transparent" }
                }
                Line { t: row.modelData }
                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: { root.cursor = row.index; root.keyTarget.forceActiveFocus(); }
                    onDoubleClicked: root.play(row.modelData)
                }
            }
            RiceText {
                anchors.centerIn: parent
                width: parent.width - 60
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                visible: root.results.length === 0
                text: !Music.online ? "[ -- ] cliamp offline — ⏎ na aba NOW PLAYING liga"
                    : root.listed && !root.providers.length ? "[ !! ] nenhuma fonte online — instale o yt-dlp (sudo pacman -S yt-dlp) e reabra o LW // MUSIC"
                    : root.searching ? "[ .. ] buscando em " + (root.names[root.provider] || root.provider) + "…"
                    : root.error ? "[ !! ] " + root.error
                    : root.lastQuery ? "nada encontrado" : "/ para buscar · tab troca a fonte"
                color: root.error || (root.listed && !root.providers.length) ? Theme.red : root.searching ? Theme.accent : Theme.faint
            }
        }
    }

    // ================= FOOTER =================
    Item {
        id: foot
        anchors.bottom: parent.bottom
        width: parent.width
        height: 32
        Rectangle { width: parent.width; height: 1; color: Theme.line }
        RiceText {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 4
            text: root.results.length ? root.results.length + " resultados · " + (root.names[root.provider] || root.provider) + (root.provider === "ytdlp" ? " · via yt-dlp" : " · via cliamp") : ""
            color: Theme.faint
            font.pixelSize: Theme.small
        }
        Row {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            spacing: 8
            AccentButton { ghost: true; label: "PRÓXIMA (a)"; enabledState: !!root.selected; onClicked: root.queueNext(root.selected) }
            AccentButton { label: "TOCAR ⏎"; enabledState: !!root.selected; onClicked: root.play(root.selected) }
        }
    }
}
