//@ pragma UseQApplication
import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.components

// Opened on demand by `rice gui`; closing the window ends the process.
// Look and behaviour follow docs/lw-prototype.html; all tokens live in Theme.qml.
FloatingWindow {
    id: window

    readonly property var screens: [
        { name: "WALLPAPERS", source: "screens/WallpaperScreen.qml", hints: [] },
        { name: "SHORTCUTS", source: "screens/ShortcutsScreen.qml", hints: [] },
        { name: "PROFILES", source: "screens/ProfilesScreen.qml", hints: [] },
        { name: "PALETTE", source: "screens/PaletteScreen.qml", hints: [["1-8", "tab"], ["esc", "quit"]] },
        { name: "DOCTOR", source: "screens/DoctorScreen.qml", hints: [["1-8", "tab"], ["esc", "quit"]] },
        { name: "BACKUPS", source: "screens/BackupsScreen.qml", hints: [["jk", "move"], ["esc", "quit"]] },
        { name: "LOCK", source: "screens/LockScreen.qml", hints: [["1-8", "tab"], ["esc", "quit"]] },
        { name: "GREETER", source: "screens/GreeterScreen.qml", hints: [["1-8", "tab"], ["esc", "quit"]] }
    ]
    property int current: 0
    property var status: ({})
    property bool statusLoaded: false
    property string syncError: ""
    readonly property var hints: screen.item && screen.item.hints ? screen.item.hints : screens[current].hints

    title: "LW // CONTROL"
    implicitWidth: 1220
    implicitHeight: 780
    color: Theme.bg
    onVisibleChanged: if (!visible) Qt.quit()

    function select(index) {
        current = Math.max(0, Math.min(screens.length - 1, index));
    }

    IpcHandler {
        target: "rice"
        function close(): void { Qt.quit(); }
        function open(index: int): void { window.select(index); }
        function toggleLog(): void { log.visible = !log.visible; }
        function shot(path: string): void { content.grabToImage(result => result.saveToFile(path)); }
        function key(name: string): void {
            const named = { Return: Qt.Key_Return, Escape: Qt.Key_Escape, Left: Qt.Key_Left, Right: Qt.Key_Right, Up: Qt.Key_Up, Down: Qt.Key_Down, Slash: Qt.Key_Slash };
            // "SUPER+SHIFT+X" style: modifiers before the last token.
            const parts = name.length > 1 && name.indexOf("+") > 0 ? name.split("+") : [name];
            const last = parts.pop();
            const flags = { SUPER: Qt.MetaModifier, CONTROL: Qt.ControlModifier, ALT: Qt.AltModifier, SHIFT: Qt.ShiftModifier };
            let modifiers = last.length === 1 && last !== last.toLowerCase() && parts.length === 0 ? Qt.ShiftModifier : 0;
            for (const m of parts) modifiers |= flags[m] || 0;
            const code = named[last] || last.toUpperCase().charCodeAt(0);
            window.handle({ key: code, text: named[last] ? "" : last, modifiers: modifiers, accepted: false });
        }
    }

    RiceCommand {
        id: statusCommand
        onSucceeded: data => {
            window.status = data;
            window.statusLoaded = true;
            Theme.terminal = data.terminal;
            Status.wallpaper = data.wallpaper ? (data.wallpaper.effective || "") : "";
        }
        onFailed: message => {
            window.statusLoaded = true;
            console.warn("status:", message);
        }
        Component.onCompleted: call(["status", "--json"])
    }

    RiceCommand {
        id: syncCommand
        onFailed: message => window.syncError = message
    }

    Connections {
        target: log
        function onEntriesChanged() {
            if (screen.item && screen.item.externalChange)
                screen.item.externalChange();
            // Wallpaper, palette or profile may have changed: refresh the CURRENT block.
            statusCommand.call(["status", "--json"]);
        }
    }

    Connections {
        target: Theme
        function onDarkChanged() { statusCommand.call(["status", "--json"]); }
    }

    Item {
        id: keys
        anchors.fill: parent
        focus: true

        Keys.onPressed: event => window.handle(event)
    }

    // Test hook: `qs ipc -p gui call rice key l` reaches only this window, never the focused one.
    function handle(event) {
        {
            if (boot.visible) {
                boot.finish();
                event.accepted = true;
                return;
            }
            const digit = parseInt(event.text);
            if (screen.item && screen.item.handleKey && screen.item.handleKey(event)) {
                event.accepted = true;
                return;
            }
            if (event.key === Qt.Key_Q || event.key === Qt.Key_Escape)
                Qt.quit();
            else if (event.key === Qt.Key_Down || event.key === Qt.Key_J)
                window.select(window.current + 1);
            else if (event.key === Qt.Key_Up || event.key === Qt.Key_K)
                window.select(window.current - 1);
            else if (digit >= 1 && digit <= window.screens.length)
                window.select(digit - 1);
            else
                return;
            event.accepted = true;
        }
    }

    Item {
        id: content
        anchors.fill: parent
        // Solid background, so window grabs look like the screen.
        Rectangle { anchors.fill: parent; color: Theme.bg }
        // ================= SIDEBAR =================
        Rectangle {
            id: sidebar
            anchors.top: parent.top
            anchors.bottom: footer.top
            width: 232
            color: Theme.panel

            Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.line }

            Logo {
                id: logo
                x: 22
                y: 30
            }

            Item {
                id: sub
                anchors.top: logo.bottom
                anchors.topMargin: 10
                x: 22
                width: parent.width - 44
                height: subText.implicitHeight
                RiceText { id: subText; text: "// control"; color: Theme.dim }
                RiceText { anchors.right: parent.right; text: "v0.1"; color: Theme.faint }
            }

            RiceText {
                id: menuLabel
                anchors.top: sub.bottom
                anchors.topMargin: 28
                x: 22
                text: "MENU"
                color: Theme.faint
                font.pixelSize: Theme.small
                font.letterSpacing: 1.5
            }

            Item {
                id: nav
                anchors.top: menuLabel.bottom
                anchors.topMargin: 8
                width: parent.width - 1
                height: navColumn.height

                // The active band slides between rows.
                Rectangle {
                    width: parent.width
                    height: 29
                    y: window.current * 29
                    color: Theme.accentA
                    Rectangle { width: 2; height: parent.height; color: Theme.accent }
                    Behavior on y { NumberAnimation { duration: Theme.tMed; easing.type: Theme.ease } }
                }

                Column {
                    id: navColumn
                    width: parent.width
                    Repeater {
                        model: window.screens
                        NavItem {
                            required property var modelData
                            required property int index
                            number: index + 1
                            label: modelData.name
                            active: window.current === index
                            onClicked: window.select(index)
                        }
                    }
                }
            }

            // CURRENT: what is applied right now.
            Column {
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 18
                x: 22
                width: parent.width - 44
                spacing: 6

                RiceText {
                    text: "CURRENT"
                    color: Theme.faint
                    font.pixelSize: Theme.small
                    font.letterSpacing: 1.5
                    bottomPadding: 2
                }

                Rectangle {
                    width: parent.width
                    height: Math.round(width * 10 / 16)
                    color: Theme.raise
                    border.width: 1
                    border.color: Theme.line2

                    Image {
                        anchors.fill: parent
                        anchors.margins: 1
                        source: window.wallpaper ? "file://" + window.wallpaper : ""
                        sourceSize.width: 380
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        clip: true
                    }
                    Rectangle {
                        x: 6
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 5
                        width: Math.min(parent.width - 12, wallName.implicitWidth + 10)
                        height: wallName.implicitHeight
                        color: Qt.alpha(Theme.bg, 0.8)
                        visible: wallName.text !== ""
                        RiceText {
                            id: wallName
                            x: 5
                            width: parent.width - 10
                            elide: Text.ElideRight
                            font.pixelSize: 10
                            text: window.wallpaper.split("/").pop().replace(/\.[^.]+$/, "")
                        }
                    }
                }

                Row {
                    width: parent.width
                    spacing: 3
                    Repeater {
                        model: [Theme.accent, Theme.red, Theme.yel, Theme.ok, Theme.cyan, Theme.blue]
                        Rectangle {
                            required property color modelData
                            width: (parent.width - 15) / 6
                            height: 14
                            color: modelData
                            Behavior on color { ColorAnimation { duration: Theme.tMed } }
                        }
                    }
                }

                Item {
                    width: parent.width
                    height: profileLabel.implicitHeight + 4
                    RiceText { id: profileLabel; y: 4; text: "profile"; color: Theme.dim }
                    RiceText { y: 4; anchors.right: parent.right; text: Theme.profile || window.status.profile || "--" }
                }
            }
        }

        Loader {
            id: screen
            anchors.top: parent.top
            anchors.bottom: footer.top
            anchors.left: sidebar.right
            anchors.right: parent.right
            anchors.leftMargin: 26
            anchors.rightMargin: 26
            anchors.topMargin: 22
            anchors.bottomMargin: 14
            source: window.screens[window.current].source || "screens/PlaceholderScreen.qml"
            onLoaded: {
                if (item.title !== undefined)
                    item.title = window.screens[window.current].name;
                if (item.keyTarget !== undefined)
                    item.keyTarget = keys;
                // Each tab enters with a short fade (refined only).
                item.opacity = Theme.motion ? 0 : 1;
                enter.restart();
            }
            NumberAnimation { id: enter; target: screen.item; property: "opacity"; to: 1; duration: Theme.tMed; easing.type: Theme.ease }
        }

        // ================= STATUS BAR =================
        Rectangle {
            id: footer
            anchors.bottom: parent.bottom
            width: parent.width
            height: 34
            color: Theme.panel

            Rectangle { width: parent.width; height: 1; color: Theme.line }

            Row {
                id: leftBlocks
                height: parent.height

                StatusBlock {
                    id: syncButton
                    label: syncCommand.running ? "SYNCING" : "SYNC ALL"
                    clickable: !syncCommand.running
                    onClicked: {
                        window.syncError = "";
                        syncCommand.call(["sync", "--json"]);
                    }
                }
                StatusBlock {
                    label: clock.text
                    textColor: Theme.ok
                    textFormat: Text.StyledText
                }
            }

            StatusBlock {
                id: message
                anchors.left: leftBlocks.right
                anchors.right: hintBlock.left
                label: typed.shown
                textColor: window.syncError ? Theme.red : Status.busy ? Theme.accent
                         : Status.message ? Status.color : Theme.statusColor(log.lastStatus)
                separator: false
                elide: true
            }

            StatusBlock {
                id: hintBlock
                anchors.right: logButton.left
                leftSeparator: true
                textColor: Theme.faint
                textFormat: Text.StyledText
                label: window.hints.map(h => "<font color='" + Theme.dim + "'>" + h[0] + "</font> " + h[1]).join("&nbsp;&nbsp;&nbsp;")
            }

            StatusBlock {
                id: logButton
                anchors.right: parent.right
                separator: false
                label: log.visible ? "LOG v" : "LOG ^"
                clickable: true
                onClicked: log.visible = !log.visible
            }
        }

        LogPanel {
            id: log
            anchors.bottom: footer.top
            width: parent.width
            height: 260
            visible: false
        }

        // Corners, as in a terminal frame.
        RiceText { x: 8; y: 6; text: "┌"; color: Theme.faint; font.pixelSize: 11 }
        RiceText { anchors.right: parent.right; anchors.rightMargin: 8; y: 6; text: "┐"; color: Theme.faint; font.pixelSize: 11 }

        BootScreen {
            id: boot
            anchors.fill: parent
            steps: [
                { label: "reading profile: " + (Theme.profile || "?"), done: Theme.profile !== "" },
                { label: "loading palette " + (window.status.generation || ""), done: Object.keys(Theme.dark).length > 0 },
                { label: "reading rice status", done: window.statusLoaded },
                { label: "reading action log", done: log.loaded },
                { label: "loading " + window.screens[window.current].name.toLowerCase(), done: screen.status === Loader.Ready },
                { label: "starting control panel", done: true }
            ]
            onFinished: keys.forceActiveFocus()
        }
    }

    readonly property string wallpaper: status.wallpaper ? (status.wallpaper.effective || "") : ""

    // hh:mm:ss with blinking colons.
    QtObject {
        id: clock
        property date now: new Date()
        property bool blink: true
        readonly property string colon: blink || !Theme.motion ? ":" : "<font color='" + Theme.panel + "'>:</font>"
        readonly property string text: Qt.formatTime(now, "hh") + colon + Qt.formatTime(now, "mm") + colon + Qt.formatTime(now, "ss")
    }
    Timer {
        interval: 500
        running: true
        repeat: true
        onTriggered: {
            clock.blink = !clock.blink;
            if (clock.blink)
                clock.now = new Date();
        }
    }

    // A new log entry replaces any short message from a screen.
    Connections {
        target: log
        function onLastLineChanged() { Status.message = ""; }
    }

    // While something runs, an ASCII bar fills to 15/16 and waits for the result.
    QtObject {
        id: progress
        property int filled: 0
        readonly property string text: Theme.motion
            ? Status.busy + " [" + "#".repeat(filled) + "-".repeat(16 - filled) + "]"
            : "[ .. ] " + Status.busy
    }
    Timer {
        running: Status.busy !== ""
        interval: 30
        repeat: true
        onRunningChanged: progress.filled = 0
        onTriggered: if (progress.filled < 15) progress.filled++
    }

    // The last log line is typed out, one character every 12 ms.
    QtObject {
        id: typed
        readonly property string full: window.syncError ? "[ FAIL ] " + window.syncError
            : Status.busy ? progress.text
            : Status.message || log.lastLine
        property int count: 0
        // One line only: log details may contain newlines.
        readonly property string flat: full.replace(/\s*\n\s*/g, " ")
        readonly property string shown: Theme.motion && !Status.busy ? flat.slice(0, count) : flat
        onFullChanged: if (!Status.busy) { count = 0; typer.restart(); }
    }
    Timer {
        id: typer
        interval: 12
        repeat: true
        onTriggered: if (++typed.count >= typed.full.length) stop()
    }
}
