import QtQuick
import qs
import qs.components

Item {
    id: root

    readonly property var cards: [
        { name: "minimal", title: "MINIMAL", text: "Shell animations off.\nInstant workspace changes." },
        { name: "refined", title: "REFINED", text: "Shell animations on.\n150 ms workspace transition." }
    ]
    property var info: ({})
    property string message: ""
    property color messageColor: Theme.muted
    readonly property bool busy: changer.running

    function pick(name) {
        if (busy || name === state.profile)
            return;
        message = "";
        changer.call(["profile", "set", name, "--json"]);
    }

    Component.onCompleted: reader.call(["profile", "get", "--json"])

    RiceCommand {
        id: reader
        onSucceeded: data => root.info = data
        onFailed: message => {
            root.message = "[ FAIL ] " + message;
            root.messageColor = Theme.fail;
        }
    }
    RiceCommand {
        id: changer
        onSucceeded: data => {
            root.info = data;
            root.message = "[ OK ] Active: " + data.profile;
            root.messageColor = Theme.ok;
        }
        onFailed: message => {
            root.message = "[ FAIL ] " + message;
            root.messageColor = Theme.fail;
        }
    }

    RiceHeader {
        id: title
        title: "LW // PROFILES"
    }

    Row {
        anchors.top: title.bottom
        anchors.topMargin: 18
        width: parent.width
        spacing: 14

        Repeater {
            model: root.cards

            Rectangle {
                id: card

                required property var modelData
                readonly property bool active: root.info.profile === modelData.name

                width: (parent.width - 14) / 2
                height: 150
                color: mouse.containsMouse && !active ? Theme.surfaceAlt : "transparent"
                border.width: 1
                border.color: active ? Theme.accent : Theme.rule

                Column {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 12

                    RiceText {
                        text: (card.active ? "[*] " : "[ ] ") + card.modelData.title
                        color: card.active ? Theme.accent : Theme.text
                        font.bold: true
                    }
                    RiceText {
                        text: card.modelData.text
                        color: Theme.muted
                    }
                }

                MouseArea {
                    id: mouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: card.active ? Qt.ArrowCursor : Qt.PointingHandCursor
                    onClicked: root.pick(card.modelData.name)
                }
            }
        }
    }

    Item {
        anchors.bottom: parent.bottom
        width: parent.width
        height: back.height

        RiceText {
            anchors.verticalCenter: parent.verticalCenter
            text: root.busy ? "[ RUNNING ] changing profile" : root.message
            color: root.busy ? Theme.muted : root.messageColor
        }

        ConfirmButton {
            id: back
            anchors.right: parent.right
            action: "RESTORE PREVIOUS" + (root.info.previous ? ": " + root.info.previous.toUpperCase() : "")
            enabledState: !root.busy && !!root.info.previous && root.info.previous !== root.info.profile
            onConfirmed: changer.call(["profile", "restore", "--json"])
        }
    }
}
