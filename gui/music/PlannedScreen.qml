import QtQuick
import qs
import qs.components

// Stand-in for a tab whose phase has not been built yet.
Item {
    id: root

    property Item keyTarget: null
    property string title: ""
    property string plan: ""
    readonly property var hints: []

    function handleKey(event) { return false; }

    Column {
        anchors.centerIn: parent
        spacing: 8
        RiceText {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "[ .. ] " + root.title.toLowerCase()
            color: Theme.dim
        }
        RiceText {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.plan
            color: Theme.faint
            font.pixelSize: Theme.small
        }
    }
}
