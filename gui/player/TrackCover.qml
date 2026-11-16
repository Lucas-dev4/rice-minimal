// TrackCover.qml — capa da faixa (ou um quadro com as iniciais quando não há capa).
import QtQuick
import qs
import qs.components

// The current track's cover: the art cliamp exposes over MPRIS (mpris:artUrl), otherwise
// a mirrored 11×11 pattern from the title+artist hash in the wallpaper's colours.
// Used by LW // MUSIC (NOW PLAYING) and the LW window (MUSIC).
Rectangle {
    id: root

    property string label: ""          // a strip at the bottom (LOCAL, RADIO…), empty = none

    color: Theme.bg
    border.width: 1
    border.color: Theme.line2
    clip: true

    Canvas {
        id: pattern
        anchors.fill: parent
        anchors.margins: 1
        property string seed: Music.title + "|" + Music.artist
        onSeedChanged: requestPaint()
        onWidthChanged: requestPaint()
        Connections { target: Theme; function onAccentChanged() { pattern.requestPaint(); } }
        onPaint: {
            const ctx = getContext("2d"), W = width, N = 11, s = W / N;
            ctx.reset();
            ctx.fillStyle = String(Theme.bg);
            ctx.fillRect(0, 0, W, height);
            if (!Music.track) return;
            // FNV-1a hash, then a small xorshift generator.
            let h = 2166136261;
            for (const c of seed) h = Math.imul(h ^ c.charCodeAt(0), 16777619) >>> 0;
            let x32 = h || 1;
            const rnd = () => { x32 ^= x32 << 13; x32 >>>= 0; x32 ^= x32 >>> 17; x32 ^= x32 << 5; x32 >>>= 0; return x32 / 4294967296; };
            const pal = [Theme.accent, Theme.hot, Theme.mix(Theme.bg, Theme.accent, 0.5), Theme.line2, Theme.ok, Theme.blue].map(String);
            const main = Math.floor(rnd() * pal.length);
            for (let y = 0; y < N; y++) {
                for (let x = 0; x < Math.ceil(N / 2); x++) {
                    if (rnd() < 0.48) {
                        ctx.fillStyle = rnd() < 0.7 ? pal[main] : pal[Math.floor(rnd() * pal.length)];
                        ctx.globalAlpha = 0.35 + rnd() * 0.65;
                        ctx.fillRect(x * s + 1, y * s + 1, s - 2, s - 2);
                        ctx.fillRect((N - 1 - x) * s + 1, y * s + 1, s - 2, s - 2);
                    }
                }
            }
            ctx.globalAlpha = 1;
        }
    }
    Image {
        anchors.fill: parent
        anchors.margins: 1
        source: Music.artUrl
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        visible: status === Image.Ready
    }
    Rectangle {
        visible: root.label !== ""
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 1
        x: 1
        width: parent.width - 2
        height: 20
        color: Qt.alpha(Theme.bg, 0.75)
        RiceText { x: 6; anchors.verticalCenter: parent.verticalCenter; text: root.label; font.pixelSize: 10; font.bold: true }
    }
}
