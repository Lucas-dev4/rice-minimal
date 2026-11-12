//@ pragma UseQApplication
import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.components
// Indexes gui/player for Quickshell; the views there are loaded by path.
import qs.player

// LW // MUSIC — controller and visualizer for cliamp, opened by `rice music`. A separate
// instance from LW // CONTROL with the same theme and components. Look and behaviour
// follow ~/Downloads/lw-music.html; everything that plays goes through Music (cliamp IPC).
FloatingWindow {
    id: window

    readonly property var screens: [
        { name: "NOW PLAYING", source: "player/NowScreen.qml" },
        { name: "PLAYLIST", source: "player/PlaylistScreen.qml" },
        { name: "EQUALIZER", source: "player/EqScreen.qml" },
        { name: "RADIO", source: "player/RadioScreen.qml" },
        { name: "LIBRARY", source: "player/LibraryScreen.qml" },
        { name: "ONLINE", source: "player/OnlineScreen.qml" }
    ]
    property int current: 0
    property bool statusLoaded: false
    readonly property var globalHints: [["1-6", "view"], ["spc", "play"], ["n/p", "faixa"], ["←→", "seek"], ["+-", "vol"], ["o", "abrir"]]
    // The view's own keys when it has them (the status bar has room for about six).
    readonly property var hints: screen.item && screen.item.hints && screen.item.hints.length ? screen.item.hints : globalHints

    title: "LW // MUSIC"
    implicitWidth: 1220
    implicitHeight: 780
    color: "transparent"
    // See-through like the terminal (RICE_GUI_OPACITY overrides; 1 = solid).
    Component.onCompleted: Theme.alpha = Number(Quickshell.env("RICE_GUI_OPACITY") || 0.85)
    onVisibleChanged: if (!visible) closePlayer()

    // Closing saves cliamp's session and switches it off; opening brings it back paused
    // (Music.closeSession / Music.startCliamp, shared with the LW window).
    property bool closing: false
    function closePlayer() {
        if (closing) return;
        closing = true;
        Music.closeSession();
        Qt.quit();
    }
    function startCliamp() { Music.startCliamp(); }

    function select(index) { current = Math.max(0, Math.min(screens.length - 1, index)); }
    function clock(seconds) {
        if (!isFinite(seconds) || seconds < 0) return "LIVE";
        const s = Math.floor(seconds);
        return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
    }

    IpcHandler {
        target: "music"
        function close(): void { window.closePlayer(); }
        function open(index: int): void { window.select(index); }
        function shot(path: string): void { content.grabToImage(result => result.saveToFile(path)); }
        function key(name: string): void {
            const named = { Return: Qt.Key_Return, Escape: Qt.Key_Escape, Left: Qt.Key_Left, Right: Qt.Key_Right, Up: Qt.Key_Up, Down: Qt.Key_Down, Space: Qt.Key_Space, Slash: Qt.Key_Slash, Plus: Qt.Key_Plus, Minus: Qt.Key_Minus, Equal: Qt.Key_Equal };
            const text = named[name] ? (name === "Space" ? " " : name === "Plus" ? "+" : name === "Minus" ? "-" : name === "Equal" ? "=" : "") : name;
            const code = named[name] || name.toUpperCase().charCodeAt(0);
            window.handle({ key: code, text: text, modifiers: name.length === 1 && name !== name.toLowerCase() ? Qt.ShiftModifier : 0, accepted: false });
        }
        // Scriptable state and actions (scripts/music-check.sh).
        function state(): string {
            return JSON.stringify({
                online: Music.online, status: Music.status, title: Music.title, artist: Music.artist,
                album: Music.album, position: Math.round(Music.position * 10) / 10, duration: Music.duration,
                live: Music.live, volume: Music.volumePercent, volumeDb: Music.volumeDb, muted: Music.muted,
                shuffle: Music.shuffle, repeat: Music.repeat, index: Music.currentIndex,
                playlist: Music.playlist.map(t => t.title || Music.fileName(t.path)),
                eq: Music.eqBands, error: Music.lastError, view: window.current
            });
        }
        function query(text: string): string {
            if (!screen.item || !screen.item.query) return "this view has no search";
            screen.item.query(text);
            return "ok";
        }
        function act(op: string, arg: string): string {
            const n = parseFloat(arg);
            switch (op) {
            case "toggle": Music.toggle(); break;
            case "next": Music.next(); break;
            case "prev": Music.previous(); break;
            case "seek": Music.seekTo(n); break;
            case "seekby": Music.seekBy(n); break;
            case "volume": Music.setVolumePercent(n); break;
            case "mute": Music.toggleMute(); break;
            case "shuffle": Music.setShuffle(!Music.shuffle); break;
            case "repeat": Music.cycleRepeat(); break;
            case "play": Music.playIndex(n); break;
            case "move": Music.moveTrack(parseInt(arg.split(",")[0]), parseInt(arg.split(",")[1])); break;
            case "remove": Music.removeTrack(n); break;
            case "add": Music.addPath(arg); break;
            case "band": Music.setBand(parseInt(arg.split(",")[0]), parseFloat(arg.split(",")[1])); break;
            case "preset": Music.setPreset(arg); break;
            case "start": window.startCliamp(); break;
            case "quit": Qt.quit(); break;
            case "bad": Music.call("queue.play", { index: 999 }); break;
            default: return "unknown " + op;
            }
            return "ok";
        }
    }

    // The terminal accent and the vivid ANSI colors come from the wallpaper, like LW // CONTROL.
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

    // Short status-bar messages for what cliamp does.
    property string lastPath: ""
    Connections {
        target: Music
        function onFailed(op, message) { Status.say("[ !! ] " + op + ": " + message, Theme.red); }
        function onChanged() {
            const path = Music.track ? Music.track.path : "";
            if (path && path !== window.lastPath)
                Status.say("[ ▶ ] " + Music.title + (Music.artist ? " — " + Music.artist : ""), Theme.ok);
            window.lastPath = path;
        }
        function onOnlineChanged() {
            if (!Music.online) Status.say("[ -- ] cliamp offline", Theme.dim);
        }
    }

    Item {
        id: keys
        anchors.fill: parent
        focus: true
        Keys.onPressed: event => window.handle(event)
    }

    // Keyboard: the view first, then the player keys. Esc only leaves text fields (in the views).
    function handle(event) {
        if (boot.visible) { boot.finish(); event.accepted = true; return; }
        if (screen.item && screen.item.handleKey && screen.item.handleKey(event)) { event.accepted = true; return; }
        const t = event.text, digit = parseInt(t);
        if (digit >= 1 && digit <= screens.length) select(digit - 1);
        else if (t === "R") select(3);
        // o opens files from any view: they land in the playlist.
        else if (t === "o" && Music.online) { select(1); Qt.callLater(() => { if (screen.item && screen.item.openFiles) screen.item.openFiles(); }); }
        else if (event.key === Qt.Key_Q) closePlayer();
        else if (!Music.online) {
            if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) startCliamp();
            else return;
        }
        else if (event.key === Qt.Key_Space) Music.toggle();
        else if (t === "n") Music.next();
        else if (t === "p") Music.previous();
        else if (event.key === Qt.Key_Left) Music.seekBy(-5);
        else if (event.key === Qt.Key_Right) Music.seekBy(5);
        // ABNT2 sends "=" for the + key without Shift.
        else if (t === "+" || t === "=") Music.volumeStep(5);
        else if (t === "-") Music.volumeStep(-5);
        else if (t === "m") Music.toggleMute();
        else if (t === "s") Music.setShuffle(!Music.shuffle);
        else if (t === "r") Music.cycleRepeat();
        else return;
        event.accepted = true;
    }

    // The spectrum comes from the shared Spectrum singleton (cava on cliamp's stream).
    readonly property var spectrum: Spectrum.levels
    readonly property string spectrumSource: Spectrum.source

    // Output format of cliamp's stream, read from PipeWire (pulse API): "44.1 kHz · 2ch".
    property string output: ""
    Process {
        id: sinkInputs
        command: ["pactl", "-f", "json", "list", "sink-inputs"]
        stdout: StdioCollector {
            onStreamFinished: {
                let list = [];
                try { list = JSON.parse(text); } catch (error) { return; }
                const mine = list.find(s => /cliamp/i.test((s.properties || {})["application.process.binary"] || "")
                                       || /cliamp/i.test((s.properties || {})["application.name"] || ""));
                const spec = mine ? /(\d+)ch (\d+)Hz/.exec(mine.sample_specification || "") : null;
                window.output = spec ? (parseInt(spec[2]) / 1000).toFixed(1).replace(/\.0$/, "") + " kHz · " + spec[1] + "ch" : "";
            }
        }
    }
    Timer {
        interval: 4000
        repeat: true
        triggeredOnStart: true
        running: Music.online
        onTriggered: if (!sinkInputs.running) sinkInputs.running = true
        onRunningChanged: if (!running) window.output = ""
    }

    Item {
        id: content
        anchors.fill: parent
        Rectangle { anchors.fill: parent; color: Theme.base }

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
                RiceText { id: subText; text: "// music"; color: Theme.dim }
                RiceText { anchors.right: parent.right; text: "cliamp"; color: Theme.faint }
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

            // Where the playlist's tracks come from; ● marks what plays now.
            Label { id: sourcesLabel; anchors.top: nav.bottom; anchors.topMargin: 22; text: "SOURCES" }
            Column {
                id: sources
                anchors.top: sourcesLabel.bottom
                anchors.topMargin: 6
                x: 22
                width: parent.width - 44
                readonly property var kinds: [["local files", "local"], ["radio", "radio"], ["streaming", "stream"]]
                Repeater {
                    model: sources.kinds
                    Item {
                        required property var modelData
                        readonly property int count: Music.playlist.filter(t => Music.sourceOf(t.path) === modelData[1]).length
                        readonly property bool on: Music.online && Music.track !== null && Music.sourceOf(Music.track.path) === modelData[1]
                        width: sources.width
                        height: srcName.implicitHeight + 2
                        RiceText {
                            id: srcName
                            textFormat: Text.StyledText
                            text: (parent.on ? "<font color='" + Theme.ok + "'>●</font> " : "<font color='" + Theme.faint + "'>○</font> ") + parent.modelData[0]
                            color: parent.on ? Theme.fg : Theme.dim
                        }
                        RiceText { anchors.right: parent.right; text: Music.online ? parent.count : "–"; color: Theme.faint }
                    }
                }
            }

            // Mini player: dimmed while NOW PLAYING shows the same thing in full.
            Column {
                id: mini
                anchors.bottom: vol.top
                anchors.bottomMargin: 14
                x: 22
                width: parent.width - 44
                spacing: 2
                opacity: window.current === 0 ? 0.25 : 1
                Visualizer {
                    width: parent.width
                    height: 34
                    count: 28
                    compact: true
                    levels: window.spectrum
                    idle: !Music.playing || window.spectrum.length === 0
                    // Dimmed under NOW PLAYING, where the big one runs: hold it still.
                    running: window.current !== 0 && Music.online
                }
                Item { width: 1; height: 4 }
                Behavior on opacity { NumberAnimation { duration: Theme.tMed; easing.type: Theme.ease } }
                RiceText {
                    width: parent.width
                    elide: Text.ElideRight
                    text: Music.online ? (Music.title || "—") : "—"
                    color: Theme.fg
                }
                RiceText {
                    width: parent.width
                    elide: Text.ElideRight
                    text: Music.online ? [Music.artist, Music.album].filter(x => x).join(" · ") : "cliamp offline"
                    color: Theme.dim
                    font.pixelSize: Theme.small
                }
                Item { width: 1; height: 4 }
                Rectangle {
                    width: parent.width
                    height: 2
                    color: Theme.line
                    Rectangle {
                        height: parent.height
                        width: Music.live ? parent.width : Music.duration > 0 ? parent.width * Math.min(1, Music.position / Music.duration) : 0
                        color: Music.live ? Theme.blue : Theme.accent
                    }
                }
            }

            // VOL ▮▮▮▮▮▮▮▮▯▯▯▯ 75%: click sets it, the wheel moves 5%.
            Item {
                id: vol
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 18
                x: 22
                width: parent.width - 44
                height: volText.implicitHeight
                readonly property int cells: 12
                readonly property int filled: Math.round(Math.min(100, Music.volumePercent) / 100 * cells)
                // The system volume is there even when cliamp is not.
                readonly property bool live: Music.online || Music.systemVolume
                RiceText { id: volText; text: "VOL"; color: Theme.dim; font.pixelSize: Theme.small }
                RiceText {
                    id: volBar
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: Music.muted || !vol.live ? "▯".repeat(vol.cells) : "▮".repeat(vol.filled) + "▯".repeat(vol.cells - vol.filled)
                    color: Music.muted || !vol.live ? Theme.faint : Theme.accent
                    font.pixelSize: Theme.small
                    font.letterSpacing: -1
                }
                RiceText {
                    anchors.right: parent.right
                    text: !vol.live ? "–" : Music.muted ? "MUTE" : Music.volumePercent + "%"
                    color: Theme.dim
                    font.pixelSize: Theme.small
                }
                MouseArea {
                    anchors.fill: volBar
                    anchors.margins: -4
                    enabled: vol.live
                    cursorShape: Qt.PointingHandCursor
                    onClicked: mouse => { Music.setVolumePercent(Math.round(mouse.x / width * 20) * 5); keys.forceActiveFocus(); }
                    onWheel: wheel => Music.volumeStep(wheel.angleDelta.y > 0 ? 5 : -5)
                }
            }
        }

        // ================= MAIN =================
        Item {
            id: main
            anchors.top: parent.top
            anchors.bottom: footer.top
            anchors.left: sidebar.right
            anchors.right: parent.right
            anchors.leftMargin: 26
            anchors.rightMargin: 26
            anchors.topMargin: 22
            anchors.bottomMargin: 14

            RiceHeader {
                id: header
                title: "LW // " + window.screens[window.current].name
                note: Music.online ? Music.status.toUpperCase() : "OFFLINE"
                noteColor: Music.playing ? Theme.ok : Music.status === "paused" ? Theme.yel : Theme.dim
                // NOW PLAYING: the visualizer modes (v cycles them).
                Repeater {
                    model: window.current === 0 && Music.online && screen.item && screen.item.modes ? screen.item.modes : []
                    Chip {
                        required property string modelData
                        label: modelData
                        on: screen.item && screen.item.mode === modelData
                        onClicked: { screen.item.setMode(modelData); keys.forceActiveFocus(); }
                    }
                }
            }

            Loader {
                id: screen
                anchors.top: header.bottom
                anchors.topMargin: 14
                anchors.bottom: parent.bottom
                width: parent.width
                visible: Music.online
                source: window.screens[window.current].source
                // Tabs that share a file are not reloaded: their texts follow the selection.
                function describe() {
                    if (!item) return;
                    item.title = window.screens[window.current].name;
                }
                Connections { target: window; function onCurrentChanged() { screen.describe(); } }
                onLoaded: {
                    describe();
                    if (item.levels !== undefined) {
                        item.levels = Qt.binding(() => window.spectrum);
                        item.levelSource = Qt.binding(() => window.spectrumSource);
                    }
                    if (item.keyTarget !== undefined) item.keyTarget = keys;
                    item.opacity = Theme.motion ? 0 : 1;
                    enter.restart();
                }
                NumberAnimation { id: enter; target: screen.item; property: "opacity"; to: 1; duration: Theme.tMed; easing.type: Theme.ease }
            }

            // cliamp is not running: say so and offer to start it headless.
            Column {
                anchors.centerIn: screen
                visible: !Music.online
                spacing: 14
                RiceText {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: Music.connecting ? "[ .. ] conectando ao cliamp" : "[ -- ] cliamp offline"
                    color: Music.connecting ? Theme.accent : Theme.dim
                    font.pixelSize: 16
                }
                AccentButton {
                    anchors.horizontalCenter: parent.horizontalCenter
                    visible: !Music.connecting
                    label: "START ⏎"
                    onClicked: window.startCliamp()
                }
                RiceText {
                    anchors.horizontalCenter: parent.horizontalCenter
                    visible: !Music.connecting
                    text: "liga o cliamp sem janela: volta pausado onde parou, ou abre ~/Músicas"
                    color: Theme.faint
                    font.pixelSize: Theme.small
                }
                // Only the errors that START cannot fix by itself.
                RiceText {
                    anchors.horizontalCenter: parent.horizontalCenter
                    visible: !Music.connecting && /não encontrado/.test(Music.lastError)
                    text: "[ !! ] " + Music.lastError
                    color: Theme.red
                    font.pixelSize: Theme.small
                }
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

            StatusBlock {
                id: clockBlock
                label: clock.text
                textColor: Theme.ok
                textFormat: Text.StyledText
            }
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
                anchors.right: outBlock.left
                leftSeparator: true
                textColor: Theme.faint
                textFormat: Text.StyledText
                label: window.hints.map(h => "<font color='" + Theme.dim + "'>" + h[0] + "</font> " + h[1]).join("&nbsp;&nbsp;&nbsp;")
            }
            StatusBlock {
                id: outBlock
                anchors.right: parent.right
                separator: false
                label: window.output || "—"
            }
        }

        // Audio files dropped on the window join cliamp's queue.
        DropArea {
            id: drop
            anchors.fill: parent
            enabled: Music.online
            keys: ["text/uri-list"]
            onDropped: event => {
                const files = event.urls.map(u => decodeURIComponent(String(u).replace(/^file:\/\//, "")))
                    .filter(f => /\.(mp3|flac|ogg|opus|m4a|aac|wav|wv|ape|aiff?|alac|wma)$/i.test(f));
                for (const f of files) Music.addPath(f);
                Status.say(files.length ? "[ + ] " + files.length + " arquivo(s) na fila" : "[ !! ] nenhum arquivo de áudio", files.length ? Theme.ok : Theme.red);
            }
        }
        Rectangle {
            anchors.fill: parent
            anchors.margins: 10
            visible: drop.containsDrag
            z: 40
            color: Qt.alpha(Theme.bg, 0.85)
            border.width: 2
            border.color: Theme.accent
            RiceText { anchors.centerIn: parent; text: "solte os arquivos de áudio"; color: Theme.accent; font.pixelSize: 16; font.letterSpacing: 1 }
        }

        RiceText { x: 8; y: 6; text: "┌"; color: Theme.faint; font.pixelSize: 11 }
        RiceText { anchors.right: parent.right; anchors.rightMargin: 8; y: 6; text: "┐"; color: Theme.faint; font.pixelSize: 11 }

        BootScreen {
            id: boot
            anchors.fill: parent
            steps: [
                { label: "loading palette", done: Object.keys(Theme.dark).length > 0 && window.statusLoaded },
                { label: Music.online ? "connected to cliamp" : "connecting to cliamp", done: !Music.connecting },
                { label: "reading playlist" + (Music.playlistLoaded ? ": " + Music.playlist.length + " tracks" : ""), done: Music.playlistLoaded || !Music.online },
                { label: "loading " + window.screens[window.current].name.toLowerCase(), done: screen.status === Loader.Ready },
                { label: "starting LW // MUSIC", done: true }
            ]
            onFinished: keys.forceActiveFocus()
        }
    }

    // hh:mm:ss with blinking colons.
    QtObject {
        id: clock
        property date now: new Date()
        property bool blink: true
        readonly property string colon: blink || !Theme.motion ? ":" : "<font color='transparent'>:</font>"
        readonly property string text: Qt.formatTime(now, "hh") + colon + Qt.formatTime(now, "mm") + colon + Qt.formatTime(now, "ss")
    }
    Timer {
        interval: 500
        running: true
        repeat: true
        onTriggered: { clock.blink = !clock.blink; if (clock.blink) clock.now = new Date(); }
    }

    // The message is typed out, one character every 12 ms (refined only).
    QtObject {
        id: typed
        readonly property string full: Status.message || (Music.online ? "" : "[ -- ] cliamp offline")
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
