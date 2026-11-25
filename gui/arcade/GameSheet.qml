// GameSheet.qml — a ficha do jogo (abre por cima da lista): status, progresso, horas, notas,
// e como o jogo roda (proton-ge, gamescope/fsr, mangohud, gamemode). Cada mudança vira Games.set().
import QtQuick
import qs
import qs.components
import qs.arcade

// The sheet that rises from the bottom for one game: cover, hours, the estimate and the
// progress (editable), status, gamemoderun / mangohud, notes, PLAY. Every edit goes to
// `lw game set` at once (text fields after a short pause). Esc or a click outside closes it.
Item {
    id: root

    property string gameId: ""
    readonly property var game: gameId ? Games.games.find(g => g.id === gameId) || null : null
    readonly property bool shown: gameId !== "" && game !== null
    property Item keyTarget: null
    property int bottomInset: 0          // the status bar stays visible below the sheet
    signal launch(string id)

    // Abre a ficha desse jogo.
    function openGame(id) { gameId = id; }
    // Fecha a ficha e devolve o foco à lista.
    function close() { gameId = ""; if (keyTarget) keyTarget.forceActiveFocus(); }
    // Horas → texto ("3.5 h").
    function hours(h) { return h ? (h < 10 ? h.toFixed(1).replace(/\.0$/, "") : Math.round(h)) + " h" : "0 h"; }
    // Muda o status do jogo.
    function setStatus(status) {
        const pairs = ["status=" + status];
        if (status === "done") pairs.push("progress=100");
        Games.set(gameId, pairs, game.title + " → " + Games.statusLabel[status]);
    }
    // Ajusta o progresso em passos (0–100%).
    function nudgeProgress(step) { Games.set(gameId, ["progress=" + Math.max(0, Math.min(100, (game.progress || 0) + step))]); }
    // Passa para o próximo status.
    function cycleStatus() { setStatus(Games.statuses[(Games.statuses.indexOf(game.status) + 1) % Games.statuses.length]); }
    // Teclas da ficha (Enter joga, s status, setas progresso, Esc fecha).
    function handleKey(event) {
        if (!shown) return false;
        if (notes.activeFocus || est.inputFocus) return false;
        const t = event.text;
        if (event.key === Qt.Key_Escape) { close(); return true; }
        if (event.key === Qt.Key_Left) { nudgeProgress(-5); return true; }
        if (event.key === Qt.Key_Right) { nudgeProgress(5); return true; }
        if (t === "s") { cycleStatus(); return true; }
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { launch(gameId); return true; }
        return true;   // the sheet is modal: nothing reaches the grid behind it
    }

    // gamemoderun / mangohud: switchable only when installed.
    property bool hasGamemode: false
    property bool hasMangohud: false
    property bool hasUmu: false
    property bool hasGamescope: false
    // Proton applies to Windows games outside Steam; Steam keeps its own launch options.
    readonly property bool windowsGame: !!game && game.source !== "steam" && /\.exe$/i.test(game.exe || "")
    RiceCommand {
        program: Theme.lw
        onSucceeded: data => {
            root.hasGamemode = data.gamemode; root.hasMangohud = data.mangohud;
            root.hasUmu = data.proton; root.hasGamescope = data.gamescope;
        }
        Component.onCompleted: call(["game", "tools", "--json"])
    }

    visible: scrim.opacity > 0

    // Scrim: a click outside closes.
    Rectangle {
        id: scrim
        anchors.fill: parent
        color: Qt.alpha(Theme.bg, 0.6)
        opacity: root.shown ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 300; easing.type: Theme.ease } }
        MouseArea { anchors.fill: parent; onClicked: root.close() }
    }

    Rectangle {
        id: sheet
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(parent.width - 40, 660)
        height: body.implicitHeight + 40
        y: root.shown ? parent.height - height - root.bottomInset : parent.height + 10
        Behavior on y { NumberAnimation { duration: Theme.motion ? 400 : 0; easing.type: Theme.ease } }
        color: Theme.sheet
        border.width: 1
        border.color: Theme.line2
        MouseArea { anchors.fill: parent }   // clicks on the sheet stay on it

        Rectangle { anchors.horizontalCenter: parent.horizontalCenter; y: 10; width: 40; height: 4; color: Theme.line2 }

        Column {
            id: body
            x: 20
            y: 26
            width: parent.width - 40
            spacing: 14
            readonly property var g: root.game || ({})

            Row {
                width: parent.width
                spacing: 16
                GameCover { id: cover; width: 96; height: 128; game: root.game; showTitle: false }
                Column {
                    width: parent.width - cover.width - 16
                    spacing: 3
                    RiceText { width: parent.width; elide: Text.ElideRight; text: body.g.title || ""; font.pixelSize: 18; font.weight: Font.ExtraBold }
                    RiceText {
                        textFormat: Text.StyledText
                        text: (body.g.system_name || body.g.source || "") + (body.g.missing ? " · <font color='" + Theme.red + "'>sumiu da fonte</font>" : "")
                        color: Theme.dim
                    }
                    // What IGDB knows: year, genres and the three times to beat.
                    RiceText {
                        readonly property var m: body.g.igdb || null
                        readonly property var t: m && m.ttb ? m.ttb : ({})
                        visible: !!m
                        width: parent.width
                        elide: Text.ElideRight
                        textFormat: Text.StyledText
                        font.pixelSize: Theme.small
                        color: Theme.faint
                        text: !m ? "" : !m.name ? "IGDB: sem par para este título"
                            : [m.year, (m.genres || []).slice(0, 3).join(", ")].filter(x => x).join(" · ")
                              + (t.normally || t.hastily || t.completely
                                 ? "  ·  <font color='" + Theme.dim + "'>zerar " + (t.hastily ? t.hastily + "–" : "") + (t.normally || "?") + " h" + (t.completely ? " · 100% " + t.completely + " h" : "") + "</font>"
                                 : "")
                    }
                    Item { width: 1; height: 6 }
                    component Kv: Row {
                        property string k: ""
                        default property alias value: slot.data
                        spacing: 10
                        height: 22
                        RiceText { width: 82; anchors.verticalCenter: parent.verticalCenter; text: parent.k; color: Theme.faint }
                        Item { id: slot; width: 220; height: parent.height }
                    }
                    Kv {
                        k: "jogado"
                        RiceText {
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.hours(body.g.hours || 0) + (body.g.hours_source ? "  ·  steam: " + root.hours(body.g.hours_source) : "")
                        }
                    }
                    Kv {
                        k: "p/ zerar"
                        // Edited in place; empty means unknown.
                        Rectangle {
                            id: est
                            readonly property bool inputFocus: estInput.activeFocus
                            width: 90
                            height: 20
                            anchors.verticalCenter: parent.verticalCenter
                            color: Theme.base
                            border.width: 1
                            border.color: estInput.activeFocus ? Theme.accent : Theme.line2
                            TextInput {
                                id: estInput
                                anchors.fill: parent
                                anchors.leftMargin: 6
                                verticalAlignment: TextInput.AlignVCenter
                                color: Theme.fg
                                font.family: Theme.font
                                font.pixelSize: Theme.fontSize
                                validator: DoubleValidator { bottom: 0; top: 9999; decimals: 1; notation: DoubleValidator.StandardNotation }
                                text: body.g.est_hours === null || body.g.est_hours === undefined ? "" : String(body.g.est_hours)
                                onEditingFinished: {
                                    const v = text.replace(",", ".");
                                    Games.set(root.gameId, ["est_hours=" + (v === "" ? "null" : v)]);
                                    if (root.keyTarget) root.keyTarget.forceActiveFocus();
                                }
                                Keys.onEscapePressed: { text = body.g.est_hours === null || body.g.est_hours === undefined ? "" : String(body.g.est_hours); root.keyTarget.forceActiveFocus(); }
                            }
                            RiceText { visible: !estInput.text && !estInput.activeFocus; x: 6; anchors.verticalCenter: parent.verticalCenter; text: "—"; color: Theme.faint }
                        }
                        RiceText { x: 98; anchors.verticalCenter: parent.verticalCenter; text: "h"; color: Theme.dim }
                    }
                    Kv {
                        k: "progresso"
                        // 0–100 in steps of 5; saved when the drag ends.
                        Item {
                            id: slider
                            width: 170
                            height: parent.height
                            property real live: -1
                            readonly property real value: live >= 0 ? live : (body.g.progress || 0)
                            Rectangle { y: 10; width: parent.width; height: 2; color: Theme.line2 }
                            Rectangle { y: 10; width: parent.width * slider.value / 100; height: 2; color: Theme.accent }
                            Rectangle {
                                x: slider.value / 100 * (parent.width - width)
                                y: 4
                                width: 10
                                height: 14
                                color: Theme.accent
                                Behavior on x { enabled: slider.live < 0; NumberAnimation { duration: Theme.tFast; easing.type: Theme.ease } }
                            }
                            MouseArea {
                                anchors.fill: parent
                                anchors.margins: -4
                                cursorShape: Qt.PointingHandCursor
                                // Clique/arraste no controle → valor.
                                function pick(x) { slider.live = Math.round(Math.max(0, Math.min(1, x / slider.width)) * 20) * 5; }
                                onPressed: mouse => pick(mouse.x)
                                onPositionChanged: mouse => { if (pressed) pick(mouse.x); }
                                onReleased: { Games.set(root.gameId, ["progress=" + slider.live]); slider.live = -1; }
                            }
                        }
                        RiceText { x: 180; anchors.verticalCenter: parent.verticalCenter; text: Math.round(slider.value) + "%"; color: Theme.accent }
                    }
                }
            }

            // Status
            Row {
                spacing: 6
                Repeater {
                    model: Games.statuses
                    Chip {
                        required property string modelData
                        label: Games.statusLabel[modelData]
                        on: body.g.status === modelData
                        onClicked: root.setStatus(modelData)
                    }
                }
                // 100%: everything done, apart from finishing the story (zerado).
                Item { width: 10; height: 1 }
                Chip {
                    label: body.g.complete ? "100% ✓" : "100%"
                    on: !!body.g.complete
                    onClicked: Games.set(root.gameId, ["complete=" + !body.g.complete], body.g.complete ? "" : "★ " + body.g.title + " em 100%")
                }
                RiceText { anchors.verticalCenter: parent.verticalCenter; leftPadding: 8; text: "s troca"; color: Theme.faint; font.pixelSize: 10 }
            }

            // How it runs: Proton (umu), gamescope (+FSR), gamemoderun, mangohud.
            Flow {
                width: parent.width
                spacing: 22
                Repeater {
                    model: (root.windowsGame ? [["proton", "proton-ge", root.hasUmu, "umu-launcher"]] : [])
                        .concat(body.g.source === "steam" ? [] : [["gamescope", "gamescope", root.hasGamescope, "gamescope"],
                                                                 ["fsr", "fsr 75%", root.hasGamescope && !!body.g.gamescope, "gamescope"]])
                        .concat([["gamemode", "gamemoderun", root.hasGamemode, "gamemode"], ["mangohud", "mangohud", root.hasMangohud, "mangohud"]])
                    Row {
                        id: toggle
                        required property var modelData
                        readonly property bool on: !!body.g[modelData[0]]
                        readonly property bool available: modelData[2]
                        spacing: 8
                        opacity: available ? 1 : 0.45
                        Rectangle {
                            width: 34
                            height: 16
                            anchors.verticalCenter: parent.verticalCenter
                            color: toggle.on ? Theme.accentA : "transparent"
                            border.width: 1
                            border.color: toggle.on ? Theme.accent : Theme.line2
                            Rectangle {
                                x: toggle.on ? 20 : 2
                                y: 2
                                width: 10
                                height: 10
                                color: toggle.on ? Theme.accent : Theme.dim
                                Behavior on x { NumberAnimation { duration: Theme.tMed; easing.type: Theme.ease } }
                            }
                            MouseArea {
                                anchors.fill: parent
                                enabled: toggle.available
                                cursorShape: Qt.PointingHandCursor
                                onClicked: Games.set(root.gameId, [toggle.modelData[0] + "=" + (!toggle.on)])
                            }
                        }
                        RiceText {
                            anchors.verticalCenter: parent.verticalCenter
                            text: toggle.modelData[1] + (toggle.available || toggle.modelData[0] === "fsr" && root.hasGamescope ? "" : "  (sudo pacman -S " + toggle.modelData[3] + ")")
                            color: toggle.available ? Theme.fg : Theme.dim
                            font.pixelSize: Theme.small
                        }
                    }
                }
            }

            // Notes: saved 800 ms after the last key.
            Rectangle {
                width: parent.width
                height: 70
                color: Theme.base
                border.width: 1
                border.color: notes.activeFocus ? Theme.accent : Theme.line2
                Flickable {
                    anchors.fill: parent
                    anchors.margins: 8
                    contentHeight: notes.implicitHeight
                    clip: true
                    TextEdit {
                        id: notes
                        width: parent.width
                        wrapMode: TextEdit.Wrap
                        color: Theme.fg
                        selectionColor: Theme.accent
                        font.family: Theme.font
                        font.pixelSize: Theme.small
                        text: body.g.notes || ""
                        onTextChanged: if (activeFocus) saveNotes.restart()
                        Keys.onEscapePressed: { saveNotes.stop(); Games.set(root.gameId, ["notes=" + text]); root.keyTarget.forceActiveFocus(); }
                    }
                }
                RiceText { visible: !notes.text && !notes.activeFocus; x: 8; y: 8; text: "notas…"; color: Theme.faint; font.pixelSize: Theme.small }
                Timer { id: saveNotes; interval: 800; onTriggered: Games.set(root.gameId, ["notes=" + notes.text]) }
            }

            Row {
                width: parent.width
                spacing: 10
                Rectangle {
                    id: playButton
                    readonly property bool live: !!Games.session && Games.session.id === root.gameId
                    readonly property color tone: live ? Theme.red : Theme.ok
                    width: parent.width - metaButton.width - 10 - (removeButton.visible ? removeButton.width + 10 : 0)
                    height: 38
                    color: playMouse.containsMouse ? tone : "transparent"
                    border.width: 1
                    border.color: tone
                    Behavior on color { ColorAnimation { duration: Theme.tFast } }
                    RiceText { anchors.centerIn: parent; text: playButton.live ? "■ PARAR SESSÃO" : "▶ JOGAR  ⏎"; font.weight: Font.ExtraBold; font.letterSpacing: 1; color: playMouse.containsMouse ? Theme.bg : playButton.tone }
                    MouseArea {
                        id: playMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: playButton.live ? Games.stop(root.gameId) : root.launch(root.gameId)
                    }
                }
                // Refaz a busca no IGDB só deste jogo (capa, gêneros, duração), para quando a
                // busca automática falhou em silêncio. Não troca capa nem horas já existentes.
                AccentButton {
                    id: metaButton
                    anchors.verticalCenter: playButton.verticalCenter
                    ghost: true
                    enabledState: !Games.fetchingMeta
                    label: Games.fetchingMeta ? "BUSCANDO…" : "↻ BUSCAR CAPA"
                    onClicked: Games.meta(false, [root.gameId])
                }
                // Only for a game its source no longer has: two clicks.
                AccentButton {
                    id: removeButton
                    property bool armed: false
                    visible: !!body.g.missing
                    anchors.verticalCenter: playButton.verticalCenter
                    ghost: true
                    label: armed ? "CONFIRMAR?" : "REMOVER"
                    onClicked: {
                        if (armed) { const id = root.gameId; root.close(); Games.remove(id); armed = false; }
                        else { armed = true; disarm.restart(); }
                    }
                    Timer { id: disarm; interval: 3000; onTriggered: removeButton.armed = false }
                }
            }
        }
    }
}
