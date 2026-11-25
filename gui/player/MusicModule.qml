import QtQuick
import Quickshell.Io
import qs
import qs.components

// MusicModule.qml — o gancho de MÚSICA: faixa na seção fechada, fontes/mini player/VOL na barra lateral,
// cabeçalho das telas, START quando o cliamp está desligado, soltar arquivos na janela, formato do áudio
// no rodapé, teclas do player e a sessão ao fechar. Quem fala com o cliamp é só o Music.qml.
LwModule {
    id: root

    // A tela aberta de MÚSICA (null nas outras seções).
    property Item screenItem: null

    summary: Music.online && Music.track
        ? "<font color='" + (Music.playing ? Theme.ok : Theme.yel) + "'>" + (Music.playing ? "▶" : "❚❚") + "</font> " + Music.title : ""
    ready: Music.online
    context: output || "—"
    idleText: Music.online ? "" : "[ -- ] cliamp offline"
    hints: [["spc", "play"], ["n/p", "faixa"], ["←→", "seek"], ["+-", "vol"], ["alt 1-3", "seção"]]
    bootStep: ({ label: Music.online ? "connected to cliamp" : "connecting to cliamp", done: !Music.connecting })

    // Entrar em MÚSICA liga o cliamp se ele estiver desligado.
    function entered() { Music.wanted = true; }
    // Fechar em MÚSICA desliga o cliamp (a sessão fica salva e volta pausada), e o que o LW ligou
    // desliga em qualquer seção; um que já estava ligado só tem a sessão salva e continua tocando.
    function closing(active) { Music.closeSession(active); }
    // O espectro vem do Spectrum (cava no áudio do cliamp); só as telas que pedem recebem.
    function screenLoaded(item) {
        screenItem = item;
        if (item.levels === undefined) return;
        item.levels = Qt.binding(() => Spectrum.levels);
        item.levelSource = Qt.binding(() => Spectrum.source);
    }

    // ---- teclas
    // Com o cliamp desligado, Enter é o START.
    function overlayKey(event) {
        if (!active || Music.online || (event.key !== Qt.Key_Return && event.key !== Qt.Key_Enter)) return false;
        Music.startCliamp();
        return true;
    }
    function key(event) {
        const t = event.text;
        // Em MÚSICA as setas são do player e das telas: ↑↓ não trocam de tela.
        if (event.key === Qt.Key_Up || event.key === Qt.Key_Down) return true;
        if (t === "R") { openScreen(3); return true; }
        if (!Music.online) return false;
        // o abre arquivos a partir de qualquer tela: eles vão para a fila.
        if (t === "o") { openScreen(1); Qt.callLater(() => { if (screenItem && screenItem.openFiles) screenItem.openFiles(); }); }
        else if (t === "n") Music.next();
        else if (t === "p") Music.previous();
        else if (event.key === Qt.Key_Left) Music.seekBy(-5);
        else if (event.key === Qt.Key_Right) Music.seekBy(5);
        // O ABNT2 manda "=" na tecla + sem Shift.
        else if (t === "+" || t === "=") Music.volumeStep(5);
        else if (t === "-") Music.volumeStep(-5);
        else if (t === "m") Music.toggleMute();
        else if (t === "s") Music.setShuffle(!Music.shuffle);
        else if (t === "r") Music.cycleRepeat();
        else return false;
        return true;
    }
    // Espaço toca/pausa em qualquer seção.
    function backgroundKey(event) {
        if (event.key !== Qt.Key_Space || !Music.online) return false;
        Music.toggle();
        return true;
    }

    // ---- IPC dos testes (scripts/music-check.sh)
    function state() {
        return {
            online: Music.online, status: Music.status, title: Music.title, artist: Music.artist,
            album: Music.album, position: Math.round(Music.position * 10) / 10, duration: Music.duration,
            live: Music.live, volume: Music.volumePercent, volumeDb: Music.volumeDb, muted: Music.muted,
            shuffle: Music.shuffle, repeat: Music.repeat, index: Music.currentIndex,
            playlist: Music.playlist.map(t => t.title || Music.fileName(t.path)),
            eq: Music.eqBands, error: Music.lastError
        };
    }
    function act(op, arg) {
        const n = parseFloat(arg);
        switch (op) {
        case "toggle": Music.toggle(); break;
        case "next": Music.next(); break;
        case "prev": Music.previous(); break;
        case "seek": Music.seekTo(n); break;
        case "seekby": Music.seekBy(n); break;
        case "volume": Music.setVolumePercent(n); break;
        case "mute": Music.toggleMute(); break;
        case "shuffle": Music.setShuffle(!Music.shuffle); break;
        case "repeat": Music.cycleRepeat(); break;
        case "play": Music.playIndex(n); break;
        case "move": Music.moveTrack(parseInt(arg.split(",")[0]), parseInt(arg.split(",")[1])); break;
        case "remove": Music.removeTrack(n); break;
        case "add": Music.addPath(arg); break;
        case "band": Music.setBand(parseInt(arg.split(",")[0]), parseFloat(arg.split(",")[1])); break;
        case "preset": Music.setPreset(arg); break;
        case "start": Music.startCliamp(); break;
        case "stop": Music.closeSession(true); break;
        case "bad": Music.call("queue.play", { index: 999 }); break;
        default: return false;
        }
        return true;
    }

    // ---- mensagens curtas no rodapé: erro do cliamp e troca de faixa
    property string lastPath: ""
    Connections {
        target: Music
        function onFailed(op, message) { Status.say("[ !! ] " + op + ": " + message, Theme.red); }
        function onChanged() {
            const path = Music.track ? Music.track.path : "";
            if (path && path !== root.lastPath && root.lastPath !== "")
                Status.say("[ ▶ ] " + Music.title + (Music.artist ? " — " + Music.artist : ""), Theme.ok);
            root.lastPath = path || root.lastPath;
        }
    }

    // ---- formato do áudio do cliamp, lido do PipeWire (API do pulse): "44.1 kHz · 2ch"
    property string output: ""
    Process {
        id: sinkInputs
        command: ["pactl", "-f", "json", "list", "sink-inputs"]
        stdout: StdioCollector {
            onStreamFinished: {
                let list = [];
                try { list = JSON.parse(text); } catch (error) { return; }
                const mine = list.find(s => /cliamp/i.test((s.properties || {})["application.process.binary"] || "")
                                       || /cliamp/i.test((s.properties || {})["application.name"] || ""));
                const spec = mine ? /(\d+)ch (\d+)Hz/.exec(mine.sample_specification || "") : null;
                root.output = spec ? (parseInt(spec[2]) / 1000).toFixed(1).replace(/\.0$/, "") + " kHz · " + spec[1] + "ch" : "";
            }
        }
    }
    Timer {
        interval: 4000
        repeat: true
        triggeredOnStart: true
        running: Music.online && root.active
        onTriggered: if (!sinkInputs.running) sinkInputs.running = true
    }

    // ---- barra lateral: de onde vem a fila, o mini player e o VOL
    sidebar: Component {
        Column {
            spacing: 2
            RiceText { text: "SOURCES"; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5; bottomPadding: 4 }
            Repeater {
                model: [["local files", "local"], ["radio", "radio"], ["streaming", "stream"]]
                Item {
                    required property var modelData
                    readonly property int count: Music.playlist.filter(t => Music.sourceOf(t.path) === modelData[1]).length
                    readonly property bool on: Music.online && Music.track !== null && Music.sourceOf(Music.track.path) === modelData[1]
                    width: parent.width
                    height: srcName.implicitHeight + 2
                    RiceText {
                        id: srcName
                        textFormat: Text.StyledText
                        text: (parent.on ? "<font color='" + Theme.ok + "'>●</font> " : "<font color='" + Theme.faint + "'>○</font> ") + parent.modelData[0]
                        color: parent.on ? Theme.fg : Theme.dim
                    }
                    RiceText { anchors.right: parent.right; text: Music.online ? parent.count : "–"; color: Theme.faint }
                }
            }
            Item { width: 1; height: 14 }
            // Mini player: apagado enquanto NOW PLAYING mostra a mesma coisa inteira.
            Column {
                width: parent.width
                spacing: 2
                opacity: root.current === 0 ? 0.25 : 1
                Behavior on opacity { NumberAnimation { duration: Theme.tMed; easing.type: Theme.ease } }
                Visualizer {
                    width: parent.width
                    height: 34
                    count: 28
                    compact: true
                    levels: Spectrum.levels
                    idle: !Music.playing || Spectrum.levels.length === 0
                    // Em NOW PLAYING quem corre é o grande: este fica parado.
                    running: root.active && root.current !== 0 && Music.online && !root.parked
                }
                Item { width: 1; height: 4 }
                RiceText { width: parent.width; elide: Text.ElideRight; text: Music.online ? (Music.title || "—") : "—"; color: Theme.fg }
                RiceText {
                    width: parent.width
                    elide: Text.ElideRight
                    text: Music.online ? [Music.artist, Music.album].filter(x => x).join(" · ") : "cliamp offline"
                    color: Theme.dim
                    font.pixelSize: Theme.small
                }
                Item { width: 1; height: 4 }
                Rectangle {
                    width: parent.width
                    height: 2
                    color: Theme.line
                    Rectangle {
                        height: parent.height
                        width: Music.live ? parent.width : Music.duration > 0 ? parent.width * Math.min(1, Music.position / Music.duration) : 0
                        color: Music.live ? Theme.blue : Theme.accent
                    }
                }
            }
            Item { width: 1; height: 14 }
            // VOL ▮▮▮▮▮▮▮▮▯▯▯▯ 75%: o clique escolhe, a roda anda 5%.
            Item {
                id: vol
                width: parent.width
                height: volText.implicitHeight
                readonly property int cells: 12
                readonly property int filled: Math.round(Math.min(100, Music.volumePercent) / 100 * cells)
                // O volume do sistema existe mesmo sem o cliamp.
                readonly property bool live: Music.online || Music.systemVolume
                RiceText { id: volText; text: "VOL"; color: Theme.dim; font.pixelSize: Theme.small }
                RiceText {
                    id: volBar
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: Music.muted || !vol.live ? "▯".repeat(vol.cells) : "▮".repeat(vol.filled) + "▯".repeat(vol.cells - vol.filled)
                    color: Music.muted || !vol.live ? Theme.faint : Theme.accent
                    font.pixelSize: Theme.small
                    font.letterSpacing: -1
                }
                RiceText {
                    anchors.right: parent.right
                    text: !vol.live ? "–" : Music.muted ? "MUTE" : Music.volumePercent + "%"
                    color: Theme.dim
                    font.pixelSize: Theme.small
                }
                MouseArea {
                    anchors.fill: volBar
                    anchors.margins: -4
                    enabled: vol.live
                    cursorShape: Qt.PointingHandCursor
                    onClicked: mouse => { Music.setVolumePercent(Math.round(mouse.x / width * 20) * 5); root.keyTarget.forceActiveFocus(); }
                    onWheel: wheel => Music.volumeStep(wheel.angleDelta.y > 0 ? 5 : -5)
                }
            }
        }
    }

    // ---- um cabeçalho para todas as telas: a tela, o estado do cliamp e, em NOW PLAYING, os modos
    // do visualizador.
    header: Component {
        RiceHeader {
            title: root.screenItem ? root.screenItem.title : ""
            note: Music.online ? Music.status.toUpperCase() : "OFFLINE"
            noteColor: Music.playing ? Theme.ok : Music.status === "paused" ? Theme.yel : Theme.dim
            Repeater {
                model: root.active && root.current === 0 && Music.online && root.screenItem && root.screenItem.modes ? root.screenItem.modes : []
                Chip {
                    required property string modelData
                    label: modelData
                    on: root.screenItem && root.screenItem.mode === modelData
                    onClicked: { root.screenItem.setMode(modelData); root.keyTarget.forceActiveFocus(); }
                }
            }
        }
    }

    // ---- cliamp desligado: diz isso e oferece o START
    gate: Component {
        Column {
            spacing: 14
            RiceText {
                anchors.horizontalCenter: parent.horizontalCenter
                text: Music.connecting ? "[ .. ] conectando ao cliamp" : "[ -- ] cliamp offline"
                color: Music.connecting ? Theme.accent : Theme.dim
                font.pixelSize: 16
            }
            AccentButton {
                anchors.horizontalCenter: parent.horizontalCenter
                visible: !Music.connecting
                label: "START ⏎"
                onClicked: Music.startCliamp()
            }
            RiceText {
                anchors.horizontalCenter: parent.horizontalCenter
                visible: !Music.connecting
                text: "liga o cliamp sem janela: volta pausado onde parou, ou abre " + Music.dirShown
                color: Theme.faint
                font.pixelSize: Theme.small
            }
            // Só os erros que o START não resolve.
            RiceText {
                anchors.horizontalCenter: parent.horizontalCenter
                visible: !Music.connecting && /não encontrado/.test(Music.lastError)
                text: "[ !! ] " + Music.lastError
                color: Theme.red
                font.pixelSize: Theme.small
            }
        }
    }

    // ---- arquivos de áudio soltos em MÚSICA entram na fila
    overlay: Component {
        Item {
            DropArea {
                id: drop
                anchors.fill: parent
                enabled: root.active && Music.online
                keys: ["text/uri-list"]
                onDropped: event => {
                    const files = event.urls.map(u => decodeURIComponent(String(u).replace(/^file:\/\//, "")))
                        .filter(f => /\.(mp3|flac|ogg|opus|m4a|aac|wav|wv|ape|aiff?|alac|wma)$/i.test(f));
                    for (const f of files) Music.addPath(f);
                    Status.say(files.length ? "[ + ] " + files.length + " arquivo(s) na fila" : "[ !! ] nenhum arquivo de áudio", files.length ? Theme.ok : Theme.red);
                }
            }
            Rectangle {
                anchors.fill: parent
                anchors.margins: 10
                visible: drop.containsDrag
                color: Qt.alpha(Theme.bg, 0.85)
                border.width: 2
                border.color: Theme.accent
                RiceText { anchors.centerIn: parent; text: "solte os arquivos de áudio"; color: Theme.accent; font.pixelSize: 16; font.letterSpacing: 1 }
            }
        }
    }
}
