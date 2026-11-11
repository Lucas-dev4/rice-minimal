import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.components

// LW // GAMES library: games. header, CONTINUE and STATS cards, filter chips + search,
// a 3:4 cover grid. A click (or ⏎) opens the game's sheet (signal `open`).
Item {
    id: root

    property Item keyTarget: null
    property string title: ""
    signal open(string id)
    signal launch(string id)
    readonly property var hints: [["hjkl", "move"], ["⏎", "abrir"], ["tab", "filtro"], ["/", "buscar"], ["a", "adicionar"], ["r", "rescan"]]

    readonly property var filters: [["todos", ""], ["jogando", "playing"], ["quero jogar", "want"], ["zerado", "done"], ["largado", "dropped"]]
    property int filter: 0
    readonly property string needle: search.text.toLowerCase()
    readonly property var shown: Games.games
        .filter(g => !filters[filter][1] || g.status === filters[filter][1])
        .filter(g => !needle || (g.title + " " + g.source).toLowerCase().includes(needle))
        .sort((a, b) => (a.missing - b.missing) || (b.last_played || 0) - (a.last_played || 0) || a.title.localeCompare(b.title, "pt"))

    function hours(h) { return h ? (h < 10 ? h.toFixed(1).replace(/\.0$/, "") : Math.round(h)) + " h" : "—"; }

    // ---- adding a game: the .exe, its Wine prefix, its name --------------------------
    property string pickedExe: ""
    property string pickedPrefix: ""
    function addGame() { if (!pickExe.running) pickExe.running = true; }
    Process {
        id: pickExe
        command: ["zenity", "--file-selection", "--title=LW // GAMES — escolha o executável do jogo",
                  "--filename=" + Quickshell.env("HOME") + "/", "--file-filter=Jogos | *.exe *.sh *.x86_64 *.AppImage", "--file-filter=Tudo | *"]
        stdout: StdioCollector {
            onStreamFinished: {
                root.pickedExe = text.trim();
                if (!root.pickedExe) return;
                if (/\.exe$/i.test(root.pickedExe)) pickPrefix.running = true;
                else { root.pickedPrefix = ""; pickName.running = true; }
            }
        }
    }
    // Wine prefixes that exist here, plus a fresh default.
    Process {
        id: pickPrefix
        command: ["bash", "-c", 'opts=(); for p in "$HOME"/.wine*/ "$HOME"/Games/*/pfx/; do [ -f "$p/system.reg" ] && opts+=("${p%/}"); done; ' +
                  'zenity --list --title="LW // GAMES — prefixo do Wine" --text="Em qual prefixo do Wine o jogo está instalado?" --column=prefixo "${opts[@]}"']
        stdout: StdioCollector {
            onStreamFinished: {
                root.pickedPrefix = text.trim();
                if (root.pickedPrefix) pickName.running = true;
            }
        }
    }
    Process {
        id: pickName
        command: ["zenity", "--entry", "--title=LW // GAMES", "--text=Nome do jogo:",
                  "--entry-text=" + root.pickedExe.split("/").pop().replace(/\.[^.]+$/, "")]
        stdout: StdioCollector {
            onStreamFinished: { if (text.trim()) Games.add(root.pickedExe, root.pickedPrefix, text.trim()); }
        }
    }

    function moveCursor(step) {
        if (!shown.length) return;
        grid.currentIndex = Math.max(0, Math.min(shown.length - 1, grid.currentIndex + step));
    }
    function handleKey(event) {
        const t = event.text;
        if (event.key === Qt.Key_Slash) { search.focusInput(); return true; }
        if (t === "h" || event.key === Qt.Key_Left) { moveCursor(-1); return true; }
        if (t === "l" || event.key === Qt.Key_Right) { moveCursor(1); return true; }
        if (t === "j" || event.key === Qt.Key_Down) { moveCursor(grid.columns); return true; }
        if (t === "k" || event.key === Qt.Key_Up) { moveCursor(-grid.columns); return true; }
        if (event.key === Qt.Key_Tab) { filter = (filter + 1) % filters.length; grid.currentIndex = 0; return true; }
        if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && shown[grid.currentIndex]) { open(shown[grid.currentIndex].id); return true; }
        if (t === "a") { addGame(); return true; }
        if (t === "r") { Games.scan(); return true; }
        return false;
    }
    // Test hook (games IPC `query`).
    function query(text) { search.text = text; }

    // ================= HEADER =================
    Item {
        id: header
        width: parent.width
        height: titleText.implicitHeight
        RiceText {
            id: titleText
            textFormat: Text.StyledText
            text: "games<font color='" + Theme.accent + "'>.</font>"
            font.pixelSize: 26
            font.weight: Font.ExtraBold
        }
        RiceText {
            anchors.left: titleText.right
            anchors.leftMargin: 12
            anchors.baseline: titleText.baseline
            text: Games.games.length + " jogos" + (Games.scanning ? " · scan…" : "")
            color: Theme.dim
        }
        Row {
            anchors.right: parent.right
            anchors.verticalCenter: titleText.verticalCenter
            spacing: 8
            AccentButton { ghost: true; label: Games.scanning ? "SCAN…" : "RESCAN (r)"; enabledState: !Games.scanning; onClicked: Games.scan() }
            AccentButton { label: "+ JOGO (a)"; onClicked: root.addGame() }
        }
    }

    // ================= CONTINUE + STATS =================
    Row {
        id: cards
        anchors.top: header.bottom
        anchors.topMargin: 16
        width: parent.width
        height: 150
        spacing: 14
        visible: Games.games.length > 0

        Rectangle {
            width: parent.width - stats.width - 14
            height: parent.height
            color: Theme.panel
            border.width: 1
            border.color: Theme.line
            readonly property var g: Games.continueGame
            GameCover {
                id: contCover
                x: 14
                anchors.verticalCenter: parent.verticalCenter
                width: 92
                height: 122
                game: parent.g
                showTitle: false
                visible: !!parent.g
            }
            Column {
                anchors.left: contCover.right
                anchors.leftMargin: 16
                anchors.right: parent.right
                anchors.rightMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 3
                visible: !!parent.g
                RiceText { text: "CONTINUAR"; color: Theme.faint; font.pixelSize: 10; font.letterSpacing: 2 }
                RiceText { width: parent.width; elide: Text.ElideRight; text: parent.parent.g ? parent.parent.g.title : ""; font.pixelSize: 18; font.weight: Font.ExtraBold }
                RiceText {
                    readonly property var g: parent.parent.g
                    text: !g ? "" : g.source + " · " + root.hours(Games.hoursOf(g)) + (g.est_hours ? " de ~" + g.est_hours + " h" : "")
                    color: Theme.dim
                    font.pixelSize: Theme.small
                }
                Rectangle {
                    width: parent.width
                    height: 3
                    color: Theme.line
                    Rectangle { height: parent.height; width: parent.width * ((parent.parent.parent.g || {}).progress || 0) / 100; color: Theme.accent }
                }
                Item { width: 1; height: 6 }
                Rectangle {
                    id: playButton
                    width: playText.implicitWidth + 36
                    height: playText.implicitHeight + 16
                    color: playMouse.containsMouse ? Theme.ok : "transparent"
                    border.width: 1
                    border.color: Theme.ok
                    Behavior on color { ColorAnimation { duration: Theme.tFast } }
                    RiceText { id: playText; anchors.centerIn: parent; text: "▶ JOGAR"; font.weight: Font.ExtraBold; font.letterSpacing: 1; color: playMouse.containsMouse ? Theme.bg : Theme.ok }
                    MouseArea { id: playMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.launch(Games.continueGame.id) }
                }
            }
            RiceText {
                visible: !parent.g
                x: 24
                anchors.verticalCenter: parent.verticalCenter
                text: "nada em andamento — marque um jogo como \"jogando\""
                color: Theme.dim
            }
        }

        // HOURS · DONE · WEEKS OF QUEUE
        Rectangle {
            id: stats
            width: 360
            height: parent.height
            color: Theme.panel
            border.width: 1
            border.color: Theme.line
            Row {
                anchors.centerIn: parent
                Repeater {
                    model: [[Math.round(Games.totalHours), "HORAS"], [Games.doneCount, "ZERADOS"], [Games.queueWeeks, "SEMANAS DE FILA"]]
                    Column {
                        required property var modelData
                        width: 116
                        spacing: 2
                        RiceText { anchors.horizontalCenter: parent.horizontalCenter; text: modelData[0]; font.pixelSize: 24; font.weight: Font.ExtraBold }
                        RiceText { anchors.horizontalCenter: parent.horizontalCenter; text: modelData[1]; color: Theme.faint; font.pixelSize: 10; font.letterSpacing: 1.5 }
                    }
                }
            }
        }
    }

    // ================= FILTERS =================
    Row {
        id: filterRow
        anchors.top: cards.visible ? cards.bottom : header.bottom
        anchors.topMargin: 16
        spacing: 6
        visible: Games.games.length > 0
        Repeater {
            model: root.filters
            Chip {
                required property var modelData
                required property int index
                label: modelData[0] + " " + Games.games.filter(g => !modelData[1] || g.status === modelData[1]).length
                on: root.filter === index
                onClicked: { root.filter = index; grid.currentIndex = 0; root.keyTarget.forceActiveFocus(); }
            }
        }
    }
    SearchBox {
        id: search
        anchors.right: parent.right
        anchors.verticalCenter: filterRow.verticalCenter
        width: 240
        visible: Games.games.length > 0
        placeholder: "buscar jogo"
        keyTarget: root.keyTarget
    }

    // ================= GRID =================
    GridView {
        id: grid
        anchors.top: filterRow.bottom
        anchors.topMargin: 14
        anchors.bottom: parent.bottom
        width: parent.width
        clip: true
        visible: Games.games.length > 0
        boundsBehavior: Flickable.StopAtBounds
        readonly property int columns: Math.max(1, Math.floor(width / 150))
        cellWidth: Math.floor(width / columns)
        cellHeight: Math.round((cellWidth - 14) * 4 / 3) + 40
        model: root.shown
        property bool entering: true
        Timer { running: true; interval: 1200; onTriggered: grid.entering = false }
        delegate: Item {
            id: cell
            required property var modelData
            required property int index
            readonly property bool chosen: GridView.isCurrentItem
            width: grid.cellWidth
            height: grid.cellHeight
            opacity: 0
            // Staggered entrance: 35 ms apart, rising 8 px.
            transform: Translate { id: rise; y: Theme.motion && grid.entering ? 8 : 0 }
            Component.onCompleted: {
                if (Theme.motion && grid.entering) appear.start();
                else { opacity = cell.modelData.missing ? 0.4 : 1; rise.y = 0; }
            }
            SequentialAnimation {
                id: appear
                PauseAnimation { duration: Math.min(cell.index, 24) * 35 }
                ParallelAnimation {
                    NumberAnimation { target: cell; property: "opacity"; to: cell.modelData.missing ? 0.4 : 1; duration: 400; easing.type: Theme.ease }
                    NumberAnimation { target: rise; property: "y"; to: 0; duration: 400; easing.type: Theme.ease }
                }
            }
            GameCover {
                id: cover
                x: 7
                y: hover.containsMouse || cell.chosen ? 4 : 7
                width: cell.width - 14
                height: Math.round(width * 4 / 3)
                game: cell.modelData
                border.color: hover.containsMouse || cell.chosen ? Theme.accent : Theme.line2
                Behavior on y { NumberAnimation { duration: 250; easing.type: Theme.ease } }
                Behavior on border.color { ColorAnimation { duration: 200 } }
            }
            Item {
                anchors.top: cover.bottom
                anchors.topMargin: 5
                x: 7
                width: cover.width
                height: statusText.implicitHeight
                RiceText {
                    id: statusText
                    text: cell.modelData.missing ? "sumiu" : Games.statusLabel[cell.modelData.status] || cell.modelData.status
                    color: cell.modelData.missing ? Theme.red : Games.statusColor(cell.modelData.status)
                    font.pixelSize: 10
                }
                RiceText { anchors.right: parent.right; text: root.hours(Games.hoursOf(cell.modelData)); color: Theme.faint; font.pixelSize: 10 }
            }
            MouseArea {
                id: hover
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: { grid.currentIndex = cell.index; root.open(cell.modelData.id); }
            }
        }
        RiceText {
            anchors.centerIn: parent
            visible: root.shown.length === 0
            text: "nenhum jogo neste filtro"
            color: Theme.faint
        }
    }

    // ================= EMPTY LIBRARY =================
    Column {
        anchors.centerIn: parent
        visible: Games.loaded && Games.games.length === 0
        spacing: 12
        width: 560
        RiceText { anchors.horizontalCenter: parent.horizontalCenter; text: Games.scanning ? "[ .. ] procurando jogos…" : "[ -- ] nenhum jogo ainda"; color: Games.scanning ? Theme.accent : Theme.dim; font.pixelSize: 16 }
        RiceText {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            color: Theme.faint
            font.pixelSize: Theme.small
            text: "O scan procura a Steam (todas as bibliotecas), o Hydra Launcher e ROMs em ~/ROMs. "
                + "Jogos do Wine (repacks, .exe) entram por + JOGO: escolha o executável já instalado e o prefixo."
        }
        AccentButton { anchors.horizontalCenter: parent.horizontalCenter; label: "+ ADICIONAR .exe (a)"; onClicked: root.addGame() }
    }
}
