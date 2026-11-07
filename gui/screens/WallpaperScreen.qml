import QtQuick
import Quickshell.Io
import qs
import qs.components

Item {
    id: root

    property Item keyTarget: null
    property var images: []
    property var thumbs: ({})
    property int thumbsDone: 0
    property int thumbsTotal: 0
    property string query: ""
    property string current: ""
    property string message: ""
    property color messageColor: Theme.muted

    readonly property var shown: {
        const needle = query.toLowerCase();
        return images.filter(image => image.name.toLowerCase().includes(needle));
    }
    readonly property var selected: shown[grid.currentIndex] || null

    function report(text, color) {
        message = text;
        messageColor = color;
    }

    function apply() {
        if (!selected || applier.running)
            return;
        report("[ RUNNING ] applying " + selected.name, Theme.muted);
        applier.call(["wallpaper", "apply", selected.path, "--json"]);
    }

    function handleKey(event) {
        switch (event.key) {
        case Qt.Key_Left: case Qt.Key_H: grid.moveCurrentIndexLeft(); return true;
        case Qt.Key_Right: case Qt.Key_L: grid.moveCurrentIndexRight(); return true;
        case Qt.Key_Up: case Qt.Key_K: grid.moveCurrentIndexUp(); return true;
        case Qt.Key_Down: case Qt.Key_J: grid.moveCurrentIndexDown(); return true;
        case Qt.Key_Return: case Qt.Key_Enter: apply(); return true;
        case Qt.Key_Slash: search.forceActiveFocus(); return true;
        }
        return false;
    }

    Component.onCompleted: lister.call(["wallpaper", "list", "--json"])

    // A wallpaper changed elsewhere (Waypaper, TUI) also republishes the palette.
    Connections {
        target: Theme
        function onDarkChanged() { lister.call(["wallpaper", "list", "--json"]); }
    }

    RiceCommand {
        id: lister
        onSucceeded: data => {
            const first = root.images.length === 0;
            root.images = data.images;
            root.current = data.current || "";
            if (first) {
                grid.currentIndex = Math.max(0, root.shown.findIndex(image => image.active));
                grid.positionViewAtIndex(grid.currentIndex, GridView.Center);
                root.thumbsTotal = data.images.filter(image => !image.thumb).length;
                if (root.thumbsTotal > 0)
                    maker.running = true;
            }
        }
        onFailed: message => root.report("[ FAIL ] " + message, Theme.fail)
    }

    RiceCommand {
        id: applier
        onSucceeded: (data, warnings) => {
            root.current = data.effective || root.current;
            if (warnings.length > 0)
                root.report("[ WARN ] " + warnings.join("; "), Theme.warn);
            else
                root.report("[ OK ] " + data.result, Theme.ok);
        }
        onFailed: message => root.report("[ FAIL ] " + message, Theme.fail)
    }

    Process {
        id: maker
        command: Theme.rice.concat(["wallpaper", "thumbs"])
        stdout: SplitParser {
            onRead: line => {
                const item = JSON.parse(line);
                root.thumbsDone++;
                if (!item.thumb)
                    return;
                const next = Object.assign({}, root.thumbs);
                next[item.path] = item.thumb;
                root.thumbs = next;
            }
        }
    }

    RiceText {
        id: title
        text: "RICE // WALLPAPERS"
        color: Theme.accent
        font.bold: true
    }

    RiceText {
        anchors.left: title.right
        anchors.leftMargin: 16
        anchors.verticalCenter: title.verticalCenter
        color: Theme.muted
        text: root.shown.length + "/" + root.images.length
            + (maker.running ? "  previews " + root.thumbsDone + "/" + root.thumbsTotal : "")
    }

    Rectangle {
        anchors.right: parent.right
        anchors.verticalCenter: title.verticalCenter
        width: 240
        height: 28
        color: "transparent"
        border.width: 1
        border.color: search.activeFocus ? Theme.accent : Theme.outline

        TextInput {
            id: search
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            verticalAlignment: TextInput.AlignVCenter
            clip: true
            color: Theme.text
            selectionColor: Theme.accent
            font.family: Theme.font
            font.pixelSize: Theme.fontSize
            onTextChanged: {
                root.query = text;
                grid.currentIndex = 0;
            }
            Keys.onEscapePressed: {
                text = "";
                root.keyTarget.forceActiveFocus();
            }
            Keys.onReturnPressed: root.keyTarget.forceActiveFocus()
        }

        RiceText {
            anchors.verticalCenter: parent.verticalCenter
            x: 8
            visible: search.text === "" && !search.activeFocus
            text: "search  /"
            color: Theme.muted
        }
    }

    GridView {
        id: grid
        anchors.top: title.bottom
        anchors.topMargin: 14
        anchors.bottom: bar.top
        anchors.bottomMargin: 10
        width: parent.width
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        cellWidth: width / Math.max(1, Math.floor(width / 220))
        cellHeight: cellWidth * 0.62
        cacheBuffer: 400
        model: root.shown

        delegate: Item {
            id: cell

            required property var modelData
            required property int index
            readonly property string thumb: root.thumbs[modelData.path] || modelData.thumb || ""
            readonly property bool selected: GridView.isCurrentItem

            width: grid.cellWidth
            height: grid.cellHeight

            Rectangle {
                anchors.fill: parent
                anchors.margins: 5
                color: Theme.surfaceAlt
                border.width: cell.selected ? 2 : 1
                border.color: cell.selected ? Theme.accent : Theme.outline

                Image {
                    id: preview
                    anchors.fill: parent
                    anchors.margins: 2
                    source: cell.thumb ? "file://" + cell.thumb : ""
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    clip: true
                }

                RiceText {
                    anchors.centerIn: parent
                    visible: preview.status !== Image.Ready
                    text: maker.running ? "[ ... ]" : "[ no preview ]"
                    color: Theme.muted
                }

                Rectangle {
                    visible: cell.modelData.path === root.current
                    x: 2
                    y: 2
                    width: active.implicitWidth + 10
                    height: active.implicitHeight + 4
                    color: Theme.accent

                    RiceText {
                        id: active
                        anchors.centerIn: parent
                        text: "[*]"
                        color: Theme.onAccent
                        font.bold: true
                    }
                }
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    grid.currentIndex = cell.index;
                    root.keyTarget.forceActiveFocus();
                }
                onDoubleClicked: root.apply()
            }
        }
    }

    Item {
        id: bar
        anchors.bottom: parent.bottom
        width: parent.width
        height: applyButton.height

        RiceText {
            anchors.verticalCenter: parent.verticalCenter
            anchors.right: applyButton.left
            anchors.rightMargin: 14
            width: parent.width - applyButton.width - 14
            elide: Text.ElideMiddle
            text: root.message || (root.selected ? root.selected.name : "")
            color: root.message ? root.messageColor : Theme.muted
        }

        RiceButton {
            id: applyButton
            anchors.right: parent.right
            label: applier.running ? "APPLYING" : "APPLY"
            enabledState: !applier.running && root.selected !== null
            onClicked: root.apply()
        }
    }

    Connections {
        target: grid
        function onCurrentIndexChanged() {
            if (!applier.running)
                root.message = "";
        }
    }
}
