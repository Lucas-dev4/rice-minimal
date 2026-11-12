import QtQuick
import qs
import qs.components
import qs.deck
import qs.player

// LW // music: what cliamp plays — the real spectrum (cava), cover, title, seek bar,
// controls, system volume — and its queue. Same Music singleton as LW // MUSIC.
Item {
    id: root

    property Item keyTarget: null
    readonly property var hints: []

    function clock(seconds) {
        if (!isFinite(seconds) || seconds < 0) return "LIVE";
        const s = Math.floor(seconds);
        return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
    }
    function handleKey(event) {
        if (!Music.online) {
            if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { Music.startCliamp(); return true; }
            return false;
        }
        const t = event.text;
        if (t === "n") { Music.next(); return true; }
        if (t === "p") { Music.previous(); return true; }
        if (event.key === Qt.Key_Left) { Music.seekBy(-5); return true; }
        if (event.key === Qt.Key_Right) { Music.seekBy(5); return true; }
        if (t === "+" || t === "=") { Music.volumeStep(5); return true; }
        if (t === "-") { Music.volumeStep(-5); return true; }
        if (t === "m") { Music.toggleMute(); return true; }
        if (t === "s") { Music.setShuffle(!Music.shuffle); return true; }
        if (t === "r") { Music.cycleRepeat(); return true; }
        return false;
    }

    Item {
        id: head
        width: parent.width
        height: musicTitle.implicitHeight
        RiceText { id: musicTitle; textFormat: Text.StyledText; text: "music<font color='" + Theme.accent + "'>.</font>"; font.pixelSize: 26; font.weight: Font.ExtraBold }
        RiceText {
            anchors.right: parent.right
            anchors.baseline: musicTitle.baseline
            text: "cliamp · " + (Music.online ? Music.status : "offline")
            color: Music.playing ? Theme.ok : Theme.dim
            font.pixelSize: Theme.small
        }
    }

    // ================= NOW PLAYING =================
    Glass {
        id: np
        k: true
        anchors.top: head.bottom
        anchors.topMargin: 12
        width: parent.width
        height: 400

        Visualizer {
            id: spec
            x: 18
            y: 18
            width: parent.width - 36
            height: 140
            mode: "bars"
            levels: Spectrum.levels
            idle: !Music.playing || Spectrum.levels.length === 0
            visible: Music.online
        }

        Item {
            id: track
            visible: Music.online
            x: 18
            anchors.top: spec.bottom
            anchors.topMargin: 16
            width: parent.width - 36
            height: 72
            TrackCover { id: cover; width: 72; height: 72 }
            Column {
                anchors.left: cover.right
                anchors.leftMargin: 14
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                RiceText { width: parent.width; elide: Text.ElideRight; text: Music.title || "—"; font.pixelSize: 20; font.weight: Font.ExtraBold }
                RiceText { width: parent.width; elide: Text.ElideRight; text: [Music.artist, Music.album].filter(x => x).join(" · "); color: Theme.accent }
                RiceText {
                    readonly property var info: Music.track ? Music.infos[Music.track.path] || null : null
                    text: Music.live ? "stream ao vivo" : info ? [info.codec, info.rate ? (info.rate / 1000).toFixed(1).replace(/\.0$/, "") + " kHz" : "", info.bitrate ? Math.round(info.bitrate / 1000) + " kbps" : ""].filter(x => x).join(" · ") : ""
                    color: Theme.dim
                    font.pixelSize: Theme.small
                }
            }
        }

        // Seek: a thin track, the accent fill and a glowing head; click to jump.
        Item {
            id: seek
            visible: Music.online
            x: 18
            anchors.top: track.bottom
            anchors.topMargin: 16
            width: parent.width - 36
            height: 16
            RiceText { id: cur; anchors.verticalCenter: parent.verticalCenter; text: root.clock(Music.position); color: Theme.dim; font.pixelSize: Theme.small; width: 44 }
            RiceText { id: dur; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; horizontalAlignment: Text.AlignRight; width: 44; text: Music.live ? "LIVE" : root.clock(Music.duration); color: Theme.dim; font.pixelSize: Theme.small }
            Item {
                id: bar
                anchors.left: cur.right
                anchors.right: dur.left
                anchors.margins: 8
                anchors.verticalCenter: parent.verticalCenter
                height: 12
                readonly property real fraction: Music.duration > 0 ? Math.min(1, Music.position / Music.duration) : (Music.live ? 1 : 0)
                Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 4; color: Qt.rgba(1, 1, 1, 0.1) }
                Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width * bar.fraction; height: 4; color: Music.live ? Theme.blue : Theme.accent }
                Rectangle {
                    visible: !Music.live
                    x: parent.width * bar.fraction - 6
                    anchors.verticalCenter: parent.verticalCenter
                    width: 12
                    height: 12
                    color: Theme.hot
                    Rectangle { anchors.centerIn: parent; width: 22; height: 22; color: "transparent"; border.width: 5; border.color: Qt.alpha(Theme.accent, 0.25) }
                }
                MouseArea {
                    anchors.fill: parent
                    anchors.margins: -6
                    enabled: Music.seekable && Music.duration > 0
                    cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: mouse => { Music.seekTo(Math.max(0, Math.min(1, (mouse.x - 6) / bar.width)) * Music.duration); root.keyTarget.forceActiveFocus(); }
                }
            }
        }

        // Controls: ⇄ |◀ ▶ ▶| ↻ — active ones in the accent.
        Row {
            id: controls
            visible: Music.online
            anchors.top: seek.bottom
            anchors.topMargin: 12
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 14
            component Ctl: RiceText {
                id: ctl
                property bool on: false
                signal clicked()
                anchors.verticalCenter: parent.verticalCenter
                padding: 8
                font.pixelSize: 15
                color: on ? Theme.accent : ctlMouse.containsMouse ? Theme.fg : Theme.dim
                MouseArea { id: ctlMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: { ctl.clicked(); root.keyTarget.forceActiveFocus(); } }
            }
            Ctl { text: "⇄"; on: Music.shuffle; onClicked: Music.setShuffle(!Music.shuffle) }
            Ctl { text: "|◀"; onClicked: Music.previous() }
            Rectangle {
                width: 56
                height: 56
                color: bigMouse.containsMouse ? Theme.accent : "transparent"
                border.width: 1
                border.color: Theme.accent
                Behavior on color { ColorAnimation { duration: 200 } }
                RiceText { anchors.centerIn: parent; text: Music.playing ? "❚❚" : "▶"; font.pixelSize: 20; color: bigMouse.containsMouse ? Theme.bg : Theme.accent }
                MouseArea { id: bigMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: { Music.toggle(); root.keyTarget.forceActiveFocus(); } }
            }
            Ctl { text: "▶|"; onClicked: Music.next() }
            Ctl { text: Music.repeat === "one" ? "↻1" : "↻"; on: Music.repeat !== "off"; onClicked: Music.cycleRepeat() }
        }

        // VOL: the system volume, the same as Super+= / Super+-.
        Item {
            visible: Music.online
            x: 18
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 14
            width: parent.width - 36
            height: 14
            RiceText { id: volLabel; anchors.verticalCenter: parent.verticalCenter; text: "VOL"; color: Theme.dim; font.pixelSize: Theme.small }
            RiceText { id: volValue; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; text: Music.muted ? "MUTE" : Music.volumePercent + "%"; color: Theme.dim; font.pixelSize: Theme.small; width: 44; horizontalAlignment: Text.AlignRight }
            Item {
                id: vol
                anchors.left: volLabel.right
                anchors.right: volValue.left
                anchors.margins: 12
                anchors.verticalCenter: parent.verticalCenter
                height: 14
                readonly property real fraction: Music.muted ? 0 : Math.min(1, Music.volumePercent / 100)
                Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 2; color: Qt.rgba(1, 1, 1, 0.12) }
                Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width * vol.fraction; height: 2; color: Theme.accent }
                Rectangle { x: parent.width * vol.fraction - 4; anchors.verticalCenter: parent.verticalCenter; width: 8; height: 12; color: Theme.accent }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    function pick(x) { Music.setVolumePercent(Math.round(Math.max(0, Math.min(1, x / vol.width)) * 20) * 5); }
                    onPressed: mouse => pick(mouse.x)
                    onPositionChanged: mouse => { if (pressed) pick(mouse.x); }
                    onReleased: root.keyTarget.forceActiveFocus()
                    onWheel: wheel => Music.volumeStep(wheel.angleDelta.y > 0 ? 5 : -5)
                }
            }
        }

        // cliamp off: say so, START brings it back where it was.
        Column {
            visible: !Music.online
            anchors.centerIn: parent
            spacing: 14
            RiceText { anchors.horizontalCenter: parent.horizontalCenter; text: Music.connecting ? "[ .. ] conectando ao cliamp" : "[ -- ] cliamp offline"; color: Music.connecting ? Theme.accent : Theme.dim; font.pixelSize: 16 }
            AccentButton { anchors.horizontalCenter: parent.horizontalCenter; visible: !Music.connecting; label: "START ⏎"; onClicked: Music.startCliamp() }
            RiceText { anchors.horizontalCenter: parent.horizontalCenter; visible: !Music.connecting; text: "volta pausado onde parou, ou abre ~/Músicas"; color: Theme.dim; font.pixelSize: Theme.small }
        }
    }

    // ================= QUEUE =================
    Glass {
        id: queue
        k: true
        anchors.top: np.bottom
        anchors.topMargin: 12
        anchors.bottom: parent.bottom
        width: parent.width
        RiceText { x: 16; y: 12; text: "FILA"; color: Theme.dim; font.pixelSize: 10; font.letterSpacing: 2 }
        RiceText { anchors.right: parent.right; anchors.rightMargin: 16; y: 12; text: Music.playlist.length + " faixas" + (Music.shuffle ? " · shuffle" : ""); color: Theme.dim; font.pixelSize: Theme.small }
        ListView {
            id: list
            anchors.fill: parent
            anchors.topMargin: 34
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            anchors.bottomMargin: 8
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: Music.online ? Music.playlist : []
            currentIndex: Music.currentIndex
            onCurrentIndexChanged: if (currentIndex >= 0) positionViewAtIndex(currentIndex, ListView.Contain)
            delegate: Item {
                id: row
                required property var modelData
                required property int index
                readonly property bool playing: index === Music.currentIndex
                width: list.width
                height: 40
                Rectangle { anchors.fill: parent; color: row.playing ? Theme.accentA : rowMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.03) : "transparent" }
                Rectangle { visible: row.index > 0; width: parent.width; height: 1; color: Qt.rgba(1, 1, 1, 0.06) }
                Item {
                    id: num
                    width: 28
                    height: parent.height
                    // Three bars on the playing track, the number elsewhere.
                    Row {
                        visible: row.playing
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 2
                        height: 12
                        Repeater {
                            model: 3
                            Rectangle {
                                id: eqBar
                                required property int index
                                width: 3
                                height: 3
                                anchors.bottom: parent.bottom
                                color: Theme.accent
                                SequentialAnimation on height {
                                    running: Music.playing && row.playing
                                    loops: Animation.Infinite
                                    PauseAnimation { duration: eqBar.index * 180 }
                                    NumberAnimation { to: 12; duration: 400; easing.type: Easing.InOutSine }
                                    NumberAnimation { to: 3; duration: 400; easing.type: Easing.InOutSine }
                                }
                            }
                        }
                    }
                    RiceText { visible: !row.playing; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; text: row.index + 1; color: Theme.dim }
                }
                Column {
                    anchors.left: num.right
                    anchors.leftMargin: 10
                    anchors.right: rowDur.left
                    anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    RiceText { width: parent.width; elide: Text.ElideRight; text: row.modelData.title || Music.fileName(row.modelData.path); color: row.playing ? Theme.accent : Theme.fg; font.weight: row.playing ? Font.DemiBold : Font.Normal }
                    RiceText { width: parent.width; elide: Text.ElideRight; text: row.modelData.artist || ""; color: Theme.dim; font.pixelSize: 11; visible: text !== "" }
                }
                RiceText {
                    id: rowDur
                    anchors.right: parent.right
                    anchors.rightMargin: 6
                    anchors.verticalCenter: parent.verticalCenter
                    readonly property var info: Music.infos[row.modelData.path] || null
                    text: Music.sourceOf(row.modelData.path) !== "local" ? "LIVE" : info ? root.clock(info.duration) : ""
                    color: Theme.dim
                    font.pixelSize: Theme.small
                }
                MouseArea { id: rowMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: { Music.playIndex(row.index); root.keyTarget.forceActiveFocus(); } }
                Component.onCompleted: Music.requestInfo(modelData.path)
            }
            RiceText { anchors.centerIn: parent; visible: list.count === 0; text: Music.online ? "fila vazia" : "—"; color: Theme.dim }
        }
    }
}
