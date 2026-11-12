import QtQuick
import Quickshell.Io
import qs
import qs.components

// LW // WALLPAPERS — 4-corner cursor, ACTIVE/★ tags, favorites kept on disk.
Item {
    id: root

    property Item keyTarget: null
    property var images: []
    property var thumbs: ({})
    property int thumbsDone: 0
    property int thumbsTotal: 0
    property string current: ""
    property bool favOnly: false
    property var favorites: []
    // Entrance stagger only for the first fill, not for delegates created while scrolling.
    property bool entering: true

    readonly property var hints: [["←↑↓→", "move"], ["⏎", "apply"], ["f", "fav"], ["F", "filter"], ["/", "search"]]
    readonly property int columns: 4
    readonly property int gap: 14

    readonly property var shown: {
        const needle = search.text.toLowerCase();
        return images.filter(image => image.name.toLowerCase().includes(needle)
                             && (!favOnly || favorites.indexOf(image.path) >= 0));
    }
    readonly property var selected: shown[grid.currentIndex] || null

    function stem(name) { return name.replace(/\.[^.]+$/, ""); }
    function megabytes(bytes) { return bytes ? (bytes / 1048576).toFixed(1) + "M" : "?"; }
    function resolution(image) { return image && image.size ? image.size[0] + "x" + image.size[1] : "?"; }

    function apply() {
        if (!selected || applier.running)
            return;
        Status.start("applying");
        applier.call(["wallpaper", "apply", selected.path, "--json"]);
    }

    function toggleFavorite() {
        if (!selected)
            return;
        const path = selected.path, name = stem(selected.name);
        const next = favorites.slice();
        const at = next.indexOf(path);
        if (at >= 0) next.splice(at, 1); else next.push(path);
        favorites = next;
        favFile.setText(JSON.stringify(next, null, 2) + "\n");
        Status.say(at >= 0 ? "[ - ] " + name + " unfavorited" : "[ ★ ] " + name + " favorited", Theme.accent);
    }

    function handleKey(event) {
        if (event.text === "F") { favOnly = !favOnly; grid.currentIndex = 0; return true; }
        if (event.text === "f") { toggleFavorite(); return true; }
        switch (event.key) {
        case Qt.Key_Left: grid.moveCurrentIndexLeft(); return true;
        case Qt.Key_Right: grid.moveCurrentIndexRight(); return true;
        case Qt.Key_Up: grid.moveCurrentIndexUp(); return true;
        case Qt.Key_Down: grid.moveCurrentIndexDown(); return true;
        case Qt.Key_Return: case Qt.Key_Enter: apply(); return true;
        case Qt.Key_Slash: search.focusInput(); return true;
        }
        return false;
    }

    Component.onCompleted: lister.call(["wallpaper", "list", "--json"])
    Timer { running: true; interval: 900; onTriggered: root.entering = false }

    // A wallpaper changed elsewhere (Waypaper, TUI) also republishes the palette.
    Connections {
        target: Theme
        function onDarkChanged() { lister.call(["wallpaper", "list", "--json"]); }
    }

    FileView {
        id: favFile
        path: Theme.guiStatePath + "/favorites.json"
        printErrors: false
        atomicWrites: true
        onLoaded: {
            try { root.favorites = JSON.parse(text()); } catch (error) { root.favorites = []; }
        }
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
        onFailed: message => Status.say("[ FAIL ] " + message, Theme.red)
    }

    RiceCommand {
        id: applier
        onSucceeded: (data, warnings) => {
            Status.stop();
            root.current = data.effective || root.current;
            if (warnings.length > 0)
                Status.say("[ WARN ] " + warnings.join("; "), Theme.yel);
            else
                Status.say("[ OK ] " + root.stem(data.effective.split("/").pop()) + " applied", Theme.ok);
        }
        onFailed: message => { Status.stop(); Status.say("[ FAIL ] " + message, Theme.red); }
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

    RiceHeader {
        id: title
        width: parent.width - search.width - 14
        title: "WALLPAPERS"
        note: root.shown.length + "/" + root.images.length + (maker.running ? "  previews " + root.thumbsDone + "/" + root.thumbsTotal : "")
    }

    SearchBox {
        id: search
        anchors.right: parent.right
        anchors.verticalCenter: title.verticalCenter
        keyTarget: root.keyTarget
        onTextChanged: grid.currentIndex = 0
    }

    Row {
        id: filters
        anchors.top: title.bottom
        anchors.topMargin: 14
        spacing: 6
        Chip { label: "ALL"; on: !root.favOnly; onClicked: { root.favOnly = false; grid.currentIndex = 0; } }
        Chip { label: "★ FAV"; on: root.favOnly; onClicked: { root.favOnly = true; grid.currentIndex = 0; } }
    }
    RiceText {
        anchors.right: parent.right
        anchors.verticalCenter: filters.verticalCenter
        text: "f favoritar · F filtrar"
        color: Theme.faint
        font.pixelSize: Theme.small
    }

    GridView {
        id: grid
        anchors.top: filters.bottom
        anchors.topMargin: 6
        anchors.bottom: info.top
        anchors.bottomMargin: 10
        anchors.left: parent.left
        anchors.leftMargin: -root.gap / 2
        anchors.right: parent.right
        anchors.rightMargin: -root.gap / 2
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        topMargin: 14
        bottomMargin: 14
        cellWidth: Math.floor(width / root.columns)
        cellHeight: Math.round((cellWidth - root.gap) * 10 / 16) + root.gap
        cacheBuffer: 600
        highlightMoveDuration: Theme.tMed
        model: root.shown

        delegate: Item {
            id: cell

            required property var modelData
            required property int index
            readonly property string thumb: root.thumbs[modelData.path] || modelData.thumb || ""
            readonly property bool selected: GridView.isCurrentItem
            readonly property bool lit: selected || mouse.containsMouse
            readonly property bool active: modelData.path === root.current
            readonly property bool favorite: root.favorites.indexOf(modelData.path) >= 0

            width: grid.cellWidth
            height: grid.cellHeight

            // Staggered entrance: 24 ms apart, 8 px rise.
            opacity: 0
            transform: Translate { id: rise; y: Theme.motion && root.entering ? 8 : 0 }
            Component.onCompleted: {
                if (Theme.motion && root.entering) {
                    entrance.start();
                } else {
                    opacity = 1;
                    rise.y = 0;
                }
            }
            SequentialAnimation {
                id: entrance
                PauseAnimation { duration: cell.index * 24 }
                ParallelAnimation {
                    NumberAnimation { target: cell; property: "opacity"; to: 1; duration: Theme.tMed; easing.type: Theme.ease }
                    NumberAnimation { target: rise; property: "y"; to: 0; duration: Theme.tMed; easing.type: Theme.ease }
                }
            }

            Item {
                id: frame
                anchors.fill: parent
                anchors.margins: root.gap / 2

                Rectangle {
                    anchors.fill: parent
                    color: Theme.raise
                    border.width: 1
                    border.color: Theme.line
                    clip: true

                    Image {
                        id: preview
                        anchors.fill: parent
                        anchors.margins: 1
                        source: cell.thumb ? "file://" + cell.thumb : ""
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        scale: mouse.containsMouse ? 1.04 : 1
                        Behavior on scale { NumberAnimation { duration: Theme.tMed; easing.type: Theme.ease } }
                    }
                    // Out of focus at ~75% brightness.
                    Rectangle {
                        anchors.fill: parent
                        color: "black"
                        opacity: cell.lit ? 0 : 0.26
                        Behavior on opacity { NumberAnimation { duration: Theme.tFast } }
                    }

                    RiceText {
                        anchors.centerIn: parent
                        visible: preview.status !== Image.Ready
                        text: maker.running ? "[ ... ]" : "[ no preview ]"
                        color: Theme.dim
                    }

                    // Sliding caption: name and resolution.
                    Rectangle {
                        width: parent.width
                        height: caption.height + 21
                        y: parent.height - height + (cell.lit ? 0 : 6)
                        opacity: cell.lit ? 1 : 0
                        gradient: Gradient {
                            GradientStop { position: 0; color: "transparent" }
                            GradientStop { position: 1; color: Qt.alpha(Theme.bg, 0.9) }
                        }
                        Behavior on y { NumberAnimation { duration: Theme.tFast; easing.type: Theme.ease } }
                        Behavior on opacity { NumberAnimation { duration: Theme.tFast } }
                        Item {
                            id: caption
                            x: 8
                            width: parent.width - 16
                            anchors.bottom: parent.bottom
                            anchors.bottomMargin: 5
                            height: capName.implicitHeight
                            RiceText {
                                id: capName
                                width: parent.width - capRes.width - 8
                                elide: Text.ElideRight
                                text: root.stem(cell.modelData.name)
                                font.pixelSize: 11
                            }
                            RiceText {
                                id: capRes
                                anchors.right: parent.right
                                text: root.resolution(cell.modelData)
                                color: Theme.dim
                                font.pixelSize: 11
                            }
                        }
                    }
                }

                // Tags: ● ACTIVE and ★.
                Row {
                    x: 6
                    y: 6
                    spacing: 4
                    Tag { visible: cell.active; label: "● ACTIVE"; tint: Theme.ok }
                    Tag { visible: cell.favorite; label: "★"; tint: Theme.accent }
                }

                // Cursor: four accent corners, not a full border.
                Item {
                    anchors.fill: parent
                    anchors.margins: -6
                    opacity: cell.selected ? 1 : 0
                    scale: cell.selected ? 1 : 1.06
                    Behavior on opacity { NumberAnimation { duration: Theme.tFast; easing.type: Theme.ease } }
                    Behavior on scale { NumberAnimation { duration: Theme.tMed; easing.type: Theme.ease } }
                    Repeater {
                        model: [[0, 0], [1, 0], [0, 1], [1, 1]]
                        Item {
                            required property var modelData
                            x: modelData[0] ? parent.width - 14 : 0
                            y: modelData[1] ? parent.height - 14 : 0
                            width: 14
                            height: 14
                            Rectangle { width: 14; height: 2; y: parent.modelData[1] ? 12 : 0; color: Theme.accent }
                            Rectangle { width: 2; height: 14; x: parent.modelData[0] ? 12 : 0; color: Theme.accent }
                        }
                    }
                }
            }

            MouseArea {
                id: mouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    grid.currentIndex = cell.index;
                    root.keyTarget.forceActiveFocus();
                }
                onDoubleClicked: root.apply()
            }
        }

        RiceText {
            anchors.centerIn: parent
            visible: root.shown.length === 0 && root.images.length > 0
            horizontalAlignment: Text.AlignHCenter
            text: "¯\\_(ツ)_/¯\n\nnada encontrado"
            color: Theme.faint
        }
    }

    // Fade at the top and bottom of the scroll area.
    Rectangle {
        anchors.top: grid.top
        width: parent.width
        height: 22
        gradient: Gradient {
            GradientStop { position: 0; color: Theme.base }
            GradientStop { position: 1; color: Qt.alpha(Theme.bg, 0) }
        }
    }
    Rectangle {
        anchors.bottom: grid.bottom
        width: parent.width
        height: 22
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.alpha(Theme.bg, 0) }
            GradientStop { position: 1; color: Theme.base }
        }
    }

    // name │ resolution │ format │ size                APPLY ⏎
    Item {
        id: info
        anchors.bottom: parent.bottom
        width: parent.width
        height: applyButton.height + 10

        Rectangle { width: parent.width; height: 1; color: Theme.line }

        RiceText {
            anchors.verticalCenter: applyButton.verticalCenter
            width: parent.width - applyButton.width - 14
            elide: Text.ElideMiddle
            textFormat: Text.StyledText
            readonly property string sep: " <font color='" + Theme.faint + "'>│</font> "
            text: !root.selected ? "" :
                  "<b><font color='" + Theme.fg + "'>" + root.stem(root.selected.name) + "</font></b>" + sep
                  + root.resolution(root.selected) + sep
                  + root.selected.name.split(".").pop().toLowerCase() + sep
                  + root.megabytes(root.selected.bytes)
            color: Theme.dim
        }

        AccentButton {
            id: applyButton
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            label: applier.running ? "APPLYING" : "APPLY ⏎"
            enabledState: !applier.running && root.selected !== null
            onClicked: root.apply()
        }
    }
}
