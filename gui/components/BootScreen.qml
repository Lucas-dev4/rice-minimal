import QtQuick
import qs

// Boot overlay (refined only): the logo is revealed, then each real start-up step
// turns from [ .. ] into [ OK ] when it has actually finished. Any key skips.
Rectangle {
    id: root

    property var steps: []
    property int shown: 0
    property bool revealed: false
    signal finished()

    function finish() {
        if (!visible || leaving.running)
            return;
        leaving.start();
    }

    color: Theme.bg
    visible: Theme.motion
    z: 50

    readonly property bool allDone: shown >= steps.length

    MouseArea { anchors.fill: parent; onClicked: root.finish() }

    Column {
        anchors.centerIn: parent
        spacing: 0

        Item {
            anchors.horizontalCenter: parent.horizontalCenter
            width: big.width
            height: big.height
            clip: true
            Logo {
                id: big
                pixelSize: 15
                // Revealed left to right in 18 steps.
                property int cut: root.revealed ? 18 : 0
                Behavior on cut { NumberAnimation { duration: 520 } }
                layer.enabled: false
            }
            Rectangle {
                anchors.right: parent.right
                width: parent.width * (18 - big.cut) / 18
                height: parent.height
                color: Theme.bg
            }
        }

        Item { width: 1; height: 30 }

        Column {
            width: 520
            height: 170
            spacing: 2
            Repeater {
                model: root.steps.slice(0, Math.min(root.shown + 1, root.steps.length))
                Row {
                    required property var modelData
                    required property int index
                    spacing: 8
                    RiceText {
                        text: index < root.shown ? "[ OK ]" : "[ .. ]"
                        color: index < root.shown ? Theme.ok : Theme.accent
                        font.pixelSize: 12
                    }
                    RiceText { text: modelData.label; color: Theme.dim; font.pixelSize: 12 }
                }
            }
        }

        RiceText {
            width: 520
            topPadding: 10
            font.pixelSize: 12
            color: Theme.accent
            readonly property int filled: Math.round(root.shown / Math.max(1, root.steps.length) * 40)
            text: "[" + "#".repeat(filled) + "-".repeat(40 - filled) + "] "
                  + String(Math.round(root.shown / Math.max(1, root.steps.length) * 100)).padStart(3) + "%"
        }
    }

    RiceText {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 16
        text: "press any key to skip"
        color: Theme.faint
        font.pixelSize: 11
    }

    Timer { running: root.visible; interval: 150; onTriggered: { root.revealed = true; advance.start(); } }

    // Each step stays visible at least 70 ms, and only advances once it is really done.
    Timer {
        id: advance
        interval: 70
        repeat: true
        onTriggered: {
            if (root.allDone) {
                stop();
                linger.start();
            } else if (root.steps[root.shown].done) {
                root.shown++;
            }
        }
    }
    Timer { id: linger; interval: 300; onTriggered: root.finish() }

    // Safety net: a stuck step never traps the window.
    Timer { running: root.visible; interval: 4000; onTriggered: root.finish() }

    ParallelAnimation {
        id: leaving
        NumberAnimation { target: root; property: "opacity"; to: 0; duration: 380; easing.type: Theme.ease }
        NumberAnimation { target: root; property: "scale"; to: 1.03; duration: 380; easing.type: Theme.ease }
        onFinished: { root.visible = false; root.finished(); }
    }
}
