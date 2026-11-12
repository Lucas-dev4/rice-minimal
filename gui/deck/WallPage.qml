import QtQuick
import qs
import qs.components
import qs.deck

// LW // wall: filled in its own step.
Item {
    id: root
    property Item keyTarget: null
    readonly property var hints: []
    function handleKey(event) { return false; }

    Column {
        width: parent.width
        spacing: 12
        Row {
            spacing: 10
            RiceText { textFormat: Text.StyledText; text: "wall<font color='" + Theme.accent + "'>.</font>"; font.pixelSize: 26; font.weight: Font.ExtraBold }
        }
        Glass {
            k: true
            width: parent.width
            height: 160
            RiceText { anchors.centerIn: parent; text: "[ .. ] wall — próxima etapa"; color: Theme.dim }
        }
    }
}
