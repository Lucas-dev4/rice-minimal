// LibraryScreen.qml — tela BIBLIOTECA (MÚSICA): todas as músicas da pasta (music.dir) com busca por
// título, artista, álbum, gênero e letra (dados de `lw library scan`).
import QtQuick
import Quickshell
import qs
import qs.components

// LW // LIBRARY: every file under music.dir, searched by its tags (title, artist, album,
// genre, year) and lyrics, grouped by artist. cliamp's own search does not look inside
// local files, so the index comes from `lw library scan` (ffprobe, cached by mtime).
Item {
    id: root

    property Item keyTarget: null
    property string title: ""
    readonly property var hints: [["/", "buscar"], ["↑↓", "move"], ["⏎", "tocar"], ["a", "pôr na fila"], ["A", "todas"]]

    property var tracks: []
    property bool loading: false
    property string error: ""
    property int cursor: 0
    property int revision: 0             // bumped by filter(): the same cursor may be a new row
    readonly property var selected: revision >= 0 && cursor >= 0 && cursor < results.count ? results.get(cursor) : null

    // Plain text matches anywhere; artista:/álbum:/gênero:/ano:/letra: narrow it to one tag.
    readonly property var fields: ({ "artista": "artist", "artist": "artist", "álbum": "album", "album": "album",
                                     "gênero": "genre", "genero": "genre", "ano": "year", "título": "title", "titulo": "title", "letra": "lyrics" })
    // Texto em minúsculas e sem acentos (busca).
    function fold(s) { return String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, ""); }
    // Aplica a busca e monta a lista visível.
    function filter() {
        const words = fold(box.text).split(/\s+/).filter(w => w);
        results.clear();
        for (const t of tracks) {
            let where = "";
            const ok = words.every(w => {
                const m = /^([a-zà-ú]+):(.*)$/.exec(w);
                if (m && fields[m[1]]) return fold(t[fields[m[1]]]).includes(m[2]);
                for (const f of ["title", "artist", "album", "genre", "year"]) if (fold(t[f]).includes(w)) return true;
                if (fold(t.lyrics).includes(w)) { where = "letra"; return true; }
                return false;
            });
            if (ok) results.append({ path: t.path, title: t.title, artist: t.artist || "Desconhecido", album: t.album,
                                     genre: t.genre, year: t.year, duration: t.duration, where: where, group: t.group });
        }
        cursor = 0;
        revision++;
        view.positionViewAtBeginning();
    }
    // Segundos → "m:ss".
    function clock(seconds) {
        if (!seconds) return "";
        const s = Math.floor(seconds);
        return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
    }
    // Move a seleção.
    function moveCursor(step) {
        if (!results.count) return;
        cursor = Math.max(0, Math.min(results.count - 1, cursor + step));
        view.positionViewAtIndex(cursor, ListView.Contain);
    }
    // Toca a música agora.
    function play(t) { if (t) { Music.playPath(t.path); Status.say("[ ▶ ] " + t.title + " — " + t.artist, Theme.ok); } }
    // Põe a música na fila.
    function enqueue(t) { if (t) { Music.addPath(t.path); Status.say("[ + ] " + t.title + " na fila", Theme.ok); } }
    // Põe todos os resultados da busca na fila.
    function enqueueAll() {
        const queued = new Set(Music.playlist.map(t => t.path));
        let n = 0;
        for (let i = 0; i < results.count; i++) {
            const p = results.get(i).path;
            if (!queued.has(p)) { Music.addPath(p); n++; }
        }
        Status.say(n ? "[ + ] " + n + " música(s) na fila" : "[ -- ] todas já estão na fila", n ? Theme.ok : Theme.dim);
    }
    // Test hook (music IPC `query`): sets the search text.
    function query(text) { box.text = text; }
    // Teclas da tela (Enter toca, a põe na fila, A todos).
    function handleKey(event) {
        const t = event.text;
        if (event.key === Qt.Key_Slash) { box.focusInput(); return true; }
        if (event.key === Qt.Key_Down) { moveCursor(1); return true; }
        if (event.key === Qt.Key_Up) { moveCursor(-1); return true; }
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { play(selected); return true; }
        if (t === "a") { enqueue(selected); return true; }
        if (t === "A") { enqueueAll(); return true; }
        return false;
    }

    // Relê a biblioteca.
    function scan() {
        if (scanner.running) return;
        loading = true;
        scanner.call(["library", "scan", "--json"]);
    }
    Component.onCompleted: scan()

    RiceCommand {
        id: scanner
        onFailed: message => { root.loading = false; root.error = message; }
        onSucceeded: data => {
            root.loading = false;
            root.error = "";
            // Grouped by the main artist (the folder name), then by title.
            for (const t of data.tracks) t.group = (t.artist || "Desconhecido").split(",")[0].trim();
            root.tracks = data.tracks.sort((a, b) => a.group.localeCompare(b.group, "pt", { sensitivity: "base" })
                                                  || a.title.localeCompare(b.title, "pt", { sensitivity: "base" }));
            root.filter();
        }
    }

    ListModel { id: results }

    // ================= SEARCH =================
    SearchBox {
        id: box
        width: 360
        placeholder: "buscar nas tags e nas letras"
        keyTarget: root.keyTarget
        onTextChanged: root.filter()
    }
    RiceText {
        anchors.verticalCenter: box.verticalCenter
        anchors.left: box.right
        anchors.leftMargin: 14
        text: "artista:wlo · álbum:… · gênero:rap · ano:2024 · letra:…"
        color: Theme.faint
        font.pixelSize: Theme.small
    }

    // ================= RESULTS =================
    Rectangle {
        id: table
        anchors.top: box.bottom
        anchors.topMargin: 12
        anchors.bottom: foot.top
        anchors.bottomMargin: 10
        anchors.left: parent.left
        anchors.right: side.left
        anchors.rightMargin: 20
        color: "transparent"
        border.width: 1
        border.color: Theme.line
        clip: true

        ListView {
            id: view
            anchors.fill: parent
            anchors.margins: 1
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: results
            section.property: "group"
            section.criteria: ViewSection.FullString
            section.delegate: Rectangle {
                required property string section
                width: view.width
                height: 26
                color: Theme.panel
                RiceText {
                    x: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: parent.section.toUpperCase()
                    color: Theme.accent
                    font.pixelSize: Theme.small
                    font.letterSpacing: 1.5
                }
            }
            delegate: Item {
                id: row
                required property int index
                required property string path
                required property string title
                required property string album
                required property string genre
                required property string year
                required property real duration
                required property string where
                readonly property bool chosen: index === root.cursor
                readonly property bool playing: Music.track !== null && Music.track.path === path
                width: view.width
                height: 26
                Rectangle {
                    anchors.fill: parent
                    color: row.playing ? Theme.accentA : row.chosen ? Qt.alpha(Theme.fg, 0.05) : rowMouse.containsMouse ? Qt.alpha(Theme.fg, 0.025) : "transparent"
                    Rectangle { width: 2; height: parent.height; color: row.playing ? Theme.accent : row.chosen ? Theme.line2 : "transparent" }
                }
                RiceText {
                    x: 22
                    width: parent.width * 0.48
                    anchors.verticalCenter: parent.verticalCenter
                    elide: Text.ElideRight
                    text: row.title
                    color: row.playing ? Theme.accent : Theme.fg
                }
                RiceText {
                    x: 22 + parent.width * 0.48 + 12
                    width: parent.width - x - 120
                    anchors.verticalCenter: parent.verticalCenter
                    elide: Text.ElideRight
                    text: [row.album !== row.title ? row.album : "", row.year, row.genre].filter(x => x).join(" · ")
                    color: Theme.faint
                    font.pixelSize: Theme.small
                }
                Rectangle {
                    visible: row.where === "letra"
                    anchors.right: dur.left
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    width: whereText.implicitWidth + 10
                    height: whereText.implicitHeight
                    color: "transparent"
                    border.width: 1
                    border.color: Qt.alpha(Theme.blue, 0.35)
                    RiceText { id: whereText; anchors.centerIn: parent; text: "letra"; color: Theme.blue; font.pixelSize: 10 }
                }
                RiceText {
                    id: dur
                    anchors.right: parent.right
                    anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.clock(row.duration)
                    color: Theme.faint
                }
                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: { root.cursor = row.index; root.keyTarget.forceActiveFocus(); }
                    onDoubleClicked: root.play(results.get(row.index))
                }
            }
            RiceText {
                anchors.centerIn: parent
                visible: results.count === 0
                text: root.loading ? "[ .. ] lendo as tags de " + Music.dirShown + "…" : root.error ? "[ !! ] " + root.error : "nada com \"" + box.text + "\""
                color: root.error ? Theme.red : root.loading ? Theme.accent : Theme.faint
            }
        }
    }

    // ================= DETAILS =================
    Rectangle {
        id: side
        anchors.top: table.top
        anchors.bottom: table.bottom
        anchors.right: parent.right
        width: 270
        color: Theme.panel
        border.width: 1
        border.color: Theme.line
        readonly property var t: root.selected
        Column {
            x: 16
            y: 16
            width: parent.width - 32
            spacing: 4
            RiceText { text: "MÚSICA"; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5; bottomPadding: 6 }
            RiceText { width: parent.width; wrapMode: Text.Wrap; text: side.t ? side.t.title : "—"; color: Theme.fg; font.bold: true; bottomPadding: 8 }
            Repeater {
                model: !side.t ? [] : [["artista", side.t.artist], ["álbum", side.t.album || "—"], ["gênero", side.t.genre || "—"],
                                       ["ano", side.t.year || "—"], ["duração", root.clock(side.t.duration) || "—"]]
                Row {
                    required property var modelData
                    spacing: 10
                    RiceText { width: 64; text: modelData[0]; color: Theme.faint }
                    RiceText { width: side.width - 32 - 74; elide: Text.ElideRight; text: modelData[1]; color: Theme.fg }
                }
            }
            RiceText {
                visible: !!side.t
                width: parent.width
                topPadding: 10
                wrapMode: Text.WrapAnywhere
                text: side.t ? side.t.path.replace(Quickshell.env("HOME"), "~") : ""
                color: Theme.faint
                font.pixelSize: 10
            }
        }
        RiceText {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 14
            x: 16
            width: parent.width - 32
            wrapMode: Text.Wrap
            text: "⏎ toca · a põe na fila · A põe todos os resultados"
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
            readonly property int artists: new Set(root.tracks.map(t => t.artist)).size
            text: (box.text ? results.count + " de " : "") + root.tracks.length + " músicas · " + artists + " artistas · " + Music.dirShown
            color: Theme.dim
        }
        AccentButton {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            ghost: true
            label: root.loading ? "LENDO…" : "RELER"
            enabledState: !root.loading
            onClicked: root.scan()
        }
    }
}
