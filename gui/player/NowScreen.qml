// NowScreen.qml — tela TOCANDO (MÚSICA): capa, faixa, barra de progresso, visualizador e controles.
import QtQuick
import Quickshell.Io
import qs
import qs.components
import qs.player

// LW // NOW PLAYING: visualizer, cover, title, ASCII seek bar, controls, up next.
// The visualizer mode is remembered in ~/.local/state/rice-minimal/gui/music.json.
Item {
    id: root

    property Item keyTarget: null
    property string title: ""
    readonly property var modes: ["bars", "ascii", "mirror", "wave"]
    property string mode: "bars"
    // Filled in phase 4 (cava); empty means the idle motion.
    property var levels: []
    property string levelSource: "idle"
    readonly property var hints: [["v", "visual"], ["m", "mute"], ["s", "shuf"], ["r", "rep"]]

    // Troca o estilo do visualizador.
    function setMode(next) {
        mode = next;
        prefs.setText(JSON.stringify({ visualizer: next }) + "\n");
    }
    // Teclas: espaço play/pause, setas avançam/volume, v visualizador.
    function handleKey(event) {
        if (event.text === "v") { setMode(modes[(modes.indexOf(mode) + 1) % modes.length]); return true; }
        return false;
    }

    FileView {
        id: prefs
        path: Theme.guiStatePath + "/music.json"
        printErrors: false
        atomicWrites: true
        onLoaded: {
            try { const m = JSON.parse(text()).visualizer; if (root.modes.indexOf(m) >= 0) root.mode = m; } catch (error) {}
        }
    }

    // Next tracks in play order; shuffle order is cliamp's secret.
    readonly property var upNext: {
        const list = Music.playlist, at = Music.currentIndex;
        if (Music.shuffle || at < 0 || !list.length) return [];
        const out = [];
        for (let k = 1; k <= 3; k++) {
            let i = at + k;
            if (i >= list.length) {
                if (Music.repeat !== "all") break;
                i = i % list.length;
                if (i === at) break;
            }
            out.push(list[i]);
        }
        return out;
    }
    onUpNextChanged: { for (const t of upNext) Music.requestInfo(t.path); }

    readonly property var info: Music.track ? Music.infos[Music.track.path] || null : null
    readonly property string kind: Music.track ? Music.sourceOf(Music.track.path) : "local"
    // Linha com formato do arquivo (codec, kbps, kHz).
    function formatLine() {
        if (Music.live) return "stream ao vivo" + (Music.track ? " · " + String(Music.track.path).replace(/^https?:\/\//, "").split("/")[0] : "");
        if (!info) return "";
        return [info.codec, info.rate ? (info.rate / 1000).toFixed(1).replace(/\.0$/, "") + " kHz" : "",
                info.bitrate ? Math.round(info.bitrate / 1000) + " kbps" : "", info.channels === 1 ? "mono" : info.channels === 2 ? "stereo" : ""]
            .filter(x => x).join(" · ");
    }
    // Segundos → "m:ss".
    function clock(seconds) {
        if (!isFinite(seconds) || seconds < 0) return "LIVE";
        const s = Math.floor(seconds);
        return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
    }

    // ================= VISUALIZER =================
    Rectangle {
        id: spec
        width: parent.width
        height: 300
        color: Theme.base
        border.width: 1
        border.color: Theme.line
        clip: true
        // A warm glow rising from the floor.
        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            gradient: Gradient {
                GradientStop { position: 0.0; color: Theme.base }
                GradientStop { position: 1.0; color: Theme.mix(Theme.bg, Theme.accent, 0.07) }
            }
        }
        Visualizer {
            anchors.fill: parent
            anchors.margins: 14
            anchors.topMargin: 26
            mode: root.mode
            levels: root.levels
            idle: !Music.playing || root.levels.length === 0
        }
        RiceText {
            anchors.right: parent.right
            anchors.rightMargin: 10
            y: 7
            text: root.mode + " · " + (Music.playing ? root.levelSource : "paused")
            color: Theme.faint
            font.pixelSize: 10
        }
    }

    // ================= TRACK =================
    Item {
        id: np
        anchors.top: spec.bottom
        anchors.topMargin: 18
        width: parent.width
        height: 110

        // Cover: the track's art when cliamp exposes one, otherwise a mirrored 11×11
        // pattern from the title+artist hash, in the wallpaper's colors.
        TrackCover {
            id: cover
            width: 110
            height: 110
            label: root.kind.toUpperCase()
        }

        Column {
            anchors.left: cover.right
            anchors.leftMargin: 20
            anchors.right: parent.right
            anchors.verticalCenter: cover.verticalCenter
            spacing: 2

            // Marquee only when the title does not fit.
            Item {
                id: titleBox
                width: parent.width
                height: titleText.implicitHeight
                clip: true
                readonly property real overflow: Math.max(0, titleText.implicitWidth - width)
                RiceText {
                    id: titleText
                    text: Music.title || "—"
                    color: Theme.fg
                    font.pixelSize: 20
                    font.weight: Font.ExtraBold
                    elide: Theme.motion ? Text.ElideNone : Text.ElideRight
                    width: Theme.motion ? implicitWidth : titleBox.width
                }
                SequentialAnimation {
                    running: Theme.motion && titleBox.overflow > 0
                    loops: Animation.Infinite
                    onRunningChanged: if (!running) titleText.x = 0
                    PauseAnimation { duration: 2000 }
                    NumberAnimation { target: titleText; property: "x"; to: -titleBox.overflow; duration: titleBox.overflow * 28; easing.type: Easing.InOutSine }
                    PauseAnimation { duration: 1600 }
                    NumberAnimation { target: titleText; property: "x"; to: 0; duration: titleBox.overflow * 14; easing.type: Easing.InOutSine }
                }
            }
            RiceText {
                width: parent.width
                elide: Text.ElideRight
                text: [Music.artist, Music.album].filter(x => x).join(" · ") || (root.kind === "radio" ? "rádio" : "artista desconhecido")
                color: Theme.accent
            }
            RiceText {
                width: parent.width
                elide: Text.ElideRight
                text: root.formatLine()
                color: Theme.faint
                font.pixelSize: Theme.small
                topPadding: 2
            }
        }
    }

    // ================= SEEK =================
    Item {
        id: seek
        anchors.top: np.bottom
        anchors.topMargin: 18
        width: parent.width
        height: barText.implicitHeight

        TextMetrics { id: cell; font.family: Theme.font; font.pixelSize: Theme.fontSize; text: "━" }
        RiceText { id: cur; text: root.clock(Music.position); color: Theme.dim; width: 52 }
        RiceText { id: dur; anchors.right: parent.right; text: Music.live ? "LIVE" : root.clock(Music.duration); color: Theme.dim; horizontalAlignment: Text.AlignRight; width: 52 }
        Item {
            id: bar
            anchors.left: cur.right
            anchors.right: dur.left
            anchors.leftMargin: 6
            anchors.rightMargin: 6
            height: parent.height
            clip: true
            readonly property int cells: Math.max(10, Math.floor(width / Math.max(1, cell.advanceWidth)))
            readonly property real fraction: Music.duration > 0 ? Math.min(1, Music.position / Music.duration) : 0
            readonly property int head: Math.round(fraction * (cells - 1))
            RiceText {
                id: barText
                textFormat: Text.StyledText
                text: Music.live
                    ? "<font color='" + Theme.blue + "'>" + "━".repeat(bar.cells) + "</font>"
                    : "<font color='" + Theme.accent + "'>" + "━".repeat(bar.head) + "</font>"
                      + "<font color='" + Theme.hot + "'>●</font>"
                      + "<font color='" + Theme.faint + "'>" + "─".repeat(Math.max(0, bar.cells - bar.head - 1)) + "</font>"
            }
            MouseArea {
                id: seekMouse
                anchors.fill: parent
                hoverEnabled: true
                enabled: Music.seekable && Music.duration > 0
                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: mouse => { Music.seekTo(mouse.x / width * Music.duration); root.keyTarget.forceActiveFocus(); }
            }
        }
        // Time under the pointer.
        Rectangle {
            visible: seekMouse.containsMouse && seekMouse.enabled
            x: bar.x + Math.min(bar.width - width, Math.max(0, seekMouse.mouseX - width / 2))
            y: -20
            width: hoverTime.implicitWidth + 8
            height: hoverTime.implicitHeight + 2
            color: Theme.raise
            border.width: 1
            border.color: Theme.line2
            RiceText { id: hoverTime; anchors.centerIn: parent; font.pixelSize: 10; text: root.clock(seekMouse.mouseX / bar.width * Music.duration) }
        }
    }

    // ================= CONTROLS =================
    component Ctrl: Rectangle {
        id: ctrl
        property string label: ""
        property bool on: false
        property bool big: false
        property bool enabledState: true
        signal clicked()
        signal wheel(int delta)
        width: ctrlText.implicitWidth + (big ? 44 : 24)
        height: ctrlText.implicitHeight + 8
        color: big && ctrlMouse.containsMouse ? Theme.accent : "transparent"
        border.width: 1
        border.color: !enabledState ? Theme.line : big || on ? Theme.accent : ctrlMouse.containsMouse ? Theme.fg : Theme.line2
        transform: Translate { y: ctrlMouse.containsMouse && !ctrl.big && Theme.motion ? -1 : 0 }
        Behavior on border.color { ColorAnimation { duration: Theme.tFast } }
        Behavior on color { ColorAnimation { duration: Theme.tFast } }
        RiceText {
            id: ctrlText
            anchors.centerIn: parent
            text: ctrl.label
            font.bold: ctrl.big
            color: !ctrl.enabledState ? Theme.faint : ctrl.big ? (ctrlMouse.containsMouse ? Theme.bg : Theme.accent)
                 : ctrl.on ? Theme.accent : ctrlMouse.containsMouse ? Theme.fg : Theme.dim
        }
        MouseArea {
            id: ctrlMouse
            anchors.fill: parent
            hoverEnabled: true
            enabled: ctrl.enabledState
            cursorShape: Qt.PointingHandCursor
            onClicked: { ctrl.clicked(); root.keyTarget.forceActiveFocus(); }
            onWheel: wheel => ctrl.wheel(wheel.angleDelta.y)
        }
    }

    Item {
        id: controls
        anchors.top: seek.bottom
        anchors.topMargin: 14
        width: parent.width
        height: playButton.height
        Row {
            spacing: 10
            Ctrl { label: "⇄ SHUF"; on: Music.shuffle; onClicked: Music.setShuffle(!Music.shuffle) }
            Ctrl { label: "|◀"; onClicked: Music.previous() }
            Ctrl { id: playButton; big: true; label: Music.playing ? "❚❚ PAUSE" : "▶ PLAY"; onClicked: Music.toggle() }
            Ctrl { label: "▶|"; onClicked: Music.next() }
            Ctrl { label: "↻ " + Music.repeat.toUpperCase(); on: Music.repeat !== "off"; onClicked: Music.cycleRepeat() }
        }
        Ctrl {
            anchors.right: parent.right
            label: Music.muted ? "♪ MUTE" : "♪ " + Music.volumePercent + "%"
            on: Music.muted
            onClicked: Music.toggleMute()
            onWheel: delta => Music.volumeStep(delta > 0 ? 5 : -5)
        }
    }

    // ================= UP NEXT =================
    Column {
        anchors.top: controls.bottom
        anchors.topMargin: 18
        width: parent.width
        spacing: 2
        RiceText { text: "UP NEXT"; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5; bottomPadding: 5 }
        RiceText {
            visible: Music.shuffle || Music.repeat === "one" || root.upNext.length === 0
            text: Music.shuffle ? "⇄ shuffle: a próxima é sorteada pelo cliamp"
                : Music.repeat === "one" ? "↻ repete esta faixa"
                : "fim da fila"
            color: Theme.dim
        }
        Repeater {
            model: Music.repeat === "one" ? [] : root.upNext
            Item {
                id: row
                required property var modelData
                width: parent.width
                height: rowTitle.implicitHeight + 4
                readonly property var meta: Music.infos[modelData.path] || null
                RiceText { y: 2; text: modelData.index + 1; color: Theme.faint; width: 24 }
                RiceText {
                    id: rowTitle
                    x: 34
                    y: 2
                    width: parent.width - 34 - 60
                    elide: Text.ElideRight
                    text: (modelData.title || Music.fileName(modelData.path)) + (modelData.artist ? "  ·  " + modelData.artist : "")
                    color: rowMouse.containsMouse ? Theme.fg : Theme.dim
                }
                RiceText {
                    anchors.right: parent.right
                    y: 2
                    text: Music.sourceOf(modelData.path) !== "local" ? "LIVE" : row.meta ? root.clock(row.meta.duration) : ""
                    color: Theme.faint
                }
                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: { Music.playIndex(row.modelData.index); root.keyTarget.forceActiveFocus(); }
                }
            }
        }
    }
}
