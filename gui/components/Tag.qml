import QtQuick
import qs

// Small boxed tag over an image: ● ACTIVE, ★, files, full...
Rectangle {
    id: root

    property string label: ""
    property color tint: Theme.dim

    implicitWidth: caption.implicitWidth + 10
    implicitHeight: caption.implicitHeight
    color: Qt.alpha(Theme.bg, 0.88)
    border.width: 1
    border.color: Qt.alpha(tint, 0.4)

    // Pops in when it appears.
    scale: visible ? 1 : 0.6
    Behavior on scale { NumberAnimation { duration: Theme.tMed; easing.type: Theme.ease } }

    RiceText {
        id: caption
        anchors.centerIn: parent
        text: root.label
        color: root.tint
        font.pixelSize: 10
        font.letterSpacing: 0.5
    }
}
