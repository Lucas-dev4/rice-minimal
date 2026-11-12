//@ pragma UseQApplication
import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.components
// Indexes the folders whose files are used here or loaded by path.
import qs.player
import qs.arcade

// LW — one window for the whole system: SISTEMA (wallpapers, shortcuts, profiles…),
// MÚSICA (cliamp) and JOGOS (library, backlog, play sessions). Opened by `lw gui`,
// `lw music` and `lw games` (Super+BackSpace / Super+M / Super+G) on that section.
// Closing it on MÚSICA stops the music; elsewhere music and a game session go on.
// Look and behaviour follow docs/lw-prototype.html; all tokens live in Theme.qml.
FloatingWindow {
    id: window

    readonly property var groups: [
        { key: "system", label: "SISTEMA", screens: [
            { name: "WALLPAPERS", source: "screens/WallpaperScreen.qml" },
            { name: "SHORTCUTS", source: "screens/ShortcutsScreen.qml" },
            { name: "PROFILES", source: "screens/ProfilesScreen.qml" },
            { name: "PALETTE", source: "screens/PaletteScreen.qml" },
            { name: "DOCTOR", source: "screens/DoctorScreen.qml" },
            { name: "BACKUPS", source: "screens/BackupsScreen.qml" },
            { name: "LOCK", source: "screens/LockScreen.qml" },
            { name: "GREETER", source: "screens/GreeterScreen.qml" }
        ] },
        { key: "music", label: "MÚSICA", screens: [
            { name: "NOW PLAYING", source: "player/NowScreen.qml" },
            { name: "PLAYLIST", source: "player/PlaylistScreen.qml" },
            { name: "EQUALIZER", source: "player/EqScreen.qml" },
            { name: "RADIO", source: "player/RadioScreen.qml" },
            { name: "LIBRARY", source: "player/LibraryScreen.qml" },
            { name: "ONLINE", source: "player/OnlineScreen.qml" }
        ] },
        { key: "games", label: "JOGOS", screens: [
            { name: "BIBLIOTECA", source: "arcade/LibraryView.qml" },
            { name: "BACKLOG", source: "arcade/BacklogView.qml" },
            { name: "DESEMPENHO", source: "arcade/StatsView.qml" }
        ] }
    ]
    // The section and, inside it, the screen; each section remembers its last screen.
    property int group: Math.max(0, groups.findIndex(g => g.key === Quickshell.env("LW_START_GROUP")))
    property var lastScreen: [0, 0, 0]
    readonly property int current: lastScreen[group]
    readonly property var screens: groups[group].screens
    readonly property string groupKey: groups[group].key
    readonly property bool inMusic: groupKey === "music"
    readonly property bool inGames: groupKey === "games"

    property var status: ({})
    property bool statusLoaded: false
    property string syncError: ""
    readonly property var globalHints: inMusic ? [["spc", "play"], ["n/p", "faixa"], ["←→", "seek"], ["+-", "vol"], ["alt 1-3", "seção"]]
                                               : [["↑↓", "tela"], ["alt 1-3", "seção"], ["q", "fechar"]]
    readonly property var hints: screen.item && screen.item.hints && screen.item.hints.length ? screen.item.hints : globalHints

    title: "LW"
    implicitWidth: 1220
    implicitHeight: 780
    color: "transparent"
    // See-through like the terminal (RICE_GUI_OPACITY overrides; 1 = solid).
    Component.onCompleted: { Theme.alpha = Number(Quickshell.env("RICE_GUI_OPACITY") || 0.85); Games.recover(); enterGroup(); }
    onVisibleChanged: if (!visible && !parked) quit()
    // Ctrl+J hides the window without closing it (music keeps playing, a game session keeps
    // counting); the same Super shortcut brings it back (`lw` asks `hidden` first).
    property bool parked: false
    function park() { parked = true; visible = false; }
    function unpark() { visible = true; parked = false; keys.forceActiveFocus(); }
    function isPark(event) { return event.key === Qt.Key_J && (event.modifiers & Qt.ControlModifier); }

    // Closing on MÚSICA stops cliamp (its session is saved: it comes back paused there);
    // closing on SISTEMA or JOGOS leaves it playing and only saves the session.
    function quit() {
        if (inMusic) Music.closeSession(); else Music.saveSession();
        Qt.quit();
    }

    function select(index) {
        const next = lastScreen.slice();
        next[group] = Math.max(0, Math.min(screens.length - 1, index));
        lastScreen = next;
    }
    function selectGroup(index) {
        if (index < 0 || index >= groups.length || index === group) return;
        sheet.close();
        installSheet.close();
        group = index;
        enterGroup();
    }
    // MÚSICA starts cliamp when it is off; JOGOS scans the libraries once per window.
    property bool scanned: false
    function enterGroup() {
        if (inMusic) Music.wanted = true;
        if (inGames && !scanned) { scanned = true; Games.scan(true); }
    }
    function launchGame(id) { sheet.close(); Games.launch(id); }

    IpcHandler {
        target: "lw"
        function close(): void { window.quit(); }
        function hidden(): string { return window.parked ? "yes" : "no"; }
        function reveal(): void { window.unpark(); }
        // The section shown now: system, music or games.
        function section(): string { return window.groupKey; }
        function go(name: string): void { window.selectGroup(window.groups.findIndex(g => g.key === name)); }
        function open(index: int): void { window.select(index); }
        function toggleLog(): void { log.visible = !log.visible; }
        function shot(path: string): void { content.grabToImage(result => result.saveToFile(path)); }
        function key(name: string): void {
            const named = { Return: Qt.Key_Return, Escape: Qt.Key_Escape, Left: Qt.Key_Left, Right: Qt.Key_Right, Up: Qt.Key_Up, Down: Qt.Key_Down,
                            Tab: Qt.Key_Tab, Slash: Qt.Key_Slash, Space: Qt.Key_Space, Plus: Qt.Key_Plus, Minus: Qt.Key_Minus, Equal: Qt.Key_Equal };
            const texts = { Space: " ", Plus: "+", Minus: "-", Equal: "=" };
            // "SUPER+SHIFT+X" style: modifiers before the last token.
            const parts = name.length > 1 && name.indexOf("+") > 0 ? name.split("+") : [name];
            const last = parts.pop();
            const flags = { SUPER: Qt.MetaModifier, CONTROL: Qt.ControlModifier, ALT: Qt.AltModifier, SHIFT: Qt.ShiftModifier };
            let modifiers = last.length === 1 && last !== last.toLowerCase() && parts.length === 0 ? Qt.ShiftModifier : 0;
            for (const m of parts) modifiers |= flags[m] || 0;
            const code = named[last] || last.toUpperCase().charCodeAt(0);
            window.handle({ key: code, text: named[last] ? (texts[last] || "") : last, modifiers: modifiers, accepted: false });
        }
        function query(text: string): string {
            if (!screen.item || !screen.item.query) return "this view has no search";
            screen.item.query(text);
            return "ok";
        }
        function openSheet(id: string): string { if (id) sheet.openGame(id); else sheet.close(); return "ok"; }
        function installer(): void { window.selectGroup(2); installSheet.openSheet(); }
        // Scriptable state and actions (scripts/music-check.sh, tests).
        function state(): string {
            return JSON.stringify({
                section: window.groupKey, view: window.current, screen: window.screens[window.current].name,
                online: Music.online, status: Music.status, title: Music.title, artist: Music.artist,
                album: Music.album, position: Math.round(Music.position * 10) / 10, duration: Music.duration,
                live: Music.live, volume: Music.volumePercent, volumeDb: Music.volumeDb, muted: Music.muted,
                shuffle: Music.shuffle, repeat: Music.repeat, index: Music.currentIndex,
                playlist: Music.playlist.map(t => t.title || Music.fileName(t.path)),
                eq: Music.eqBands, error: Music.lastError,
                games: Games.games.length, scanning: Games.scanning, session: Games.session, message: Status.message
            });
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
            case "start": Music.startCliamp(); break;
            case "stop": Music.closeSession(); break;
            case "quit": window.quit(); break;
            case "bad": Music.call("queue.play", { index: 999 }); break;
            default: return "unknown " + op;
            }
            return "ok";
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
        // A new log entry replaces any short message from a screen.
        function onLastLineChanged() { Status.message = ""; }
    }
    Connections {
        target: Theme
        function onDarkChanged() { statusCommand.call(["status", "--json"]); }
    }

    // Short status-bar messages for what cliamp and the games do.
    property string lastPath: ""
    Connections {
        target: Music
        function onFailed(op, message) { Status.say("[ !! ] " + op + ": " + message, Theme.red); }
        function onChanged() {
            const path = Music.track ? Music.track.path : "";
            if (path && path !== window.lastPath && window.lastPath !== "")
                Status.say("[ ▶ ] " + Music.title + (Music.artist ? " — " + Music.artist : ""), Theme.ok);
            window.lastPath = path || window.lastPath;
        }
    }
    Connections {
        target: Games
        function onFailed(message) { Status.say("[ !! ] " + message, Theme.red); }
        function onChanged(message) { Status.say(message, Theme.ok); }
        function onSessionEnded(title, hours) { Status.say(Games.hoursText(hours) + " em " + title, Theme.ok); }
    }

    Item {
        id: keys
        anchors.fill: parent
        focus: true
        Keys.onPressed: event => window.handle(event)
    }

    // Keyboard: overlays, then the screen, then the section keys, then the window keys.
    // Test hook: `qs ipc -p gui call lw key l` reaches only this window, never the focused one.
    function handle(event) {
        // Not while SHORTCUTS records a combination: Ctrl+J is a combination too.
        if (isPark(event) && !(screen.item && screen.item.recording)) { park(); event.accepted = true; return; }
        if (boot.visible) { boot.finish(); event.accepted = true; return; }
        if (launchScreen.shown) { launchScreen.handleKey(event); event.accepted = true; return; }
        if (installSheet.shown) { installSheet.handleKey(event); event.accepted = true; return; }
        if (sheet.shown) { if (sheet.handleKey(event)) event.accepted = true; return; }
        const t = event.text, digit = parseInt(t);
        // Alt+1/2/3: SISTEMA, MÚSICA, JOGOS. Checked before the screen so no screen eats it.
        if ((event.modifiers & Qt.AltModifier) && event.key >= Qt.Key_1 && event.key <= Qt.Key_3) {
            selectGroup(event.key - Qt.Key_1);
            event.accepted = true;
            return;
        }
        // MÚSICA without cliamp: only START.
        if (inMusic && !Music.online && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)) {
            Music.startCliamp();
            event.accepted = true;
            return;
        }
        if (screen.item && screen.item.handleKey && screen.item.handleKey(event)) { event.accepted = true; return; }
        if (digit >= 1 && digit <= screens.length) select(digit - 1);
        else if (event.key === Qt.Key_Q || event.key === Qt.Key_Escape) quit();
        else if (event.key === Qt.Key_Down && !inMusic) select(current + 1);
        else if (event.key === Qt.Key_Up && !inMusic) select(current - 1);
        else if (event.key === Qt.Key_Space && Music.online) Music.toggle();
        else if (!inMusic) return;
        else if (t === "R") select(3);
        // o opens files from any music view: they land in the playlist.
        else if (t === "o" && Music.online) { select(1); Qt.callLater(() => { if (screen.item && screen.item.openFiles) screen.item.openFiles(); }); }
        else if (!Music.online) return;
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
        running: Music.online && window.inMusic
        onTriggered: if (!sinkInputs.running) sinkInputs.running = true
    }

    readonly property string wallpaper: status.wallpaper ? (status.wallpaper.effective || "") : ""
    function elapsed(t) {
        return (t >= 3600 ? Math.floor(t / 3600) + ":" + String(Math.floor(t % 3600 / 60)).padStart(2, "0") : Math.floor(t / 60)) + ":" + String(t % 60).padStart(2, "0");
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

            component Label: RiceText { x: 22; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5 }

            // The three sections; the open one lists its screens, the others say what they hold.
            Column {
                id: nav
                anchors.top: logo.bottom
                anchors.topMargin: 26
                width: parent.width - 1
                Repeater {
                    model: window.groups
                    Column {
                        id: section
                        required property var modelData
                        required property int index
                        readonly property bool open: window.group === index
                        width: nav.width

                        Item {
                            width: parent.width
                            height: 30
                            RiceText {
                                x: 22
                                anchors.verticalCenter: parent.verticalCenter
                                text: section.modelData.label
                                color: section.open ? Theme.fg : headMouse.containsMouse ? Theme.fg : Theme.faint
                                font.pixelSize: Theme.small
                                font.letterSpacing: 1.5
                                font.bold: section.open
                            }
                            RiceText {
                                anchors.right: parent.right
                                anchors.rightMargin: 22
                                anchors.verticalCenter: parent.verticalCenter
                                text: "alt " + (section.index + 1)
                                color: Theme.faint
                                font.pixelSize: Theme.small
                                visible: !section.open
                            }
                            MouseArea {
                                id: headMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: { window.selectGroup(section.index); keys.forceActiveFocus(); }
                            }
                        }

                        // Closed: one line about what the section holds right now.
                        RiceText {
                            x: 22
                            width: parent.width - 44
                            visible: !section.open && text !== ""
                            elide: Text.ElideRight
                            textFormat: Text.StyledText
                            font.pixelSize: Theme.small
                            color: Theme.dim
                            bottomPadding: 8
                            text: section.modelData.key === "music"
                                ? (Music.online && Music.track ? "<font color='" + (Music.playing ? Theme.ok : Theme.yel) + "'>" + (Music.playing ? "▶" : "❚❚") + "</font> " + Music.title : "")
                                : section.modelData.key === "games"
                                ? (Games.session ? "<font color='" + Theme.ok + "'>● " + window.elapsed(Games.sessionSeconds) + "</font> " + (Games.sessionGame ? Games.sessionGame.title : "") : "")
                                : ""
                        }

                        // Open: its screens, with the active band.
                        Item {
                            visible: section.open
                            width: parent.width
                            height: visible ? items.height + 8 : 0
                            Rectangle {
                                width: parent.width
                                height: 29
                                y: window.current * 29
                                color: Theme.accentA
                                Rectangle { width: 2; height: parent.height; color: Theme.accent }
                                Behavior on y { NumberAnimation { duration: Theme.tMed; easing.type: Theme.ease } }
                            }
                            Column {
                                id: items
                                width: parent.width
                                Repeater {
                                    model: section.open ? section.modelData.screens : []
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
                    }
                }
            }

            // ---- bottom block: what the open section is about ---------------------
            // SISTEMA: CURRENT, the wallpaper, palette and profile applied now.
            Column {
                visible: window.groupKey === "system"
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 18
                x: 22
                width: parent.width - 44
                spacing: 6
                Label { x: 0; text: "CURRENT"; bottomPadding: 2 }
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

            // MÚSICA: where the queue comes from, the mini player and VOL.
            Column {
                visible: window.inMusic
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 18
                x: 22
                width: parent.width - 44
                spacing: 2
                Label { x: 0; text: "SOURCES"; bottomPadding: 4 }
                Repeater {
                    model: [["local files", "local"], ["radio", "radio"], ["streaming", "stream"]]
                    Item {
                        required property var modelData
                        readonly property int count: Music.playlist.filter(t => Music.sourceOf(t.path) === modelData[1]).length
                        readonly property bool on: Music.online && Music.track !== null && Music.sourceOf(Music.track.path) === modelData[1]
                        width: parent.width
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
                Item { width: 1; height: 14 }
                // Mini player: dimmed while NOW PLAYING shows the same thing in full.
                Column {
                    width: parent.width
                    spacing: 2
                    opacity: window.current === 0 ? 0.25 : 1
                    Behavior on opacity { NumberAnimation { duration: Theme.tMed; easing.type: Theme.ease } }
                    Visualizer {
                        width: parent.width
                        height: 34
                        count: 28
                        compact: true
                        levels: window.spectrum
                        idle: !Music.playing || window.spectrum.length === 0
                        // Under NOW PLAYING the big one runs: hold this one still.
                        running: window.inMusic && window.current !== 0 && Music.online && !window.parked
                    }
                    Item { width: 1; height: 4 }
                    RiceText { width: parent.width; elide: Text.ElideRight; text: Music.online ? (Music.title || "—") : "—"; color: Theme.fg }
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
                Item { width: 1; height: 14 }
                // VOL ▮▮▮▮▮▮▮▮▯▯▯▯ 75%: click sets it, the wheel moves 5%.
                Item {
                    id: vol
                    width: parent.width
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

            // JOGOS: where the games come from and the session.
            Column {
                visible: window.inGames
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 18
                x: 22
                width: parent.width - 44
                spacing: 2
                Label { x: 0; text: "SOURCES"; bottomPadding: 4 }
                Repeater {
                    model: [["steam", "steam"], ["wine / .exe", "wine"], ["hydra", "hydra"], ["roms", "rom"]]
                    Item {
                        required property var modelData
                        readonly property int count: Games.games.filter(g => g.source === modelData[1] && !g.missing).length
                        width: parent.width
                        height: gameSrc.implicitHeight + 2
                        RiceText {
                            id: gameSrc
                            textFormat: Text.StyledText
                            text: (parent.count ? "<font color='" + Theme.ok + "'>●</font> " : "<font color='" + Theme.faint + "'>○</font> ") + parent.modelData[0]
                            color: parent.count ? Theme.fg : Theme.dim
                        }
                        RiceText { anchors.right: parent.right; text: parent.count; color: Theme.faint }
                    }
                }
                Item { width: 1; height: 14 }
                // SESSÃO: ● game mm:ss while it runs (the watcher keeps counting with LW closed).
                Label { x: 0; text: "SESSÃO"; bottomPadding: 2 }
                RiceText {
                    width: parent.width
                    elide: Text.ElideRight
                    textFormat: Text.StyledText
                    text: Games.session ? "<font color='" + Theme.ok + "'>● " + window.elapsed(Games.sessionSeconds) + "</font>  " + (Games.sessionGame ? Games.sessionGame.title : "") : "nenhum jogo rodando"
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

            // MÚSICA has one header for all its screens: the screen, cliamp's state and,
            // on NOW PLAYING, the visualizer modes. The other screens draw their own.
            RiceHeader {
                id: musicHeader
                visible: window.inMusic
                title: window.screens[window.current].name
                note: Music.online ? Music.status.toUpperCase() : "OFFLINE"
                noteColor: Music.playing ? Theme.ok : Music.status === "paused" ? Theme.yel : Theme.dim
                Repeater {
                    model: window.inMusic && window.current === 0 && Music.online && screen.item && screen.item.modes ? screen.item.modes : []
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
                anchors.top: window.inMusic ? musicHeader.bottom : parent.top
                anchors.topMargin: window.inMusic ? 14 : 0
                anchors.bottom: parent.bottom
                width: parent.width
                visible: !window.inMusic || Music.online
                source: window.screens[window.current].source
                onLoaded: {
                    if (item.title !== undefined) item.title = window.screens[window.current].name;
                    if (item.keyTarget !== undefined) item.keyTarget = keys;
                    if (item.levels !== undefined) {
                        item.levels = Qt.binding(() => window.spectrum);
                        item.levelSource = Qt.binding(() => window.spectrumSource);
                    }
                    // Each screen enters with a short fade.
                    item.opacity = Theme.motion ? 0 : 1;
                    enter.restart();
                }
                NumberAnimation { id: enter; target: screen.item; property: "opacity"; to: 1; duration: Theme.tMed; easing.type: Theme.ease }
                Connections {
                    target: screen.item
                    ignoreUnknownSignals: true
                    function onOpen(id) { sheet.openGame(id); }
                    function onLaunch(id) { window.launchGame(id); }
                    function onInstaller() { installSheet.openSheet(); }
                }
            }

            // MÚSICA with cliamp off: say so and offer to start it headless.
            Column {
                anchors.centerIn: screen
                visible: window.inMusic && !Music.online
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
                    onClicked: Music.startCliamp()
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

            Row {
                id: leftBlocks
                height: parent.height
                StatusBlock {
                    visible: window.groupKey === "system"
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
                anchors.right: contextBlock.left
                leftSeparator: true
                textColor: Theme.faint
                textFormat: Text.StyledText
                label: window.hints.map(h => "<font color='" + Theme.dim + "'>" + h[0] + "</font> " + h[1]).join("&nbsp;&nbsp;&nbsp;")
            }
            // The section's own end of the bar: the log, cliamp's output format, the last scan.
            StatusBlock {
                id: contextBlock
                anchors.right: parent.right
                separator: false
                clickable: window.groupKey === "system"
                label: window.inMusic ? (window.output || "—")
                     : window.inGames ? (Games.scanning ? "scan…" : Games.lastScan ? "scan: " + Games.lastScan.total + " · " + Games.lastScan.new + " novos" : "—")
                     : log.visible ? "LOG v" : "LOG ^"
                onClicked: log.visible = !log.visible
            }
        }

        LogPanel {
            id: log
            anchors.bottom: footer.top
            width: parent.width
            height: 260
            visible: false
            z: 20
        }

        // Audio files dropped on MÚSICA join cliamp's queue.
        DropArea {
            id: drop
            anchors.fill: parent
            enabled: window.inMusic && Music.online
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

        GameSheet {
            id: sheet
            anchors.fill: parent
            z: 30
            keyTarget: keys
            bottomInset: footer.height
            onLaunch: id => window.launchGame(id)
        }
        InstallSheet {
            id: installSheet
            anchors.fill: parent
            z: 30
            keyTarget: keys
            bottomInset: footer.height
        }
        LaunchScreen {
            id: launchScreen
            anchors.fill: parent
            z: 40
        }

        // Corners, as in a terminal frame.
        RiceText { x: 8; y: 6; text: "┌"; color: Theme.faint; font.pixelSize: 11 }
        RiceText { anchors.right: parent.right; anchors.rightMargin: 8; y: 6; text: "┐"; color: Theme.faint; font.pixelSize: 11 }

        BootScreen {
            id: boot
            anchors.fill: parent
            z: 50
            steps: [
                { label: "loading palette " + (window.status.generation || ""), done: Object.keys(Theme.dark).length > 0 && window.statusLoaded },
                { label: "reading action log", done: log.loaded },
                { label: window.inMusic ? (Music.online ? "connected to cliamp" : "connecting to cliamp") : window.inGames ? "reading games.json: " + Games.games.length + " games" : "reading profile: " + (Theme.profile || "?"),
                  done: window.inMusic ? !Music.connecting : window.inGames ? Games.loaded : Theme.profile !== "" },
                { label: "loading " + window.screens[window.current].name.toLowerCase(), done: screen.status === Loader.Ready },
                { label: "starting LW", done: true }
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
        running: !window.parked
        repeat: true
        onTriggered: {
            clock.blink = !clock.blink;
            if (clock.blink)
                clock.now = new Date();
        }
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

    // The message is typed out, one character every 12 ms.
    QtObject {
        id: typed
        readonly property string full: window.syncError ? "[ FAIL ] " + window.syncError
            : Status.busy ? progress.text
            : Status.message ? Status.message
            : window.inMusic && !Music.online ? "[ -- ] cliamp offline"
            : window.groupKey === "system" ? log.lastLine : ""
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
