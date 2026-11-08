import QtQuick
import qs

// LW in ANSI Shadow. Every ~30 s a 180 ms glitch (refined only).
Item {
    id: root

    readonly property string art: "██╗     ██╗    ██╗\n██║     ██║    ██║\n██║     ██║ █╗ ██║\n██║     ██║███╗██║\n███████╗╚███╔███╔╝\n╚══════╝ ╚══╝╚══╝ "
    property int pixelSize: 10
    property bool glitching: false
    property int phase: 0

    implicitWidth: main.implicitWidth
    implicitHeight: main.implicitHeight
    width: implicitWidth
    height: implicitHeight

    component Art: Text {
        text: root.art
        // Block glyphs must touch: a fixed line height, like the prototype's line-height:1.05.
        font.family: Theme.font
        font.pixelSize: root.pixelSize
        lineHeightMode: Text.FixedHeight
        lineHeight: Math.round(root.pixelSize * 1.2)
    }

    // Chromatic ghosts, shown only during the glitch.
    Art { x: -2; color: Theme.cyan; opacity: 0.7; visible: root.glitching }
    Art { x: 2; color: Theme.magenta; opacity: 0.7; visible: root.glitching }
    Art {
        id: main
        color: Theme.accent
        x: root.glitching ? (root.phase === 0 ? 2 : -2) : 0
        y: root.glitching && root.phase === 1 ? 1 : 0
    }

    Timer {
        interval: 30000
        running: Theme.motion
        repeat: true
        onTriggered: { root.phase = 0; root.glitching = true; step.restart(); }
    }
    Timer {
        id: step
        interval: 90
        repeat: true
        onTriggered: {
            if (root.phase === 0) root.phase = 1;
            else { root.glitching = false; stop(); }
        }
    }
}
