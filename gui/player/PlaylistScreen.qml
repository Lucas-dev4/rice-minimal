import QtQuick
import Quickshell.Io
import qs
import qs.components

// LW // PLAYLIST: cliamp's live queue. The cursor (dashed) is separate from the playing
// track (accent band). Edits go to cliamp (queue.*); files on disk are never touched.
Item {
    id: root

    property Item keyTarget: null
    property string title: ""
    property int cursor: 0                 // index into Music.playlist
    readonly property var hints: [["jk", "move"], ["⏎", "play"], ["JK", "mover"], ["d", "remover"], ["o", "abrir"], ["/", "filtro"]]

    readonly property string needle: search.text.toLowerCase()
    readonly property var rows: needle === "" ? Music.playlist
        : Music.playlist.filter(t => [t.title, t.artist, t.album, t.path].join(" ").toLowerCase().includes(needle))
    readonly property var selected: Music.playlist[cursor] || null

    // Durations come from ffprobe, a few at a time.
    onRowsChanged: { for (const t of Music.playlist) Music.requestInfo(t.path); }

    function clock(seconds) {
        if (!isFinite(seconds) || seconds <= 0) return "";
        const s = Math.floor(seconds);
        const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60);
        return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(s % 60).padStart(2, "0");
    }
    function durationOf(t) {
        if (Music.sourceOf(t.path) !== "local") return "LIVE";
        const i = Music.infos[t.path];
        return i ? clock(i.duration) : "";
    }
    function moveCursor(step) {
        const list = rows;
        if (!list.length) return;
        const at = list.findIndex(t => t.index === cursor);
        const next = list[Math.max(0, Math.min(list.length - 1, (at < 0 ? 0 : at) + step))];
        cursor = next.index;
        view.positionViewAtIndex(list.indexOf(next), ListView.Contain);
    }
    // cliamp swaps the two positions; one step at a time that is a move.
    function reorder(step) {
        if (needle !== "") { Status.say("[ -- ] limpe o filtro para reordenar", Theme.dim); return; }
        const to = cursor + step;
        if (!selected || to < 0 || to >= Music.playlist.length) return;
        Music.moveTrack(cursor, to);
        cursor = to;
    }
    function remove() {
        if (!selected) return;
        const name = selected.title || Music.fileName(selected.path);
        Music.removeTrack(cursor);
        Status.say("[ - ] " + name + " saiu da fila (o arquivo continua no disco)", Theme.dim);
        cursor = Math.max(0, Math.min(cursor, Music.playlist.length - 2));
    }
    function openFiles() {
        if (picker.running) return;
        picker.running = true;
    }

    function handleKey(event) {
        const t = event.text;
        if (t === "j" || event.key === Qt.Key_Down) { moveCursor(1); return true; }
        if (t === "k" || event.key === Qt.Key_Up) { moveCursor(-1); return true; }
        if (t === "J") { reorder(1); return true; }
        if (t === "K") { reorder(-1); return true; }
        if (t === "d" || event.key === Qt.Key_Delete) { remove(); return true; }
        if (t === "o") { openFiles(); return true; }
        if (event.key === Qt.Key_Slash) { search.focusInput(); return true; }
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { if (selected) Music.playIndex(cursor); return true; }
        return false;
    }

    // Start on the playing track.
    Component.onCompleted: if (Music.currentIndex >= 0) cursor = Music.currentIndex

    // The system file chooser (zenity, GTK): several files at once, audio only.
    Process {
        id: picker
        command: ["zenity", "--file-selection", "--multiple", "--separator=\n", "--title=LW // MUSIC — adicionar à fila",
                  "--file-filter=Áudio | *.mp3 *.flac *.ogg *.opus *.m4a *.aac *.wav *.wv *.ape *.aiff *.alac *.wma",
                  "--file-filter=Tudo | *"]
        stdout: StdioCollector {
            onStreamFinished: {
                const files = text.split("\n").filter(f => f.trim() !== "");
                for (const f of files) Music.addPath(f);
                if (files.length) Status.say("[ + ] " + files.length + " arquivo(s) na fila", Theme.ok);
            }
        }
    }

    SearchBox {
        id: search
        width: 260
        keyTarget: root.keyTarget
    }
    RiceText {
        anchors.verticalCenter: search.verticalCenter
        anchors.left: search.right
        anchors.leftMargin: 14
        text: root.needle ? root.rows.length + " de " + Music.playlist.length : "arraste arquivos de áudio para a janela para adicionar"
        color: Theme.faint
        font.pixelSize: Theme.small
    }

    // ================= TABLE =================
    Rectangle {
        id: table
        anchors.top: search.bottom
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

        component Cells: Item {
            id: cells
            property bool head: false
            property var track: null
            property bool playing: false
            height: 26
            width: parent ? parent.width : 0
            readonly property int artistW: 150
            readonly property int sourceW: 64
            readonly property int timeW: 54
            Item {
                id: num
                x: 10
                width: 30
                height: parent.height
                // Three small bars in place of the number on the playing track.
                Row {
                    visible: cells.playing
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2
                    height: 10
                    Repeater {
                        model: 3
                        Rectangle {
                            id: barIcon
                            required property int index
                            width: 2
                            height: 3
                            anchors.bottom: parent.bottom
                            color: Theme.accent
                            SequentialAnimation on height {
                                running: Music.playing && cells.playing && Theme.motion
                                loops: Animation.Infinite
                                PauseAnimation { duration: barIcon.index * 180 }
                                NumberAnimation { to: 10; duration: 400; easing.type: Easing.InOutSine }
                                NumberAnimation { to: 3; duration: 400; easing.type: Easing.InOutSine }
                            }
                        }
                    }
                }
                RiceText {
                    visible: !cells.playing
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    text: cells.head ? "#" : cells.track ? cells.track.index + 1 : ""
                    color: Theme.faint
                    font.pixelSize: cells.head ? Theme.small : Theme.fontSize
                }
            }
            RiceText {
                x: 54
                width: parent.width - x - cells.artistW - cells.sourceW - cells.timeW - 40
                anchors.verticalCenter: parent.verticalCenter
                elide: Text.ElideRight
                text: cells.head ? "TÍTULO" : cells.track ? cells.track.title || Music.fileName(cells.track.path) : ""
                color: cells.head ? Theme.faint : cells.playing ? Theme.accent : Theme.fg
                font.pixelSize: cells.head ? Theme.small : Theme.fontSize
                font.letterSpacing: cells.head ? 1.5 : 0
            }
            RiceText {
                x: parent.width - cells.artistW - cells.sourceW - cells.timeW - 30
                width: cells.artistW
                anchors.verticalCenter: parent.verticalCenter
                elide: Text.ElideRight
                text: cells.head ? "ARTISTA" : cells.track ? cells.track.artist || "" : ""
                color: cells.head ? Theme.faint : Theme.dim
                font.pixelSize: cells.head ? Theme.small : Theme.fontSize
                font.letterSpacing: cells.head ? 1.5 : 0
            }
            Item {
                x: parent.width - cells.sourceW - cells.timeW - 20
                width: cells.sourceW
                height: parent.height
                readonly property string kind: cells.track ? Music.sourceOf(cells.track.path) : ""
                readonly property color tint: kind === "local" ? Theme.ok : kind === "radio" ? Theme.blue : Theme.accent
                RiceText {
                    visible: cells.head
                    anchors.verticalCenter: parent.verticalCenter
                    text: "FONTE"
                    color: Theme.faint
                    font.pixelSize: Theme.small
                    font.letterSpacing: 1.5
                }
                Rectangle {
                    visible: !cells.head && parent.kind !== ""
                    anchors.verticalCenter: parent.verticalCenter
                    width: badge.implicitWidth + 10
                    height: badge.implicitHeight
                    color: "transparent"
                    border.width: 1
                    border.color: Qt.alpha(parent.tint, 0.35)
                    RiceText { id: badge; anchors.centerIn: parent; text: parent.parent.kind; color: parent.parent.tint; font.pixelSize: 10 }
                }
            }
            RiceText {
                x: parent.width - cells.timeW - 10
                width: cells.timeW
                anchors.verticalCenter: parent.verticalCenter
                horizontalAlignment: Text.AlignRight
                text: cells.head ? "TEMPO" : cells.track ? root.durationOf(cells.track) : ""
                color: Theme.faint
                font.pixelSize: cells.head ? Theme.small : Theme.fontSize
                font.letterSpacing: cells.head ? 1.5 : 0
            }
        }

        ListView {
            id: view
            anchors.fill: parent
            anchors.margins: 1
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: root.rows
            headerPositioning: ListView.OverlayHeader
            header: Rectangle {
                width: view.width
                height: 26
                z: 2
                color: Theme.bg
                Cells { head: true }
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
            }
            delegate: Item {
                id: row
                required property var modelData
                readonly property bool playing: modelData.index === Music.currentIndex
                readonly property bool chosen: modelData.index === root.cursor
                width: view.width
                height: 26
                Rectangle {
                    anchors.fill: parent
                    color: row.playing ? Theme.accentA : rowMouse.containsMouse ? Qt.alpha(Theme.fg, 0.025) : "transparent"
                    Rectangle { width: 2; height: parent.height; color: row.playing ? Theme.accent : "transparent" }
                }
                // The cursor: a dashed outline, apart from the playing band.
                Canvas {
                    anchors.fill: parent
                    visible: row.chosen
                    onVisibleChanged: requestPaint()
                    onWidthChanged: requestPaint()
                    onPaint: {
                        const ctx = getContext("2d");
                        ctx.clearRect(0, 0, width, height);
                        ctx.strokeStyle = String(Theme.line2);
                        ctx.setLineDash([3, 3]);
                        ctx.strokeRect(0.5, 0.5, width - 1, height - 1);
                    }
                }
                Cells { track: row.modelData; playing: row.playing }
                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: { root.cursor = row.modelData.index; root.keyTarget.forceActiveFocus(); }
                    onDoubleClicked: Music.playIndex(row.modelData.index)
                }
            }
            RiceText {
                anchors.centerIn: parent
                visible: root.rows.length === 0
                text: Music.playlist.length ? "nada com \"" + search.text + "\"" : "fila vazia — o para abrir arquivos"
                color: Theme.faint
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
        readonly property var info: t ? Music.infos[t.path] || null : null

        Column {
            x: 16
            y: 16
            width: parent.width - 32
            spacing: 4
            RiceText { text: "FAIXA"; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5; bottomPadding: 6 }
            RiceText {
                width: parent.width
                wrapMode: Text.Wrap
                text: side.t ? side.t.title || Music.fileName(side.t.path) : "—"
                color: Theme.fg
                font.bold: true
                bottomPadding: 8
            }
            Repeater {
                model: !side.t ? [] : [
                    ["artista", side.t.artist || "—"],
                    ["álbum", side.t.album || "—"],
                    ["fonte", Music.sourceOf(side.t.path)],
                    ["formato", side.info ? [side.info.codec, side.info.rate ? (side.info.rate / 1000).toFixed(1).replace(/\.0$/, "") + " kHz" : "", side.info.bitrate ? Math.round(side.info.bitrate / 1000) + " kbps" : ""].filter(x => x).join(" · ") : Music.sourceOf(side.t.path) === "local" ? "…" : "stream"],
                    ["duração", root.durationOf(side.t) || "…"],
                    ["posição", (side.t.index + 1) + " de " + Music.playlist.length]
                ]
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
                text: side.t ? side.t.path : ""
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
            text: "⏎ toca · J/K muda a posição · d tira da fila (o arquivo fica no disco)"
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
            readonly property var local: Music.playlist.filter(t => Music.sourceOf(t.path) === "local")
            readonly property real total: local.reduce((sum, t) => sum + ((Music.infos[t.path] || {}).duration || 0), 0)
            readonly property int pending: local.filter(t => !Music.infos[t.path]).length
            readonly property int live: Music.playlist.length - local.length
            text: Music.playlist.length + " faixas · " + (root.clock(total) || "0:00") + (pending ? " (calculando " + pending + ")" : "")
                + (live ? " + " + live + " ao vivo" : "")
            color: Theme.dim
        }
        AccentButton {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            ghost: true
            label: picker.running ? "ABRINDO…" : "+ ABRIR ARQUIVOS"
            enabledState: !picker.running
            onClicked: root.openFiles()
        }
    }
}
