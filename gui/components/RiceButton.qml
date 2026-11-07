import QtQuick
import qs

Rectangle {
    id: root

    property string label: ""
    property bool enabledState: true
    signal clicked()

    implicitWidth: caption.implicitWidth + 24
    implicitHeight: 30
    color: mouse.containsMouse && enabledState ? Theme.accent : "transparent"
    border.color: enabledState ? Theme.accent : Theme.outline
    border.width: 1

    RiceText {
        id: caption
        anchors.centerIn: parent
        text: "[ " + root.label + " ]"
        color: !root.enabledState ? Theme.muted : mouse.containsMouse ? Theme.onAccent : Theme.accent
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.enabledState ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: if (root.enabledState) root.clicked()
    }
}
