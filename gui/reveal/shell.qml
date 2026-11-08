import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

// Started by the wallpaper hook (theme.py reveal()) for every real wallpaper change:
// covers the screen, builds the new image out of colored ASCII, then dissolves into the
// real picture, which Noctalia has set underneath by then, and exits. Cosmetic only:
// click-through, no keyboard, and a hard time limit.
//   RICE_REVEAL_IMAGE  the new wallpaper
//   RICE_REVEAL_READY  written once the screen is covered, so the hook can swap the image unseen
ShellRoot {
    id: shell

    readonly property string image: Quickshell.env("RICE_REVEAL_IMAGE") || ""
    readonly property string font: "JetBrains Mono"
    readonly property int px: 13
    readonly property string ramp: " .:-=+*#%@"
    readonly property int buildMs: 1600
    property var dark: ({})
    readonly property color bg: dark.mSurface || "#12100e"

    FileView {
        path: Quickshell.env("HOME") + "/.config/noctalia/palettes/RiceMinimal.json"
        blockLoading: true
        printErrors: false
        onLoaded: { try { shell.dark = JSON.parse(text()).dark || {}; } catch (error) {} }
    }
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

                Rectangle { anchors.fill: parent; color: shell.bg }

                TextMetrics { id: glyph; font.family: shell.font; font.pixelSize: shell.px; text: "M" }

                // Sampled small: one pixel per character cell is all that is needed.
                Image {
                    id: sampler
                    visible: false
                    source: shell.image ? "file://" + shell.image : ""
                    sourceSize.width: 640
                    asynchronous: true
                    onStatusChanged: if (status === Image.Ready) art.prepare()
                }

                Canvas {
                    id: art
                    anchors.fill: parent
                    property var cells: []
                    property int drawn: 0
                    property double started: 0
                    readonly property real cw: Math.max(1, glyph.advanceWidth)
                    readonly property real ch: Math.round(shell.px * 1.25)

                    function prepare() {
                        if (cells.length || width < 10) return;
                        const cols = Math.floor(width / cw), rows = Math.floor(height / ch);
                        const ctx = getContext("2d");
                        // Crop like the wallpaper (cover), then shrink to one pixel per cell.
                        const iw = sampler.implicitWidth, ih = sampler.implicitHeight;
                        const want = (cols * cw) / (rows * ch);
                        let sw = iw, sh = ih;
                        if (iw / ih > want) sw = ih * want; else sh = iw / want;
                        ctx.drawImage(sampler, (iw - sw) / 2, (ih - sh) / 2, sw, sh, 0, 0, cols, rows);
                        const data = ctx.getImageData(0, 0, cols, rows).data;
                        ctx.clearRect(0, 0, width, height);

                        const out = [];
                        for (let y = 0; y < rows; y++) {
                            for (let x = 0; x < cols; x++) {
                                const i = (y * cols + x) * 4;
                                const r = data[i], g = data[i + 1], b = data[i + 2];
                                const lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
                                const c = shell.ramp[Math.min(shell.ramp.length - 1, Math.floor(lum * shell.ramp.length))];
                                if (c === " ") continue;
                                // Density carries brightness; lift the color so dark tones stay visible.
                                const k = Math.min(2.6, 0.5 + 0.5 * 255 / Math.max(1, r, g, b));
                                out.push({ x: x * cw, y: y * ch, c: c,
                                           s: "rgb(" + Math.min(255, r * k | 0) + "," + Math.min(255, g * k | 0) + "," + Math.min(255, b * k | 0) + ")",
                                           o: y + Math.random() * rows * 0.35 });
                            }
                        }
                        // Top to bottom with a ragged front.
                        out.sort((a, b) => a.o - b.o);
                        cells = out;
                        started = Date.now();
                        ticker.start();
                    }

                    onPaint: {
                        if (!cells.length) return;
                        const ctx = getContext("2d");
                        const target = Math.min(cells.length, Math.ceil(cells.length * (Date.now() - started) / shell.buildMs));
                        // Canvas only accepts installed family names, so fall back the way Text does.
                        ctx.font = shell.px + "px '" + shell.font + "', 'JetBrainsMono Nerd Font Mono', monospace";
                        ctx.textBaseline = "top";
                        for (let i = drawn; i < target; i++) {
                            const cell = cells[i];
                            ctx.fillStyle = cell.s;
                            ctx.fillText(cell.c, cell.x, cell.y);
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
                ScriptAction { script: { if (ready.path) ready.setText("1\n"); if (sampler.status === Image.Ready) art.prepare(); } }
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
