import QtQuick
import qs

Rectangle {
    id: root

    property int number: 0
    property string label: ""
    property bool active: false
    signal clicked()

    width: parent ? parent.width : 0
    height: 34
    color: active ? Theme.accent : mouse.containsMouse ? Theme.surfaceAlt : "transparent"
    Behavior on color { ColorAnimation { duration: 90 } }

    RiceText {
        anchors.verticalCenter: parent.verticalCenter
        x: 14
        text: String(root.number).padStart(2, "0") + " " + root.label
        color: root.active ? Theme.onAccent : Theme.text
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
