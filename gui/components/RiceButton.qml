import QtQuick
import qs

// Like the bar's [ 1 ]: the brackets are the whole control.
Item {
    id: root

    property string label: ""
    property bool enabledState: true
    signal clicked()

    implicitWidth: caption.implicitWidth + 4
    implicitHeight: 26

    RiceText {
        id: caption
        anchors.centerIn: parent
        text: "[ " + root.label + " ]"
        font.bold: mouse.containsMouse && root.enabledState
        color: !root.enabledState ? Theme.rule : mouse.containsMouse ? Theme.accent : Theme.text
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.enabledState ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: if (root.enabledState) root.clicked()
    }
}
