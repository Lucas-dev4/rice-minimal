//@ pragma UseQApplication
import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.components
// Indexes the folders whose files are used here or loaded by path: one line per module.
import qs.screens
import qs.player
import qs.arcade

// shell.qml — a janela principal do LW (Quickshell). Barra lateral com as seções, que são os
// módulos ativos (Modules.qml; hoje SISTEMA, MÚSICA, JOGOS), a área da tela escolhida, o rodapé
// de status e o painel LOG. O que é só de um módulo fica no gancho dele (components/LwModule.qml).
// Cada tela fica num arquivo: screens/ (SISTEMA), player/ (MÚSICA) e arcade/ (JOGOS).
// Os atalhos do Hyprland chegam aqui pelo IPC "lw" (bloco IpcHandler abaixo).
//
// LW — one window for the whole system: SISTEMA (wallpapers, shortcuts, profiles…),
// MÚSICA (cliamp) and JOGOS (library, backlog, play sessions). Opened by `lw gui`,
// `lw music` and `lw games` (Super+BackSpace / Super+M / Super+G) on that section.
// Look and behaviour follow docs/lw-prototype.html; all tokens live in Theme.qml.
FloatingWindow {
    id: window

    // The active modules, in sidebar order (Modules.qml).
    readonly property var groups: Modules.active
    // The section and, inside it, the screen; each section remembers its last screen.
    // Until the person picks one, it follows LW_START_GROUP, even if that module arrives later.
    readonly property string start: Quickshell.env("LW_START_GROUP") || ""
    property string groupKey: groups.some(g => g.id === start) ? start : groups[0].id
    readonly property int group: Math.max(0, groups.findIndex(g => g.id === groupKey))
    property var lastScreen: ({})
    readonly property int current: lastScreen[groupKey] || 0
    readonly property var screens: groups[group].screens
    // What each module puts on the window outside its screens (components/LwModule.qml), by id.
    property var hooks: ({})
    readonly property LwModule hook: hookOf(groupKey)
    // O gancho de um módulo; o neutro se ele não tem (ou ainda não carregou).
    function hookOf(id) { return hooks[id] || neutral; }
    // Os ganchos carregados, na ordem da barra lateral.
    function allHooks() { return groups.map(g => hooks[g.id]).filter(h => h); }
    readonly property bool inGames: groupKey === "games"

    property var status: ({})
    property bool statusLoaded: false
    readonly property var globalHints: hook.hints.length ? hook.hints : [["↑↓", "tela"], ["alt 1-3", "seção"], ["q", "fechar"]]
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
    // Ctrl+J: esconde a janela sem parar nada (música e jogo continuam).
    function park() { parked = true; visible = false; }
    // Mostra de novo a janela escondida.
    function unpark() { visible = true; parked = false; keys.forceActiveFocus(); }
    // True se a tecla é Ctrl+J.
    function isPark(event) { return event.key === Qt.Key_J && (event.modifiers & Qt.ControlModifier); }

    // Each module decides what closing does to it (MÚSICA: stop the music or only save the session).
    function quit() {
        for (const id in hooks) if (hooks[id]) hooks[id].closing(id === groupKey);
        Qt.quit();
    }

    // Abre a tela de número index dentro da seção atual.
    function select(index) {
        const next = Object.assign({}, lastScreen);
        next[groupKey] = Math.max(0, Math.min(screens.length - 1, index));
        lastScreen = next;
    }
    // Troca de seção pela posição na barra lateral (Alt+1/2/3).
    function selectGroup(index) {
        if (index < 0 || index >= groups.length || index === group) return;
        sheet.close();
        installSheet.close();
        groupKey = groups[index].id;
        enterGroup();
    }
    // The section the hooks were last told about (its hook may still be loading).
    property string enteredKey: ""
    // JOGOS scans the libraries once per window.
    property bool scanned: false
    // Avisa os ganchos da troca de seção; JOGOS faz o scan de jogos.
    function enterGroup() {
        if (enteredKey !== groupKey) {
            hookOf(enteredKey).exited();
            enteredKey = groupKey;
            hookOf(groupKey).entered();
        }
        if (inGames && !scanned) { scanned = true; Games.scan(true); }
    }
    // Fecha a ficha e inicia o jogo.
    function launchGame(id) { sheet.close(); Games.launch(id); }

    IpcHandler {
        target: "lw"
        function close(): void { window.quit(); }
        // IPC: "yes" se a janela está escondida (Ctrl+J).
        function hidden(): string { return window.parked ? "yes" : "no"; }
        // IPC: mostra a janela escondida.
        function reveal(): void { window.unpark(); }
        // The section shown now: system, music or games.
        function section(): string { return window.groupKey; }
        // IPC: vai para uma seção pelo nome (usado pelos atalhos Super+BackSpace/M/G).
        function go(name: string): void { window.selectGroup(window.groups.findIndex(g => g.id === name)); }
        // IPC: abre uma tela da seção atual.
        function open(index: int): void { window.select(index); }
        // IPC: mostra/esconde o painel LOG.
        function toggleLog(): void { Status.logOpen = !Status.logOpen; }
        // IPC: salva um print da janela (testes).
        function shot(path: string): void { content.grabToImage(result => result.saveToFile(path)); }
        // IPC: simula uma tecla (testes automáticos).
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
        // IPC: digita uma busca na tela atual (testes).
        function query(text: string): string {
            if (!screen.item || !screen.item.query) return "this view has no search";
            screen.item.query(text);
            return "ok";
        }
        // IPC: abre a ficha de um jogo (vazio fecha).
        function openSheet(id: string): string { if (id) sheet.openGame(id); else sheet.close(); return "ok"; }
        // IPC: abre a tela INSTALAR de JOGOS.
        function installer(): void { window.selectGroup(window.groups.findIndex(g => g.id === "games")); installSheet.openSheet(); }
        // Scriptable state and actions (scripts/music-check.sh, tests): the hooks add theirs.
        function state(): string {
            return JSON.stringify(Object.assign({
                section: window.groupKey, view: window.current, screen: window.screens[window.current].name
            }, ...window.allHooks().map(h => h.state()), {
                games: Games.games.length, scanning: Games.scanning, session: Games.session, message: Status.message
            }));
        }
        // IPC: executa uma ação pelo nome (testes); o primeiro gancho que a conhece responde.
        function act(op: string, arg: string): string {
            if (op === "quit") window.quit();
            else if (!window.allHooks().some(h => h.act(op, arg))) return "unknown " + op;
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
            Status.profile = data.profile || "";
        }
        onFailed: message => {
            window.statusLoaded = true;
            console.warn("status:", message);
        }
        Component.onCompleted: call(["status", "--json"])
    }

    // Um gancho ficou pronto: recebe o que só o shell sabe e, se a seção dele já está aberta, é avisado.
    function addHook(id, item) {
        item.keyTarget = keys;
        item.active = Qt.binding(() => window.groupKey === id);
        item.current = Qt.binding(() => window.lastScreen[id] || 0);
        item.parked = Qt.binding(() => window.parked);
        hooks = Object.assign({}, hooks, { [id]: item });
        if (enteredKey === id) item.entered();
        if (groupKey === id && screen.status === Loader.Ready) item.screenLoaded(screen.item);
    }
    // The modules' hooks stay alive with the window.
    LwModule { id: neutral }
    Repeater {
        model: ScriptModel { values: window.groups; objectProp: "id" }
        Loader {
            required property var modelData
            visible: false
            source: modelData.hook ? modelData.folder + "/" + modelData.hook : ""
            onLoaded: window.addHook(modelData.id, item)
            Connections {
                target: item
                ignoreUnknownSignals: true
                function onOpenScreen(index) { if (window.groupKey === modelData.id) window.select(index); }
            }
        }
    }
    // Without LW_MODULES the starting section may arrive late.
    Connections {
        target: Modules
        function onActiveChanged() { Qt.callLater(window.enterGroup); }
    }
    Binding { target: Status; property: "logLine"; value: log.lastLine }

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

    // Short status-bar messages for what the games do.
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

    // Keyboard: overlays, then the screen, then the section keys, then the window keys, then
    // the keys a module answers from any section.
    // Test hook: `qs ipc -p gui call lw key l` reaches only this window, never the focused one.
    function handle(event) {
        // Not while SHORTCUTS records a combination: Ctrl+J is a combination too.
        if (isPark(event) && !(screen.item && screen.item.recording)) { park(); event.accepted = true; return; }
        if (boot.visible) { boot.finish(); event.accepted = true; return; }
        if (launchScreen.shown) { launchScreen.handleKey(event); event.accepted = true; return; }
        if (installSheet.shown) { installSheet.handleKey(event); event.accepted = true; return; }
        if (sheet.shown) { if (sheet.handleKey(event)) event.accepted = true; return; }
        if (allHooks().some(h => h.overlayKey(event))) { event.accepted = true; return; }
        const digit = parseInt(event.text);
        // Alt+1/2/3: the sections, by position. Checked before the screen so no screen eats it.
        if ((event.modifiers & Qt.AltModifier) && event.key >= Qt.Key_1 && event.key < Qt.Key_1 + Math.min(9, groups.length)) {
            selectGroup(event.key - Qt.Key_1);
            event.accepted = true;
            return;
        }
        if (screen.item && screen.item.handleKey && screen.item.handleKey(event)) { event.accepted = true; return; }
        if (hook.key(event)) { event.accepted = true; return; }
        if (digit >= 1 && digit <= screens.length) select(digit - 1);
        else if (event.key === Qt.Key_Q || event.key === Qt.Key_Escape) quit();
        else if (event.key === Qt.Key_Down) select(current + 1);
        else if (event.key === Qt.Key_Up) select(current - 1);
        else if (!allHooks().some(h => h.backgroundKey(event))) return;
        event.accepted = true;
    }

    // Segundos → "m:ss" ou "h:mm:ss".
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

            // The sections; the open one lists its screens, the others say what they hold.
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
                                text: section.modelData.name
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
                            text: section.modelData.id === "games"
                                ? (Games.session ? "<font color='" + Theme.ok + "'>● " + window.elapsed(Games.sessionSeconds) + "</font> " + (Games.sessionGame ? Games.sessionGame.title : "") : "")
                                : window.hookOf(section.modelData.id).summary
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
            // From the module's hook; JOGOS is still drawn below.
            Repeater {
                model: ScriptModel { values: window.groups; objectProp: "id" }
                Loader {
                    required property var modelData
                    visible: window.groupKey === modelData.id
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 18
                    x: 22
                    width: parent.width - 44
                    sourceComponent: window.hookOf(modelData.id).sidebar
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

            // A module may have one header for all its screens; the other screens draw their own.
            Loader {
                id: header
                width: parent.width
                sourceComponent: window.hook.header
            }

            Loader {
                id: screen
                anchors.top: parent.top
                // Not header.bottom: an empty Loader keeps the height of its last item.
                anchors.topMargin: header.item ? header.item.height + 14 : 0
                anchors.bottom: parent.bottom
                width: parent.width
                visible: window.hook.ready
                source: window.groups[window.group].folder + "/" + window.screens[window.current].file
                onLoaded: {
                    if (item.title !== undefined) item.title = window.screens[window.current].name;
                    if (item.keyTarget !== undefined) item.keyTarget = keys;
                    window.hookOf(window.groupKey).screenLoaded(item);
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

            // What the module shows while its screens cannot work (MÚSICA with cliamp off).
            Loader {
                anchors.centerIn: screen
                visible: !window.hook.ready
                sourceComponent: window.hook.gate
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
                Repeater {
                    model: ScriptModel { values: window.groups; objectProp: "id" }
                    Loader {
                        required property var modelData
                        visible: window.groupKey === modelData.id
                        height: parent.height
                        sourceComponent: window.hookOf(modelData.id).footerLeft
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
                textColor: Status.error ? Theme.red : Status.busy ? Theme.accent
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
            // The section's own end of the bar: the log, the audio format, the last scan.
            StatusBlock {
                id: contextBlock
                anchors.right: parent.right
                separator: false
                clickable: window.hook.contextClickable
                label: window.inGames ? (Games.scanning ? "scan…" : Games.lastScan ? "scan: " + Games.lastScan.total + " · " + Games.lastScan.new + " novos" : "—")
                     : window.hook.context
                onClicked: window.hook.contextClicked()
            }
        }

        LogPanel {
            id: log
            anchors.bottom: footer.top
            width: parent.width
            height: 260
            visible: Status.logOpen
            z: 20
        }

        // The modules' layers over the window (MÚSICA: dropping files).
        Repeater {
            model: ScriptModel { values: window.groups; objectProp: "id" }
            Loader {
                required property var modelData
                anchors.fill: parent
                z: 40
                sourceComponent: window.hookOf(modelData.id).overlay
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
                !window.inGames && window.hook.bootStep ? window.hook.bootStep :
                { label: window.inGames ? "reading games.json: " + Games.games.length + " games" : "reading profile: " + (Theme.profile || "?"),
                  done: window.inGames ? Games.loaded : Theme.profile !== "" },
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
        readonly property string full: Status.error ? "[ FAIL ] " + Status.error
            : Status.busy ? progress.text
            : Status.message ? Status.message
            : window.hook.idleText
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
