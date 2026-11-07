import QtQuick
import Quickshell
import qs
import qs.components

Item {
    id: root

    property var backups: []
    property var recovery: ({})
    property var palette_: ({})
    property var profile: ({})
    property string message: ""
    property color messageColor: Theme.muted
    readonly property var selected: backups[list.currentIndex] || null

    function report(text, color) {
        message = text;
        messageColor = color;
    }

    function refresh() {
        reader.call(["backups", "list", "--json"]);
        palette.call(["palette", "show", "--json"]);
        profiles.call(["profile", "get", "--json"]);
    }

    function copy(text) {
        // wl-copy outlives this window; the clipboard would otherwise die with it.
        Quickshell.execDetached(["wl-copy", text]);
        report("[ OK ] Copied; paste it in a terminal at ~/Projetos/rice-minimal", Theme.ok);
    }

    function size(bytes) {
        return bytes < 1048576 ? Math.ceil(bytes / 1024) + "K" : (bytes / 1048576).toFixed(1) + "M";
    }

    function handleKey(event) {
        switch (event.key) {
        case Qt.Key_Up: case Qt.Key_K: list.decrementCurrentIndex(); return true;
        case Qt.Key_Down: case Qt.Key_J: list.incrementCurrentIndex(); return true;
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
        onFailed: message => root.report("[ FAIL ] " + message, Theme.fail)
    }
    RiceCommand { id: palette; onSucceeded: data => root.palette_ = data }
    RiceCommand { id: profiles; onSucceeded: data => root.profile = data }
    RiceCommand {
        id: restorer
        onSucceeded: (data, warnings) => {
            root.report(warnings.length > 0 ? "[ WARN ] " + warnings.join("; ") : "[ OK ] Restored", warnings.length > 0 ? Theme.warn : Theme.ok);
            root.refresh();
        }
        onFailed: message => root.report("[ FAIL ] " + message, Theme.fail)
    }

    RiceHeader {
        id: title
        title: "RICE // RESTORE / BACKUPS"
        note: root.backups.length + " saved"
    }

    ListView {
        id: list
        anchors.top: title.bottom
        anchors.topMargin: 14
        anchors.bottom: details.top
        anchors.bottomMargin: 12
        width: parent.width
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        highlightMoveDuration: 0
        model: root.backups

        delegate: Item {
            id: row

            required property var modelData
            required property int index
            readonly property bool current: ListView.isCurrentItem

            width: ListView.view.width
            height: 26

            RiceText {
                id: name
                anchors.verticalCenter: parent.verticalCenter
                width: 400
                elide: Text.ElideMiddle
                text: (row.current ? "> " : "  ") + row.modelData.name
                color: row.current ? Theme.accent : Theme.text
                font.bold: row.current
            }
            RiceText {
                id: kind
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: name.right
                anchors.leftMargin: 10
                width: 90
                text: row.modelData.kind
                color: Theme.muted
            }
            RiceText {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: kind.right
                width: 150
                text: new Date(row.modelData.time_ns / 1e6).toLocaleString(Qt.locale(), "dd/MM HH:mm")
                color: Theme.muted
            }
            RiceText {
                anchors.verticalCenter: parent.verticalCenter
                anchors.right: parent.right
                anchors.rightMargin: 6
                text: root.size(row.modelData.size)
                color: Theme.muted
            }
            MouseArea {
                anchors.fill: parent
                onClicked: list.currentIndex = row.index
            }
        }
    }

    Column {
        id: details
        anchors.bottom: warning.top
        anchors.bottomMargin: 12
        width: parent.width
        spacing: 6

        RiceHeader { title: "TERMINAL ONLY" }
        RiceText {
            width: parent.width
            elide: Text.ElideRight
            text: root.selected ? root.selected.description : ""
            color: Theme.muted
        }
        RiceText {
            width: parent.width
            elide: Text.ElideMiddle
            text: "$ " + (root.selected && root.selected.command ? root.selected.command : "no automatic restore; copy the files by hand")
            color: root.selected && root.selected.command ? Theme.text : Theme.muted
        }
        RiceText {
            width: parent.width
            elide: Text.ElideRight
            text: "login screen  $ " + (root.recovery.greeter || "")
            color: Theme.muted
        }
    }

    RiceText {
        id: warning
        anchors.bottom: actions.top
        anchors.bottomMargin: 10
        width: parent.width
        wrapMode: Text.Wrap
        text: "[ WARN ] A full restore replaces newer code and can remove this window. Commit first."
        color: Theme.warn
    }

    Item {
        id: actions
        anchors.bottom: parent.bottom
        width: parent.width
        height: copyButton.height

        RiceText {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - buttons.width - 14
            elide: Text.ElideRight
            text: restorer.running ? "[ RUNNING ] restoring" : root.message
            color: restorer.running ? Theme.muted : root.messageColor
        }

        Row {
            id: buttons
            anchors.right: parent.right
            spacing: 10

            ConfirmButton {
                action: "PREVIOUS PROFILE"
                enabledState: !restorer.running && !!root.profile.previous && root.profile.previous !== root.profile.profile
                onConfirmed: restorer.call(["profile", "restore", "--json"])
            }
            ConfirmButton {
                action: "PREVIOUS PALETTE"
                enabledState: !restorer.running && root.palette_.can_restore === true
                onConfirmed: restorer.call(["palette", "restore", "--json"])
            }
            RiceButton {
                id: copyButton
                label: "COPY COMMAND"
                enabledState: !!root.selected && !!root.selected.command
                onClicked: root.copy(root.selected.command)
            }
        }
    }
}
