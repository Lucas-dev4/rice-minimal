//@ pragma UseQApplication
import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.components
// Indexes gui/arcade for Quickshell; the views there are loaded by path.
import qs.arcade

// LW // GAMES — game library, backlog and play sessions, opened by `rice games` (Super+G).
// A separate instance from LW // CONTROL and LW // MUSIC with the same theme and
// components. Look follows the GAMES screen of ~/Downloads/lw-trio.html, in the solid
// LW style. Data: Games (games.json, written only by extras/games.py).
FloatingWindow {
    id: window

    readonly property var views: [
        { name: "BIBLIOTECA", source: "arcade/LibraryView.qml" },
        { name: "BACKLOG", source: "arcade/BacklogView.qml" }
    ]
    property int current: 0
    property bool statusLoaded: false
    readonly property var hints: screen.item && screen.item.hints ? screen.item.hints : []

    title: "LW // GAMES"
    implicitWidth: 1220
    implicitHeight: 780
    color: Theme.bg
    onVisibleChanged: if (!visible) Qt.quit()

    function select(index) { current = Math.max(0, Math.min(views.length - 1, index)); }
    function launchGame(id) { sheet.close(); Games.launch(id); }
    function stopGame(id) { Games.stop(id); }

    IpcHandler {
        target: "games"
        function close(): void { Qt.quit(); }
        function open(index: int): void { window.select(index); }
        function shot(path: string): void { content.grabToImage(result => result.saveToFile(path)); }
        function key(name: string): void {
            const named = { Return: Qt.Key_Return, Escape: Qt.Key_Escape, Left: Qt.Key_Left, Right: Qt.Key_Right, Up: Qt.Key_Up, Down: Qt.Key_Down, Tab: Qt.Key_Tab, Slash: Qt.Key_Slash, Space: Qt.Key_Space };
            const code = named[name] || name.toUpperCase().charCodeAt(0);
            window.handle({ key: code, text: named[name] ? (name === "Space" ? " " : "") : name, modifiers: name.length === 1 && name !== name.toLowerCase() ? Qt.ShiftModifier : 0, accepted: false });
        }
        function query(text: string): string {
            if (!screen.item || !screen.item.query) return "no search here";
            screen.item.query(text);
            return "ok";
        }
        function openSheet(id: string): string { if (id) sheet.openGame(id); else sheet.close(); return "ok"; }
        function state(): string {
            return JSON.stringify({ loaded: Games.loaded, scanning: Games.scanning, count: Games.games.length,
                                    lastScan: Games.lastScan, view: window.current, message: Status.message,
                                    titles: Games.games.map(g => g.title) });
        }
    }

    // Wallpaper accent and ANSI colours, like the other LW windows.
    RiceCommand {
        id: statusCommand
        onSucceeded: data => { Theme.terminal = data.terminal; window.statusLoaded = true; }
        onFailed: message => { window.statusLoaded = true; console.warn("status:", message); }
        Component.onCompleted: call(["status", "--json"])
    }
    Connections {
        target: Theme
        function onDarkChanged() { statusCommand.call(["status", "--json"]); }
    }
    Connections {
        target: Games
        function onFailed(message) { Status.say("[ !! ] " + message, Theme.red); }
        function onChanged(message) { Status.say(message, Theme.ok); }
        function onSessionEnded(title, hours) { Status.say(Games.hoursText(hours) + " em " + title, Theme.ok); }
    }
    // The window opens with what games.json has; the scan runs behind it.
    Component.onCompleted: { Games.recover(); Games.scan(true); }

    Item {
        id: keys
        anchors.fill: parent
        focus: true
        Keys.onPressed: event => window.handle(event)
    }

    function handle(event) {
        if (boot.visible) { boot.finish(); event.accepted = true; return; }
        if (launchScreen.shown) { launchScreen.handleKey(event); event.accepted = true; return; }
        if (sheet.shown) { if (sheet.handleKey(event)) event.accepted = true; return; }
        if (screen.item && screen.item.handleKey && screen.item.handleKey(event)) { event.accepted = true; return; }
        const digit = parseInt(event.text);
        if (digit >= 1 && digit <= views.length) select(digit - 1);
        else if (event.key === Qt.Key_Q) Qt.quit();
        else return;
        event.accepted = true;
    }

    Item {
        id: content
        anchors.fill: parent
        Rectangle { anchors.fill: parent; color: Theme.bg }

        // ================= SIDEBAR =================
        Rectangle {
            id: sidebar
            anchors.top: parent.top
            anchors.bottom: footer.top
            width: 232
            color: Theme.panel
            Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.line }

            Logo { id: logo; x: 22; y: 30 }
            Item {
                id: sub
                anchors.top: logo.bottom
                anchors.topMargin: 10
                x: 22
                width: parent.width - 44
                height: subText.implicitHeight
                RiceText { id: subText; text: "// games"; color: Theme.dim }
                RiceText { anchors.right: parent.right; text: "play"; color: Theme.faint }
            }

            component Label: RiceText { x: 22; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5 }

            Label { id: viewLabel; anchors.top: sub.bottom; anchors.topMargin: 28; text: "VIEW" }
            Item {
                id: nav
                anchors.top: viewLabel.bottom
                anchors.topMargin: 8
                width: parent.width - 1
                height: navColumn.height
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
                        model: window.views
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

            // Where the games come from.
            Label { id: sourcesLabel; anchors.top: nav.bottom; anchors.topMargin: 22; text: "SOURCES" }
            Column {
                id: sources
                anchors.top: sourcesLabel.bottom
                anchors.topMargin: 6
                x: 22
                width: parent.width - 44
                Repeater {
                    model: [["steam", "steam"], ["wine / .exe", "wine"], ["hydra", "hydra"], ["roms", "rom"]]
                    Item {
                        required property var modelData
                        readonly property int count: Games.games.filter(g => g.source === modelData[1] && !g.missing).length
                        width: sources.width
                        height: srcName.implicitHeight + 2
                        RiceText {
                            id: srcName
                            textFormat: Text.StyledText
                            text: (parent.count ? "<font color='" + Theme.ok + "'>●</font> " : "<font color='" + Theme.faint + "'>○</font> ") + parent.modelData[0]
                            color: parent.count ? Theme.fg : Theme.dim
                        }
                        RiceText { anchors.right: parent.right; text: parent.count; color: Theme.faint }
                    }
                }
            }

            // SESSION: ● game mm:ss while it runs (the watcher keeps counting with LW closed).
            Column {
                id: session
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 18
                x: 22
                width: parent.width - 44
                spacing: 3
                Label { x: 0; text: "SESSÃO" }
                RiceText {
                    width: parent.width
                    elide: Text.ElideRight
                    textFormat: Text.StyledText
                    readonly property int t: Games.sessionSeconds
                    readonly property string elapsed: (t >= 3600 ? Math.floor(t / 3600) + ":" + String(Math.floor(t % 3600 / 60)).padStart(2, "0") : Math.floor(t / 60)) + ":" + String(t % 60).padStart(2, "0")
                    text: Games.session ? "<font color='" + Theme.ok + "'>● " + elapsed + "</font>  " + (Games.sessionGame ? Games.sessionGame.title : "") : "nenhum jogo rodando"
                    color: Games.session ? Theme.fg : Theme.dim
                    font.pixelSize: Games.session ? Theme.fontSize : Theme.small
                }
                RiceText {
                    visible: !!Games.session
                    text: "■ PARAR"
                    color: stopMouse.containsMouse ? Theme.fg : Theme.red
                    font.pixelSize: Theme.small
                    MouseArea { id: stopMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: Games.stop(Games.session.id) }
                }
            }
        }

        // ================= MAIN =================
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
            source: window.views[window.current].source
            onLoaded: {
                item.title = window.views[window.current].name;
                if (item.keyTarget !== undefined) item.keyTarget = keys;
            }
            Connections {
                target: screen.item
                ignoreUnknownSignals: true
                function onOpen(id) { sheet.openGame(id); }
                function onLaunch(id) { window.launchGame(id); }
            }
        }

        // ================= STATUS BAR =================
        Rectangle {
            id: footer
            anchors.bottom: parent.bottom
            width: parent.width
            height: 34
            color: Theme.panel
            Rectangle { width: parent.width; height: 1; color: Theme.line }
            StatusBlock { id: clockBlock; label: clock.text; textColor: Theme.ok; textFormat: Text.StyledText }
            StatusBlock {
                anchors.left: clockBlock.right
                anchors.right: hintBlock.left
                label: typed.shown
                textColor: Status.message ? Status.color : Theme.dim
                separator: false
                elide: true
            }
            StatusBlock {
                id: hintBlock
                anchors.right: scanBlock.left
                leftSeparator: true
                textColor: Theme.faint
                textFormat: Text.StyledText
                label: window.hints.map(h => "<font color='" + Theme.dim + "'>" + h[0] + "</font> " + h[1]).join("&nbsp;&nbsp;&nbsp;")
            }
            StatusBlock {
                id: scanBlock
                anchors.right: parent.right
                separator: false
                label: Games.scanning ? "scan…" : Games.lastScan ? "scan: " + Games.lastScan.total + " · " + Games.lastScan.new + " novos" : "—"
            }
        }

        GameSheet {
            id: sheet
            anchors.fill: parent
            z: 30
            keyTarget: keys
            bottomInset: footer.height
            onLaunch: id => window.launchGame(id)
        }

        LaunchScreen {
            id: launchScreen
            anchors.fill: parent
            z: 40
        }

        RiceText { x: 8; y: 6; text: "┌"; color: Theme.faint; font.pixelSize: 11 }
        RiceText { anchors.right: parent.right; anchors.rightMargin: 8; y: 6; text: "┐"; color: Theme.faint; font.pixelSize: 11 }

        BootScreen {
            id: boot
            anchors.fill: parent
            steps: [
                { label: "loading palette", done: Object.keys(Theme.dark).length > 0 && window.statusLoaded },
                { label: "reading games.json: " + Games.games.length + " games", done: Games.loaded },
                { label: "scanning steam, hydra, roms", done: !Games.scanning },
                { label: "loading library", done: screen.status === Loader.Ready },
                { label: "starting LW // GAMES", done: true }
            ]
            onFinished: keys.forceActiveFocus()
        }
    }

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
        onTriggered: { clock.blink = !clock.blink; if (clock.blink) clock.now = new Date(); }
    }
    QtObject {
        id: typed
        readonly property string full: Status.message
        property int count: 0
        readonly property string shown: Theme.motion ? full.slice(0, count) : full
        onFullChanged: { count = 0; typer.restart(); }
    }
    Timer {
        id: typer
        interval: 12
        repeat: true
        onTriggered: if (++typed.count >= typed.full.length) stop()
    }
}
