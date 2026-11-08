import QtQuick
import Quickshell
import qs
import qs.components

// LW // BACKUPS — grouped by day, colored kinds, log-scale size bars.
// Restoring stays terminal only: this window shows and copies the command.
Item {
    id: root

    property Item keyTarget: null
    property var backups: []
    property var recovery: ({})
    property var palette_: ({})
    property var profile: ({})
    property string currentName: ""
    property bool armedProfile: false
    property bool armedPalette: false

    readonly property var hints: [["jk", "move"], ["y", "copy cmd"], ["/", "search"]]
    readonly property var kindColor: ({ files: Theme.dim, snapshot: Theme.blue, full: Theme.accent, lock: Theme.magenta })
    readonly property var kindText: ({
        files: "arquivos alterados por uma etapa de instalação",
        snapshot: "cópias de configs antes de uma mudança",
        full: "o rice inteiro: arquivos ativos e estado do tema",
        lock: "só o visual da tela de bloqueio"
    })

    readonly property var shown: {
        const needle = search.text.toLowerCase();
        return backups.filter(b => !needle || (b.name + " " + b.kind + " " + b.description).toLowerCase().includes(needle));
    }
    readonly property var selected: shown.find(b => b.name === currentName) || shown[0] || null
    readonly property real maxSize: Math.max(1, ...backups.map(b => b.size))

    function day(ns) { return new Date(ns / 1e6); }
    function dayKey(ns) { return Qt.formatDate(day(ns), "dd/MM"); }
    function dayLabel(ns) {
        const key = dayKey(ns);
        const today = Qt.formatDate(new Date(), "dd/MM");
        const yesterday = Qt.formatDate(new Date(Date.now() - 864e5), "dd/MM");
        return key === today ? "HOJE · " + key : key === yesterday ? "ONTEM · " + key : key;
    }
    function size(bytes) { return bytes < 1048576 ? Math.max(1, Math.ceil(bytes / 1024)) + "K" : (bytes / 1048576).toFixed(1) + "M"; }

    readonly property var entries: {
        const out = [];
        let last = "";
        for (const b of shown) {
            const key = dayKey(b.time_ns);
            if (key !== last) {
                out.push({ day: dayLabel(b.time_ns), count: shown.filter(x => dayKey(x.time_ns) === key).length });
                last = key;
            }
            out.push({ backup: b });
        }
        return out;
    }

    function refresh() {
        reader.call(["backups", "list", "--json"]);
        palette.call(["palette", "show", "--json"]);
        profiles.call(["profile", "get", "--json"]);
    }
    function copy(text, label) {
        // wl-copy outlives this window; the clipboard would otherwise die with it.
        Quickshell.execDetached(["wl-copy", "--", text]);
        Status.say("[ OK ] " + label + " copiado — cole num terminal em ~/Projetos/rice-minimal");
    }
    function move(step) {
        if (!shown.length) return;
        // By name: each read of a var property may hand back a copy of the list.
        const at = shown.findIndex(b => selected && b.name === selected.name);
        currentName = shown[Math.max(0, Math.min(shown.length - 1, at + step))].name;
    }

    function handleKey(event) {
        switch (event.key) {
        case Qt.Key_Up: case Qt.Key_K: move(-1); return true;
        case Qt.Key_Down: case Qt.Key_J: move(1); return true;
        case Qt.Key_Y: if (selected && selected.command) copy(selected.command, "comando"); return true;
        case Qt.Key_Slash: search.focusInput(); return true;
        }
        return false;
    }

    Component.onCompleted: refresh()

    RiceCommand {
        id: reader
        onSucceeded: data => {
            root.backups = data.backups;
            root.recovery = data.recovery;
        }
        onFailed: message => Status.say("[ FAIL ] " + message, Theme.red)
    }
    RiceCommand { id: palette; onSucceeded: data => root.palette_ = data }
    RiceCommand { id: profiles; onSucceeded: data => root.profile = data }
    RiceCommand {
        id: restorer
        onSucceeded: (data, warnings) => {
            Status.stop();
            Status.say(warnings.length > 0 ? "[ WARN ] " + warnings.join("; ") : "[ OK ] restaurado", warnings.length > 0 ? Theme.yel : Theme.ok);
            root.refresh();
        }
        onFailed: message => { Status.stop(); Status.say("[ FAIL ] " + message, Theme.red); }
    }
    Timer { id: disarm; interval: 3000; onTriggered: { root.armedProfile = false; root.armedPalette = false; } }

    RiceHeader {
        id: title
        width: parent.width - search.width - 14
        title: "LW // BACKUPS"
        note: root.shown.length + "/" + root.backups.length
    }
    SearchBox {
        id: search
        anchors.right: parent.right
        anchors.verticalCenter: title.verticalCenter
        keyTarget: root.keyTarget
    }

    // ================= LIST =================
    ListView {
        id: list
        anchors.top: title.bottom
        anchors.topMargin: 14
        anchors.bottom: foot.top
        anchors.bottomMargin: 12
        anchors.left: parent.left
        anchors.right: panel.left
        anchors.rightMargin: 20
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: root.entries

        delegate: Item {
            id: entry
            required property var modelData
            readonly property bool isDay: modelData.day !== undefined
            readonly property var b: modelData.backup || null
            readonly property bool current: !isDay && root.selected && b.name === root.selected.name

            width: ListView.view.width
            height: isDay ? 30 : 28

            Row {
                visible: entry.isDay
                x: 10
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 6
                spacing: 8
                RiceText { text: entry.modelData.day || ""; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5 }
                RiceText { text: entry.modelData.count || ""; color: Theme.dim; font.pixelSize: Theme.small }
            }

            Rectangle {
                visible: !entry.isDay
                anchors.fill: parent
                color: entry.current ? Theme.accentA : rowMouse.containsMouse ? Qt.alpha(Theme.fg, 0.025) : "transparent"
                Rectangle { width: 2; height: parent.height; color: entry.current ? Theme.accent : "transparent" }
            }
            Item {
                visible: !entry.isDay
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                RiceText {
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 78 - 46 - 92 - 36
                    elide: Text.ElideMiddle
                    text: entry.b ? entry.b.name : ""
                }
                Tag {
                    anchors.verticalCenter: parent.verticalCenter
                    x: parent.width - 78 - 46 - 92 - 24
                    width: 78
                    label: entry.b ? entry.b.kind : ""
                    tint: entry.b ? root.kindColor[entry.b.kind] || Theme.dim : Theme.dim
                    color: "transparent"
                }
                RiceText {
                    anchors.verticalCenter: parent.verticalCenter
                    x: parent.width - 46 - 92 - 12
                    text: entry.b ? Qt.formatTime(root.day(entry.b.time_ns), "hh:mm") : ""
                    color: Theme.dim
                }
                // Size bar on a log scale, so 1K and 600K both stay visible.
                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    spacing: 6
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        height: 3
                        width: entry.b ? Math.max(3, Math.log(entry.b.size + 1) / Math.log(root.maxSize + 1) * 44) : 0
                        color: entry.current ? Theme.accent : Theme.line2
                        Behavior on color { ColorAnimation { duration: Theme.tFast } }
                    }
                    RiceText {
                        width: 40
                        horizontalAlignment: Text.AlignRight
                        text: entry.b ? root.size(entry.b.size) : ""
                        color: Theme.dim
                        font.pixelSize: Theme.small
                    }
                }
            }
            MouseArea {
                id: rowMouse
                visible: !entry.isDay
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: { root.currentName = entry.b.name; root.keyTarget.forceActiveFocus(); }
            }
        }

        RiceText {
            anchors.centerIn: parent
            visible: root.shown.length === 0 && root.backups.length > 0
            horizontalAlignment: Text.AlignHCenter
            text: "¯\\_(ツ)_/¯\n\nnada encontrado"
            color: Theme.faint
        }
    }

    // ================= DETAIL =================
    Rectangle {
        id: panel
        anchors.top: title.bottom
        anchors.topMargin: 14
        anchors.bottom: foot.top
        anchors.bottomMargin: 12
        anchors.right: parent.right
        width: 320
        color: Theme.panel
        border.width: 1
        border.color: Theme.line

        component Label: RiceText { color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5 }
        component Command: Rectangle {
            property string text: ""
            width: parent.width
            height: cmd.implicitHeight + 16
            color: Theme.bg
            border.width: 1
            border.color: Theme.line
            RiceText {
                id: cmd
                x: 8
                y: 8
                width: parent.width - 16
                wrapMode: Text.WrapAnywhere
                textFormat: Text.StyledText
                font.pixelSize: Theme.small
                text: "<font color='" + Theme.accent + "'>$</font> " + parent.text
            }
        }

        Column {
            x: 16
            y: 16
            width: parent.width - 32
            spacing: 8
            visible: !!root.selected

            Label { text: "BACKUP" }
            RiceText {
                width: parent.width
                wrapMode: Text.WrapAnywhere
                text: root.selected ? root.selected.name : ""
                color: Theme.accent
                font.bold: true
            }
            Grid {
                columns: 2
                columnSpacing: 10
                rowSpacing: 6
                topPadding: 4
                bottomPadding: 8
                RiceText { text: "tipo"; color: Theme.faint }
                Tag { label: root.selected ? root.selected.kind : ""; tint: root.selected ? root.kindColor[root.selected.kind] || Theme.dim : Theme.dim; color: "transparent" }
                RiceText { text: "quando"; color: Theme.faint }
                RiceText { text: root.selected ? Qt.formatDateTime(root.day(root.selected.time_ns), "dd/MM/yyyy hh:mm") : "" }
                RiceText { text: "tamanho"; color: Theme.faint }
                RiceText { text: root.selected ? root.size(root.selected.size) : "" }
                RiceText { text: "contém"; color: Theme.faint }
                RiceText {
                    width: 210
                    wrapMode: Text.Wrap
                    text: root.selected ? (root.kindText[root.selected.kind] || root.selected.description) : ""
                }
            }

            Label { text: "RESTAURAR — TERMINAL" }
            Command {
                text: root.selected && root.selected.command ? root.selected.command : "sem restauração automática; copie os arquivos à mão"
            }
            AccentButton {
                ghost: true
                width: parent.width
                label: "COPY COMMAND (y)"
                enabledState: !!root.selected && !!root.selected.command
                onClicked: root.copy(root.selected.command, "comando")
            }

            Item { width: 1; height: 8 }
            Label { text: "LOGIN SCREEN" }
            Command { text: root.recovery.greeter || "" }

            // A full restore can replace newer code.
            Rectangle {
                visible: !!root.selected && root.selected.kind === "full"
                width: parent.width
                height: warnText.implicitHeight + 12
                color: Qt.alpha(Theme.yel, 0.06)
                Rectangle { width: 2; height: parent.height; color: Theme.yel }
                RiceText {
                    id: warnText
                    x: 10
                    y: 6
                    width: parent.width - 16
                    wrapMode: Text.Wrap
                    text: "⚠ restaurar um backup full substitui código mais novo e pode remover esta janela. Faça commit antes."
                    color: Theme.yel
                    font.pixelSize: Theme.small
                }
            }
        }
    }

    // Footer: restore only one part
    Item {
        id: foot
        anchors.bottom: parent.bottom
        width: parent.width
        height: profileButton.height + 10
        Rectangle { width: parent.width; height: 1; color: Theme.line }
        RiceText { anchors.bottom: parent.bottom; anchors.bottomMargin: 4; text: "restaurar só uma parte"; color: Theme.dim }
        Row {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            spacing: 8
            AccentButton {
                id: profileButton
                ghost: true
                label: root.armedProfile ? "CONFIRM?" : "PREVIOUS PROFILE"
                enabledState: !restorer.running && !!root.profile.previous && root.profile.previous !== root.profile.profile
                onClicked: {
                    if (root.armedProfile) { root.armedProfile = false; Status.start("restoring profile"); restorer.call(["profile", "restore", "--json"]); }
                    else { root.armedProfile = true; disarm.restart(); }
                }
            }
            AccentButton {
                ghost: true
                label: root.armedPalette ? "CONFIRM?" : "PREVIOUS PALETTE"
                enabledState: !restorer.running && root.palette_.can_restore === true
                onClicked: {
                    if (root.armedPalette) { root.armedPalette = false; Status.start("restoring palette"); restorer.call(["palette", "restore", "--json"]); }
                    else { root.armedPalette = true; disarm.restart(); }
                }
            }
        }
    }
}
