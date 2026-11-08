import QtQuick
import qs

// WALLPAPERS ................ 1
// The active row's band and bar belong to the sidebar, so they can slide between rows.
Item {
    id: root

    property int number: 0
    property string label: ""
    property bool active: false
    signal clicked()

    width: parent ? parent.width : 0
    height: 29

    RiceText {
        anchors.verticalCenter: parent.verticalCenter
        x: 22 + (mouse.containsMouse && !root.active ? 4 : 0)
        text: root.label
        color: root.active ? Theme.accent : mouse.containsMouse ? Theme.fg : Theme.dim
        font.bold: root.active
        Behavior on x { NumberAnimation { duration: Theme.tFast; easing.type: Theme.ease } }
        Behavior on color { ColorAnimation { duration: Theme.tFast } }
    }

    RiceText {
        anchors.verticalCenter: parent.verticalCenter
        anchors.right: parent.right
        anchors.rightMargin: 22
        text: root.number
        color: root.active ? Theme.accent : Theme.faint
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
