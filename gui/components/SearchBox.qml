import QtQuick
import qs

// [ / search█ ]  — focus with "/", Esc clears, Enter goes back to the list.
Rectangle {
    id: root

    property alias text: input.text
    property Item keyTarget: null
    property string placeholder: "search"
    signal accepted()

    // Põe o cursor na busca.
    function focusInput() { input.forceActiveFocus(); }

    implicitWidth: 230
    implicitHeight: 24
    color: Theme.panel
    border.width: 1
    border.color: input.activeFocus ? Theme.accent : Theme.line
    Behavior on border.color { ColorAnimation { duration: Theme.tFast } }

    // Focus ring, like the prototype's box-shadow.
    Rectangle {
        anchors.fill: parent
        anchors.margins: -3
        z: -1
        color: "transparent"
        border.width: 3
        border.color: Theme.accentA
        visible: input.activeFocus
    }

    RiceText {
        id: slash
        anchors.verticalCenter: parent.verticalCenter
        x: 8
        text: "/"
        color: Theme.accent
    }

    TextInput {
        id: input
        anchors.left: slash.right
        anchors.leftMargin: 8
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        clip: true
        color: Theme.fg
        selectionColor: Theme.accent
        selectedTextColor: Theme.bg
        font.family: Theme.font
        font.pixelSize: Theme.fontSize
        cursorDelegate: RiceText { text: "█"; color: Theme.accent; visible: input.activeFocus }
        Keys.onEscapePressed: { text = ""; if (root.keyTarget) root.keyTarget.forceActiveFocus(); }
        Keys.onReturnPressed: { root.accepted(); if (root.keyTarget) root.keyTarget.forceActiveFocus(); }
    }

    RiceText {
        anchors.verticalCenter: parent.verticalCenter
        anchors.left: input.left
        visible: input.text === "" && !input.activeFocus
        text: root.placeholder
        color: Theme.faint
    }
}
