import QtQuick
import qs
import qs.components

Item {
    id: root

    property Item keyTarget: null
    property var binds: []
    property string revision: ""
    property string query: ""
    property string message: ""
    property color messageColor: Theme.muted
    readonly property bool busy: saver.running || restorer.running
    readonly property var shown: {
        const needle = query.toLowerCase();
        return binds.filter(b => (b.key + " " + b.action + " " + b.section).toLowerCase().includes(needle));
    }
    readonly property var selected: shown[list.currentIndex] || null
    readonly property bool commandEditable: !!selected && selected.editable && selected.command !== null

    function report(text, color) {
        message = text;
        messageColor = color;
    }

    function reload() {
        reader.call(["shortcuts", "list", "--json"]);
    }

    function fill() {
        keyField.text = selected ? selected.key : "";
        commandField.text = commandEditable ? selected.command : "";
    }

    function save() {
        if (!selected || busy)
            return;
        const args = ["shortcuts", "set", "--line", String(selected.line), "--revision", revision, "--json"];
        const before = args.length;
        if (keyField.text !== selected.key)
            args.push("--key", keyField.text);
        if (commandEditable && commandField.text !== selected.command)
            args.push("--command", commandField.text);
        if (args.length === before) {
            report("[ WARN ] Nothing changed", Theme.warn);
            return;
        }
        saver.call(args);
    }

    function handleKey(event) {
        switch (event.key) {
        case Qt.Key_Up: case Qt.Key_K: list.decrementCurrentIndex(); return true;
        case Qt.Key_Down: case Qt.Key_J: list.incrementCurrentIndex(); return true;
        case Qt.Key_Slash: search.focusInput(); return true;
        case Qt.Key_Return: case Qt.Key_Enter:
            if (selected && selected.editable)
                keyField.focusInput();
            return true;
        }
        return false;
    }

    Component.onCompleted: reload()
    onSelectedChanged: fill()
    onQueryChanged: list.currentIndex = 0

    RiceCommand {
        id: reader
        onSucceeded: data => {
            root.revision = data.revision;
            root.binds = data.binds.concat(data.external);
            root.fill();
        }
        onFailed: message => root.report("[ FAIL ] " + message, Theme.fail)
    }
    RiceCommand {
        id: saver
        onSucceeded: {
            root.report("[ OK ] Saved; a backup was kept", Theme.ok);
            root.reload();
        }
        onFailed: message => root.report("[ FAIL ] " + message, Theme.fail)
    }
    RiceCommand {
        id: checker
        onSucceeded: data => {
            if (data.duplicates.length > 0)
                root.report("[ WARN ] Duplicated: " + data.duplicates.join(", "), Theme.warn);
            else
                root.report("[ OK ] " + data.count + " shortcuts, no duplicates", Theme.ok);
        }
        onFailed: message => root.report("[ FAIL ] " + message, Theme.fail)
    }
    RiceCommand {
        id: finder
        onSucceeded: data => {
            if (data.backups.length === 0)
                root.report("[ WARN ] No backups yet", Theme.warn);
            else
                restorer.call(["shortcuts", "restore", data.backups[0].path, "--json"]);
        }
        onFailed: message => root.report("[ FAIL ] " + message, Theme.fail)
    }
    RiceCommand {
        id: restorer
        onSucceeded: {
            root.report("[ OK ] Last backup restored", Theme.ok);
            root.reload();
        }
        onFailed: message => root.report("[ FAIL ] " + message, Theme.fail)
    }

    RiceHeader {
        id: title
        title: "RICE // SUPER SHORTCUTS"
        note: root.shown.length + "/" + root.binds.length
    }

    RiceInput {
        id: search
        anchors.right: parent.right
        anchors.verticalCenter: title.verticalCenter
        width: 240
        placeholder: "search  /"
        onTextChanged: root.query = text
        onFinished: root.keyTarget.forceActiveFocus()
    }

    ListView {
        id: list
        anchors.top: title.bottom
        anchors.topMargin: 14
        anchors.bottom: editor.top
        anchors.bottomMargin: 10
        width: parent.width
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        highlightMoveDuration: 0
        model: root.shown

        delegate: Rectangle {
            id: row

            required property var modelData
            required property int index
            readonly property bool current: ListView.isCurrentItem

            width: ListView.view.width
            height: 26
            color: hover.containsMouse && !current ? Theme.surfaceAlt : "transparent"

            RiceText {
                id: key
                anchors.verticalCenter: parent.verticalCenter
                x: 6
                width: 250
                elide: Text.ElideRight
                text: (row.current ? "> " : "  ") + row.modelData.key
                color: row.current ? Theme.accent : Theme.text
                font.bold: row.current
            }
            RiceText {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: key.right
                anchors.leftMargin: 10
                anchors.right: parent.right
                anchors.rightMargin: 6
                elide: Text.ElideRight
                text: (row.modelData.editable ? "" : "[fixed] ") + (row.modelData.command ?? row.modelData.action)
                color: row.current ? Theme.text : Theme.muted
            }
            MouseArea {
                id: hover
                anchors.fill: parent
                hoverEnabled: true
                onClicked: {
                    list.currentIndex = row.index;
                    root.keyTarget.forceActiveFocus();
                }
            }
        }
    }

    Column {
        id: editor
        anchors.bottom: actions.top
        anchors.bottomMargin: 10
        width: parent.width
        spacing: 6

        RiceText {
            width: parent.width
            elide: Text.ElideRight
            color: Theme.muted
            text: !root.selected ? "" : !root.selected.editable
                ? "Managed by the rice; edit config/hypr/rice-integration.lua"
                : root.selected.section + (root.commandEditable ? "" : "  //  action is fixed; only the combination can change")
        }
        Row {
            width: parent.width
            spacing: 10

            RiceInput {
                id: keyField
                width: 300
                placeholder: "combination"
                editable: !!root.selected && root.selected.editable
                onFinished: root.keyTarget.forceActiveFocus()
            }
            RiceInput {
                id: commandField
                width: parent.width - 310
                placeholder: root.commandEditable ? "command" : "not a plain command"
                editable: root.commandEditable
                onFinished: root.keyTarget.forceActiveFocus()
            }
        }
    }

    Item {
        id: actions
        anchors.bottom: parent.bottom
        width: parent.width
        height: saveButton.height

        RiceText {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - buttons.width - 14
            elide: Text.ElideRight
            text: root.message
            color: root.messageColor
        }

        Row {
            id: buttons
            anchors.right: parent.right
            spacing: 10

            RiceButton {
                label: "CHECK"
                enabledState: !checker.running
                onClicked: checker.call(["shortcuts", "check", "--json"])
            }
            ConfirmButton {
                action: "RESTORE LAST"
                enabledState: !root.busy
                onConfirmed: finder.call(["shortcuts", "backups", "--json"])
            }
            ConfirmButton {
                id: saveButton
                action: "SAVE"
                enabledState: !root.busy && !!root.selected && root.selected.editable
                onConfirmed: root.save()
            }
        }
    }
}
