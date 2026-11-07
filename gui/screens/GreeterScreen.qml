import QtQuick
import qs
import qs.components

Item {
    id: root

    property var info: ({})
    property string message: ""
    property color messageColor: Theme.muted
    readonly property bool synced: info.colors_match === true && info.image_match === true

    function refresh() {
        reader.call(["greeter", "status", "--json"]);
    }

    function report(text, color) {
        message = text;
        messageColor = color;
    }

    function check(value) {
        return value === null || value === undefined ? "[ -- ]" : value ? "[ OK ]" : "[ WARN ]";
    }

    function checkColor(value) {
        return value === null || value === undefined ? Theme.muted : value ? Theme.ok : Theme.warn;
    }

    Component.onCompleted: refresh()

    // The sync finishes in the background after the command returns.
    Timer {
        id: settle
        interval: 1500
        onTriggered: root.refresh()
    }

    // Called for every log entry, so SYNC ALL and other front-ends show up here too.
    function externalChange() {
        settle.restart();
    }

    RiceCommand {
        id: reader
        onSucceeded: data => root.info = data
        onFailed: message => root.report("[ FAIL ] " + message, Theme.fail)
    }
    RiceCommand {
        id: syncer
        onSucceeded: {
            root.report("[ OK ] sent to the login screen", Theme.ok);
            settle.restart();
        }
        onFailed: message => root.report("[ FAIL ] " + message, Theme.fail)
    }
    RiceCommand {
        id: toggler
        onSucceeded: root.refresh()
        onFailed: message => root.report("[ FAIL ] " + message, Theme.fail)
    }

    RiceHeader {
        id: title
        title: "RICE // LOGIN GREETER"
    }

    Rectangle {
        id: preview
        anchors.top: title.bottom
        anchors.topMargin: 16
        width: 400
        height: 225
        color: Theme.surfaceAlt

        Image {
            anchors.fill: parent
            anchors.margins: 1
            source: root.info.image ? "file://" + root.info.image + "?" + root.info.last_sync_ns : ""
            cache: false
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            sourceSize.width: 800
            clip: true
        }
        RiceText {
            anchors.centerIn: parent
            visible: !root.info.image
            text: "[ nothing sent since boot ]"
            color: Theme.muted
        }
    }

    Column {
        anchors.top: preview.top
        anchors.left: preview.right
        anchors.leftMargin: 20
        anchors.right: parent.right
        spacing: 12

        RiceText {
            text: root.check(root.info.colors_match) + " Colors match the theme"
            color: root.checkColor(root.info.colors_match)
        }
        RiceText {
            text: root.check(root.info.image_match) + " Image matches the wallpaper"
            color: root.checkColor(root.info.image_match)
        }
        RiceText {
            text: (root.info.auto_sync ? "[ OK ]" : "[ WARN ]") + " Automatic sync: " + (root.info.auto_sync ? "on" : "off")
            color: root.info.auto_sync ? Theme.ok : Theme.warn
        }
        RiceText {
            text: "[ -- ] Passwordless rule: root only, check in a terminal"
            color: Theme.muted
        }
        RiceText {
            text: "Last sent: " + (root.info.last_sync_ns
                ? new Date(root.info.last_sync_ns / 1e6).toLocaleString(Qt.locale(), "dd/MM HH:mm:ss") : "not since boot")
            color: Theme.muted
        }
    }

    Item {
        anchors.bottom: parent.bottom
        width: parent.width
        height: syncButton.height

        RiceText {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - buttons.width - 14
            elide: Text.ElideRight
            text: syncer.running ? "[ RUNNING ] sending" : root.message
            color: syncer.running ? Theme.muted : root.messageColor
        }

        Row {
            id: buttons
            anchors.right: parent.right
            spacing: 10

            RiceButton {
                label: "AUTO: " + (root.info.auto_sync ? "ON" : "OFF")
                enabledState: !toggler.running
                onClicked: toggler.call(["greeter", "auto", root.info.auto_sync ? "off" : "on", "--json"])
            }
            RiceButton {
                id: syncButton
                label: syncer.running ? "SENDING" : "SYNC NOW"
                enabledState: !syncer.running
                onClicked: {
                    root.message = "";
                    syncer.call(["greeter", "sync", "--json"]);
                }
            }
        }
    }
}
