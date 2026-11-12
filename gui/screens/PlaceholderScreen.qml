import QtQuick
import qs
import qs.components

Item {
    id: root
    property string title: ""

    Column {
        anchors.centerIn: parent
        spacing: 8
        RiceText {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.title
            color: Theme.accent
            font.bold: true
        }
        RiceText {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Not in the GUI yet. Use the TUI: rice"
            color: Theme.muted
        }
    }
}
