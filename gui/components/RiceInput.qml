// RiceInput.qml — campo de texto no estilo do LW.
import QtQuick
import qs

Rectangle {
    id: root

    property alias text: input.text
    property string placeholder: ""
    property bool editable: true
    signal finished()

    // Põe o cursor no campo.
    function focusInput() {
        input.forceActiveFocus();
    }

    implicitHeight: 26
    color: Theme.surface

    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: 1
        color: input.activeFocus ? Theme.accent : Theme.outline
    }

    TextInput {
        id: input
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        verticalAlignment: TextInput.AlignVCenter
        clip: true
        readOnly: !root.editable
        color: root.editable ? Theme.text : Theme.muted
        selectionColor: Theme.accent
        font.family: Theme.font
        font.pixelSize: Theme.fontSize
        Keys.onEscapePressed: root.finished()
        Keys.onReturnPressed: root.finished()
    }

    RiceText {
        anchors.verticalCenter: parent.verticalCenter
        x: 8
        visible: input.text === "" && !input.activeFocus
        text: root.placeholder
        color: Theme.muted
    }
}
