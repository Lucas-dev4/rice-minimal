// OnlineScreen.qml — tela ONLINE (MÚSICA): busca no YouTube (yt-dlp) e no SoundCloud (cliamp).
// / busca, Tab troca a fonte, Enter toca agora, a põe como próxima. Colar um link (música ou
// playlist) na busca lista o que tem nele; b baixa a música, B a playlist inteira, x cancela.
// O que baixa vai sozinho para a pasta de gênero do artista; g escolhe a pasta de um artista novo.
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
    readonly property var hints: picking ? [["↑↓", "música"], ["←→", "pasta"], ["⏎", "mover"], ["esc", "fechar"]]
        : [["/", "buscar/link"], ["tab", "fonte"], ["⏎", "tocar"], ["a", "próxima"], ["b", "baixar"], ["B", "playlist"]]
            .concat(Downloads.unknown.length ? [["g", "pasta"]] : [])

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
    // Link colado na busca: os resultados vêm dele, e playlist é {title, url} se for uma.
    property bool fromLink: false
    property var playlist: null
    // Escolha de pasta (g): música de artista novo em Downloads e a pasta de gênero marcada.
    property bool picking: false
    property int pickRow: 0
    property int pickFolder: 0
    readonly property var pickFile: Downloads.unknown[pickRow] || null

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
    // Um link (http/https) em vez de texto de busca.
    function isLink(text) { return /^https?:\/\/\S+$/.test(text); }
    // Faz a busca na fonte escolhida (um link sempre vai pelo yt-dlp).
    function search() {
        const query = box.text.trim();
        const link = isLink(query);
        if (!query || !(provider || (link && hasYtdlp))) return;
        error = "";
        searching = true;
        lastQuery = query;
        results = [];             // never show one source's results under another's name
        fromLink = link;
        playlist = null;
        const mine = ++seq;
        if (link || provider === "ytdlp") {
            if (link && !hasYtdlp) { searching = false; error = "links precisam do yt-dlp (sudo pacman -S yt-dlp)"; return; }
            ytSearch.mine = mine;
            ytSearch.link = link ? query : "";
            ytSearch.command = ["yt-dlp", "--flat-playlist", "--no-warnings", "-J", link ? query : "ytsearch25:" + query];
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
    // Baixa um resultado (MP3 em ~/Músicas/Downloads), pelo Downloads.qml.
    function download(track) {
        if (!track) return;
        if (!/^https?:\/\//.test(track.path || "")) { Status.say("[ -- ] esse resultado não tem link para baixar", Theme.dim); return; }
        if (!hasYtdlp) { Status.say("[ !! ] baixar precisa do yt-dlp: sudo pacman -S yt-dlp", Theme.red); return; }
        Downloads.add(track.path, false, label(track));
    }
    // Baixa a playlist inteira do link colado (numa pasta com o nome dela).
    function downloadPlaylist() {
        if (!playlist) { Status.say("[ -- ] cole o link de uma playlist na busca (/) para baixar ela inteira", Theme.dim); return; }
        Downloads.add(playlist.url, true, playlist.title);
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
    // Abre a escolha de pasta para as músicas de artista novo.
    function openPicker() {
        if (!Downloads.unknown.length) { Status.say("[ -- ] nada em Downloads esperando pasta", Theme.dim); return; }
        pickRow = Math.min(pickRow, Downloads.unknown.length - 1);
        picking = true;
    }
    // Teclas da escolha de pasta (todas ficam nela enquanto está aberta).
    function pickKey(event) {
        const n = Downloads.folders.length;
        if (event.key === Qt.Key_Escape || event.text === "g") picking = false;
        else if (event.key === Qt.Key_Down) pickRow = Math.min(Downloads.unknown.length - 1, pickRow + 1);
        else if (event.key === Qt.Key_Up) pickRow = Math.max(0, pickRow - 1);
        else if (event.key === Qt.Key_Right && n) pickFolder = (pickFolder + 1) % n;
        else if (event.key === Qt.Key_Left && n) pickFolder = (pickFolder + n - 1) % n;
        else if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && pickFile && n)
            Downloads.moveTo(pickFile.file, Downloads.folders[pickFolder]);
        return true;
    }
    // Teclas da tela.
    function handleKey(event) {
        if (picking) return pickKey(event);
        const t = event.text;
        if (event.key === Qt.Key_Slash) { box.focusInput(); return true; }
        if (event.key === Qt.Key_Tab) { cycleProvider(); return true; }
        if (event.key === Qt.Key_Down) { moveCursor(1); return true; }
        if (event.key === Qt.Key_Up) { moveCursor(-1); return true; }
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { play(selected); return true; }
        if (t === "a") { queueNext(selected); return true; }
        if (t === "b") { download(selected); return true; }
        if (t === "B") { downloadPlaylist(); return true; }
        if (t === "x" && Downloads.active) { Downloads.cancel(); return true; }
        if (t === "g") { openPicker(); return true; }
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
        property string link: ""
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
            // A playlist (ou busca) traz entries; o link de uma música só, o próprio vídeo.
            const link = ytSearch.link;
            const entries = data.entries ? data.entries : (link ? [Object.assign({}, data, { url: data.webpage_url || link })] : []);
            root.results = entries.filter(e => e && e.url).map(e => ({
                title: e.title || e.url, artist: e.artist || e.channel || e.uploader || "",
                path: e.url, duration_secs: e.duration || 0, stream: true }));
            if (link && data.entries)
                root.playlist = { title: data.title || "Playlist", url: data.webpage_url || link };
            root.cursor = 0;
            view.positionViewAtBeginning();
        }
    }
    Timer {
        id: ytGuard
        interval: 30000
        onTriggered: if (ytSearch.running) { ytSearch.signal(15); root.searching = false; root.error = "o YouTube não respondeu em 30 s"; }
    }
    Component.onCompleted: { loadProviders(); Downloads.organize(); }
    Connections {
        target: Downloads
        // Acabaram as músicas sem pasta: fecha a escolha; senão mantém a linha dentro da lista.
        function onUnknownChanged() {
            if (!Downloads.unknown.length) root.picking = false;
            else root.pickRow = Math.min(root.pickRow, Downloads.unknown.length - 1);
        }
    }
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
            placeholder: "buscar música online ou colar link (música/playlist)"
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
                    : root.lastQuery ? "nada encontrado" : "/ para buscar ou colar um link · tab troca a fonte · b baixa"
                color: root.error || (root.listed && !root.providers.length) ? Theme.red : root.searching ? Theme.accent : Theme.faint
            }
        }
    }

    // ================= PASTA (g) =================
    // Música de artista novo: escolha a pasta de gênero uma vez; as próximas do artista vão sozinhas.
    Rectangle {
        anchors.fill: table
        visible: root.picking
        color: Theme.sheet
        border.width: 1
        border.color: Theme.accent
        z: 5
        MouseArea { anchors.fill: parent }        // nothing under the panel reacts to clicks

        RiceText {
            id: pickHead
            x: 14; y: 12
            width: parent.width - 28
            text: "SEM PASTA · artista novo — a pasta escolhida vale para as próximas músicas dele"
            color: Theme.accent
            font.pixelSize: Theme.small
            font.letterSpacing: 1.5
        }
        ListView {
            id: pickList
            anchors.top: pickHead.bottom
            anchors.topMargin: 10
            x: 14
            width: parent.width - 28
            height: Math.min(contentHeight, parent.height * 0.42)
            clip: true
            model: Downloads.unknown
            currentIndex: root.pickRow
            onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
            delegate: Item {
                id: pickItem
                required property var modelData
                required property int index
                width: pickList.width
                height: 24
                Rectangle {
                    anchors.fill: parent
                    color: pickItem.index === root.pickRow ? Qt.alpha(Theme.fg, 0.05) : "transparent"
                    Rectangle { width: 2; height: parent.height; color: pickItem.index === root.pickRow ? Theme.accent : "transparent" }
                }
                RiceText {
                    x: 10
                    width: parent.width - 20
                    anchors.verticalCenter: parent.verticalCenter
                    elide: Text.ElideRight
                    text: (pickItem.modelData.artist || "sem artista") + "  —  " + pickItem.modelData.title
                    color: pickItem.index === root.pickRow ? Theme.fg : Theme.dim
                }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.pickRow = pickItem.index }
            }
        }
        Rectangle { id: pickRule; anchors.top: pickList.bottom; anchors.topMargin: 10; x: 14; width: parent.width - 28; height: 1; color: Theme.line }
        Flow {
            anchors.top: pickRule.bottom
            anchors.topMargin: 12
            x: 14
            width: parent.width - 28
            spacing: 6
            Repeater {
                model: Downloads.folders
                Chip {
                    required property var modelData
                    required property int index
                    label: modelData
                    on: index === root.pickFolder
                    // Clique move direto para a pasta.
                    onClicked: { root.pickFolder = index; if (root.pickFile) Downloads.moveTo(root.pickFile.file, modelData); }
                }
            }
        }
        RiceText {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 10
            x: 14
            text: "↑↓ música · ←→ pasta · ⏎ move · clique na pasta move · esc fecha"
            color: Theme.faint
            font.pixelSize: Theme.small
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
            width: parent.width - buttons.width - 16
            elide: Text.ElideRight
            text: Downloads.active
                ? "[ ↓ ] " + (Downloads.total > 1 ? Downloads.index + "/" + Downloads.total + " · " : "") + Downloads.title
                  + " · " + Math.round(Downloads.percent) + "%" + (Downloads.queue.length ? " · +" + Downloads.queue.length + " na fila" : "") + " · x cancela"
                : Downloads.unknown.length ? Downloads.unknown.length + (Downloads.unknown.length === 1 ? " música" : " músicas")
                  + " de artista novo em Downloads · g escolhe a pasta"
                : !root.results.length ? ""
                : root.playlist ? root.playlist.title + " · " + root.results.length + " músicas · B baixa tudo"
                : root.results.length + " resultados · " + (root.fromLink ? "link" : (root.names[root.provider] || root.provider))
                  + (root.fromLink || root.provider === "ytdlp" ? " · via yt-dlp" : " · via cliamp")
            color: Downloads.active || Downloads.unknown.length ? Theme.accent : Theme.faint
            font.pixelSize: Theme.small
        }
        Row {
            id: buttons
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            spacing: 8
            AccentButton { ghost: true; visible: !!root.playlist; label: "PLAYLIST (B)"; onClicked: root.downloadPlaylist() }
            AccentButton { ghost: true; label: "BAIXAR (b)"; enabledState: !!root.selected; onClicked: root.download(root.selected) }
            AccentButton { ghost: true; label: "PRÓXIMA (a)"; enabledState: !!root.selected; onClicked: root.queueNext(root.selected) }
            AccentButton { label: "TOCAR ⏎"; enabledState: !!root.selected; onClicked: root.play(root.selected) }
        }
    }
}
