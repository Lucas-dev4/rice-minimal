import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.components
import "ShortcutWords.js" as Words

// LW // SHORTCUTS — readable descriptions, keycaps, collapsible groups, recording.
// binds.lua is only changed through `rice shortcuts set` (same validation as before);
// descriptions and groups are GUI notes kept in ~/.local/state/rice-minimal/gui/shortcuts.json.
Item {
    id: root

    property Item keyTarget: null
    property var binds: []
    property string revision: ""
    property var notes: ({})
    property var closed: []
    property string currentId: ""
    property var draft: ({ key: "", command: "", desc: "", group: "" })
    property bool recording: false
    property var recordMods: []
    property bool armedRestore: false
    property bool armedSave: false

    readonly property var hints: recording ? [["esc", "cancelar"]] : [["jk", "move"], ["hl", "grupo"], ["r", "gravar"], ["⏎", "editar"], ["/", "search"]]
    readonly property bool busy: saver.running || restorer.running

    function idOf(b) { return (b.editable ? "b" : "x") + b.line; }
    function info(b) {
        const auto = Words.describe(b);
        const note = notes[b.action] || {};
        return { desc: note.desc || auto[0], group: note.group || auto[1] };
    }

    // normal(key) -> [ids]; a combination used twice is a conflict.
    readonly property var usage: {
        const map = {};
        for (const b of binds) {
            const k = Words.normal(b.key);
            (map[k] = map[k] || []).push(idOf(b));
        }
        return map;
    }
    function conflictsOf(b, key) {
        return (usage[Words.normal(key || b.key)] || []).filter(id => id !== idOf(b));
    }
    function byId(id) { return binds.find(b => idOf(b) === id) || null; }

    readonly property var entries: {
        const needle = search.text.toLowerCase();
        const out = [];
        for (const g of Words.GROUPS) {
            const rows = binds.filter(b => {
                const i = info(b);
                return i.group === g && (!needle || (i.desc + " " + b.action + " " + b.key).toLowerCase().includes(needle));
            });
            if (rows.length === 0)
                continue;
            const shut = closed.indexOf(g) >= 0 && !needle;
            out.push({ group: g, count: rows.length, shut: shut });
            if (!shut)
                for (const b of rows)
                    out.push({ bind: b });
        }
        return out;
    }
    readonly property var visibleIds: entries.filter(e => e.bind).map(e => idOf(e.bind))
    readonly property var selected: byId(currentId)
    readonly property bool commandEditable: !!selected && selected.editable && selected.command !== null
    // A phrase such as "aumentar o som" in COMANDO becomes the real command when saved.
    readonly property bool noctPrefix: !!selected && /noctCall\s*\.\./.test(selected.action)
    readonly property var phrase: commandEditable && draft.command !== (selected ? selected.command : "")
        ? Words.translate(draft.command, noctPrefix) : null

    function reload() { reader.call(["shortcuts", "list", "--json"]); }

    function fill() {
        if (!selected) {
            draft = { key: "", command: "", desc: "", group: "" };
            return;
        }
        const i = info(selected);
        draft = { key: selected.key, command: selected.command || "", desc: i.desc, group: i.group };
        armedSave = false;
        // Typing into a field replaces its binding, so the fields are refilled explicitly.
        descField.text = i.desc;
        // Computed here: commandEditable may still hold the previous row's value.
        commandField.text = selected.editable && selected.command !== null ? draft.command : selected.action;
    }

    function move(step) {
        const ids = visibleIds;
        if (ids.length === 0)
            return;
        const at = ids.indexOf(currentId);
        currentId = ids[Math.max(0, Math.min(ids.length - 1, at < 0 ? 0 : at + step))];
    }

    function toggleGroup(g, shut) {
        const next = closed.filter(x => x !== g);
        if (shut)
            next.push(g);
        closed = next;
        if (selected && info(selected).group === g && shut)
            Qt.callLater(() => { if (visibleIds.indexOf(currentId) < 0 && visibleIds.length) currentId = visibleIds[0]; });
    }

    function setDraft(field, value) {
        const next = Object.assign({}, draft);
        next[field] = value;
        draft = next;
    }

    function writeNotes(next) {
        notes = next;
        notesFile.setText(JSON.stringify(next, null, 2) + "\n");
    }

    function save() {
        const b = selected;
        if (!b || busy)
            return;
        const auto = Words.describe(b);
        const i = info(b);
        const noteChanged = draft.desc !== i.desc || draft.group !== i.group;
        const args = ["shortcuts", "set", "--line", String(b.line), "--revision", revision, "--json"];
        const before = args.length;
        if (b.editable && Words.normal(draft.key) !== Words.normal(b.key))
            args.push("--key", draft.key);
        if (phrase && phrase.error) {
            Status.say("[ FAIL ] " + phrase.error, Theme.red);
            return;
        }
        const command = phrase ? phrase.command : draft.command;
        if (commandEditable && command !== b.command)
            args.push("--command", command);
        if (noteChanged) {
            const next = Object.assign({}, notes);
            // A command edit changes the action text; the note follows it.
            const action = args.indexOf("--command") >= 0 ? b.action.replace(b.command, command) : b.action;
            delete next[b.action];
            const note = {};
            if (draft.desc !== auto[0]) note.desc = draft.desc;
            if (draft.group !== auto[1]) note.group = draft.group;
            if (note.desc || note.group)
                next[action] = note;
            writeNotes(next);
        }
        if (args.length > before) {
            Status.start("saving");
            saver.call(args);
        } else if (noteChanged) {
            Status.say("[ OK ] descrição salva (só na GUI)");
        } else {
            Status.say("[ -- ] nada mudou", Theme.dim);
        }
    }

    // ---- recording: an empty Hyprland submap lets Super combinations reach this window.
    function startRecording() {
        if (!selected || !selected.editable || recording)
            return;
        recording = true;
        recordMods = [];
        root.keyTarget.forceActiveFocus();
        submap.exec(["hyprctl", "dispatch", 'hl.dsp.submap("lw-record")']);
        Status.say("[ .. ] gravando — pressione o atalho (Esc cancela)", Theme.accent);
    }
    function stopRecording(message, tint) {
        if (!recording)
            return;
        recording = false;
        recordMods = [];
        submap.exec(["hyprctl", "dispatch", 'hl.dsp.submap("reset")']);
        if (message)
            Status.say(message, tint);
    }
    function record(event) {
        const mods = Words.modifierNames(event.modifiers);
        if (Words.isModifierKey(event.key)) {
            recordMods = mods;
            return;
        }
        if (event.key === Qt.Key_Escape && mods.length === 0) {
            stopRecording("[ -- ] gravação cancelada", Theme.dim);
            return;
        }
        const name = Words.keyName(event);
        if (!name)
            return;
        // binds.lua writes every combination as mainMod .. "+ ...": Super is mandatory.
        if (mods.indexOf("SUPER") < 0) {
            stopRecording("[ !! ] use Super na combinação — binds.lua sempre começa com Super", Theme.red);
            return;
        }
        const key = mods.concat([name]).join(" + ");
        setDraft("key", key);
        const clash = conflictsOf(selected, key);
        if (clash.length)
            stopRecording("[ !! ] " + key + " já é usado por: " + clash.map(id => info(byId(id)).desc).join(", "), Theme.red);
        else
            stopRecording("[ OK ] atalho gravado: " + key + " — SAVE grava no arquivo", Theme.ok);
    }

    function handleKey(event) {
        if (recording) {
            record(event);
            return true;
        }
        switch (event.key) {
        case Qt.Key_Up: case Qt.Key_K: move(-1); return true;
        case Qt.Key_Down: case Qt.Key_J: move(1); return true;
        case Qt.Key_Left: case Qt.Key_H: if (selected) toggleGroup(info(selected).group, true); return true;
        case Qt.Key_Right: case Qt.Key_L:
            closed = [];
            return true;
        case Qt.Key_R: startRecording(); return true;
        case Qt.Key_Slash: search.focusInput(); return true;
        case Qt.Key_Return: case Qt.Key_Enter: descField.focusInput(); return true;
        }
        return false;
    }

    Component.onCompleted: reload()
    Component.onDestruction: if (recording) Quickshell.execDetached(["hyprctl", "dispatch", 'hl.dsp.submap("reset")'])
    onSelectedChanged: fill()
    onVisibleIdsChanged: if (visibleIds.length && visibleIds.indexOf(currentId) < 0) currentId = visibleIds[0]

    Process { id: submap; function exec(cmd) { command = cmd; running = true; } }

    // Esc is bound inside the submap and handled by Hyprland; notice when it left.
    Process {
        id: submapPoll
        command: ["hyprctl", "submap"]
        stdout: StdioCollector {
            onStreamFinished: if (root.recording && text.trim() === "default" && recordTimeout.elapsed > 400)
                root.stopRecording("[ -- ] gravação cancelada", Theme.dim)
        }
    }
    Timer {
        id: recordTimeout
        property int elapsed: 0
        running: root.recording
        interval: 200
        repeat: true
        onRunningChanged: elapsed = 0
        onTriggered: {
            elapsed += interval;
            if (!submapPoll.running) submapPoll.running = true;
            if (elapsed >= 10000) root.stopRecording("[ -- ] gravação expirou (10 s)", Theme.dim);
        }
    }

    FileView {
        id: notesFile
        path: Theme.guiStatePath + "/shortcuts.json"
        printErrors: false
        atomicWrites: true
        onLoaded: {
            try { root.notes = JSON.parse(text()); } catch (error) { root.notes = {}; }
        }
    }

    RiceCommand {
        id: reader
        onSucceeded: data => {
            root.revision = data.revision;
            root.binds = data.binds.concat(data.external);
            if (!root.selected && root.visibleIds.length)
                root.currentId = root.visibleIds[0];
            root.fill();
        }
        onFailed: message => Status.say("[ FAIL ] " + message, Theme.red)
    }
    RiceCommand {
        id: saver
        onSucceeded: {
            Status.stop();
            Status.say("[ OK ] salvo em binds.lua; backup guardado");
            root.reload();
        }
        onFailed: message => { Status.stop(); Status.say("[ FAIL ] " + message, Theme.red); }
    }
    RiceCommand {
        id: checker
        onSucceeded: data => {
            const local = Object.keys(root.usage).filter(k => root.usage[k].length > 1);
            if (data.duplicates.length > 0 || local.length > 0)
                Status.say("[ !! ] em conflito: " + data.duplicates.concat(local).join(", "), Theme.red);
            else
                Status.say("[ OK ] " + data.count + " atalhos, nenhum conflito");
        }
        onFailed: message => Status.say("[ FAIL ] " + message, Theme.red)
    }
    RiceCommand {
        id: finder
        onSucceeded: data => {
            if (data.backups.length === 0)
                Status.say("[ WARN ] nenhum backup ainda", Theme.yel);
            else
                restorer.call(["shortcuts", "restore", data.backups[0].path, "--json"]);
        }
        onFailed: message => Status.say("[ FAIL ] " + message, Theme.red)
    }
    RiceCommand {
        id: restorer
        onSucceeded: {
            Status.say("[ OK ] último backup restaurado", Theme.accent);
            root.reload();
        }
        onFailed: message => Status.say("[ FAIL ] " + message, Theme.red)
    }
    Timer { id: disarm; interval: 3000; onTriggered: { root.armedRestore = false; root.armedSave = false; } }

    RiceHeader {
        id: title
        width: parent.width - search.width - 14
        title: "LW // SHORTCUTS"
        note: root.visibleIds.length + "/" + root.binds.length
    }

    SearchBox {
        id: search
        anchors.right: parent.right
        anchors.verticalCenter: title.verticalCenter
        keyTarget: root.keyTarget
    }

    // Legend + hint
    Row {
        id: legend
        anchors.top: title.bottom
        anchors.topMargin: 14
        spacing: 5
        Repeater {
            model: [["◆", "super"], ["⌃", "ctrl"], ["⌥", "alt"], ["⇧", "shift"]]
            Row {
                required property var modelData
                spacing: 5
                Keycap { label: modelData[0]; modifier: true }
                RiceText { anchors.verticalCenter: parent.verticalCenter; text: modelData[1] + "  "; color: Theme.faint; font.pixelSize: Theme.small }
            }
        }
    }
    RiceText {
        anchors.right: parent.right
        anchors.verticalCenter: legend.verticalCenter
        text: "r gravar · h/l recolher grupo"
        color: Theme.faint
        font.pixelSize: Theme.small
    }

    // ================= LIST =================
    ListView {
        id: list
        anchors.top: legend.bottom
        anchors.topMargin: 6
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: panel.left
        anchors.rightMargin: 20
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        topMargin: 6
        bottomMargin: 6
        model: root.entries
        currentIndex: root.entries.findIndex(e => e.bind && root.idOf(e.bind) === root.currentId)
        highlightMoveDuration: 0
        highlightFollowsCurrentItem: false
        onCurrentIndexChanged: if (currentIndex >= 0) positionViewAtIndex(currentIndex, ListView.Contain)

        delegate: Item {
            id: entry

            required property var modelData
            required property int index
            readonly property bool isGroup: modelData.group !== undefined
            readonly property var bind: modelData.bind || null
            readonly property bool current: !isGroup && root.idOf(bind) === root.currentId
            readonly property bool lit: current || hover.containsMouse
            readonly property var clash: isGroup ? [] : root.conflictsOf(bind)
            readonly property var text: isGroup ? null : root.info(bind)

            width: ListView.view.width
            height: isGroup ? groupRow.height : Math.max(keys.height, words.height) + 12

            // Group header: ▾ JANELA 7
            Row {
                id: groupRow
                visible: entry.isGroup
                height: 30
                x: 10
                spacing: 8
                RiceText {
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 6
                    text: "▾"
                    color: Theme.faint
                    rotation: entry.isGroup && entry.modelData.shut ? -90 : 0
                    Behavior on rotation { NumberAnimation { duration: Theme.tFast; easing.type: Theme.ease } }
                }
                RiceText {
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 6
                    text: entry.isGroup ? entry.modelData.group : ""
                    color: hover.containsMouse ? Theme.dim : Theme.faint
                    font.pixelSize: Theme.small
                    font.letterSpacing: 1.5
                }
                RiceText {
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 6
                    text: entry.isGroup ? entry.modelData.count : ""
                    color: Theme.dim
                    font.pixelSize: Theme.small
                }
            }

            // Bind row
            Rectangle {
                visible: !entry.isGroup
                anchors.fill: parent
                color: entry.current ? Theme.accentA : hover.containsMouse ? Qt.alpha(Theme.fg, 0.025) : "transparent"
                Rectangle { width: 2; height: parent.height; color: entry.current ? Theme.accent : "transparent" }
            }
            Flow {
                id: keys
                visible: !entry.isGroup
                x: 10
                y: 6
                width: 170
                spacing: 4
                Repeater {
                    model: entry.isGroup ? [] : Words.tokens(entry.bind.key)
                    Keycap {
                        required property string modelData
                        label: Words.symbol(modelData)
                        modifier: Words.isMod(modelData)
                    }
                }
            }
            Column {
                id: words
                visible: !entry.isGroup
                x: 194
                y: 6
                width: parent.width - x - 10
                Row {
                    spacing: 0
                    RiceText {
                        id: descText
                        anchors.verticalCenter: parent.verticalCenter
                        text: entry.text ? entry.text.desc : ""
                        color: Theme.fg
                    }
                    RiceText {
                        visible: entry.clash.length > 0
                        anchors.verticalCenter: parent.verticalCenter
                        text: "  ⚠ conflito"
                        color: Theme.red
                        font.pixelSize: Theme.small
                    }
                    RiceText {
                        visible: entry.bind && !entry.bind.editable
                        anchors.verticalCenter: parent.verticalCenter
                        text: "  [fixo]"
                        color: Theme.faint
                        font.pixelSize: Theme.small
                    }
                }
                // The raw command shows only on the selected or hovered row.
                RiceText {
                    width: parent.width
                    height: entry.lit ? 16 : 0
                    opacity: entry.lit ? 1 : 0
                    clip: true
                    elide: Text.ElideRight
                    text: entry.bind ? entry.bind.action : ""
                    color: Theme.faint
                    font.pixelSize: Theme.small
                    Behavior on height { NumberAnimation { duration: Theme.tMed; easing.type: Theme.ease } }
                    Behavior on opacity { NumberAnimation { duration: Theme.tMed } }
                }
            }

            MouseArea {
                id: hover
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    if (entry.isGroup)
                        root.toggleGroup(entry.modelData.group, !entry.modelData.shut);
                    else
                        root.currentId = root.idOf(entry.bind);
                    root.keyTarget.forceActiveFocus();
                }
            }
        }

        RiceText {
            anchors.centerIn: parent
            visible: root.entries.length === 0 && root.binds.length > 0
            horizontalAlignment: Text.AlignHCenter
            text: "¯\\_(ツ)_/¯\n\nnada encontrado"
            color: Theme.faint
        }
    }
    Rectangle {
        anchors.top: list.top
        width: list.width
        height: 16
        gradient: Gradient {
            GradientStop { position: 0; color: Theme.bg }
            GradientStop { position: 1; color: Qt.alpha(Theme.bg, 0) }
        }
    }
    Rectangle {
        anchors.bottom: list.bottom
        width: list.width
        height: 16
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.alpha(Theme.bg, 0) }
            GradientStop { position: 1; color: Theme.bg }
        }
    }

    // ================= DETAIL PANEL =================
    Rectangle {
        id: panel
        anchors.top: legend.bottom
        anchors.topMargin: 6
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        width: 300
        color: Theme.panel
        border.width: 1
        border.color: Theme.line

        Column {
            x: 18
            y: 18
            width: parent.width - 36
            spacing: 14

            Column {
                width: parent.width
                spacing: 8
                RiceText { text: "ATALHO"; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5 }
                Flow {
                    width: parent.width
                    spacing: 4
                    Repeater {
                        model: root.recording ? root.recordMods.map(m => m).concat(["…"]) : Words.tokens(root.draft.key)
                        Keycap {
                            required property string modelData
                            big: true
                            label: Words.symbol(modelData)
                            modifier: Words.isMod(modelData)
                        }
                    }
                }
            }

            // ● GRAVAR ATALHO (r)
            Rectangle {
                width: parent.width
                height: recText.implicitHeight + 24
                color: "transparent"
                border.width: 1
                border.color: root.recording || recMouse.containsMouse ? Theme.accent : Theme.line2
                opacity: root.selected && root.selected.editable ? 1 : 0.4
                RiceText {
                    id: recText
                    anchors.centerIn: parent
                    text: root.recording ? "pressione o atalho… (Esc cancela)" : "● GRAVAR ATALHO (r)"
                    color: root.recording ? Theme.accent : recMouse.containsMouse ? Theme.fg : Theme.dim
                }
                MouseArea {
                    id: recMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.recording ? root.stopRecording("[ -- ] gravação cancelada", Theme.dim) : root.startRecording()
                }
            }

            Field {
                id: descField
                width: parent.width
                label: "DESCRIÇÃO"
                text: root.draft.desc
                keyTarget: root.keyTarget
                onEdited: root.setDraft("desc", text)
            }
            Field {
                id: commandField
                width: parent.width
                label: "COMANDO"
                text: root.commandEditable ? root.draft.command : (root.selected ? root.selected.action : "")
                editable: root.commandEditable
                keyTarget: root.keyTarget
                onEdited: root.setDraft("command", text)
            }
            RiceText {
                width: parent.width
                visible: root.commandEditable
                wrapMode: Text.Wrap
                font.pixelSize: Theme.small
                topPadding: -6
                color: !root.phrase ? Theme.faint : root.phrase.error ? Theme.red : Theme.ok
                text: !root.phrase ? "dica: escreva uma frase — " + Words.phraseExamples().join(", ")
                    : root.phrase.error ? "⚠ " + root.phrase.error
                    : "→ " + root.phrase.say + "  ·  salva como: " + root.phrase.command
            }

            Column {
                width: parent.width
                spacing: 6
                RiceText { text: "GRUPO"; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5 }
                Flow {
                    width: parent.width
                    spacing: 4
                    Repeater {
                        model: Words.GROUPS
                        Chip {
                            required property string modelData
                            label: modelData
                            on: root.draft.group === modelData
                            onClicked: { root.setDraft("group", modelData); root.keyTarget.forceActiveFocus(); }
                        }
                    }
                }
            }

            RiceText {
                width: parent.width
                wrapMode: Text.Wrap
                font.pixelSize: Theme.small
                color: Theme.red
                readonly property var clash: root.selected ? root.conflictsOf(root.selected, root.draft.key) : []
                text: clash.length ? "⚠ também usado em: " + clash.map(id => root.info(root.byId(id)).desc).join(", ")
                    : root.selected && !root.selected.editable ? "" : ""
                visible: text !== ""
            }
            RiceText {
                width: parent.width
                wrapMode: Text.Wrap
                font.pixelSize: Theme.small
                color: Theme.faint
                visible: text !== ""
                text: !root.selected ? "" : !root.selected.editable
                    ? "Atalho do rice: edite config/hypr/rice-integration.lua. Descrição e grupo podem mudar."
                    : !root.commandEditable ? "Ação fixa: só a combinação pode mudar." : ""
            }
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: 18
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 18
            spacing: 8
            AccentButton {
                ghost: true
                label: "CHECK"
                enabledState: !checker.running
                onClicked: checker.call(["shortcuts", "check", "--json"])
            }
            AccentButton {
                ghost: true
                label: root.armedRestore ? "CONFIRM?" : "RESTORE"
                enabledState: !root.busy
                onClicked: {
                    if (root.armedRestore) { root.armedRestore = false; finder.call(["shortcuts", "backups", "--json"]); }
                    else { root.armedRestore = true; disarm.restart(); }
                }
            }
            AccentButton {
                label: root.armedSave ? "CONFIRM?" : "SAVE"
                enabledState: !root.busy && !!root.selected
                onClicked: {
                    if (root.armedSave) { root.armedSave = false; root.save(); }
                    else { root.armedSave = true; disarm.restart(); }
                }
            }
        }
    }
}
