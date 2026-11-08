import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

// Started by the wallpaper hook (theme.py reveal()) for every real wallpaper change:
// covers the screen, builds the new image block by block from the middle outwards, slow
// at first and then accelerating, then dissolves into the
// real picture, which Noctalia has set underneath by then, and exits. Cosmetic only:
// click-through, no keyboard, and a hard time limit.
//   RICE_REVEAL_IMAGE  the new wallpaper
//   RICE_REVEAL_READY  written once the screen is covered, so the hook can swap the image unseen
ShellRoot {
    id: shell

    readonly property string image: Quickshell.env("RICE_REVEAL_IMAGE") || ""
    // Block size in pixels and the time to fill the screen.
    readonly property int block: 4
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

                // Only for the natural size; the Canvas loads its own copy to read pixels from.
                Image {
                    id: sampler
                    visible: false
                    source: art.url
                    asynchronous: true
                    onStatusChanged: art.tryPrepare()
                }

                Canvas {
                    id: art
                    anchors.fill: parent
                    readonly property string url: shell.image ? "file://" + shell.image : ""
                    property var cells: []
                    property int drawn: 0
                    property double started: 0
                    property bool sampling: false
                    readonly property int size: shell.block

                    Component.onCompleted: if (url) loadImage(url)
                    onImageLoaded: tryPrepare()
                    // Pixels can only be read reliably inside onPaint, on the GPU too.
                    function tryPrepare() {
                        if (!cells.length && !sampling && stage.covered && sampler.status === Image.Ready && isImageLoaded(url)) {
                            sampling = true;
                            requestPaint();
                        }
                    }

                    function prepare(ctx) {
                        const cols = Math.ceil(width / size), rows = Math.ceil(height / size);
                        // Crop like the wallpaper (cover), then shrink to one pixel per block.
                        const iw = sampler.implicitWidth, ih = sampler.implicitHeight;
                        const want = cols / rows;
                        let sw = iw, sh = ih;
                        if (iw / ih > want) sw = ih * want; else sh = iw / want;
                        ctx.drawImage(url, (iw - sw) / 2, (ih - sh) / 2, sw, sh, 0, 0, cols, rows);
                        const data = ctx.getImageData(0, 0, cols, rows).data;
                        ctx.clearRect(0, 0, width, height);

                        // From the middle outwards, in a circle, with a slightly ragged edge.
                        const cx = (cols - 1) / 2, cy = (rows - 1) / 2;
                        const reach = Math.hypot(cx, cy);
                        const out = [];
                        for (let y = 0; y < rows; y++) {
                            for (let x = 0; x < cols; x++) {
                                const i = (y * cols + x) * 4;
                                out.push({ x: x * size, y: y * size,
                                           s: "rgb(" + data[i] + "," + data[i + 1] + "," + data[i + 2] + ")",
                                           o: Math.hypot(x - cx, y - cy) / reach + Math.random() * 0.06 });
                            }
                        }
                        out.sort((a, b) => a.o - b.o);
                        cells = out;
                        started = Date.now();
                        ticker.start();
                    }

                    onPaint: {
                        const ctx = getContext("2d");
                        if (sampling) { sampling = false; prepare(ctx); return; }
                        if (!cells.length) return;
                        // Slow at first, block by block, then faster and faster (cubic ease-in).
                        const t = Math.min(1, (Date.now() - started) / shell.buildMs);
                        const target = Math.min(cells.length, Math.ceil(cells.length * t * t * t));
                        for (let i = drawn; i < target; i++) {
                            const cell = cells[i];
                            ctx.fillStyle = cell.s;
                            ctx.fillRect(cell.x, cell.y, size, size);
                        }
                        drawn = target;
                        if (drawn >= cells.length) {
                            ticker.stop();
                            if (photo.status === Image.Ready) reveal.start(); else photo.waiting = true;
                        }
                    }
                    Timer { id: ticker; interval: 16; repeat: true; onTriggered: art.requestPaint() }
                }

                Image {
                    id: photo
                    property bool waiting: false
                    anchors.fill: parent
                    source: shell.image ? "file://" + shell.image : ""
                    sourceSize.width: win.width
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    opacity: 0
                    onStatusChanged: {
                        if (status === Image.Ready && waiting) reveal.start();
                        if (status === Image.Error) Qt.quit();
                    }
                }
            }

            Component.onCompleted: cover.start()
            SequentialAnimation {
                id: cover
                NumberAnimation { target: stage; property: "opacity"; to: 1; duration: 140; easing.type: Easing.OutCubic }
                ScriptAction { script: { if (ready.path) ready.setText("1\n"); stage.covered = true; art.tryPrepare(); } }
            }
            SequentialAnimation {
                id: reveal
                NumberAnimation { target: photo; property: "opacity"; to: 1; duration: 500; easing.type: Easing.OutCubic }
                PauseAnimation { duration: 250 }
                // The same picture is underneath now, so fading out is seamless.
                NumberAnimation { target: stage; property: "opacity"; to: 0; duration: 400; easing.type: Easing.OutCubic }
                ScriptAction { script: Qt.quit() }
            }
        }
    }
}
