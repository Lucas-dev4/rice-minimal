import QtQuick
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

    readonly property color low: Theme.mix(Theme.bg, Theme.accent, 0.45)
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
            // Rise at once, fall smoothly (~0.86 per frame at 60 fps).
            next[i] = Math.max(target, next[i] * 0.86);
            peak[i] = Math.max(next[i], peak[i] - 0.006);
        }
        shown = next;
        peaks = peak;
        canvas.requestPaint();
    }

    Timer {
        interval: root.idle ? 33 : 16
        repeat: true
        running: root.running
        onTriggered: root.step()
    }

    Canvas {
        id: canvas
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative
        onPaint: {
            const ctx = getContext("2d");
            const W = width, H = height, n = root.shown.length;
            ctx.clearRect(0, 0, W, H);
            if (!n) return;
            const gap = root.compact ? 1 : 3;
            const bw = Math.max(1, (W - gap * (n - 1)) / n);
            const accent = String(Theme.accent), hot = String(Theme.hot), low = String(root.low);

            if (root.mode === "wave") {
                // Sum of band-shaped sines across the width: louder bands, bigger ripples.
                const t = (Date.now() - root.started) / 1000;
                ctx.lineWidth = root.compact ? 1 : 2;
                ctx.strokeStyle = accent;
                ctx.shadowColor = accent;
                ctx.shadowBlur = root.compact ? 0 : 12;
                ctx.beginPath();
                const steps = Math.floor(W / 3);
                for (let s = 0; s <= steps; s++) {
                    const x = s / steps;
                    let y = 0;
                    for (let b = 0; b < n; b += 4)
                        y += root.shown[b] * Math.sin((b / n * 38 + 2) * x * Math.PI * 2 + t * (2 + b / 9)) / (1 + b / 18);
                    const py = H / 2 - y * H * 0.32;
                    s === 0 ? ctx.moveTo(x * W, py) : ctx.lineTo(x * W, py);
                }
                ctx.stroke();
                ctx.shadowBlur = 0;
                return;
            }

            if (root.mode === "ascii") {
                const glyphs = "▁▂▃▄▅▆▇█";
                const cell = Math.max(8, Math.round(bw));
                const rows = Math.floor(H / cell);
                ctx.font = cell + "px '" + Theme.font + "', 'JetBrainsMono Nerd Font Mono', monospace";
                ctx.textBaseline = "bottom";
                for (let i = 0; i < n; i++) {
                    const x = i * (bw + gap);
                    const v = root.shown[i] * rows;
                    const full = Math.floor(v);
                    for (let r = 0; r < full && r < rows; r++) {
                        ctx.fillStyle = r / rows > 0.75 ? hot : r / rows > 0.3 ? accent : low;
                        ctx.fillText("█", x, H - r * cell);
                    }
                    const part = v - full;
                    if (part > 0.05 && full < rows) {
                        ctx.fillStyle = accent;
                        ctx.fillText(glyphs[Math.min(7, Math.floor(part * 8))], x, H - full * cell);
                    }
                    if (!root.compact && root.peaks[i] > 0.04) {
                        ctx.fillStyle = hot;
                        ctx.fillText("▔", x, H - Math.floor(root.peaks[i] * rows) * cell - 2);
                    }
                }
                return;
            }

            // bars / mirror: LED segments.
            const seg = root.compact ? 2 : 5, sgap = root.compact ? 1 : 2;
            const mirror = root.mode === "mirror";
            const base = mirror ? H / 2 : H;
            const span = mirror ? H / 2 : H;
            const total = Math.floor(span / (seg + sgap));
            for (let i = 0; i < n; i++) {
                const x = i * (bw + gap);
                const lit = Math.round(root.shown[i] * total);
                for (let k = 0; k < lit; k++) {
                    const f = k / total;
                    ctx.fillStyle = f > 0.8 ? hot : f > 0.35 ? accent : low;
                    const y = base - (k + 1) * (seg + sgap) + sgap;
                    ctx.globalAlpha = 1;
                    ctx.fillRect(x, y, bw, seg);
                    if (mirror) {
                        ctx.globalAlpha = 0.35;
                        ctx.fillRect(x, base + k * (seg + sgap) + sgap, bw, seg);
                    }
                }
                if (!root.compact && root.peaks[i] > 0.04) {
                    const pk = Math.round(root.peaks[i] * total);
                    ctx.globalAlpha = 1;
                    ctx.fillStyle = hot;
                    ctx.fillRect(x, base - pk * (seg + sgap) - 2, bw, 2);
                }
            }
            ctx.globalAlpha = 1;
        }
    }
}
