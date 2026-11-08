import QtQuick
import qs

// The main action: accent border, fills from the left on hover.
Item {
    id: root

    property string label: ""
    property bool enabledState: true
    property bool ghost: false
    signal clicked()

    implicitWidth: caption.implicitWidth + (ghost ? 20 : 28)
    implicitHeight: caption.implicitHeight + 6

    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.width: 1
        border.color: !root.enabledState ? Theme.line : root.ghost ? (mouse.containsMouse ? Theme.fg : Theme.line2) : Theme.accent
    }
    Rectangle {
        visible: !root.ghost
        height: parent.height
        width: mouse.containsMouse && root.enabledState ? parent.width : 0
        color: Theme.accent
        Behavior on width { NumberAnimation { duration: Theme.tMed; easing.type: Theme.ease } }
    }
    RiceText {
        id: caption
        anchors.centerIn: parent
        text: root.label
        font.bold: !root.ghost
        color: !root.enabledState ? Theme.faint
             : root.ghost ? (mouse.containsMouse ? Theme.fg : Theme.dim)
             : mouse.containsMouse ? Theme.bg : Theme.accent
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.enabledState ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: if (root.enabledState) root.clicked()
    }
}
