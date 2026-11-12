import QtQuick
import qs
import qs.components
import qs.arcade

// LW // GAMES backlog: four columns by status, top of a column = highest priority.
// Drag a card to another column or place; or keys: h/l j/k select, H/L change column,
// J/K change priority, ⏎ opens the sheet. Every change is one `games.py arrange`.
Item {
    id: root

    property Item keyTarget: null
    property string title: ""
    signal open(string id)
    signal launch(string id)
    readonly property var hints: [["←↑↓→", "move"], ["⇧←→", "coluna"], ["⇧↑↓", "prioridade"], ["⏎", "abrir"]]

    readonly property var columns: [["want", "QUERO JOGAR"], ["playing", "JOGANDO"], ["done", "ZERADO"], ["dropped", "LARGADO"]]
    readonly property var lists: columns.map(c => Games.column(c[0]))
    property int col: 0
    property int row: 0
    readonly property var selected: (lists[col] || [])[row] || null
    readonly property int cardHeight: 70
    readonly property real colWidth: (width - 3 * 14) / 4

    function ids(list) { return list.map(g => g.id); }
    function clampRow() { row = Math.max(0, Math.min(Math.max(0, lists[col].length - 1), row)); }
    // Moves `id` to column `to` at position `at` (and renumbers that column).
    function place(id, to, at) {
        const from = columns.findIndex(c => lists[columns.indexOf(c)].some(g => g.id === id));
        const target = ids(lists[to]).filter(x => x !== id);
        at = Math.max(0, Math.min(target.length, at));
        target.splice(at, 0, id);
        const g = Games.byId(id);
        Games.arrange(columns[to][0], target, from !== to && g ? g.title + " → " + Games.statusLabel[columns[to][0]] : "");
        col = to;
        row = at;
    }
    function handleKey(event) {
        const t = event.text;
        // Shift+arrows carry the selected game; plain arrows move the cursor.
        if (event.modifiers & Qt.ShiftModifier) {
            if (!selected) return false;
            if (event.key === Qt.Key_Left && col > 0) { place(selected.id, col - 1, row); return true; }
            if (event.key === Qt.Key_Right && col < 3) { place(selected.id, col + 1, row); return true; }
            if (event.key === Qt.Key_Down && row < lists[col].length - 1) { place(selected.id, col, row + 1); return true; }
            if (event.key === Qt.Key_Up && row > 0) { place(selected.id, col, row - 1); return true; }
        }
        if (event.key === Qt.Key_Left) { col = Math.max(0, col - 1); clampRow(); return true; }
        if (event.key === Qt.Key_Right) { col = Math.min(3, col + 1); clampRow(); return true; }
        if (event.key === Qt.Key_Down) { row = Math.min(lists[col].length - 1, row + 1); return true; }
        if (event.key === Qt.Key_Up) { row = Math.max(0, row - 1); return true; }
        if (!selected) return false;
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { open(selected.id); return true; }
        return false;
    }

    // ---- drag ---------------------------------------------------------------------
    property string dragId: ""
    property point dragAt: Qt.point(0, 0)
    readonly property int dropCol: Math.max(0, Math.min(3, Math.floor(dragAt.x / (colWidth + 14))))
    function dropRow() {
        const list = lists[dropCol];
        const view = columnViews.itemAt(dropCol);
        const y = dragAt.y - columnsRow.y - view.listY + view.contentY;
        return Math.max(0, Math.min(list.length, Math.round(y / cardHeight)));
    }

    RiceText {
        id: header
        textFormat: Text.StyledText
        text: "backlog<font color='" + Theme.accent + "'>.</font>"
        font.pixelSize: 26
        font.weight: Font.ExtraBold
    }
    RiceText {
        anchors.left: header.right
        anchors.leftMargin: 12
        anchors.baseline: header.baseline
        text: "o topo de cada coluna é a prioridade · arraste ou use H/L e J/K"
        color: Theme.dim
    }

    Row {
        id: columnsRow
        anchors.top: header.bottom
        anchors.topMargin: 18
        anchors.bottom: parent.bottom
        spacing: 14
        Repeater {
            id: columnViews
            model: root.columns
            Rectangle {
                id: column
                required property var modelData
                required property int index
                readonly property var list: root.lists[index]
                readonly property real listY: list_.y
                readonly property real contentY: list_.contentY
                readonly property bool dropTarget: root.dragId !== "" && root.dropCol === index
                width: root.colWidth
                height: columnsRow.height
                color: dropTarget ? Theme.accentA : Theme.panel
                border.width: 1
                border.color: dropTarget ? Theme.accent : Theme.line
                Behavior on color { ColorAnimation { duration: 150 } }

                Row {
                    id: colHead
                    x: 12
                    y: 12
                    spacing: 8
                    RiceText { text: column.modelData[1]; color: Games.statusColor(column.modelData[0]); font.pixelSize: Theme.small; font.letterSpacing: 1.5 }
                    RiceText { text: column.list.length; color: Theme.faint; font.pixelSize: Theme.small }
                }
                RiceText {
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    y: 12
                    visible: column.modelData[0] === "want"
                    readonly property real est: column.list.reduce((s, g) => s + (g.est_hours || 0), 0)
                    text: est ? "~" + Math.round(est) + " h" : ""
                    color: Theme.faint
                    font.pixelSize: Theme.small
                }

                ListView {
                    id: list_
                    anchors.top: colHead.bottom
                    anchors.topMargin: 10
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 8
                    width: parent.width
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    model: column.list
                    displaced: Transition { NumberAnimation { properties: "y"; duration: 200; easing.type: Theme.ease } }
                    delegate: Item {
                        id: card
                        required property var modelData
                        required property int index
                        readonly property bool chosen: root.col === column.index && root.row === index
                        readonly property bool dragging: root.dragId === modelData.id
                        width: list_.width
                        height: root.cardHeight
                        opacity: dragging ? 0.3 : modelData.missing ? 0.45 : 1
                        Rectangle {
                            x: 8
                            width: parent.width - 16
                            height: parent.height - 6
                            color: cardMouse.containsMouse ? Theme.raise : "transparent"
                            border.width: 1
                            border.color: card.chosen ? Theme.accent : Theme.line
                            GameCover { id: mini; x: 6; y: 6; width: 39; height: 52; game: card.modelData; showTitle: false }
                            Column {
                                anchors.left: mini.right
                                anchors.leftMargin: 10
                                anchors.right: parent.right
                                anchors.rightMargin: 8
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 2
                                RiceText { width: parent.width; elide: Text.ElideRight; text: (column.index === 0 ? (card.index + 1) + ". " : "") + card.modelData.title; font.weight: Font.DemiBold }
                                RiceText {
                                    width: parent.width
                                    elide: Text.ElideRight
                                    readonly property real h: Games.hoursOf(card.modelData)
                                    text: (card.modelData.missing ? "sumiu · " : "") + card.modelData.source + (h ? " · " + (h < 10 ? h.toFixed(1) : Math.round(h)) + " h" : "")
                                          + (card.modelData.est_hours ? " / ~" + card.modelData.est_hours + " h" : "")
                                    color: card.modelData.missing ? Theme.red : Theme.dim
                                    font.pixelSize: 10
                                }
                                Rectangle {
                                    width: parent.width
                                    height: 2
                                    color: Theme.line
                                    Rectangle { height: parent.height; width: parent.width * (card.modelData.progress || 0) / 100; color: Games.statusColor(card.modelData.status) }
                                }
                            }
                        }
                        MouseArea {
                            id: cardMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: root.dragId ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                            property point pressAt
                            onPressed: mouse => { pressAt = Qt.point(mouse.x, mouse.y); root.col = column.index; root.row = card.index; }
                            onPositionChanged: mouse => {
                                if (!pressed) return;
                                const p = mapToItem(root, mouse.x, mouse.y);
                                if (!root.dragId && Math.hypot(mouse.x - pressAt.x, mouse.y - pressAt.y) > 6) root.dragId = card.modelData.id;
                                if (root.dragId) root.dragAt = p;
                            }
                            onReleased: {
                                if (root.dragId) { const id = root.dragId; const r = root.dropRow(); root.dragId = ""; root.place(id, root.dropCol, r); }
                                root.keyTarget.forceActiveFocus();
                            }
                            onDoubleClicked: root.open(card.modelData.id)
                        }
                    }
                    RiceText { anchors.horizontalCenter: parent.horizontalCenter; y: 20; visible: column.list.length === 0; text: "vazio"; color: Theme.faint; font.pixelSize: Theme.small }
                }
            }
        }
    }

    // The card being dragged follows the pointer.
    Rectangle {
        visible: root.dragId !== ""
        x: root.dragAt.x - width / 2
        y: root.dragAt.y - height / 2
        width: root.colWidth - 16
        height: root.cardHeight - 6
        color: Theme.sheet
        border.width: 1
        border.color: Theme.accent
        opacity: 0.92
        readonly property var g: root.dragId ? Games.byId(root.dragId) : null
        RiceText { anchors.centerIn: parent; width: parent.width - 20; elide: Text.ElideRight; horizontalAlignment: Text.AlignHCenter; text: parent.g ? parent.g.title : ""; font.weight: Font.DemiBold }
    }
}
