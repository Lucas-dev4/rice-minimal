import QtQuick
import qs

// LW in ANSI Shadow, colored by the wallpaper's palette. Every ~30 s a 180 ms glitch (refined only).
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

    // Each line takes its own color: a vertical gradient from the terminal accent to the
    // palette's tertiary, both from the current wallpaper. Spaces become &nbsp; because
    // styled text collapses whitespace.
    component Art: Text {
        id: art
        property bool ghost: false
        property color tint: Theme.accent
        property color headColor: Theme.logoTop
        property color footColor: Theme.logoBottom
        Behavior on headColor { ColorAnimation { duration: Theme.tMed; easing.type: Theme.ease } }
        Behavior on footColor { ColorAnimation { duration: Theme.tMed; easing.type: Theme.ease } }
        textFormat: ghost ? Text.PlainText : Text.StyledText
        color: tint
        text: ghost ? root.art : root.art.split("\n").map((line, i) =>
            "<font color='" + Theme.mix(headColor, footColor, i / 5) + "'>" + line.replace(/ /g, "&nbsp;") + "</font>").join("<br>")
        // Block glyphs must touch: a fixed line height, like the prototype's line-height:1.05.
        font.family: Theme.font
        font.pixelSize: root.pixelSize
        lineHeightMode: Text.FixedHeight
        lineHeight: Math.round(root.pixelSize * 1.2)
    }

    // Chromatic ghosts, shown only during the glitch.
    Art { x: -2; ghost: true; tint: Theme.cyan; opacity: 0.7; visible: root.glitching }
    Art { x: 2; ghost: true; tint: Theme.magenta; opacity: 0.7; visible: root.glitching }
    Art {
        id: main
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
