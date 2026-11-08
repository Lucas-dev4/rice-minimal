import QtQuick
import qs

// Builds an image out of colored ASCII, top to bottom with a ragged front, then
// dissolves into the real picture. Pure QML: a Canvas samples the thumbnail.
//   play(sample, full)  start; `sample` is read for the characters, `full` is shown at the end
//   finish()            the work behind it is done: dissolve once the build completes
//   cancel()            hide at once
Rectangle {
    id: root

    property string sample: ""
    property string full: ""
    property bool done: false
    // The build always plays: it is the feedback the user asked for, ~1.4 s.
    readonly property int buildMs: 1400
    readonly property string ramp: " .:-=+*#%@"
    readonly property int px: 11

    signal finished()

    color: Theme.bg
    border.width: 1
    border.color: Theme.line
    visible: opacity > 0
    opacity: 0
    clip: true

    function play(sampleSource, fullSource) {
        hide.stop();
        done = false;
        photo.opacity = 0;
        art.cells = [];
        art.drawn = 0;
        art.wipe = true;
        art.requestPaint();
        sample = sampleSource;
        full = fullSource;
        opacity = 1;
        if (sampler.status === Image.Ready && sampler.source.toString() === "file://" + sampleSource)
            art.prepare();
    }
    function finish() { done = true; maybeReveal(); }
    function cancel() { ticker.stop(); hide.restart(); }
    function maybeReveal() {
        if (done && art.cells.length && art.drawn >= art.cells.length && photo.status === Image.Ready && !reveal.running)
            reveal.start();
    }

    TextMetrics { id: glyph; font.family: Theme.font; font.pixelSize: root.px; text: "M" }

    // Natural size is needed to crop like PreserveAspectCrop.
    Image {
        id: sampler
        visible: false
        source: root.sample ? "file://" + root.sample : ""
        asynchronous: true
        onStatusChanged: if (status === Image.Ready && root.opacity > 0) art.prepare()
    }

    Canvas {
        id: art
        anchors.fill: parent
        anchors.margins: 1
        property var cells: []
        property int drawn: 0
        property bool wipe: false
        readonly property real cw: Math.max(1, glyph.advanceWidth)
        readonly property real ch: Math.round(root.px * 1.25)

        function prepare() {
            const cols = Math.floor(width / cw), rows = Math.floor(height / ch);
            if (cols < 2 || rows < 2) return;
            const ctx = getContext("2d");
            // Crop the source to this area's aspect, then shrink it to one pixel per cell.
            const iw = sampler.implicitWidth, ih = sampler.implicitHeight;
            const want = (cols * cw) / (rows * ch);
            let sw = iw, sh = ih;
            if (iw / ih > want) sw = ih * want; else sh = iw / want;
            ctx.clearRect(0, 0, width, height);
            ctx.drawImage(sampler, (iw - sw) / 2, (ih - sh) / 2, sw, sh, 0, 0, cols, rows);
            const px = ctx.getImageData(0, 0, cols, rows).data;
            ctx.clearRect(0, 0, width, height);

            const out = [];
            for (let y = 0; y < rows; y++) {
                for (let x = 0; x < cols; x++) {
                    const i = (y * cols + x) * 4;
                    const r = px[i], g = px[i + 1], b = px[i + 2];
                    const lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
                    const c = root.ramp[Math.min(root.ramp.length - 1, Math.floor(lum * root.ramp.length))];
                    if (c === " ") continue;
                    // Density carries brightness; lift the color so dark tones stay visible.
                    const k = Math.min(2.6, 0.5 + 0.5 * 255 / Math.max(1, r, g, b));
                    out.push({ x: x * cw, y: y * ch, c: c,
                               s: "rgb(" + Math.min(255, r * k | 0) + "," + Math.min(255, g * k | 0) + "," + Math.min(255, b * k | 0) + ")",
                               o: y + Math.random() * rows * 0.35 });
                }
            }
            out.sort((a, b) => a.o - b.o);
            cells = out;
            drawn = 0;
            ticker.started = Date.now();
            ticker.restart();
        }

        onPaint: {
            const ctx = getContext("2d");
            if (wipe) { ctx.clearRect(0, 0, width, height); wipe = false; }
            if (!cells.length) return;
            const target = Math.min(cells.length, Math.ceil(cells.length * (Date.now() - ticker.started) / root.buildMs));
            // Canvas only takes installed family names, so fall back the way Text does.
            ctx.font = root.px + "px '" + Theme.font + "', 'JetBrainsMono Nerd Font Mono', monospace";
            ctx.textBaseline = "top";
            for (let i = drawn; i < target; i++) {
                const cell = cells[i];
                ctx.fillStyle = cell.s;
                ctx.fillText(cell.c, cell.x, cell.y);
            }
            drawn = target;
            if (drawn >= cells.length) { ticker.stop(); root.maybeReveal(); }
        }
    }

    Timer {
        id: ticker
        property double started: 0
        interval: 16
        repeat: true
        onTriggered: art.requestPaint()
    }

    Image {
        id: photo
        anchors.fill: parent
        anchors.margins: 1
        source: root.full ? "file://" + root.full : ""
        sourceSize.width: 1400
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        opacity: 0
        onStatusChanged: root.maybeReveal()
    }

    SequentialAnimation {
        id: reveal
        NumberAnimation { target: photo; property: "opacity"; to: 1; duration: 450; easing.type: Easing.OutCubic }
        PauseAnimation { duration: 700 }
        ScriptAction { script: { root.finished(); hide.restart(); } }
    }
    NumberAnimation { id: hide; target: root; property: "opacity"; to: 0; duration: 250; easing.type: Easing.OutCubic }

    // A click skips the build.
    MouseArea {
        anchors.fill: parent
        onClicked: {
            if (art.cells.length) { ticker.started = 0; art.requestPaint(); }
        }
    }
}
