import QtQuick
import Quickshell.Io
import qs
import qs.components

// INSTALAR: Windows installers found in the download folders (games.py installers). ⏎ runs
// one in a new Wine prefix (~/Games/<name>); its own window does the rest. When it ends, LW
// lists the new .exe files: ⏎ again, pick the game, and it joins the library.
Item {
    id: root

    property bool shown: false
    property Item keyTarget: null
    property int bottomInset: 0
    property int cursor: 0
    property bool picking: false             // choosing the .exe of a finished install
    property int pick: 0
    property var extra: []                   // installers chosen with `o`, not in a download folder

    // Ready games first (Hydra downloads: nothing to install), then installers.
    readonly property var rows: Games.readyGames.map(r => Object.assign({ kind: "ready", setup: r.folder }, r))
        .concat(extra, Games.installers.filter(i => !extra.some(e => e.setup === i.setup)))
    readonly property var selected: rows[cursor] || null
    // The record in games.json is live; the list's copy is from the last search.
    function recordOf(item) { return item && item.kind !== "ready" ? (Games.installs[item.setup] || item.install || null) : null; }
    readonly property bool isReady: !!selected && selected.kind === "ready"
    readonly property var record: recordOf(selected)
    readonly property var choices: isReady ? selected.candidates || [] : record && record.state === "done" ? record.candidates || [] : []

    function openSheet() { shown = true; picking = false; cursor = 0; Games.findInstallers(); }
    function close() { shown = false; picking = false; if (keyTarget) keyTarget.forceActiveFocus(); }

    function stateText(r, item) {
        if (item && item.kind === "ready") return "pronto para jogar";
        if (!r) return "novo";
        if (r.state === "running") return "instalando… " + clock(Math.max(0, Math.floor(tick.now / 1000 - r.started)));
        if (r.state === "done") return "pronto · escolha o .exe";
        if (r.state === "failed") return "falhou";
        return "na biblioteca";
    }
    function stateColor(r, item) {
        if (item && item.kind === "ready") return Theme.ok;
        return !r ? Theme.faint : r.state === "running" ? Theme.accent : r.state === "done" ? Theme.ok : r.state === "failed" ? Theme.red : Theme.dim;
    }
    function clock(t) { return Math.floor(t / 60) + ":" + String(t % 60).padStart(2, "0"); }
    // C:/… inside a prefix; a ready game's path starts at its folder.
    function inside(exe) {
        if (isReady && exe.startsWith(selected.folder + "/")) return exe.slice(selected.folder.length + 1);
        const i = exe.indexOf("/drive_c/");
        return i >= 0 ? "C:/" + exe.slice(i + 9) : exe;
    }
    function mb(bytes) { return bytes >= 1048576 ? (bytes / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(bytes / 1024)) + " KB"; }

    function act() {
        if (!selected) return;
        const r = record;
        if (picking) {
            if (!choices[pick]) return;
            if (isReady) Games.addReady(choices[pick].exe, selected.name);
            else Games.installAdd(selected.setup, choices[pick].exe);
            picking = false;
            return;
        }
        if (isReady) { if (choices.length) { picking = true; pick = 0; } return; }
        if (!r || r.state === "failed") Games.install(selected.setup, selected.name);
        else if (r.state === "done" && choices.length) { picking = true; pick = 0; }
    }
    function handleKey(event) {
        if (!shown) return false;
        const t = event.text;
        if (event.key === Qt.Key_Escape) { if (picking) picking = false; else close(); return true; }
        if (event.key === Qt.Key_Up) { if (picking) pick = Math.max(0, pick - 1); else { cursor = Math.max(0, cursor - 1); } return true; }
        if (event.key === Qt.Key_Down) { if (picking) pick = Math.min(choices.length - 1, pick + 1); else { cursor = Math.min(rows.length - 1, cursor + 1); } return true; }
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { act(); return true; }
        if (t === "o" && !picking) { if (!pickSetup.running) pickSetup.running = true; return true; }
        if (t === "r" && !picking) { Games.findInstallers(); return true; }
        if (t === "d" && !picking && !isReady && record && record.state !== "running") { Games.installForget(selected.setup); return true; }
        return true;   // modal: nothing reaches the library behind it
    }
    onCursorChanged: picking = false

    // Any installer on disk, through the system file picker.
    Process {
        id: pickSetup
        command: ["zenity", "--file-selection", "--title=LW — escolha o instalador",
                  "--file-filter=Instaladores | *.exe *.EXE *.msi *.MSI"]
        stdout: StdioCollector {
            onStreamFinished: {
                const path = text.trim();
                if (!path) return;
                const folder = path.split("/").slice(0, -1).join("/");
                const name = folder.split("/").pop().replace(/[\[({][^\])}]*[\])}]/g, " ").replace(/[_.]+/g, " ").replace(/\s+/g, " ").replace(/^[\s-]+|[\s-]+$/g, "") || "Jogo";
                root.extra = [{ setup: path, name: name, folder: folder, install: null }].concat(root.extra.filter(e => e.setup !== path));
                root.cursor = 0;
            }
        }
    }
    QtObject { id: tick; property double now: Date.now() }
    Timer {
        interval: 1000
        repeat: true
        running: root.shown && Object.keys(Games.installs).some(k => Games.installs[k].state === "running")
        onTriggered: tick.now = Date.now()
    }

    visible: scrim.opacity > 0

    Rectangle {
        id: scrim
        anchors.fill: parent
        color: Qt.alpha(Theme.bg, 0.6)
        opacity: root.shown ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 300; easing.type: Theme.ease } }
        MouseArea { anchors.fill: parent; onClicked: root.close() }
    }

    Rectangle {
        id: panel
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(parent.width - 40, 760)
        height: body.implicitHeight + 40
        y: root.shown ? parent.height - height - root.bottomInset : parent.height + 10
        Behavior on y { NumberAnimation { duration: Theme.motion ? 400 : 0; easing.type: Theme.ease } }
        color: Theme.sheet
        border.width: 1
        border.color: Theme.line2
        MouseArea { anchors.fill: parent }

        Rectangle { anchors.horizontalCenter: parent.horizontalCenter; y: 10; width: 40; height: 4; color: Theme.line2 }

        Column {
            id: body
            x: 20
            y: 26
            width: parent.width - 40
            spacing: 12

            Item {
                width: parent.width
                height: head.implicitHeight
                RiceText { id: head; text: "INSTALAR"; font.pixelSize: 18; font.weight: Font.ExtraBold }
                RiceText {
                    anchors.left: head.right
                    anchors.leftMargin: 12
                    anchors.baseline: head.baseline
                    text: Games.findingInstallers ? "procurando…"
                        : [Games.readyGames.length ? Games.readyGames.length + " pronto(s) para jogar" : "",
                           root.rows.length - Games.readyGames.length ? (root.rows.length - Games.readyGames.length) + " instalador(es)" : ""].filter(x => x).join(" · ") || "nada novo em Downloads"
                    color: Theme.dim
                }
            }

            // ---- installers ----
            Rectangle {
                width: parent.width
                height: Math.min(6, Math.max(1, root.rows.length)) * 30 + 2
                color: "transparent"
                border.width: 1
                border.color: Theme.line
                clip: true
                ListView {
                    id: list
                    anchors.fill: parent
                    anchors.margins: 1
                    model: root.rows
                    currentIndex: root.cursor
                    boundsBehavior: Flickable.StopAtBounds
                    onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
                    delegate: Item {
                        id: row
                        required property var modelData
                        required property int index
                        readonly property bool chosen: index === root.cursor
                        readonly property var rec: root.recordOf(modelData)
                        width: list.width
                        height: 30
                        Rectangle {
                            anchors.fill: parent
                            color: row.chosen ? Qt.alpha(Theme.fg, 0.05) : rowMouse.containsMouse ? Qt.alpha(Theme.fg, 0.025) : "transparent"
                            Rectangle { width: 2; height: parent.height; color: row.chosen ? Theme.accent : "transparent" }
                        }
                        RiceText {
                            x: 12
                            width: parent.width * 0.42
                            anchors.verticalCenter: parent.verticalCenter
                            elide: Text.ElideRight
                            text: row.modelData.name
                            color: Theme.fg
                            font.weight: row.chosen ? Font.DemiBold : Font.Normal
                        }
                        RiceText {
                            x: 12 + parent.width * 0.42 + 10
                            width: parent.width - x - stateLabel.width - 24
                            anchors.verticalCenter: parent.verticalCenter
                            elide: Text.ElideMiddle
                            text: (row.modelData.kind === "ready" ? row.modelData.folder : row.modelData.setup).replace(/^\/home\/[^/]+/, "~")
                            color: Theme.faint
                            font.pixelSize: Theme.small
                        }
                        RiceText {
                            id: stateLabel
                            anchors.right: parent.right
                            anchors.rightMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.stateText(row.rec, row.modelData)
                            color: root.stateColor(row.rec, row.modelData)
                            font.pixelSize: Theme.small
                        }
                        MouseArea {
                            id: rowMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.cursor = row.index
                            onDoubleClicked: { root.cursor = row.index; root.act(); }
                        }
                    }
                    RiceText {
                        anchors.centerIn: parent
                        visible: root.rows.length === 0
                        text: Games.findingInstallers ? "[ .. ] procurando instaladores" : "nada novo em Downloads — o: escolher um instalador"
                        color: Theme.faint
                    }
                }
            }

            // ---- what the selected one needs ----
            RiceText {
                width: parent.width
                wrapMode: Text.Wrap
                textFormat: Text.StyledText
                color: Theme.dim
                font.pixelSize: Theme.small
                readonly property var r: root.record
                readonly property string home: "~/Games/" + (root.selected ? root.selected.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") : "")
                text: !root.selected ? ""
                    : root.isReady ? (root.picking ? "↑↓ escolha o executável do jogo · ⏎ adiciona à biblioteca · esc volta"
                                     : "Já vem pronto (download do Hydra). ⏎ escolhe o executável; o jogo entra com prefixo próprio em <font color='" + Theme.fg + "'>" + home + "</font> e proton-ge ligado.")
                    : !r ? "⏎ instala em <font color='" + Theme.fg + "'>~/Games/" + root.selected.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") + "</font> (um prefixo Wine só dele). O instalador abre na própria janela: siga os passos; o LW espera ele terminar, mesmo com esta janela fechada."
                    : r.state === "running" ? "O instalador está aberto numa janela do Wine. Quando ele terminar, os executáveis novos aparecem aqui."
                    : r.state === "failed" ? "<font color='" + Theme.red + "'>" + (r.error || "falhou") + "</font> · ⏎ tenta de novo · log em " + r.prefix.replace(/^\/home\/[^/]+/, "~") + "/lw-install.log"
                    : r.state === "added" ? "Já está na biblioteca. d apaga este registro (o jogo e o prefixo ficam)."
                    : root.picking ? "↑↓ escolha o executável do jogo · ⏎ adiciona à biblioteca · esc volta"
                    : "⏎ para escolher qual destes é o jogo."
            }

            Rectangle {
                visible: root.choices.length > 0
                width: parent.width
                height: visible ? root.choices.length * 26 + 30 : 0
                color: "transparent"
                border.width: 1
                border.color: root.picking ? Theme.accent : Theme.line
                RiceText { x: 12; y: 7; text: "EXECUTÁVEL DO JOGO"; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5 }
                Column {
                    y: 26
                    width: parent.width
                    Repeater {
                        model: root.choices
                        Item {
                            id: choice
                            required property var modelData
                            required property int index
                            readonly property bool on: root.picking && index === root.pick
                            width: parent.width
                            height: 26
                            Rectangle { anchors.fill: parent; anchors.margins: 1; color: choice.on ? Theme.accentA : "transparent" }
                            RiceText {
                                x: 12
                                width: parent.width - 120
                                anchors.verticalCenter: parent.verticalCenter
                                elide: Text.ElideMiddle
                                text: root.inside(choice.modelData.exe)
                                color: choice.on ? Theme.accent : choice.index === 0 ? Theme.fg : Theme.dim
                            }
                            RiceText {
                                anchors.right: parent.right
                                anchors.rightMargin: 12
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.mb(choice.modelData.size)
                                color: Theme.faint
                                font.pixelSize: Theme.small
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: { root.picking = true; root.pick = choice.index; }
                                onDoubleClicked: { root.picking = true; root.pick = choice.index; root.act(); }
                            }
                        }
                    }
                }
            }

            RiceText {
                text: "↑↓ escolher   ⏎ instalar/continuar   o outro arquivo   r procurar de novo   d esquecer   esc fechar"
                color: Theme.faint
                font.pixelSize: Theme.small
            }
        }
    }
}
