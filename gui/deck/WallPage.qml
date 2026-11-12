import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.components
import qs.deck

// LW // wall: the current wallpaper large, its palette, what follows it (greeter, lock),
// then every wallpaper as a grid. Click or ⏎ applies through the rice (the screen builds
// the new image, the palette follows); f marks a favorite, F shows only favorites.
Item {
    id: root

    property Item keyTarget: null
    readonly property var hints: []

    property var images: []
    property var thumbs: ({})
    property string current: ""
    property var favorites: []
    property bool favOnly: false
    property int cursor: 0
    property var greeter: ({})
    property var lock: ({})

    readonly property var shown: images.filter(i => !favOnly || favorites.indexOf(i.path) >= 0)
    readonly property var active: images.find(i => i.path === current) || null

    function stem(name) { return String(name).replace(/\.[^.]+$/, ""); }
    function meta(i) {
        if (!i) return "";
        return [i.size ? i.size[0] + "×" + i.size[1] : "", i.name.split(".").pop().toLowerCase(),
                i.bytes ? (i.bytes / 1048576).toFixed(1) + " MB" : ""].filter(x => x).join(" · ");
    }
    function apply(i) {
        if (!i || applier.running) return;
        if (i.path === current) { Status.say("● " + stem(i.name) + " já está ativo", Theme.dim); return; }
        Status.say("aplicando " + stem(i.name) + "…", Theme.accent);
        applier.call(["wallpaper", "apply", i.path, "--json"]);
    }
    function toggleFavorite(i) {
        if (!i) return;
        const next = favorites.slice(), at = next.indexOf(i.path);
        if (at >= 0) next.splice(at, 1); else next.push(i.path);
        favorites = next;
        favFile.setText(JSON.stringify(next, null, 2) + "\n");
        Status.say((at >= 0 ? "☆ " : "★ ") + stem(i.name), Theme.accent);
    }
    function moveCursor(step) {
        if (!shown.length) return;
        cursor = Math.max(0, Math.min(shown.length - 1, cursor + step));
        const row = Math.floor(cursor / grid.columns);
        const y = grid.y + row * grid.cellH;
        if (y < flick.contentY) flick.contentY = y;
        else if (y + grid.cellH > flick.contentY + flick.height) flick.contentY = y + grid.cellH - flick.height;
    }
    function handleKey(event) {
        const t = event.text;
        if (t === "h" || event.key === Qt.Key_Left) { moveCursor(-1); return true; }
        if (t === "l" || event.key === Qt.Key_Right) { moveCursor(1); return true; }
        if (t === "j" || event.key === Qt.Key_Down) { moveCursor(grid.columns); return true; }
        if (t === "k" || event.key === Qt.Key_Up) { moveCursor(-grid.columns); return true; }
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { apply(shown[cursor]); return true; }
        if (t === "f") { toggleFavorite(shown[cursor]); return true; }
        if (t === "F") { favOnly = !favOnly; cursor = 0; return true; }
        return false;
    }

    function refresh() { lister.call(["wallpaper", "list", "--json"]); greeterCmd.call(["greeter", "status", "--json"]); lockCmd.call(["lock", "status", "--json"]); }
    Component.onCompleted: refresh()
    // A wallpaper changed (here or elsewhere): the palette follows, so read everything again.
    Connections { target: Theme; function onDarkChanged() { root.refresh(); } }

    RiceCommand {
        id: lister
        onSucceeded: data => {
            const first = root.images.length === 0;
            root.images = data.images;
            root.current = data.current || "";
            if (first) {
                root.cursor = Math.max(0, root.shown.findIndex(i => i.active));
                if (data.images.some(i => !i.thumb)) maker.running = true;
            }
        }
    }
    RiceCommand {
        id: applier
        onSucceeded: (data, warnings) => {
            root.current = data.effective || root.current;
            Status.say(warnings.length ? "[ !! ] " + warnings.join("; ") : "● " + root.stem(root.current.split("/").pop()) + " aplicado",
                       warnings.length ? Theme.yel : Theme.ok);
        }
        onFailed: message => Status.say("[ !! ] " + message, Theme.red)
    }
    RiceCommand { id: greeterCmd; onSucceeded: data => root.greeter = data }
    RiceCommand { id: lockCmd; onSucceeded: data => root.lock = data }
    RiceCommand {
        id: greeterAuto
        onSucceeded: data => { root.greeter = Object.assign({}, root.greeter, { auto_sync: data.auto_sync }); Status.say("tela de login: envio automático " + (data.auto_sync ? "ligado" : "desligado"), Theme.accent); }
        onFailed: message => Status.say("[ !! ] " + message, Theme.red)
    }
    Process {
        id: maker
        command: Theme.rice.concat(["wallpaper", "thumbs"])
        stdout: SplitParser {
            onRead: line => {
                let item;
                try { item = JSON.parse(line); } catch (error) { return; }
                if (!item.thumb) return;
                const next = Object.assign({}, root.thumbs);
                next[item.path] = item.thumb;
                root.thumbs = next;
            }
        }
    }
    FileView {
        id: favFile
        path: Theme.guiStatePath + "/favorites.json"
        printErrors: false
        atomicWrites: true
        onLoaded: { try { root.favorites = JSON.parse(text()); } catch (error) { root.favorites = []; } }
    }

    Flickable {
        id: flick
        anchors.fill: parent
        contentHeight: body.height + 10
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        onContentYChanged: Deck.bump()

        Column {
            id: body
            width: flick.width
            spacing: 12

            Item {
                width: parent.width
                height: wallTitle.implicitHeight
                RiceText { id: wallTitle; textFormat: Text.StyledText; text: "wall<font color='" + Theme.accent + "'>.</font>"; font.pixelSize: 26; font.weight: Font.ExtraBold }
                RiceText { anchors.right: parent.right; anchors.baseline: wallTitle.baseline; text: root.images.length + " imagens · " + root.favorites.length + " ★"; color: Theme.dim; font.pixelSize: Theme.small }
            }

            // ---- hero: the wallpaper in use ------------------------------------
            Glass {
                width: parent.width
                height: 250
                Image {
                    anchors.fill: parent
                    anchors.margins: 1
                    source: root.current ? "file://" + root.current : ""
                    sourceSize.width: 1200
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                }
                Rectangle {
                    anchors.fill: parent
                    gradient: Gradient {
                        GradientStop { position: 0.5; color: "transparent" }
                        GradientStop { position: 1.0; color: Qt.rgba(0.05, 0.04, 0.035, 0.78) }
                    }
                }
                Column {
                    x: 16
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 14
                    RiceText { text: root.active ? root.stem(root.active.name) : "—"; font.pixelSize: 20; font.weight: Font.ExtraBold }
                    RiceText { text: root.meta(root.active); color: Theme.dim; font.pixelSize: Theme.small }
                }
                Rectangle {
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: 14
                    width: activeTag.implicitWidth + 14
                    height: activeTag.implicitHeight + 2
                    color: Qt.alpha(Theme.bg, 0.6)
                    border.width: 1
                    border.color: Theme.ok
                    RiceText { id: activeTag; anchors.centerIn: parent; text: "● ATIVO"; color: Theme.ok; font.pixelSize: 10 }
                }
            }

            // ---- palette + sync -------------------------------------------------
            Row {
                width: parent.width
                spacing: 12
                Glass {
                    k: true
                    width: (parent.width - 12) / 2
                    height: 92
                    RiceText { x: 16; y: 14; text: "PALETA"; color: Theme.dim; font.pixelSize: 10; font.letterSpacing: 2 }
                    RiceText { anchors.right: parent.right; anchors.rightMargin: 16; y: 14; text: "matugen"; color: Theme.dim; font.pixelSize: Theme.small }
                    Row {
                        x: 16
                        y: 44
                        width: parent.width - 32
                        height: 24
                        Repeater {
                            model: [Theme.bg, Theme.raise, Theme.accent, Theme.hot, Theme.ok, Theme.yel, Theme.red, Theme.blue, Theme.magenta, Theme.cyan, Theme.fg]
                            Rectangle {
                                required property color modelData
                                width: parent.width / 11
                                height: parent.height
                                color: modelData
                                Behavior on color { ColorAnimation { duration: 600 } }
                            }
                        }
                    }
                }
                Glass {
                    k: true
                    width: (parent.width - 12) / 2
                    height: 92
                    RiceText { x: 16; y: 14; text: "SYNC"; color: Theme.dim; font.pixelSize: 10; font.letterSpacing: 2 }
                    RiceText {
                        anchors.right: parent.right
                        anchors.rightMargin: 16
                        y: 14
                        readonly property double ns: root.greeter.last_sync_ns || 0
                        text: ns ? "login: " + Qt.formatDateTime(new Date(ns / 1e6), "dd/MM hh:mm") : ""
                        color: Theme.dim
                        font.pixelSize: Theme.small
                    }
                    Column {
                        x: 16
                        y: 38
                        width: parent.width - 32
                        // Greeter: the real automatic-sync switch.
                        Item {
                            width: parent.width
                            height: 24
                            RiceText { anchors.verticalCenter: parent.verticalCenter; text: "tela de login (envio automático)"; color: Theme.dim }
                            Rectangle {
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                width: 30
                                height: 16
                                color: "transparent"
                                border.width: 1
                                border.color: root.greeter.auto_sync ? Theme.accent : Theme.line2
                                Rectangle {
                                    x: root.greeter.auto_sync ? 17 : 3
                                    y: 3
                                    width: 8
                                    height: 8
                                    color: root.greeter.auto_sync ? Theme.accent : Theme.faint
                                    Behavior on x { NumberAnimation { duration: 250; easing.type: Theme.ease } }
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: greeterAuto.call(["greeter", "auto", root.greeter.auto_sync ? "off" : "on", "--json"])
                                }
                            }
                        }
                        Rectangle { width: parent.width; height: 1; color: Qt.rgba(1, 1, 1, 0.08) }
                        // Lock: always follows the wallpaper; its state is shown, not switched here.
                        Item {
                            width: parent.width
                            height: 24
                            RiceText { anchors.verticalCenter: parent.verticalCenter; text: "bloqueio de tela"; color: Theme.dim }
                            RiceText {
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.lock.enabled ? "● ativo · dim " + Math.round((root.lock.dim || 0) * 100) + "%" : "candidato"
                                color: root.lock.enabled ? Theme.ok : Theme.faint
                                font.pixelSize: Theme.small
                            }
                        }
                    }
                }
            }

            // ---- chips -------------------------------------------------------------
            Row {
                spacing: 6
                Chip { label: "todos " + root.images.length; on: !root.favOnly; onClicked: { root.favOnly = false; root.cursor = 0; root.keyTarget.forceActiveFocus(); } }
                Chip { label: "★ " + root.favorites.length; on: root.favOnly; onClicked: { root.favOnly = true; root.cursor = 0; root.keyTarget.forceActiveFocus(); } }
                RiceText { anchors.verticalCenter: parent.verticalCenter; leftPadding: 10; text: "⏎ aplica · f favorita · F só ★"; color: Theme.dim; font.pixelSize: 10 }
            }

            // ---- grid ----------------------------------------------------------------
            Grid {
                id: grid
                width: parent.width
                readonly property int columns_: Math.max(2, Math.floor(width / 190))
                columns: columns_
                spacing: 10
                readonly property real cellW: (width - (columns - 1) * spacing) / columns
                readonly property real cellH: Math.round(cellW * 10 / 16) + spacing
                property bool entering: true
                Timer { running: true; interval: 1200; onTriggered: grid.entering = false }
                Repeater {
                    model: root.shown
                    Item {
                        id: cell
                        required property var modelData
                        required property int index
                        readonly property bool isActive: modelData.path === root.current
                        readonly property bool chosen: index === root.cursor
                        readonly property string thumb: root.thumbs[modelData.path] || modelData.thumb || ""
                        width: grid.cellW
                        height: Math.round(grid.cellW * 10 / 16)
                        opacity: 0
                        transform: Translate { id: rise; y: Theme.motion && grid.entering ? 10 : 0 }
                        Component.onCompleted: {
                            if (Theme.motion && grid.entering) appear.start();
                            else { opacity = 1; rise.y = 0; }
                        }
                        SequentialAnimation {
                            id: appear
                            PauseAnimation { duration: Math.min(cell.index, 20) * 30 }
                            ParallelAnimation {
                                NumberAnimation { target: cell; property: "opacity"; to: 1; duration: 450; easing.type: Theme.ease }
                                NumberAnimation { target: rise; property: "y"; to: 0; duration: 450; easing.type: Theme.ease }
                            }
                        }
                        Rectangle {
                            anchors.fill: parent
                            color: Theme.raise
                            clip: true
                            border.width: 1
                            border.color: cell.isActive || cell.chosen ? Theme.accent : Qt.rgba(1, 1, 1, 0.08)
                            Image {
                                anchors.fill: parent
                                anchors.margins: 1
                                source: cell.thumb ? "file://" + cell.thumb : ""
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                scale: hover.containsMouse ? 1.04 : 1
                                opacity: hover.containsMouse || cell.isActive || cell.chosen ? 1 : 0.8
                                Behavior on scale { NumberAnimation { duration: 500; easing.type: Theme.ease } }
                                Behavior on opacity { NumberAnimation { duration: 300 } }
                            }
                            RiceText {
                                x: 8
                                anchors.bottom: parent.bottom
                                anchors.bottomMargin: 6
                                width: parent.width - 16
                                elide: Text.ElideRight
                                text: root.stem(cell.modelData.name)
                                font.pixelSize: 11
                                style: Text.Outline
                                styleColor: Qt.rgba(0, 0, 0, 0.55)
                            }
                            RiceText { visible: root.favorites.indexOf(cell.modelData.path) >= 0; anchors.right: parent.right; anchors.rightMargin: 6; y: 4; text: "★"; color: Theme.accent; font.pixelSize: 14 }
                            Rectangle {
                                visible: cell.isActive
                                x: 6
                                y: 6
                                width: on_.implicitWidth + 12
                                height: on_.implicitHeight + 2
                                color: Qt.alpha(Theme.bg, 0.6)
                                border.width: 1
                                border.color: Theme.ok
                                RiceText { id: on_; anchors.centerIn: parent; text: "● ATIVO"; color: Theme.ok; font.pixelSize: 10 }
                            }
                        }
                        MouseArea {
                            id: hover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: { root.cursor = cell.index; root.apply(cell.modelData); root.keyTarget.forceActiveFocus(); }
                        }
                    }
                }
            }
        }
    }
}
