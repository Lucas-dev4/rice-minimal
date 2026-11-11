import QtQuick
import QtQuick.Shapes
import Quickshell
import qs

// Spectrum drawing for LW // MUSIC, four modes:
//   bars    LED-like segments (5 px + 2 px gap), dark accent → accent → hot at the top, slow peaks
//   ascii   columns of ▁▂▃▄▅▆▇█ with ▔ on the peak
//   mirror  bars from the middle, the lower half at 35% opacity
//   wave    a glowing line built from the band levels (cava gives bands, not samples)
// `levels` are 0..1 targets (log-spaced bands); empty or `idle` → a very low breathing motion.
Item {
    id: root

    property var levels: []
    property string mode: "bars"
    property bool idle: levels.length === 0
    property int count: 56
    property bool running: visible
    property bool compact: false          // mini player: no peaks, thinner segments
    // RICE_MUSIC_FPS lowers it on slow machines.
    property int fps: parseInt(Quickshell.env("RICE_MUSIC_FPS")) || 60

    readonly property color low: Theme.mix(Theme.bg, Theme.accent, 0.45)
    // No canvas per frame: bars/mirror are clipped items, ascii is text, wave a Shape;
    // each frame only updates numbers and the GPU draws.
    readonly property bool leds: mode === "bars" || mode === "mirror"
    readonly property real decay: Math.pow(0.86, 60 / fps)
    property var shown: []
    property var peaks: []
    property double started: Date.now()

    function step() {
        const n = count, t = (Date.now() - started) / 1000;
        const next = shown.length === n ? shown.slice() : new Array(n).fill(0);
        const peak = peaks.length === n ? peaks.slice() : new Array(n).fill(0);
        for (let i = 0; i < n; i++) {
            let target;
            if (idle || !levels.length) {
                // Barely moving: two slow waves, never above ~6%.
                target = 0.025 + 0.02 * (Math.sin(t * 1.3 + i * 0.35) + 1) / 2 + 0.012 * Math.sin(t * 0.7 - i * 0.9);
            } else {
                const at = Math.min(levels.length - 1, Math.floor(i * levels.length / n));
                target = Math.max(0, Math.min(1, levels[at] || 0));
            }
            // Rise at once, fall smoothly (0.86 per frame at 60 fps, the same speed at any rate).
            next[i] = Math.max(target, next[i] * root.decay);
            peak[i] = Math.max(next[i], peak[i] - 0.36 / root.fps);
        }
        shown = next;
        peaks = peak;
    }

    Timer {
        // Idle motion is slow anyway: 24 fps is enough and saves CPU while paused.
        interval: root.idle ? 42 : Math.round(1000 / root.fps)
        repeat: true
        running: root.running
        onTriggered: root.step()
    }

    // ---- bars / mirror ------------------------------------------------------
    Item {
        id: ledArea
        anchors.fill: parent
        visible: root.leds
        readonly property bool mirror: root.mode === "mirror"
        readonly property int gap: root.compact ? 1 : 3
        readonly property real bw: Math.max(1, (width - gap * (root.count - 1)) / root.count)
        readonly property real span: mirror ? height / 2 : height
        readonly property int seg: root.compact ? 2 : 5
        readonly property int sgap: root.compact ? 1 : 2
        // Whole segments only.
        function litHeight(v) { const step = seg + sgap; return Math.round(v * Math.floor(span / step)) * step; }

        // One delegate per band; with mirror a second, flipped set below the middle.
        Repeater {
            model: root.count * (ledArea.mirror ? 2 : 1)
            Item {
                id: col
                required property int index
                readonly property int band: index % root.count
                readonly property bool lower: index >= root.count
                readonly property real v: root.shown[band] || 0
                x: band * (ledArea.bw + ledArea.gap)
                width: ledArea.bw
                height: ledArea.span
                y: lower ? ledArea.span : 0
                opacity: lower ? 0.35 : 1
                transform: Scale { origin.y: col.height / 2; yScale: col.lower ? -1 : 1 }
                // Every segment painted once, full height; the clip shows only the lit ones.
                Item {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: ledArea.litHeight(col.v)
                    clip: true
                    Canvas {
                        anchors.bottom: parent.bottom
                        width: col.width
                        height: ledArea.span
                        property string key: [width, height, Theme.accent, Theme.hot, root.low, ledArea.seg].join()
                        onKeyChanged: requestPaint()
                        onAvailableChanged: requestPaint()
                        onPaint: {
                            const ctx = getContext("2d"), step = ledArea.seg + ledArea.sgap, total = Math.floor(height / step);
                            ctx.reset();
                            for (let k = 0; k < total; k++) {
                                const f = k / total;
                                ctx.fillStyle = String(f > 0.8 ? Theme.hot : f > 0.35 ? Theme.accent : root.low);
                                ctx.fillRect(0, height - (k + 1) * step + ledArea.sgap, width, ledArea.seg);
                            }
                        }
                    }
                }
                Rectangle {
                    visible: !root.compact && !col.lower && (root.peaks[col.band] || 0) > 0.04
                    width: parent.width
                    height: 2
                    y: parent.height - ledArea.litHeight(root.peaks[col.band] || 0) - 3
                    color: Theme.hot
                }
            }
        }
    }

    // ---- ascii: one text column per band (no canvas) ---------------------
    Item {
        id: asciiArea
        anchors.fill: parent
        visible: root.mode === "ascii"
        readonly property int gap: root.compact ? 1 : 3
        readonly property real bw: Math.max(1, (width - gap * (root.count - 1)) / root.count)
        readonly property int cell: Math.max(8, Math.round(bw))
        readonly property int rows: Math.max(1, Math.floor(height / cell))
        readonly property string glyphs: "▁▂▃▄▅▆▇█"
        Repeater {
            model: asciiArea.visible ? root.count : 0
            Item {
                id: acol
                required property int index
                readonly property real v: (root.shown[index] || 0) * asciiArea.rows
                readonly property int full: Math.floor(v)
                readonly property real part: v - full
                readonly property int peak: root.compact ? -1 : Math.floor((root.peaks[index] || 0) * asciiArea.rows)
                x: index * (asciiArea.bw + asciiArea.gap)
                width: asciiArea.cell
                height: parent.height
                // The █ column, painted once (a block glyph is a filled cell), cut to the level.
                Item {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: acol.full * asciiArea.cell
                    clip: true
                    Canvas {
                        anchors.bottom: parent.bottom
                        width: acol.width
                        height: asciiArea.rows * asciiArea.cell
                        property string key: [width, height, asciiArea.cell, Theme.accent, Theme.hot, root.low].join()
                        onKeyChanged: requestPaint()
                        onAvailableChanged: requestPaint()
                        onPaint: {
                            const ctx = getContext("2d"), cell = asciiArea.cell, rows = asciiArea.rows, w = width * 0.62;
                            ctx.reset();
                            for (let r = 0; r < rows; r++) {
                                ctx.fillStyle = String(r / rows > 0.75 ? Theme.hot : r / rows > 0.3 ? Theme.accent : root.low);
                                ctx.fillRect(0, height - (r + 1) * cell, w, cell);
                            }
                        }
                    }
                }
                // ▁▂▃▄▅▆▇ on top and the ▔ peak are block glyphs: drawn as the same
                // rectangles, so no text is laid out again per frame.
                Rectangle {
                    visible: acol.part > 0.05 && acol.full < asciiArea.rows
                    width: parent.width * 0.62
                    height: Math.max(1, Math.round(Math.floor(acol.part * 8) / 8 * asciiArea.cell))
                    y: parent.height - acol.full * asciiArea.cell - height
                    color: Theme.accent
                }
                Rectangle {
                    visible: acol.peak > 0 && acol.peak > acol.full
                    width: parent.width * 0.62
                    height: Math.max(1, Math.round(asciiArea.cell / 8))
                    y: parent.height - (acol.peak + 1) * asciiArea.cell
                    color: Theme.hot
                }
            }
        }
    }

    // ---- wave: a vector line drawn by the GPU ------------------------------
    // The sum of band-shaped sines across the width: louder bands, bigger ripples.
    Shape {
        id: wave
        anchors.fill: parent
        visible: root.mode === "wave"
        preferredRendererType: Shape.CurveRenderer
        property var points: []
        function update() {
            const W = width, H = height, n = root.shown.length, t = (Date.now() - root.started) / 1000;
            const steps = Math.max(40, Math.floor(W / 6)), out = [];
            for (let s = 0; s <= steps; s++) {
                const x = s / steps;
                let y = 0;
                for (let b = 0; b < n; b += 4)
                    y += root.shown[b] * Math.sin((b / n * 38 + 2) * x * Math.PI * 2 + t * (2 + b / 9)) / (1 + b / 18);
                out.push(Qt.point(x * W, H / 2 - y * H * 0.32));
            }
            points = out;
        }
        Connections {
            target: root
            enabled: wave.visible
            function onShownChanged() { wave.update(); }
        }
        // Glow: a wide translucent stroke under the line.
        ShapePath {
            strokeWidth: root.compact ? 0 : 7
            strokeColor: Qt.alpha(Theme.accent, 0.16)
            fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin
            PathPolyline { path: wave.points }
        }
        ShapePath {
            strokeWidth: root.compact ? 1 : 2
            strokeColor: Theme.accent
            fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin
            PathPolyline { path: wave.points }
        }
    }
}
