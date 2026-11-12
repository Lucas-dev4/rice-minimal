import QtQuick
import qs

// TITLE  [ note ]  - - - - - - -
// The title "decodes" from noise each time it appears (refined profile only).
Item {
    id: root

    property string title: ""
    property string note: ""
    // A status chip (MUSIC: PLAYING green, PAUSED yellow); dim by default.
    property color noteColor: Theme.dim
    // Items placed at the right end; the dashed rule stops before them.
    default property alias trailing: rightSlot.data
    property bool primary: true

    width: parent ? parent.width : 0
    height: label.implicitHeight
    clip: true

    readonly property string noise: "!<>-_\\/[]{}=+*^?#░▒"
    property int frame: 14

    function scrambled() {
        if (frame >= 14)
            return title;
        const done = frame / 14 * title.length;
        let out = "";
        for (let i = 0; i < title.length; i++)
            out += title[i] === " " || i < done ? title[i] : noise[Math.floor(Math.random() * noise.length)];
        return out;
    }

    onTitleChanged: if (Theme.motion && primary) { frame = 0; decode.restart(); }
    Component.onCompleted: if (Theme.motion && primary) { frame = 0; decode.restart(); }

    Timer {
        id: decode
        interval: 28
        repeat: true
        onTriggered: if (++root.frame >= 14) stop()
    }

    Row {
        id: row
        spacing: 10

        RiceText {
            id: label
            text: root.frame >= 14 ? root.title : root.scrambled()
            color: root.primary ? Theme.accent : Theme.faint
            font.bold: true
            font.letterSpacing: root.primary ? 0.6 : 1.5
            font.pixelSize: root.primary ? Theme.fontSize : Theme.small
        }
        Rectangle {
            visible: root.note !== ""
            anchors.verticalCenter: label.verticalCenter
            width: noteText.implicitWidth + 12
            height: noteText.implicitHeight + 2
            color: "transparent"
            border.width: 1
            border.color: root.noteColor === Theme.dim ? Theme.line : Qt.alpha(root.noteColor, 0.35)
            Behavior on border.color { ColorAnimation { duration: Theme.tFast } }
            RiceText {
                id: noteText
                anchors.centerIn: parent
                text: root.note
                color: root.noteColor
                font.pixelSize: Theme.small
            }
        }
    }

    // Dashed rule to the right edge.
    Row {
        anchors.left: row.right
        anchors.leftMargin: 10
        anchors.right: rightSlot.left
        anchors.rightMargin: rightSlot.width > 0 ? 10 : 0
        y: Math.round(label.height / 2)
        clip: true
        spacing: 4
        Repeater {
            model: 200
            Rectangle { width: 4; height: 1; color: Theme.line }
        }
    }

    Row {
        id: rightSlot
        anchors.right: parent.right
        anchors.verticalCenter: row.verticalCenter
        spacing: 6
    }
}
