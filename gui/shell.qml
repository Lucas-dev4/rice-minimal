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
// módulos ativos (Modules.qml), a área da tela escolhida, o rodapé de status e o painel LOG.
// Esta janela não conhece nenhum módulo: o que é só de um fica no gancho dele
// (components/LwModule.qml), e cada tela num arquivo da pasta dele.
// Os atalhos do Hyprland chegam aqui pelo IPC "lw" (bloco IpcHandler abaixo).
//
// LW — one window for the whole system. Opened by `lw gui` and by each module's `open`
// command (modules/<id>/module.toml) on that section.
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
    // A tela aberta (folder, name e file). Uma conta só: `screens` e `current` não mudam juntos na
    // troca de seção, e a posição de uma seção não vale na lista da outra.
    readonly property var shown: {
        const g = groups.find(g => g.id === groupKey) || groups[0];
        const s = g.screens[Math.min(lastScreen[groupKey] || 0, g.screens.length - 1)];
        return { folder: g.folder, name: s.name, file: s.file };
    }
    // What each module puts on the window outside its screens (components/LwModule.qml), by id.
    property var hooks: ({})
    readonly property LwModule hook: hookOf(groupKey)
    // O gancho de um módulo; o neutro se ele não tem (ou ainda não carregou).
    function hookOf(id) { return hooks[id] || neutral; }
    // Os ganchos carregados, na ordem da barra lateral.
    function allHooks() { return groups.map(g => hooks[g.id]).filter(h => h); }

    property var status: ({})
    property bool statusLoaded: false
    readonly property var globalHints: hook.hints.length ? hook.hints : [["↑↓", "tela"], [Modules.altKeys, "seção"], ["q", "fechar"]]
    readonly property var hints: screen.item && screen.item.hints && screen.item.hints.length ? screen.item.hints : globalHints

    title: "LW"
    implicitWidth: 1220
    implicitHeight: 780
    // system.fullscreen: a janela pede tela cheia ao compositor. Fora dela valem o tamanho e a
    // posição da regra do Hyprland (config/hypr/rice-integration.lua).
    fullscreen: Modules.fullscreen
    color: "transparent"
    // See-through like the terminal (RICE_GUI_OPACITY overrides; 1 = solid).
    Component.onCompleted: { Theme.alpha = Number(Quickshell.env("RICE_GUI_OPACITY") || 0.85); enterGroup(); }
    onVisibleChanged: if (!visible && !parked) quit()
    // Ctrl+J hides the window without closing it: the modules keep running. The same Super
    // shortcut brings it back (`lw` asks `hidden` first).
    property bool parked: false
    // Como a janela estava ao ser escondida: ela renasce ao voltar, e o compositor não lembra.
    property bool parkedFull: false
    // Ctrl+J: esconde a janela sem parar nada.
    function park() { parkedFull = fullscreen; parked = true; visible = false; }
    // Mostra de novo a janela escondida (só o IPC pode pedir isso com ela à vista).
    function unpark() { if (parked) fullscreen = parkedFull; visible = true; parked = false; keys.forceActiveFocus(); }
    // True se a tecla é Ctrl+J.
    function isPark(event) { return event.key === Qt.Key_J && (event.modifiers & Qt.ControlModifier); }

    // Each module decides what closing does to it.
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
        // O foco sai da tela antiga antes de ela sumir: sem isso, um campo levaria o teclado junto.
        keys.forceActiveFocus();
        groupKey = groups[index].id;
        enterGroup();
    }
    // The section the hooks were last told about (its hook may still be loading).
    property string enteredKey: ""
    // Avisa os ganchos da troca de seção.
    function enterGroup() {
        if (enteredKey !== groupKey) {
            hookOf(enteredKey).exited();
            enteredKey = groupKey;
            hookOf(groupKey).entered();
        }
    }
    // Uma ação pelo nome: o primeiro gancho que a conhece responde.
    function act(op, arg) { return allHooks().some(h => h.act(op, arg)) ? "ok" : "unknown " + op; }

    IpcHandler {
        target: "lw"
        function close(): void { window.quit(); }
        // IPC: "yes" se a janela está escondida (Ctrl+J).
        function hidden(): string { return window.parked ? "yes" : "no"; }
        // IPC: mostra a janela escondida.
        function reveal(): void { window.unpark(); }
        // The id of the section shown now.
        function section(): string { return window.groupKey; }
        // IPC: vai para uma seção pelo nome (usado pelos atalhos do Hyprland). "unknown": esta janela não a tem.
        function go(name: string): string {
            const index = window.groups.findIndex(g => g.id === name);
            window.selectGroup(index);
            return index < 0 ? "unknown" : "ok";
        }
        // IPC: um aviso no rodapé.
        function notice(text: string): void { Status.say("[ !! ] " + text, Theme.yel); }
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
        // Nomes antigos de duas ações: abrir uma ficha (vazio fecha) e a tela de instalar.
        function openSheet(id: string): string { return window.act("openSheet", id); }
        function installer(): void { window.act("installer", ""); }
        // Scriptable state and actions (scripts/music-check.sh, tests): the hooks add theirs.
        function state(): string {
            return JSON.stringify(Object.assign({
                section: window.groupKey, view: window.current, screen: window.shown.name, typing: !keys.focus, fullscreen: window.fullscreen
            }, ...window.allHooks().map(h => h.state()), { message: Status.message }));
        }
        // IPC: executa uma ação pelo nome (testes).
        function act(op: string, arg: string): string {
            if (op !== "quit") return window.act(op, arg);
            window.quit();
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
        item.footerHeight = Qt.binding(() => footer.height);
        hooks = Object.assign({}, hooks, { [id]: item });
        item.started();
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
                function onOpenSection() { window.selectGroup(window.groups.findIndex(g => g.id === modelData.id)); }
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
        // O gancho desenhado por cima (o último da barra lateral) recebe antes.
        if (allHooks().reverse().some(h => h.overlayKey(event))) { event.accepted = true; return; }
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
                            text: window.hookOf(section.modelData.id).summary
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
            // From the module's hook.
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
                source: window.shown.folder + "/" + window.shown.file
                onLoaded: {
                    if (item.title !== undefined) item.title = window.shown.name;
                    if (item.keyTarget !== undefined) item.keyTarget = keys;
                    window.hookOf(window.groupKey).screenLoaded(item);
                    // Each screen enters with a short fade.
                    item.opacity = Theme.motion ? 0 : 1;
                    enter.restart();
                }
                NumberAnimation { id: enter; target: screen.item; property: "opacity"; to: 1; duration: Theme.tMed; easing.type: Theme.ease }
            }

            // What the module shows while its screens cannot work.
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
            // The section's own end of the bar.
            StatusBlock {
                id: contextBlock
                anchors.right: parent.right
                separator: false
                clickable: window.hook.contextClickable
                label: window.hook.context
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

        // The modules' layers over the window.
        Repeater {
            model: ScriptModel { values: window.groups; objectProp: "id" }
            Loader {
                required property var modelData
                anchors.fill: parent
                z: 40
                sourceComponent: window.hookOf(modelData.id).overlay
            }
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
                window.hook.bootStep || { label: "reading profile: " + (Theme.profile || "?"), done: Theme.profile !== "" },
                { label: "loading " + window.shown.name.toLowerCase(), done: screen.status === Loader.Ready },
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
