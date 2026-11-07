import QtQuick
import qs

// Same grammar as the Waybar workspaces: the active one is only bold and tinted.
Item {
    id: root

    property int number: 0
    property string label: ""
    property bool active: false
    signal clicked()

    width: parent ? parent.width : 0
    height: 28

    RiceText {
        anchors.verticalCenter: parent.verticalCenter
        x: 18
        text: "[ " + root.number + " ] " + root.label
        color: root.active ? Theme.accent : mouse.containsMouse ? Theme.text : Theme.muted
        font.bold: root.active
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
