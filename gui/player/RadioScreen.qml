// RadioScreen.qml — tela RÁDIO (MÚSICA): busca estações no radio-browser.info e as salvas do cliamp
// (`lw radio`).
import QtQuick
import qs
import qs.components

// LW // RADIO: radio-browser.info (the directory behind cliamp's own radio browser) by
// name or tag, plus the stations saved in ~/.config/cliamp/radios.toml. ⏎ hands the
// stream URL to cliamp (url.load); `a` saves the selected station.
Item {
    id: root

    property Item keyTarget: null
    property string title: ""
    readonly property var hints: [["/", "buscar"], ["↑↓", "move"], ["⏎", "tocar"], ["a", "salvar"]]
    readonly property var tags: ["lofi", "jazz", "ambient", "synthwave", "chillout", "rock", "classical", "news"]

    property var results: []
    property var saved: []
    property string tag: ""
    property string error: ""
    property string server: ""
    property int cursor: 0
    readonly property var selected: results[cursor] || null

    // Roda `lw radio` com esses argumentos; done(ok, dados ou {error}). stoppable: a busca, que
    // um sinal precisa alcançar.
    function run(args, done, stoppable) {
        const proc = runner.createObject(root, { program: stoppable ? Theme.lw : Theme.rice, done: done });
        proc.call(["radio"].concat(args, ["--json"]));
        return proc;
    }
    property var searching: null
    property int seq: 0
    // Busca estações por nome ou gênero; uma busca nova cancela a anterior.
    function search() {
        error = "";
        if (searching) searching.signal(15);
        const args = ["search"];
        if (box.text.trim()) args.push("--name=" + box.text.trim());
        if (tag) args.push("--tag", tag);
        const mine = ++seq;
        searching = run(args, (ok, data) => {
            if (mine !== seq) return;          // uma busca mais nova tomou o lugar desta
            searching = null;
            if (!ok) { error = data.error || "falha na busca"; results = []; return; }
            results = data.stations;
            server = data.server;
            cursor = 0;
            view.positionViewAtBeginning();
        }, true);
    }
    // Lê as estações salvas.
    function loadSaved() { run(["saved"], (ok, data) => { if (ok) saved = data.stations; }); }
    // Toca uma estação.
    function play(station) {
        if (!station) return;
        Music.playUrl(station.url);
        Status.say("[ ▶ ] " + station.name + " (rádio)", Theme.ok);
    }
    // Salva uma estação no radios.toml.
    function save(station) {
        if (!station) return;
        run(["add", "--name=" + station.name, "--url=" + station.url], (ok, data) => {
            Status.say(ok ? "[ + ] " + station.name + " salva em radios.toml" : "[ !! ] " + data.error, ok ? Theme.ok : Theme.red);
            if (ok) loadSaved();
        });
    }
    // Move a seleção.
    function moveCursor(step) {
        if (!results.length) return;
        cursor = Math.max(0, Math.min(results.length - 1, cursor + step));
        view.positionViewAtIndex(cursor, ListView.Contain);
    }
    // Teclas da tela.
    function handleKey(event) {
        const t = event.text;
        if (event.key === Qt.Key_Slash) { box.focusInput(); return true; }
        if (event.key === Qt.Key_Down) { moveCursor(1); return true; }
        if (event.key === Qt.Key_Up) { moveCursor(-1); return true; }
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { play(selected); return true; }
        if (t === "a") { save(selected); return true; }
        return false;
    }

    Component.onCompleted: { loadSaved(); search(); }

    Component {
        id: runner
        RiceCommand {
            id: proc
            property var done: null
            onSucceeded: data => { if (done) done(true, data); proc.destroy(); }
            onFailed: message => { if (done) done(false, { error: message }); proc.destroy(); }
        }
    }

    // ================= SEARCH =================
    Row {
        id: top
        width: parent.width
        spacing: 10
        SearchBox {
            id: box
            width: parent.width - goButton.width - 10
            placeholder: "buscar estação (radio-browser.info)"
            keyTarget: root.keyTarget
            onAccepted: root.search()
        }
        AccentButton { id: goButton; label: root.searching ? "BUSCANDO…" : "SEARCH ⏎"; onClicked: root.search() }
    }
    Flow {
        id: tagRow
        anchors.top: top.bottom
        anchors.topMargin: 10
        width: parent.width
        spacing: 6
        Repeater {
            model: root.tags
            Chip {
                required property string modelData
                label: modelData
                on: root.tag === modelData
                onClicked: { root.tag = root.tag === modelData ? "" : modelData; root.search(); root.keyTarget.forceActiveFocus(); }
            }
        }
    }

    // ================= RESULTS =================
    Rectangle {
        id: table
        anchors.top: tagRow.bottom
        anchors.topMargin: 10
        anchors.bottom: foot.top
        anchors.bottomMargin: 10
        anchors.left: parent.left
        anchors.right: side.left
        anchors.rightMargin: 20
        color: "transparent"
        border.width: 1
        border.color: Theme.line
        clip: true

        component Line: Item {
            id: line
            property bool head: false
            property var s: null
            width: parent ? parent.width : 0
            height: 26
            readonly property color tone: head ? Theme.faint : Theme.dim
            RiceText {
                x: 10
                width: parent.width - 10 - 70 - 90 - 60 - 40
                anchors.verticalCenter: parent.verticalCenter
                elide: Text.ElideRight
                text: line.head ? "ESTAÇÃO" : line.s.name
                color: line.head ? Theme.faint : Theme.fg
                font.pixelSize: line.head ? Theme.small : Theme.fontSize
                font.letterSpacing: line.head ? 1.5 : 0
            }
            RiceText {
                x: parent.width - 70 - 90 - 60 - 20
                width: 70
                anchors.verticalCenter: parent.verticalCenter
                elide: Text.ElideRight
                text: line.head ? "PAÍS" : line.s.countrycode || "—"
                color: line.tone
                font.pixelSize: line.head ? Theme.small : Theme.fontSize
                font.letterSpacing: line.head ? 1.5 : 0
            }
            RiceText {
                x: parent.width - 90 - 60 - 15
                width: 90
                anchors.verticalCenter: parent.verticalCenter
                text: line.head ? "FORMATO" : [line.s.codec, line.s.bitrate ? line.s.bitrate + "k" : ""].filter(x => x).join(" ")
                color: line.tone
                font.pixelSize: line.head ? Theme.small : Theme.fontSize
                font.letterSpacing: line.head ? 1.5 : 0
            }
            RiceText {
                x: parent.width - 60 - 10
                width: 60
                anchors.verticalCenter: parent.verticalCenter
                horizontalAlignment: Text.AlignRight
                text: line.head ? "VOTOS" : line.s.votes
                color: Theme.faint
                font.pixelSize: line.head ? Theme.small : Theme.fontSize
                font.letterSpacing: line.head ? 1.5 : 0
            }
        }

        ListView {
            id: view
            anchors.fill: parent
            anchors.margins: 1
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: root.results
            headerPositioning: ListView.OverlayHeader
            header: Rectangle {
                width: view.width
                height: 26
                z: 2
                color: Theme.base
                Line { head: true }
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
            }
            delegate: Item {
                id: row
                required property var modelData
                required property int index
                readonly property bool chosen: index === root.cursor
                readonly property bool playing: Music.track !== null && Music.track.path === modelData.url
                width: view.width
                height: 26
                Rectangle {
                    anchors.fill: parent
                    color: row.playing ? Theme.accentA : row.chosen ? Qt.alpha(Theme.fg, 0.04) : rowMouse.containsMouse ? Qt.alpha(Theme.fg, 0.025) : "transparent"
                    Rectangle { width: 2; height: parent.height; color: row.playing ? Theme.accent : row.chosen ? Theme.line2 : "transparent" }
                }
                Line { s: row.modelData }
                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: { root.cursor = row.index; root.keyTarget.forceActiveFocus(); }
                    onDoubleClicked: root.play(row.modelData)
                }
            }
            // Searching, nothing found, or the network is down: say it in the list.
            RiceText {
                anchors.centerIn: parent
                width: parent.width - 60
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                visible: root.results.length === 0
                text: root.searching ? "[ .. ] buscando no radio-browser…"
                    : root.error ? "[ !! ] " + root.error : "nenhuma estação encontrada"
                color: root.error ? Theme.red : root.searching ? Theme.accent : Theme.faint
            }
        }
    }

    // ================= SAVED =================
    Rectangle {
        id: side
        anchors.top: table.top
        anchors.bottom: table.bottom
        anchors.right: parent.right
        width: 270
        color: Theme.panel
        border.width: 1
        border.color: Theme.line
        RiceText { x: 16; y: 14; text: "SALVAS · radios.toml"; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5 }
        ListView {
            anchors.fill: parent
            anchors.topMargin: 38
            anchors.margins: 8
            clip: true
            model: root.saved
            delegate: Item {
                id: st
                required property var modelData
                readonly property bool playing: Music.track !== null && Music.track.path === modelData.url
                width: ListView.view.width
                height: 24
                RiceText {
                    x: 8
                    width: parent.width - 16
                    anchors.verticalCenter: parent.verticalCenter
                    elide: Text.ElideRight
                    textFormat: Text.StyledText
                    text: (st.playing ? "<font color='" + Theme.ok + "'>●</font> " : "") + st.modelData.name
                    color: stMouse.containsMouse ? Theme.fg : Theme.dim
                }
                MouseArea {
                    id: stMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: { root.play(st.modelData); root.keyTarget.forceActiveFocus(); }
                }
            }
            RiceText {
                anchors.centerIn: parent
                width: parent.width - 20
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                visible: root.saved.length === 0
                text: "nenhuma ainda — selecione uma estação e aperte a"
                color: Theme.faint
                font.pixelSize: Theme.small
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
            text: root.results.length ? root.results.length + " estações · " + root.server + " · só streams funcionando, mais votadas primeiro" : ""
            color: Theme.faint
            font.pixelSize: Theme.small
        }
        Row {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            spacing: 8
            AccentButton { ghost: true; label: "SALVAR (a)"; enabledState: !!root.selected; onClicked: root.save(root.selected) }
            AccentButton { label: "TOCAR ⏎"; enabledState: !!root.selected; onClicked: root.play(root.selected) }
        }
    }
}
