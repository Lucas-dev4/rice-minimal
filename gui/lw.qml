//@ pragma UseQApplication
import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Io
import qs
import qs.components
// Indexes the folders whose files are loaded by path or reused here.
import qs.deck
import qs.player
import qs.arcade

// LW — WALL / MUSIC / GAMES in one window, glass over the current wallpaper (the look of
// ~/Downloads/lw-trio.html, as a desktop window). Super+W / Super+M / Super+G open it on
// a page (`rice lw wall|music|games`). Data and actions come from the same singletons as
// the other LW windows: Music (cliamp), Games (games.json), the rice CLI for wallpapers.
FloatingWindow {
    id: window

    readonly property var pages: [
        { name: "wall", label: "WALL", icon: "▦", source: "deck/WallPage.qml" },
        { name: "music", label: "MUSIC", icon: "♪", source: "deck/MusicPage.qml" },
        { name: "games", label: "GAMES", icon: "▶", source: "deck/GamesPage.qml" }
    ]
    property int current: Math.max(0, pages.findIndex(p => p.name === (Quickshell.env("LW_PAGE") || "wall")))
    property bool statusLoaded: false
    property string wallpaper: ""

    title: "LW"
    implicitWidth: 1220
    implicitHeight: 780
    color: Theme.bg
    onVisibleChanged: if (!visible) closeWindow()

    // Closing stops cliamp and saves where it was (as LW // MUSIC does); game sessions
    // are counted by their own watcher and are not touched.
    property bool closing: false
    function closeWindow() {
        if (closing) return;
        closing = true;
        Music.closeSession();
        Qt.quit();
    }
    function select(index) {
        if (index === current || index < 0 || index >= pages.length) return;
        previous = current;
        current = index;
    }
    property int previous: -1

    IpcHandler {
        target: "lw"
        function close(): void { window.closeWindow(); }
        function page(): string { return window.pages[window.current].name; }
        function open(name: string): void { window.select(window.pages.findIndex(p => p.name === name)); }
        function shot(path: string): void { content.grabToImage(result => result.saveToFile(path)); }
        function key(name: string): void {
            const named = { Return: Qt.Key_Return, Escape: Qt.Key_Escape, Left: Qt.Key_Left, Right: Qt.Key_Right, Up: Qt.Key_Up, Down: Qt.Key_Down, Tab: Qt.Key_Tab, Slash: Qt.Key_Slash, Space: Qt.Key_Space };
            const code = named[name] || name.toUpperCase().charCodeAt(0);
            window.handle({ key: code, text: named[name] ? (name === "Space" ? " " : "") : name, modifiers: name.length === 1 && name !== name.toLowerCase() ? Qt.ShiftModifier : 0, accepted: false });
        }
        function query(text: string): string {
            const item = pageRepeater.itemAt(window.current);
            if (!item || !item.item || !item.item.query) return "no search here";
            item.item.query(text);
            return "ok";
        }
        function state(): string {
            return JSON.stringify({ page: window.pages[window.current].name, wallpaper: window.wallpaper, music: Music.status,
                                    track: Music.title, session: Games.session, games: Games.games.length, toast: toast.text });
        }
    }

    // The wallpaper and the terminal accent, from `rice status`; refreshed on palette changes.
    RiceCommand {
        id: statusCommand
        onSucceeded: data => {
            Theme.terminal = data.terminal;
            window.wallpaper = data.wallpaper ? (data.wallpaper.effective || "") : "";
            Status.wallpaper = window.wallpaper;
            window.statusLoaded = true;
        }
        onFailed: message => { window.statusLoaded = true; console.warn("status:", message); }
        Component.onCompleted: call(["status", "--json"])
    }
    Connections {
        target: Theme
        function onDarkChanged() { statusCommand.call(["status", "--json"]); }
    }
    Connections {
        target: Games
        function onFailed(message) { toast.show(message, Theme.red); }
        function onChanged(message) { toast.show(message, Theme.accent); }
        function onSessionEnded(title, hours) { toast.show(Games.hoursText(hours) + " em " + title, Theme.ok); }
    }
    Connections {
        target: Music
        function onFailed(op, message) { toast.show(op + ": " + message, Theme.red); }
    }
    Connections {
        target: Status
        function onStampChanged() { toast.show(Status.message, Status.color); }
    }
    Component.onCompleted: { Games.recover(); Games.scan(true); }

    Item {
        id: keys
        anchors.fill: parent
        focus: true
        Keys.onPressed: event => window.handle(event)
    }
    function handle(event) {
        const page = pageRepeater.itemAt(current);
        if (page && page.item && page.item.handleKey && page.item.handleKey(event)) { event.accepted = true; return; }
        const t = event.text, digit = parseInt(t);
        if (digit >= 1 && digit <= pages.length) select(digit - 1);
        else if (event.key === Qt.Key_Tab) select((current + 1) % pages.length);
        else if (event.key === Qt.Key_Backtab) select((current + pages.length - 1) % pages.length);
        else if (event.key === Qt.Key_Q || event.key === Qt.Key_Escape) closeWindow();
        else if (event.key === Qt.Key_Space && Music.online) Music.toggle();
        else return;
        event.accepted = true;
    }

    Item {
        id: content
        anchors.fill: parent

        // ================= BACKGROUND =================
        // The current wallpaper, cross-fading when it changes; a blurred copy feeds the glass.
        Item {
            id: wall
            anchors.fill: parent
            Rectangle { anchors.fill: parent; color: "#0d0b0a" }
            property bool flip: false
            property string shownA: ""
            property string shownB: ""
            Connections {
                target: window
                function onWallpaperChanged() {
                    if (!window.wallpaper) return;
                    if (wall.flip) wall.shownA = window.wallpaper; else wall.shownB = window.wallpaper;
                    wall.flip = !wall.flip;
                }
            }
            component Paper: Image {
                anchors.fill: parent
                fillMode: Image.PreserveAspectCrop
                sourceSize.width: 1600
                asynchronous: true
                Behavior on opacity { NumberAnimation { duration: 900; easing.type: Theme.ease } }
            }
            Paper { source: wall.shownA ? "file://" + wall.shownA : ""; opacity: !wall.flip && status === Image.Ready ? 1 : 0 }
            Paper { source: wall.shownB ? "file://" + wall.shownB : ""; opacity: wall.flip && status === Image.Ready ? 1 : 0 }
        }
        MultiEffect {
            id: blurred
            anchors.fill: parent
            source: wall
            blurEnabled: true
            blur: 1.0
            blurMax: 48
            saturation: 0.15
            autoPaddingEnabled: false
            layer.enabled: true
            visible: true
            z: -1
            Component.onCompleted: { Deck.backdrop = blurred; Deck.root = content; }
        }
        // A dark veil keeps text readable over any wallpaper, light ones too.
        Rectangle { anchors.fill: parent; color: Qt.rgba(0.05, 0.04, 0.035, 0.5) }
        // Readability: darker at the top and the bottom, like the prototype.
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(0.05, 0.04, 0.035, 0.55) }
                GradientStop { position: 0.14; color: Qt.rgba(0.05, 0.04, 0.035, 0.15) }
                GradientStop { position: 0.8; color: Qt.rgba(0.05, 0.04, 0.035, 0.2) }
                GradientStop { position: 1.0; color: Qt.rgba(0.05, 0.04, 0.035, 0.6) }
            }
        }

        // ================= TOP BAR =================
        Item {
            id: top
            x: 18
            width: parent.width - 36
            height: 44
            RiceText { id: brand; anchors.verticalCenter: parent.verticalCenter; text: "LW"; color: Theme.accent; font.weight: Font.ExtraBold; font.letterSpacing: 1 }
            RiceText { anchors.left: brand.right; anchors.leftMargin: 10; anchors.verticalCenter: parent.verticalCenter; text: "// " + window.pages[window.current].name; color: Theme.dim }
            RiceText {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                textFormat: Text.StyledText
                text: Qt.formatTime(clock.now, "hh") + "<font color='" + Theme.accent + "'>" + (clock.blink ? ":" : "&nbsp;") + "</font>" + Qt.formatTime(clock.now, "mm")
            }
        }

        // ================= PAGES =================
        // All three stay loaded (state survives switching); the current one slides in.
        Item {
            id: pagesArea
            anchors.top: top.bottom
            anchors.topMargin: 6
            anchors.bottom: mini.visible ? mini.top : dock.top
            anchors.bottomMargin: 12
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(parent.width - 28, 980)
            Repeater {
                id: pageRepeater
                model: window.pages
                Loader {
                    id: pageLoader
                    required property var modelData
                    required property int index
                    readonly property bool active_: window.current === index
                    width: pagesArea.width
                    height: pagesArea.height
                    source: modelData.source
                    visible: opacity > 0
                    opacity: active_ ? 1 : 0
                    enabled: active_
                    x: active_ ? 0 : (index < window.current ? -24 : 24)
                    Behavior on opacity { NumberAnimation { duration: 350; easing.type: Theme.ease } }
                    Behavior on x { NumberAnimation { duration: 350; easing.type: Theme.ease } }
                    onXChanged: Deck.bump()
                    onLoaded: if (item.keyTarget !== undefined) item.keyTarget = keys
                }
            }
        }

        // ================= MINI PLAYER =================
        // A game session wins; otherwise what cliamp plays. Hidden on MUSIC.
        Glass {
            id: mini
            readonly property bool game: Games.session !== null
            readonly property bool music: Music.online && Music.track !== null
            visible: (game || music) && window.current !== 1
            anchors.bottom: dock.top
            anchors.bottomMargin: 8
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(parent.width - 28, 640)
            height: 58
            tint: 0.6
            k: true
            Row {
                x: 12
                anchors.verticalCenter: parent.verticalCenter
                spacing: 12
                width: parent.width - 24 - miniButtons.width
                RiceText {
                    visible: mini.game
                    anchors.verticalCenter: parent.verticalCenter
                    textFormat: Text.StyledText
                    readonly property int t: Games.sessionSeconds
                    text: "<font color='" + Theme.ok + "'>● " + Math.floor(t / 60) + ":" + String(t % 60).padStart(2, "0") + "</font>  "
                          + (Games.sessionGame ? Games.sessionGame.title : "")
                    font.weight: Font.DemiBold
                }
                Column {
                    visible: !mini.game
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width
                    RiceText { width: parent.width; elide: Text.ElideRight; text: Music.title; font.weight: Font.DemiBold }
                    RiceText { width: parent.width; elide: Text.ElideRight; text: [Music.artist, Music.album].filter(x => x).join(" · "); color: Theme.dim; font.pixelSize: Theme.small }
                }
            }
            Row {
                id: miniButtons
                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4
                component MiniButton: RiceText {
                    signal clicked()
                    font.pixelSize: 16
                    padding: 6
                    color: mbMouse.containsMouse ? Theme.accent : Theme.fg
                    MouseArea { id: mbMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: parent.clicked() }
                }
                MiniButton { visible: mini.game; text: "■"; color: Theme.red; onClicked: Games.stop(Games.session.id) }
                MiniButton { visible: !mini.game; text: Music.playing ? "❚❚" : "▶"; onClicked: Music.toggle() }
                MiniButton { visible: !mini.game; text: "▶|"; onClicked: Music.next() }
            }
            Rectangle {
                visible: !mini.game
                anchors.bottom: parent.bottom
                x: 1
                width: parent.width - 2
                height: 2
                color: Qt.rgba(1, 1, 1, 0.08)
                Rectangle { height: parent.height; width: Music.duration > 0 ? parent.width * Math.min(1, Music.position / Music.duration) : 0; color: Theme.accent }
            }
        }

        // ================= DOCK =================
        Glass {
            id: dock
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 10
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(parent.width - 28, 640)
            height: 60
            tint: 0.62
            Rectangle {
                y: 0
                x: window.current * dock.width / 3
                width: dock.width / 3
                height: 2
                color: Theme.accent
                Behavior on x { NumberAnimation { duration: 350; easing.type: Theme.ease } }
                // glow
                Rectangle { anchors.centerIn: parent; width: parent.width; height: 8; color: Qt.alpha(Theme.accent, 0.18) }
            }
            Row {
                anchors.fill: parent
                Repeater {
                    model: window.pages
                    Item {
                        required property var modelData
                        required property int index
                        readonly property bool on: window.current === index
                        // Activity dots: music playing, game running.
                        readonly property bool busy: (index === 1 && Music.playing) || (index === 2 && Games.session !== null)
                        width: dock.width / 3
                        height: dock.height
                        Column {
                            anchors.centerIn: parent
                            spacing: 3
                            RiceText { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.icon; font.pixelSize: 18; color: parent.parent.on ? Theme.accent : Theme.dim }
                            RiceText { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.label; font.pixelSize: 10; font.letterSpacing: 1.5; color: parent.parent.on ? Theme.accent : Theme.dim }
                        }
                        Rectangle { visible: parent.busy; x: parent.width / 2 + 16; y: 12; width: 6; height: 6; radius: 3; color: Theme.ok }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { window.select(index); keys.forceActiveFocus(); } }
                    }
                }
            }
        }

        // ================= TOAST =================
        Glass {
            id: toast
            property string text: ""
            property color tone: Theme.accent
            function show(message, color) {
                if (!message) return;
                text = message;
                tone = color || Theme.accent;
                shown = true;
                hide.restart();
            }
            property bool shown: false
            anchors.horizontalCenter: parent.horizontalCenter
            y: top.height + (shown ? 8 : -2)
            opacity: shown ? 1 : 0
            visible: opacity > 0
            width: Math.min(parent.width - 60, toastText.implicitWidth + 28)
            height: toastText.implicitHeight + 12
            tint: 0.85
            z: 20
            Behavior on opacity { NumberAnimation { duration: 300; easing.type: Theme.ease } }
            Behavior on y { NumberAnimation { duration: 300; easing.type: Theme.ease } }
            Rectangle { anchors.fill: parent; color: "transparent"; border.width: 1; border.color: toast.tone }
            RiceText { id: toastText; anchors.centerIn: parent; text: toast.text; color: Theme.fg; font.pixelSize: 12 }
            Timer { id: hide; interval: 1800; onTriggered: toast.shown = false }
        }
    }

    QtObject {
        id: clock
        property date now: new Date()
        property bool blink: true
    }
    Timer {
        interval: 500
        running: true
        repeat: true
        onTriggered: { clock.blink = !clock.blink; if (clock.blink) clock.now = new Date(); }
    }
}
