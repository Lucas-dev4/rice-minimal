import QtQuick
import qs

// A filter chip: filled with the accent when on.
Rectangle {
    id: root

    property string label: ""
    property bool on: false
    signal clicked()

    implicitWidth: caption.implicitWidth + 18
    implicitHeight: caption.implicitHeight + 2
    color: on ? Theme.accent : "transparent"
    border.width: 1
    border.color: on ? Theme.accent : mouse.containsMouse ? Theme.line2 : Theme.line
    Behavior on color { ColorAnimation { duration: Theme.tFast } }

    RiceText {
        id: caption
        anchors.centerIn: parent
        text: root.label
        color: root.on ? Theme.bg : mouse.containsMouse ? Theme.fg : Theme.dim
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
