import QtQuick
import qs

// One block of the status bar: | label |
Item {
    id: root

    property string label: ""
    property color textColor: Theme.dim
    property bool clickable: false
    property bool separator: true
    property bool leftSeparator: false
    property bool elide: false
    property int textFormat: Text.PlainText
    signal clicked()

    height: parent ? parent.height : 34
    implicitWidth: caption.implicitWidth + 28

    Rectangle { anchors.fill: parent; anchors.topMargin: 1; color: Theme.accentA; visible: root.clickable && mouse.containsMouse }

    RiceText {
        id: caption
        anchors.verticalCenter: parent.verticalCenter
        x: 14
        width: root.elide ? root.width - 28 : implicitWidth
        elide: root.elide ? Text.ElideRight : Text.ElideNone
        textFormat: root.textFormat
        text: root.label
        font.pixelSize: Theme.small + 0.5
        color: root.clickable && mouse.containsMouse ? Theme.accent : root.textColor
    }

    Rectangle { visible: root.separator; anchors.right: parent.right; width: 1; height: parent.height; color: Theme.line }
    Rectangle { visible: root.leftSeparator; width: 1; height: parent.height; color: Theme.line }

    MouseArea {
        id: mouse
        anchors.fill: parent
        enabled: root.clickable
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
