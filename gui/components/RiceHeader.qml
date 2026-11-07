import QtQuick
import qs

// The TUI's frame title: +-- RICE // X -- note --------
Item {
    id: root

    property string title: ""
    property string note: ""

    width: parent ? parent.width : 0
    height: label.implicitHeight
    clip: true

    Row {
        spacing: 0

        RiceText { text: "+-- "; color: Theme.rule }
        RiceText { id: label; text: root.title; color: Theme.accent; font.bold: true }
        RiceText { text: root.note ? " -- " : ""; color: Theme.rule }
        RiceText { text: root.note; color: Theme.muted }
        RiceText { text: " " + "-".repeat(160); color: Theme.rule }
    }
}
