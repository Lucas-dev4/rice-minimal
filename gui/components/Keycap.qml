import QtQuick
import qs

// One key drawn as a keycap; modifiers in the accent color.
Rectangle {
    id: root

    property string label: ""
    property bool modifier: false
    property bool big: false

    implicitWidth: Math.max(big ? 34 : 22, caption.implicitWidth + (big ? 20 : 12))
    implicitHeight: big ? 30 : 20
    color: Theme.raise
    border.width: 1
    border.color: Theme.line2

    // Thicker bottom edge.
    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 2; color: Theme.line2 }

    RiceText {
        id: caption
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -1
        text: root.label
        color: root.modifier ? Theme.accent : Theme.fg
        font.pixelSize: root.big ? 13 : 11
    }
}
