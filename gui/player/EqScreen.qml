import QtQuick
import Quickshell.Io
import qs
import qs.components

// LW // EQUALIZER: cliamp's 10-band peaking EQ (70 Hz … 16 kHz, Q 1.4, ±12 dB), live.
// cliamp has no pre-amp and no bypass: BYPASS saves the curve, goes flat, and brings it
// back (the saved curve survives a restart in ~/.local/state/rice-minimal/gui/music-eq.json).
Item {
    id: root

    property Item keyTarget: null
    property string title: ""
    readonly property var hints: [["←→", "banda"], ["↑↓", "±1 dB"], ["0", "zera"], ["b", "bypass"], ["f", "flat"]]

    readonly property var freqs: Music.eqFrequencies
    property var gains: Music.eqBands.slice()
    property int focusBand: 0
    property bool holding: false
    property var saved: null              // the curve put aside by BYPASS
    readonly property bool bypassed: saved !== null

    // The prototype's presets, applied band by band to cliamp's bands.
    readonly property var presets: [
        ["flat", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]], ["bass", [6, 5, 4, 2, 0, 0, 0, 0, 0, 0]],
        ["lofi", [3, 3, 2, 0, -1, -2, -3, -4, -6, -8]], ["vocal", [-2, -2, -1, 1, 3, 4, 3, 1, 0, -1]],
        ["treble", [0, 0, 0, 0, 0, 1, 2, 4, 5, 6]], ["v-shape", [5, 4, 2, 0, -2, -2, 0, 2, 4, 5]]
    ]
    // cliamp's own presets (ui/model/eq_presets.go, v2.4.0), applied by name.
    readonly property var cliampPresets: [
        ["Rock", [5, 4, 2, -1, -2, 2, 4, 5, 5, 5]], ["Pop", [-1, 2, 4, 5, 4, 1, -1, -1, 1, 2]],
        ["Jazz", [3, 4, 2, 1, -1, -1, 1, 2, 3, 4]], ["Classical", [3, 2, 1, 0, -1, -1, 0, 2, 3, 4]],
        ["Bass Boost", [8, 6, 4, 2, 0, 0, 0, 0, 0, 0]], ["Treble Boost", [0, 0, 0, 0, 0, 1, 3, 5, 6, 7]],
        ["Vocal", [-2, -1, 1, 4, 5, 4, 2, 0, -1, -2]], ["Electronic", [6, 4, 1, -1, -2, 1, 3, 4, 5, 6]],
        ["Acoustic", [3, 3, 2, 0, 1, 2, 3, 3, 2, 1]], ["Hip-Hop", [7, 5, 3, 1, -1, -1, 1, 3, 3, 3]],
        ["R&B", [4, 6, 3, 1, -1, 1, 2, 2, 1, 0]], ["Loudness", [6, 4, 1, 0, -2, -1, 1, 4, 5, 5]],
        ["Late Night", [5, 3, 1, 0, -2, -1, 0, 2, 3, 3]], ["Podcast", [-3, -1, 2, 4, 4, 3, 1, -1, -2, -3]],
        ["Small Speakers", [7, 5, 4, 2, 1, 0, -1, 0, 1, 2]]
    ]
    function same(a, b) { return a.length === b.length && a.every((v, i) => Math.round(v) === b[i]); }
    function label(f) { return f >= 1000 ? f / 1000 + "k" : String(f); }

    // cliamp follows unless we are in the middle of a change.
    Connections {
        target: Music
        function onChanged() { if (!root.holding && !morph.running && !pending.running) root.gains = Music.eqBands.slice(); }
    }

    // ---- sending ------------------------------------------------------------
    property var dirty: ({})
    function setGain(band, value) {
        const v = Math.max(-12, Math.min(12, Math.round(value)));
        if (gains[band] === v) return;
        const next = gains.slice();
        next[band] = v;
        gains = next;
        dirty[band] = true;
        pending.restart();
    }
    // While dragging, cliamp hears about it every 80 ms, not on every pixel.
    Timer {
        id: pending
        interval: 80
        onTriggered: {
            for (const b in root.dirty) Music.setBand(parseInt(b), root.gains[b]);
            root.dirty = {};
        }
    }

    // Presets slide to their values in ~260 ms, then go to cliamp in one go.
    property var from: []
    property var to: []
    property real t: 0
    onTChanged: if (morph.running) gains = from.map((v, i) => v + (to[i] - v) * t)
    NumberAnimation {
        id: morph
        target: root
        property: "t"
        from: 0
        to: 1
        duration: Theme.motion ? 260 : 0
        easing.type: Theme.ease
        onFinished: root.finishMorph()
    }
    property string morphName: ""
    function apply(values, name) {
        from = gains.slice();
        to = values.slice();
        morphName = name || "";
        morph.restart();
    }
    function finishMorph() {
        gains = to.slice();
        if (morphName) Music.setPreset(morphName);
        else to.forEach((v, i) => { if (Music.eqBands[i] !== v) Music.setBand(i, v); });
    }
    function bypass() {
        if (bypassed) {
            apply(saved);
            saved = null;
            Status.say("[ OK ] eq ligado", Theme.accent);
        } else {
            saved = gains.slice();
            apply([0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "Flat");
            Status.say("[ -- ] eq em bypass (b volta)", Theme.dim);
        }
    }
    onSavedChanged: if (storeLoaded) store.setText(JSON.stringify({ saved: saved }) + "\n")
    property bool storeLoaded: false

    function handleKey(event) {
        const t = event.text;
        if (event.key === Qt.Key_Left) { focusBand = Math.max(0, focusBand - 1); return true; }
        if (event.key === Qt.Key_Right) { focusBand = Math.min(9, focusBand + 1); return true; }
        if (event.key === Qt.Key_Up) { setGain(focusBand, gains[focusBand] + 1); return true; }
        if (event.key === Qt.Key_Down) { setGain(focusBand, gains[focusBand] - 1); return true; }
        if (t === "0") { setGain(focusBand, 0); return true; }
        if (t === "b") { bypass(); return true; }
        if (t === "f") { saved = null; apply([0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "Flat"); return true; }
        return false;
    }

    FileView {
        id: store
        path: Theme.guiStatePath + "/music-eq.json"
        printErrors: false
        atomicWrites: true
        onLoaded: {
            try { const s = JSON.parse(text()).saved; root.saved = Array.isArray(s) && s.length === 10 ? s : null; } catch (error) {}
            root.storeLoaded = true;
        }
        onLoadFailed: root.storeLoaded = true
    }

    // ================= PRESETS =================
    Column {
        id: presetRows
        width: parent.width
        spacing: 6
        Flow {
            width: parent.width
            spacing: 6
            Repeater {
                model: root.presets
                Chip {
                    required property var modelData
                    label: modelData[0]
                    on: root.same(root.gains, modelData[1])
                    onClicked: { root.saved = null; root.apply(modelData[1]); root.keyTarget.forceActiveFocus(); }
                }
            }
        }
        Flow {
            width: parent.width
            spacing: 4
            RiceText { text: "cliamp"; color: Theme.faint; font.pixelSize: Theme.small; rightPadding: 4; topPadding: 2 }
            Repeater {
                model: root.cliampPresets
                Rectangle {
                    id: small
                    required property var modelData
                    readonly property bool on: root.same(root.gains, modelData[1])
                    width: smallText.implicitWidth + 10
                    height: smallText.implicitHeight + 2
                    color: on ? Theme.accentA : "transparent"
                    border.width: 1
                    border.color: on ? Theme.accent : smallMouse.containsMouse ? Theme.line2 : Theme.line
                    RiceText { id: smallText; anchors.centerIn: parent; text: small.modelData[0]; font.pixelSize: 10; color: small.on ? Theme.accent : smallMouse.containsMouse ? Theme.fg : Theme.dim }
                    MouseArea {
                        id: smallMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { root.saved = null; root.apply(small.modelData[1], small.modelData[0]); root.keyTarget.forceActiveFocus(); }
                    }
                }
            }
        }
    }

    // ================= RESPONSE CURVE =================
    // The sum of the ten peaking filters cliamp runs (Audio EQ Cookbook, Q 1.4, 44.1 kHz).
    Rectangle {
        id: curveBox
        anchors.top: presetRows.bottom
        anchors.topMargin: 12
        width: parent.width
        height: 150
        color: Theme.panel
        border.width: 1
        border.color: Theme.line
        Canvas {
            id: curve
            anchors.fill: parent
            anchors.margins: 1
            property var g: root.gains
            onGChanged: requestPaint()
            onWidthChanged: requestPaint()
            Connections { target: Theme; function onAccentChanged() { curve.requestPaint(); } }
            function responseDb(f) {
                const sr = 44100;
                let total = 0;
                for (let i = 0; i < 10; i++) {
                    const dB = g[i] || 0;
                    if (!dB) continue;
                    const A = Math.pow(10, dB / 40), w0 = 2 * Math.PI * root.freqs[i] / sr, alpha = Math.sin(w0) / (2 * 1.4);
                    const b0 = 1 + alpha * A, b1 = -2 * Math.cos(w0), b2 = 1 - alpha * A;
                    const a0 = 1 + alpha / A, a1 = -2 * Math.cos(w0), a2 = 1 - alpha / A;
                    const w = 2 * Math.PI * f / sr, c1 = Math.cos(w), s1 = Math.sin(w), c2 = Math.cos(2 * w), s2 = Math.sin(2 * w);
                    const nr = b0 + b1 * c1 + b2 * c2, ni = -(b1 * s1 + b2 * s2);
                    const dr = a0 + a1 * c1 + a2 * c2, di = -(a1 * s1 + a2 * s2);
                    total += 10 * Math.log10((nr * nr + ni * ni) / (dr * dr + di * di));
                }
                return total;
            }
            onPaint: {
                const ctx = getContext("2d"), W = width, H = height, left = 34, right = 8;
                // The context keeps line width and glow between paints: start clean.
                ctx.reset();
                ctx.lineWidth = 1;
                const lo = Math.log10(20), hi = Math.log10(20000);
                const xOf = f => left + (Math.log10(f) - lo) / (hi - lo) * (W - left - right);
                const yOf = dB => H / 2 - dB / 15 * (H / 2 - 8);
                ctx.font = "10px '" + Theme.font + "', 'JetBrainsMono Nerd Font Mono', monospace";
                ctx.textBaseline = "middle";
                for (const dB of [12, 6, 0, -6, -12]) {
                    ctx.strokeStyle = String(dB === 0 ? Theme.line2 : Theme.line);
                    ctx.beginPath(); ctx.moveTo(left, yOf(dB)); ctx.lineTo(W - right, yOf(dB)); ctx.stroke();
                    ctx.fillStyle = String(Theme.faint);
                    ctx.fillText((dB > 0 ? "+" : "") + dB, 4, yOf(dB));
                }
                ctx.textBaseline = "bottom";
                for (const f of [100, 1000, 10000]) {
                    ctx.strokeStyle = String(Theme.line);
                    ctx.beginPath(); ctx.moveTo(xOf(f), 4); ctx.lineTo(xOf(f), H - 4); ctx.stroke();
                    ctx.fillStyle = String(Theme.faint);
                    ctx.fillText(f >= 1000 ? f / 1000 + "k" : String(f), xOf(f) + 3, H - 3);
                }
                const on = !root.bypassed;
                const pts = [];
                for (let s = 0; s <= 160; s++) {
                    const f = Math.pow(10, lo + (hi - lo) * s / 160);
                    pts.push([xOf(f), yOf(Math.max(-15, Math.min(15, responseDb(f))))]);
                }
                // Gradient fill between the curve and 0 dB.
                const fill = ctx.createLinearGradient(0, 0, 0, H);
                fill.addColorStop(0, String(Qt.alpha(Theme.accent, 0.28)));
                fill.addColorStop(0.5, String(Qt.alpha(Theme.accent, 0.04)));
                fill.addColorStop(1, String(Qt.alpha(Theme.accent, 0.28)));
                ctx.fillStyle = fill;
                ctx.beginPath(); ctx.moveTo(pts[0][0], yOf(0));
                for (const p of pts) ctx.lineTo(p[0], p[1]);
                ctx.lineTo(pts[pts.length - 1][0], yOf(0)); ctx.closePath(); ctx.fill();
                ctx.strokeStyle = String(on ? Theme.accent : Theme.dim);
                ctx.lineWidth = 2;
                ctx.shadowColor = String(Theme.accent);
                ctx.shadowBlur = on ? 8 : 0;
                ctx.beginPath();
                pts.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
                ctx.stroke();
                ctx.shadowBlur = 0;
                ctx.fillStyle = String(Theme.hot);
                for (let i = 0; i < 10; i++) {
                    ctx.beginPath();
                    ctx.arc(xOf(root.freqs[i]), yOf(responseDb(root.freqs[i])), 2.5, 0, Math.PI * 2);
                    ctx.fill();
                }
            }
        }
    }

    // ================= SLIDERS =================
    Item {
        id: sliders
        anchors.top: curveBox.bottom
        anchors.topMargin: 16
        anchors.bottom: foot.top
        anchors.bottomMargin: 12
        width: parent.width
        readonly property real colW: (width - 70) / 10

        // dB scale where the prototype had PRE (cliamp has no pre-amp).
        Item {
            width: 70
            height: parent.height
            Repeater {
                model: [12, 6, 0, -6, -12]
                RiceText {
                    required property int modelData
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    y: 22 + (12 - modelData) / 24 * (sliders.height - 22 - 22) - height / 2
                    text: (modelData > 0 ? "+" : "") + modelData + " dB"
                    color: modelData === 0 ? Theme.dim : Theme.faint
                    font.pixelSize: 10
                }
            }
        }

        Repeater {
            model: 10
            Item {
                id: band
                required property int index
                readonly property int value: Math.round(root.gains[index] || 0)
                readonly property bool focused: root.focusBand === index
                x: 70 + index * sliders.colW
                width: sliders.colW
                height: sliders.height

                RiceText {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: (band.value > 0 ? "+" : "") + band.value + " dB"
                    color: band.value === 0 ? Theme.dim : Theme.fg
                    font.pixelSize: Theme.small
                }
                Item {
                    id: track
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: 22
                    width: 26
                    height: parent.height - 44
                    readonly property real zeroY: height / 2
                    function yOf(dB) { return (12 - dB) / 24 * height; }
                    Rectangle { anchors.horizontalCenter: parent.horizontalCenter; width: 1; height: parent.height; color: Theme.line2 }
                    Repeater {
                        model: 9
                        Rectangle {
                            required property int index
                            readonly property bool zero: index === 4
                            x: zero ? 2 : 6
                            width: parent.width - 2 * x
                            y: Math.round(index / 8 * track.height)
                            height: 1
                            color: zero ? Theme.dim : Theme.line
                        }
                    }
                    // Fill from 0 dB to the value.
                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 3
                        y: Math.min(track.zeroY, track.yOf(band.value))
                        height: Math.abs(track.yOf(band.value) - track.zeroY)
                        color: root.bypassed ? Theme.dim : Theme.accent
                        Behavior on y { enabled: !root.holding; NumberAnimation { duration: Theme.tFast; easing.type: Theme.ease } }
                        Behavior on height { enabled: !root.holding; NumberAnimation { duration: Theme.tFast; easing.type: Theme.ease } }
                    }
                    // Thumb with a soft glow.
                    Rectangle {
                        id: thumb
                        x: 2
                        width: parent.width - 4
                        height: 8
                        y: track.yOf(band.value) - 4
                        color: root.bypassed ? Theme.dim : trackMouse.containsMouse || band.focused ? Theme.hot : Theme.accent
                        Behavior on y { enabled: !root.holding; NumberAnimation { duration: Theme.tFast; easing.type: Theme.ease } }
                        Rectangle {
                            anchors.centerIn: parent
                            width: parent.width + 8
                            height: parent.height + 8
                            z: -1
                            color: "transparent"
                            border.width: 4
                            border.color: Qt.alpha(Theme.accent, root.bypassed ? 0 : 0.18)
                        }
                    }
                    MouseArea {
                        id: trackMouse
                        anchors.fill: parent
                        anchors.margins: -6
                        hoverEnabled: true
                        cursorShape: Qt.SizeVerCursor
                        function valueAt(y) { return 12 - (y - 6) / track.height * 24; }
                        onPressed: mouse => { root.holding = true; root.focusBand = band.index; root.saved = null; root.setGain(band.index, valueAt(mouse.y)); }
                        onPositionChanged: mouse => { if (pressed) root.setGain(band.index, valueAt(mouse.y)); }
                        onReleased: { root.holding = false; root.keyTarget.forceActiveFocus(); }
                        onDoubleClicked: root.setGain(band.index, 0)
                        onWheel: wheel => { root.focusBand = band.index; root.setGain(band.index, band.value + (wheel.angleDelta.y > 0 ? 1 : -1)); }
                    }
                }
                RiceText {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    text: root.label(root.freqs[band.index])
                    color: band.focused ? Theme.accent : Theme.dim
                    font.pixelSize: Theme.small
                }
            }
        }
    }

    // ================= FOOTER =================
    Item {
        id: foot
        anchors.bottom: parent.bottom
        width: parent.width
        height: 32
        Rectangle { width: parent.width; height: 1; color: Theme.line }
        RiceText {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 4
            textFormat: Text.StyledText
            text: "arraste · roda ±1 dB · duplo clique zera  <font color='" + Theme.faint + "'>10 bandas peaking do cliamp, Q 1.4 · sem pré-amp</font>"
            color: Theme.dim
            font.pixelSize: Theme.small
        }
        Row {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            spacing: 8
            AccentButton { ghost: true; label: root.bypassed ? "BYPASSED (b)" : "BYPASS (b)"; onClicked: root.bypass() }
            AccentButton { label: "FLAT"; onClicked: { root.saved = null; root.apply([0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "Flat"); } }
        }
    }
}
