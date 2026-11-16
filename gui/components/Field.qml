import QtQuick
import qs

// LABEL above a boxed input, as in the prototype's detail panels.
Column {
    id: root

    property string label: ""
    property alias text: input.text
    property bool editable: true
    property string placeholder: ""
    property Item keyTarget: null
    signal edited()

    // Põe o cursor no campo.
    function focusInput() { input.forceActiveFocus(); }

    spacing: 4

    RiceText {
        text: root.label
        color: Theme.faint
        font.pixelSize: Theme.small
        font.letterSpacing: 1.5
    }
    Rectangle {
        width: root.width
        height: 26
        color: Theme.base
        border.width: 1
        border.color: input.activeFocus ? Theme.accent : Theme.line
        Behavior on border.color { ColorAnimation { duration: Theme.tFast } }

        TextInput {
            id: input
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            verticalAlignment: TextInput.AlignVCenter
            clip: true
            readOnly: !root.editable
            autoScroll: activeFocus
            color: root.editable ? Theme.fg : Theme.dim
            selectionColor: Theme.accent
            selectedTextColor: Theme.bg
            font.family: Theme.font
            font.pixelSize: Theme.fontSize - 1
            onTextEdited: root.edited()
            Keys.onEscapePressed: if (root.keyTarget) root.keyTarget.forceActiveFocus()
            Keys.onReturnPressed: if (root.keyTarget) root.keyTarget.forceActiveFocus()
        }
        RiceText {
            anchors.verticalCenter: parent.verticalCenter
            x: 8
            visible: input.text === "" && !input.activeFocus
            text: root.placeholder
            color: Theme.faint
            font.pixelSize: Theme.fontSize - 1
        }
    }
}
