// LockScreen.qml — tela Lock (SISTEMA): prévia da tela de bloqueio, escurecimento (55–85%),
// teste real de bloqueio e ativação. Só visual: senha e PAM nunca mudam.
import QtQuick
import Quickshell
import qs
import qs.components

// LW // LOCK — visual only: password and PAM are never touched.
// The preview mirrors lockscreen.render(): the wallpaper, the dim and the password field alone.
Item {
    id: root

    property Item keyTarget: null
    property var info: ({})
    property int dim: 55
    property bool trialRunning: false
    property bool armedTrial: false
    property bool armedRestore: false
    property bool armedActivate: false

    readonly property bool busy: worker.running || trialRunning
    readonly property var presets: [["LIGHT", 55], ["BALANCED", 60], ["DARK", 75]]
    readonly property var hints: [["←→", "dim"], ["t", "trial"]]

    // Relê o estado do bloqueio.
    function refresh() { reader.call(["lock", "status", "--json"]); }
    // Roda um comando "lw lock ..." mostrando o rótulo enquanto trabalha.
    function run(args, label) {
        if (worker.running) return;
        Status.start(label);
        worker.call(args);
    }
    // Saved when the slider stops moving, not on every step.
    function setDim(value) {
        dim = Math.max(55, Math.min(85, Math.round(value / 5) * 5));
        save.restart();
    }
    // Detached so that closing this window cannot interrupt a locked session.
    function trial() {
        trialRunning = true;
        Status.say("[ .. ] trial lock — desbloqueie com sua senha normal", Theme.accent);
        Quickshell.execDetached(Theme.rice.concat(["lock", "trial", "--confirm"]));
    }
    // Ações perigosas pedem um segundo clique.
    function confirm(flag, action) {
        if (root[flag]) { root[flag] = false; action(); }
        else { root[flag] = true; disarm.restart(); }
    }
    // Algo mudou fora da tela: relê daqui a pouco.
    function externalChange() { settle.restart(); }

    // Teclas da tela.
    function handleKey(event) {
        switch (event.key) {
        case Qt.Key_Left: setDim(dim - 5); return true;
        case Qt.Key_Right: setDim(dim + 5); return true;
        case Qt.Key_T: if (!busy && info.session_locked === false) confirm("armedTrial", trial); return true;
        }
        return false;
    }

    Component.onCompleted: refresh()
    Timer { id: settle; interval: 400; onTriggered: root.refresh() }
    Timer { id: disarm; interval: 3000; onTriggered: { root.armedTrial = false; root.armedRestore = false; root.armedActivate = false; } }
    Timer {
        id: save
        interval: 600
        onTriggered: if (Math.round((root.info.dim || 0) * 100) !== root.dim) root.run(["lock", "dim", String(root.dim), "--json"], "dim " + root.dim + "%")
    }

    RiceCommand {
        id: reader
        onSucceeded: data => {
            root.info = data;
            if (!save.running && !worker.running)
                root.dim = Math.round((data.dim || 0.55) * 100);
            if (root.trialRunning && data.session_locked === false && !trialGrace.running) {
                root.trialRunning = false;
                Status.say("[ OK ] trial terminado — veja o LOG");
            }
        }
        onFailed: message => Status.say("[ FAIL ] " + message, Theme.red)
    }
    // The session takes a moment to lock after the detached command starts.
    Timer { id: trialGrace; interval: 6000; running: root.trialRunning; onTriggered: root.refresh() }
    RiceCommand {
        id: worker
        onSucceeded: data => {
            Status.stop();
            Status.say("[ OK ] " + String(data.result || "lock visuals updated").replace("[ OK ] ", ""));
            root.refresh();
        }
        onFailed: message => { Status.stop(); Status.say("[ FAIL ] " + message, Theme.red); }
    }

    RiceHeader {
        id: title
        title: "LOCK"
    }

    // ================= PREVIEW =================
    Rectangle {
        id: preview
        anchors.top: title.bottom
        anchors.topMargin: 14
        anchors.bottom: foot.top
        anchors.bottomMargin: 12
        anchors.left: parent.left
        anchors.right: panel.left
        anchors.rightMargin: 20
        color: Theme.raise
        border.width: 1
        border.color: Theme.line
        clip: true

        Image {
            anchors.fill: parent
            anchors.margins: 1
            source: root.info.wallpaper ? "file://" + root.info.wallpaper : ""
            sourceSize.width: 900
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
        }
        // Live dim, while dragging too.
        Rectangle {
            anchors.fill: parent
            color: Theme.bg
            opacity: root.dim / 100
            Behavior on opacity { NumberAnimation { duration: Theme.tMed } }
        }
        Rectangle {
            anchors.centerIn: parent
            width: 180
            height: 26
            color: Qt.alpha(Theme.bg, 0.6)
            border.width: 1
            border.color: Qt.alpha(Theme.fg, 0.25)
            RiceText { anchors.centerIn: parent; text: "password"; color: Theme.dim; font.pixelSize: Theme.small }
        }
        RiceText {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 10
            text: "prévia — o bloqueio real mostra só o campo de senha"
            color: Qt.alpha(Theme.fg, 0.45)
            font.pixelSize: 10
        }
    }

    // ================= PANEL =================
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

        component Check: Row {
            property string status: "OK"
            property string text: ""
            spacing: 10
            RiceText {
                text: parent.status === "OK" ? "[ OK ]" : parent.status === "NA" ? "[ -- ]" : "[" + parent.status + "]"
                color: parent.status === "NA" ? Theme.dim : Theme.statusColor(parent.status)
            }
            RiceText { text: parent.text; width: 230; wrapMode: Text.Wrap }
        }

        Column {
            x: 16
            y: 16
            width: parent.width - 32
            spacing: 6

            RiceText { text: "STATUS"; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5; bottomPadding: 4 }
            Check { status: root.info.enabled ? "OK" : "NA"; text: root.info.enabled ? "Active" : "Not active; candidate only" }
            Check { status: root.info.tested ? "OK" : "WARN"; text: root.info.tested ? "Trial passed on this layout" : "Trial needed" }
            Check {
                status: root.info.layout_current === false ? "WARN" : "OK"
                text: root.info.layout_current === false ? "Monitors changed; press UPDATE" : "Layout: " + (root.info.displays || []).join(", ")
            }
            Check { status: "NA"; text: "Dim: mínimo " + root.dim + "%, efetivo " + Math.round((root.info.effective_dim || 0) * 100) + "%" }

            Item { width: 1; height: 14 }
            Row {
                spacing: 6
                RiceText { text: "DIM"; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5 }
                RiceText { text: root.dim + "%"; color: Theme.accent; font.pixelSize: Theme.small }
            }

            // Slider 55..85, step 5.
            Item {
                id: slider
                width: parent.width
                height: 22
                readonly property real fraction: (root.dim - 55) / 30
                Rectangle { y: 10; width: parent.width; height: 2; color: Theme.line2 }
                Rectangle { y: 10; width: slider.fraction * parent.width; height: 2; color: Theme.accent }
                Rectangle {
                    x: slider.fraction * (parent.width - width)
                    y: 4
                    width: 10
                    height: 14
                    color: Theme.accent
                    Behavior on x { NumberAnimation { duration: Theme.tFast; easing.type: Theme.ease } }
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    // Clique/arraste na barra → escurecimento correspondente.
                    function pick(x) { root.setDim(55 + Math.max(0, Math.min(1, x / width)) * 30); }
                    onPressed: mouse => pick(mouse.x)
                    onPositionChanged: mouse => { if (pressed) pick(mouse.x); }
                    onReleased: root.keyTarget.forceActiveFocus()
                }
            }
            Row {
                spacing: 6
                topPadding: 4
                Repeater {
                    model: root.presets
                    Chip {
                        required property var modelData
                        label: modelData[0]
                        on: root.dim === modelData[1]
                        onClicked: root.setDim(modelData[1])
                    }
                }
            }
            RiceText {
                width: parent.width
                topPadding: 12
                wrapMode: Text.Wrap
                text: "visual only — senha e PAM nunca são alterados."
                color: Theme.faint
                font.pixelSize: Theme.small
            }
            RiceText {
                width: parent.width
                topPadding: 8
                visible: root.armedTrial
                wrapMode: Text.Wrap
                text: "⚠ isto bloqueia a sessão de verdade. Desbloqueie com sua senha normal. Se a tela falhar: Ctrl+Alt+F3, entre e rode: rice lock-restore"
                color: Theme.yel
                font.pixelSize: Theme.small
            }
        }
    }

    // ================= FOOTER =================
    Item {
        id: foot
        anchors.bottom: parent.bottom
        width: parent.width
        height: trialButton.height + 10
        Rectangle { width: parent.width; height: 1; color: Theme.line }
        Row {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 4
            spacing: 6
            RiceText { text: "●"; color: root.info.enabled ? Theme.ok : Theme.dim }
            RiceText { text: root.info.enabled ? "ACTIVE" : "CANDIDATE"; color: Theme.dim }
        }
        Row {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            spacing: 8
            AccentButton { ghost: true; label: "CHECK"; enabledState: !root.busy; onClicked: root.run(["lock", "check", "--json"], "validating") }
            AccentButton {
                ghost: true
                label: root.armedRestore ? "CONFIRM?" : "RESTORE VISUALS"
                enabledState: !root.busy && root.info.enabled === true
                onClicked: root.confirm("armedRestore", () => root.run(["lock", "restore", "--json"], "restoring"))
            }
            AccentButton { ghost: true; label: "UPDATE"; enabledState: !root.busy; onClicked: root.run(["lock", "update", "--json"], "updating candidate") }
            AccentButton {
                ghost: true
                visible: !root.info.enabled
                label: root.armedActivate ? "CONFIRM?" : "ACTIVATE"
                enabledState: !root.busy && root.info.tested === true
                onClicked: root.confirm("armedActivate", () => root.run(["lock", "activate", "--confirm", "--json"], "activating"))
            }
            AccentButton {
                id: trialButton
                label: root.armedTrial ? "CONFIRM?" : root.trialRunning ? "LOCKED…" : "TRIAL LOCK"
                enabledState: !root.busy && root.info.session_locked === false
                onClicked: root.confirm("armedTrial", root.trial)
            }
        }
    }
}
