import QtQuick
import qs
import qs.components

Item {
    id: root

    property var current: ({})
    property string message: ""
    property color messageColor: Theme.muted
    readonly property bool busy: regenerate.running || restore.running

    function report(text, color) {
        message = text;
        messageColor = color;
    }

    function finished(data, warnings) {
        if (warnings.length > 0)
            report("[ WARN ] " + warnings.join("; "), Theme.warn);
        else
            report("[ OK ] " + data.result, Theme.ok);
        show.call(["palette", "show", "--json"]);
    }

    Component.onCompleted: show.call(["palette", "show", "--json"])

    Connections {
        target: Theme
        function onDarkChanged() { show.call(["palette", "show", "--json"]); }
    }

    RiceCommand {
        id: show
        onSucceeded: data => root.current = data
        onFailed: message => root.report("[ FAIL ] " + message, Theme.fail)
    }
    RiceCommand {
        id: regenerate
        onSucceeded: (data, warnings) => root.finished(data, warnings)
        onFailed: message => root.report("[ FAIL ] " + message, Theme.fail)
    }
    RiceCommand {
        id: restore
        onSucceeded: (data, warnings) => root.finished(data, warnings)
        onFailed: message => root.report("[ FAIL ] " + message, Theme.fail)
    }

    RiceText {
        id: title
        text: "RICE // COLOR PALETTE"
        color: Theme.accent
        font.bold: true
    }

    RiceText {
        anchors.right: parent.right
        anchors.verticalCenter: title.verticalCenter
        visible: root.current.emergency === true
        text: "[ WARN ] emergency palette"
        color: Theme.warn
    }

    Flickable {
        anchors.top: title.bottom
        anchors.topMargin: 14
        anchors.bottom: actions.top
        anchors.bottomMargin: 10
        width: parent.width
        clip: true
        contentHeight: views.implicitHeight
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: views
            width: parent.width
            spacing: 22

            PaletteView {
                width: parent.width
                caption: "CURRENT  //  " + (root.current.generator || "") + "  //  " + String(root.current.wallpaper || "").split("/").pop()
                colors: root.current.colors || ({})
                thumb: root.current.thumb || ""
            }
            PaletteView {
                width: parent.width
                visible: !!root.current.previous
                caption: "PREVIOUS  //  " + (root.current.previous ? String(root.current.previous.wallpaper || "").split("/").pop() : "")
                colors: root.current.previous ? root.current.previous.colors : ({})
                thumb: root.current.previous ? root.current.previous.thumb || "" : ""
            }
        }
    }

    Item {
        id: actions
        anchors.bottom: parent.bottom
        width: parent.width
        height: regenerateButton.height

        RiceText {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - buttons.width - 14
            elide: Text.ElideRight
            text: root.busy ? "[ RUNNING ] updating colors" : root.message
                || (root.current.can_restore === false ? "Previous palette has the same colors" : "")
            color: root.busy || !root.message ? Theme.muted : root.messageColor
        }

        Row {
            id: buttons
            anchors.right: parent.right
            spacing: 10

            ConfirmButton {
                action: "RESTORE PREVIOUS"
                enabledState: !root.busy && root.current.can_restore === true
                onConfirmed: restore.call(["palette", "restore", "--json"])
            }
            RiceButton {
                id: regenerateButton
                label: regenerate.running ? "RUNNING" : "REGENERATE"
                enabledState: !root.busy
                onClicked: regenerate.call(["palette", "regenerate", "--json"])
            }
        }
    }
}
