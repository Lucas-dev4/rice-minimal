import QtQuick
import qs

// A 3:4 game cover: the real art when the source has it (decoded small: sourceSize),
// otherwise one generated from the title's hash — gradient, diagonal stripes, initials.
Rectangle {
    id: root

    property var game: null
    property bool showTitle: true
    readonly property string title: game ? game.title : ""
    readonly property bool hasArt: art.status === Image.Ready

    implicitWidth: 140
    implicitHeight: Math.round(implicitWidth * 4 / 3)
    color: Theme.raise
    border.width: 1
    border.color: Theme.line2
    clip: true

    // FNV-1a, as in the prototype.
    function hash(s) {
        let h = 2166136261;
        for (const c of String(s)) h = Math.imul(h ^ c.charCodeAt(0), 16777619) >>> 0;
        return h;
    }
    function initials(t) {
        return String(t).split(/\s+/).filter(w => /^[A-Za-zÀ-ú0-9]/.test(w)).slice(0, 2).map(w => w[0].toUpperCase()).join("");
    }

    Canvas {
        id: generated
        anchors.fill: parent
        anchors.margins: 1
        visible: !root.hasArt
        property string seed: root.title
        onSeedChanged: requestPaint()
        onWidthChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d"), W = width, H = height, r = root.hash(seed);
            const h = r % 360, h2 = (h + 30 + (r >> 8) % 80) % 360, a = ((r >> 3) % 360) * Math.PI / 180;
            ctx.reset();
            // Base gradient along a hashed angle.
            const dx = Math.cos(a) * W, dy = Math.sin(a) * H;
            const g = ctx.createLinearGradient(W / 2 - dx / 2, H / 2 - dy / 2, W / 2 + dx / 2, H / 2 + dy / 2);
            g.addColorStop(0, String(Qt.hsla(h / 360, 0.38, 0.24, 1)));
            g.addColorStop(0.7, String(Qt.hsla(h2 / 360, 0.45, 0.12, 1)));
            g.addColorStop(1, String(Qt.hsla(h / 360, 0.20, 0.06, 1)));
            ctx.fillStyle = g;
            ctx.fillRect(0, 0, W, H);
            // Thin stripes at another hashed angle.
            ctx.save();
            ctx.translate(W / 2, H / 2);
            ctx.rotate(((r >> 4) % 360) * Math.PI / 180);
            ctx.fillStyle = "rgba(255,255,255,0.05)";
            const span = Math.hypot(W, H);
            for (let x = -span; x < span; x += 9) ctx.fillRect(x, -span, 2, span * 2);
            ctx.restore();
        }
    }
    Image {
        id: art
        anchors.fill: parent
        anchors.margins: 1
        source: root.game && root.game.cover ? "file://" + root.game.cover : ""
        sourceSize.width: 320
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: true
    }
    Text {
        visible: !root.hasArt
        anchors.right: parent.right
        anchors.rightMargin: 6
        y: 3
        text: root.initials(root.title)
        color: Qt.rgba(1, 1, 1, 0.2)
        font.family: Theme.font
        font.pixelSize: Math.max(14, Math.round(root.width / 6.4))
        font.weight: Font.ExtraBold
    }
    Text {
        visible: root.showTitle && !root.hasArt
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 7
        text: root.title
        color: "#f2ece4"
        wrapMode: Text.Wrap
        maximumLineCount: 3
        elide: Text.ElideRight
        lineHeight: 1.1
        font.family: Theme.font
        font.pixelSize: Math.max(10, Math.round(root.width / 11.5))
        font.weight: Font.ExtraBold
        style: Text.Raised
        styleColor: Qt.rgba(0, 0, 0, 0.6)
    }
}
