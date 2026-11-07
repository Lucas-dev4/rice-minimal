import QtQuick
import Quickshell
import qs
import qs.components

Item {
    id: root

    property var info: ({})
    property string message: ""
    property color messageColor: Theme.muted
    readonly property bool busy: worker.running || trialRunning
    property bool trialRunning: false
    readonly property var levels: [{ label: "LIGHT", value: 35 }, { label: "BALANCED", value: 55 }, { label: "DARK", value: 75 }]

    function report(text, color) {
        message = text;
        messageColor = color;
    }

    function refresh() {
        reader.call(["lock", "status", "--json"]);
    }

    function run(args, text) {
        report("[ RUNNING ] " + text, Theme.muted);
        worker.call(args);
    }

    // Detached so that closing this window cannot interrupt a locked session.
    function trial() {
        trialRunning = true;
        report("[ RUNNING ] Locking; unlock with your normal password", Theme.warn);
        Quickshell.execDetached(Theme.rice.concat(["lock", "trial", "--confirm"]));
    }

    function externalChange() {
        settle.restart();
    }

    Component.onCompleted: refresh()

    Timer {
        id: settle
        interval: 400
        onTriggered: root.refresh()
    }

    RiceCommand {
        id: reader
        onSucceeded: data => {
            root.info = data;
            if (root.trialRunning && data.session_locked === false && !trialGrace.running) {
                root.trialRunning = false;
                root.report("Trial finished; see the log", Theme.muted);
            }
        }
        onFailed: message => root.report("[ FAIL ] " + message, Theme.fail)
    }

    // The session takes a moment to lock after the detached command starts.
    Timer {
        id: trialGrace
        interval: 6000
        running: root.trialRunning
        onTriggered: root.refresh()
    }

    RiceCommand {
        id: worker
        onSucceeded: data => {
            root.report("[ OK ] " + (data.result || "Done").replace("[ OK ] ", ""), Theme.ok);
            root.refresh();
        }
        onFailed: message => root.report("[ FAIL ] " + message, Theme.fail)
    }

    RiceHeader {
        id: title
        title: "RICE // LOCK SCREEN"
    }

    // Approximates the widget rows from lockscreen.render().
    Rectangle {
        id: preview
        anchors.top: title.bottom
        anchors.topMargin: 16
        width: 480
        height: 270
        clip: true
        color: Theme.surface
        border.width: 1
        border.color: Theme.outline

        Image {
            anchors.fill: parent
            source: root.info.thumb ? "file://" + root.info.thumb : ""
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
        }
        Rectangle {
            anchors.fill: parent
            color: Theme.surface
            opacity: root.info.effective_dim || 0
        }
        RiceText {
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height * .33 - height / 2
            text: root.info.title || ""
            font.bold: true
        }
        RiceText {
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height * .43 - height / 2
            text: "00:00"
            font.pixelSize: 30
            font.bold: true
        }
        RiceText {
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height * .54 - height / 2
            text: "date"
            font.pixelSize: 11
        }
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height * .65
            width: 120
            height: 22
            color: Theme.surfaceAlt
            border.width: 1
            border.color: Theme.outline

            RiceText {
                anchors.centerIn: parent
                text: "password"
                color: Theme.muted
                font.pixelSize: 11
            }
        }
    }

    Column {
        anchors.top: preview.top
        anchors.left: preview.right
        anchors.leftMargin: 20
        anchors.right: parent.right
        spacing: 10

        RiceText {
            text: (root.info.enabled ? "[ OK ] Active" : "[ -- ] Not active; candidate only")
            color: root.info.enabled ? Theme.ok : Theme.muted
        }
        RiceText {
            text: (root.info.tested ? "[ OK ] Trial passed on this layout" : "[ WARN ] Trial needed")
            color: root.info.tested ? Theme.ok : Theme.warn
        }
        RiceText {
            text: (root.info.layout_current === false ? "[ WARN ] Monitors changed; press UPDATE" : "[ OK ] Layout: " + (root.info.displays || []).join(", "))
            color: root.info.layout_current === false ? Theme.warn : Theme.ok
        }
        RiceText {
            text: "Dim: minimum " + Math.round((root.info.dim || 0) * 100) + "%, effective " + Math.round((root.info.effective_dim || 0) * 100) + "%"
            color: Theme.muted
        }
        RiceText {
            width: parent.width
            wrapMode: Text.Wrap
            text: "Visual only: password and PAM are never changed."
            color: Theme.muted
        }

        Row {
            spacing: 8

            Repeater {
                model: root.levels
                RiceButton {
                    required property var modelData
                    label: (Math.round((root.info.dim || 0) * 100) === modelData.value ? "* " : "") + modelData.label
                    enabledState: !root.busy
                    onClicked: root.run(["lock", "dim", String(modelData.value), "--json"], "updating dim")
                }
            }
        }
    }

    RiceText {
        anchors.bottom: actions.top
        anchors.bottomMargin: 10
        width: parent.width
        wrapMode: Text.Wrap
        visible: trialButton.armed
        text: "[ WARN ] This really locks the session. Unlock with your normal password. If the screen fails: Ctrl+Alt+F3, log in, then run: rice lock-restore"
        color: Theme.warn
    }

    Item {
        id: actions
        anchors.bottom: parent.bottom
        width: parent.width
        height: 66

        RiceText {
            width: parent.width
            elide: Text.ElideRight
            text: root.message
            color: root.messageColor
        }

        Row {
            anchors.bottom: parent.bottom
            anchors.right: parent.right
            spacing: 10

            RiceButton {
                label: "CHECK"
                enabledState: !root.busy
                onClicked: root.run(["lock", "check", "--json"], "validating")
            }
            RiceButton {
                label: "UPDATE"
                enabledState: !root.busy
                onClicked: root.run(["lock", "update", "--json"], "updating candidate")
            }
            ConfirmButton {
                action: "RESTORE VISUALS"
                enabledState: !root.busy && root.info.enabled === true
                onConfirmed: root.run(["lock", "restore", "--json"], "restoring")
            }
            ConfirmButton {
                id: trialButton
                action: "TRIAL LOCK"
                enabledState: !root.busy && root.info.session_locked === false
                onConfirmed: root.trial()
            }
            ConfirmButton {
                action: root.info.enabled ? "ACTIVE" : "ACTIVATE"
                enabledState: !root.busy && root.info.tested === true && !root.info.enabled
                onConfirmed: root.run(["lock", "activate", "--confirm", "--json"], "activating")
            }
        }
    }
}
