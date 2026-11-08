import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

// Started by the wallpaper hook (theme.py reveal()) for every real wallpaper change:
// covers the screen, builds the new image block by block from the middle outwards, slow at
// first and then accelerating (a GPU shader, reveal.frag; recompile reveal.frag.qsb with
// `/usr/lib/qt6/bin/qsb --qt6 -o reveal.frag.qsb reveal.frag`), sharpens into the real
// picture, which Noctalia has set underneath by then, and exits. Cosmetic only:
// click-through, no keyboard, and a hard time limit.
//   RICE_REVEAL_BLOCK  block size in pixels (default 4)
//   RICE_REVEAL_IMAGE  the new wallpaper
//   RICE_REVEAL_READY  written once the screen is covered, so the hook can swap the image unseen
ShellRoot {
    id: shell

    readonly property string image: Quickshell.env("RICE_REVEAL_IMAGE") || ""
    // Block size in pixels and the time to fill the screen.
    readonly property int block: parseInt(Quickshell.env("RICE_REVEAL_BLOCK")) || 4
    readonly property int buildMs: 2400
    readonly property color bg: "#000000"

    FileView { id: ready; path: Quickshell.env("RICE_REVEAL_READY") || ""; printErrors: false }

    Component.onCompleted: if (!image) Qt.quit()
    // Never stay on screen, whatever happens.
    Timer { running: true; interval: 9000; onTriggered: Qt.quit() }

    Variants {
        model: Quickshell.screens

        PanelWindow {
            id: win
            required property var modelData
            screen: modelData
            anchors { top: true; bottom: true; left: true; right: true }
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.namespace: "rice-reveal"
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
            color: "transparent"
            // An empty input region: clicks go to whatever is underneath.
            mask: Region {}

            Item {
                id: stage
                anchors.fill: parent
                opacity: 0
                property bool covered: false

                Rectangle { anchors.fill: parent; color: shell.bg }

                // Cropped like the wallpaper (cover); the shader reads it through `crop`.
                Image {
                    id: photo
                    anchors.fill: parent
                    source: shell.image ? "file://" + shell.image : ""
                    sourceSize.width: win.width
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    visible: false
                    onStatusChanged: {
                        if (status === Image.Ready) stage.tryBuild();
                        if (status === Image.Error) Qt.quit();
                    }
                }
                ShaderEffectSource { id: crop; sourceItem: photo; hideSource: true; live: false }

                ShaderEffect {
                    id: art
                    anchors.fill: parent
                    visible: false
                    // Linear time; the radius grows as t^1.5, so the shown area grows as t^3:
                    // slow at first, block by block, then faster and faster.
                    property real t: 0
                    property real progress: Math.pow(t, 1.5)
                    property real sharp: 0
                    property real block: shell.block
                    property size size: Qt.size(width, height)
                    property variant source: crop
                    fragmentShader: Qt.resolvedUrl("reveal.frag.qsb")
                }

                function tryBuild() {
                    if (!covered || photo.status !== Image.Ready || build.running || art.visible || photo.visible) return;
                    // Without a GPU the shader draws nothing: show the picture plainly instead.
                    if (art.GraphicsInfo.api === GraphicsInfo.Software) {
                        crop.hideSource = false;
                        photo.visible = true;
                        plain.start();
                        return;
                    }
                    crop.scheduleUpdate();
                    art.visible = true;
                    build.start();
                }
            }

            Component.onCompleted: cover.start()
            SequentialAnimation {
                id: cover
                NumberAnimation { target: stage; property: "opacity"; to: 1; duration: 140; easing.type: Easing.OutCubic }
                ScriptAction { script: { if (ready.path) ready.setText("1\n"); stage.covered = true; stage.tryBuild(); } }
            }
            SequentialAnimation {
                id: plain
                PauseAnimation { duration: 600 }
                NumberAnimation { target: stage; property: "opacity"; to: 0; duration: 400; easing.type: Easing.OutCubic }
                ScriptAction { script: Qt.quit() }
            }
            SequentialAnimation {
                id: build
                NumberAnimation { target: art; property: "t"; to: 1; duration: shell.buildMs }
                NumberAnimation { target: art; property: "sharp"; to: 1; duration: 500; easing.type: Easing.OutCubic }
                PauseAnimation { duration: 250 }
                // The same picture is underneath now, so fading out is seamless.
                NumberAnimation { target: stage; property: "opacity"; to: 0; duration: 400; easing.type: Easing.OutCubic }
                ScriptAction { script: Qt.quit() }
            }
        }
    }
}
