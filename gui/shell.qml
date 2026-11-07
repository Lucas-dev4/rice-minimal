//@ pragma UseQApplication
import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.components

// Opened on demand by `rice gui`; closing the window ends the process.
FloatingWindow {
    id: window

    readonly property var screens: [
        { name: "WALLPAPERS", source: "screens/WallpaperScreen.qml" }, { name: "SHORTCUTS", source: "screens/ShortcutsScreen.qml" }, { name: "PROFILES", source: "screens/ProfilesScreen.qml" },
        { name: "PALETTE", source: "screens/PaletteScreen.qml" },
        { name: "DOCTOR", source: "screens/DoctorScreen.qml" },
        { name: "BACKUPS" }, { name: "LOCK", source: "screens/LockScreen.qml" },
        { name: "GREETER", source: "screens/GreeterScreen.qml" }
    ]
    property int current: 0
    property var status: ({})
    property string syncError: ""

    title: "RICE // CONTROL"
    implicitWidth: 1120
    implicitHeight: 720
    color: Theme.surface
    onVisibleChanged: if (!visible) Qt.quit()

    function select(index) {
        current = Math.max(0, Math.min(screens.length - 1, index));
    }

    IpcHandler {
        target: "rice"
        function close(): void { Qt.quit(); }
        function open(index: int): void { window.select(index); }
        function toggleLog(): void { log.visible = !log.visible; }
    }

    RiceCommand {
        id: statusCommand
        onSucceeded: data => {
            window.status = data;
            Theme.terminal = data.terminal;
        }
        onFailed: message => console.warn("status:", message)
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

        Keys.onPressed: event => {
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

        Item {
            id: sidebar
            anchors.top: parent.top
            anchors.bottom: footer.top
            width: 216

            RiceText {
                id: logo
                x: 18
                y: 18
                color: Theme.accent
                font.pixelSize: 11
                lineHeight: 1.1
                text: " ____  ___ ____ _____\n|  _ \\|_ _/ ___| ____|\n| |_) || | |   |  _|\n|  _ < | | |___| |___\n|_| \\_\\___\\____|_____|"
            }

            RiceText {
                id: tagline
                anchors.top: logo.bottom
                anchors.topMargin: 8
                x: 18
                text: "// CONTROL"
                color: Theme.muted
            }

            Column {
                id: nav
                anchors.top: tagline.bottom
                anchors.topMargin: 22
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

            Column {
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 14
                x: 18
                width: parent.width - 30
                spacing: 2

                RiceText {
                    width: parent.width
                    text: "PROFILE " + (window.status.profile || "")
                    color: Theme.muted
                }
                RiceText {
                    width: parent.width
                    elide: Text.ElideMiddle
                    text: window.status.wallpaper ? (window.status.wallpaper.effective || "").split("/").pop() : ""
                    color: Theme.muted
                }
            }
        }

        Rectangle {
            anchors.top: parent.top
            anchors.bottom: footer.top
            anchors.left: sidebar.right
            width: 1
            color: Theme.rule
        }

        Loader {
            id: screen
            anchors.top: parent.top
            anchors.bottom: footer.top
            anchors.left: sidebar.right
            anchors.right: parent.right
            anchors.margins: 20
            source: window.screens[window.current].source || "screens/PlaceholderScreen.qml"
            onLoaded: {
                if (item.title !== undefined)
                    item.title = window.screens[window.current].name;
                if (item.keyTarget !== undefined)
                    item.keyTarget = keys;
            }
        }

        Rectangle {
            id: footer
            anchors.bottom: parent.bottom
            width: parent.width
            height: 36
            color: "transparent"

            Rectangle { width: parent.width; height: 1; color: Theme.rule }

            RiceButton {
                id: syncButton
                anchors.verticalCenter: parent.verticalCenter
                x: 16
                label: syncCommand.running ? "SYNCING" : "SYNC ALL"
                enabledState: !syncCommand.running
                onClicked: {
                    window.syncError = "";
                    syncCommand.call(["sync", "--json"]);
                }
            }

            RiceText {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: syncButton.right
                anchors.leftMargin: 14
                anchors.right: logButton.left
                anchors.rightMargin: 14
                elide: Text.ElideRight
                text: "| " + (window.syncError ? "[ FAIL ] " + window.syncError : log.lastLine)
                color: window.syncError ? Theme.fail : Theme.statusColor(log.lastStatus)
            }

            RiceButton {
                id: logButton
                anchors.verticalCenter: parent.verticalCenter
                anchors.right: parent.right
                anchors.rightMargin: 16
                label: log.visible ? "LOG v" : "LOG ^"
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
    }
}
