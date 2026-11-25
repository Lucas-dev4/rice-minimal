// EmulatorsView.qml — a tela EMULADORES de JOGOS: ajustes rápidos de cada emulador
// (resolução, tela cheia, vsync, FPS, controle como player 1) e o controle conectado:
// detectar, testar ao vivo e mapear para o SDL (controllers.txt). Tudo por `lw emu ... --json`.
import QtQuick
import Quickshell.Io
import qs
import qs.components

Item {
    id: root

    property Item keyTarget: null
    property string title: ""
    readonly property var hints: mode === "map" ? [["aperte", "o botão pedido"], ["s", "pular"], ["esc", "cancelar"]]
        : mode === "test" ? [["esc", "fecha o teste"]]
        : [["↑↓", "emulador"], ["←→", "resolução"], ["f", "tela cheia"], ["v", "vsync"], ["p", "fps"], ["c", "controle"], ["t", "testar"], ["m", "mapear"]]

    property var emus: []
    property var pads: []
    property int selected: 0
    readonly property var emu: emus[selected] || null
    readonly property var pad: pads[0] || null
    property string mode: ""                  // "", "test" ou "map"

    // ---- comandos ------------------------------------------------------------------
    function load() {
        listCommand.call(["emu", "list", "--json"]);
        loadPads();
    }
    function loadPads() { padsCommand.call(["emu", "pads", "--json"]); }
    // As leituras morrem com a tela; o que grava vai pelo Games.run, termina sozinho e pode responder
    // depois de a tela sumir (root null).
    RiceCommand {
        id: listCommand
        program: Theme.lw
        onSucceeded: data => root.emus = data.emulators
        onFailed: message => Games.failed(message)
    }
    RiceCommand {
        id: padsCommand
        program: Theme.lw
        onSucceeded: data => root.pads = data.pads
    }
    // Muda um ajuste e troca o emulador na lista pelo que voltou do arquivo.
    function setValue(e, key, value) {
        Games.run(["emu", "set", e.id, key, String(value)], (ok, data, error) => {
            if (!ok) { Games.failed(error); return; }
            const fresh = data.emulator;
            if (root) root.emus = root.emus.map(x => x.id === fresh.id ? fresh : x);
            const s = fresh.settings.find(x => x.key === key);
            Games.changed(fresh.name + ": " + s.label + " → " + (s.kind === "bool" ? (s.value ? "on" : "off") : s.choices.find(c => c.v === s.value).label));
        });
    }
    function setting(e, key) { return e ? e.settings.find(s => s.key === key) || null : null; }
    function toggle(key) {
        const s = setting(emu, key);
        if (!emu || !s) return;
        if (!emu.has_config) { Games.failed("abra o " + emu.name + " uma vez para ele criar a configuração"); return; }
        setValue(emu, key, !s.value);
    }
    function stepRes(step) {
        const s = setting(emu, "res");
        if (!s || !emu.has_config) return;
        const i = s.choices.findIndex(c => c.v === s.value);
        const next = s.choices[Math.max(0, Math.min(s.choices.length - 1, i + step))];
        if (next.v !== s.value) setValue(emu, "res", next.v);
    }
    function applyPad(e) {
        if (!e || e.pad !== "apply") { if (e) Games.changed(e.name + ": " + e.pad_note); return; }
        Games.run(["emu", "apply-pad", e.id], (ok, data, error) => ok ? Games.changed("🎮 controle no " + data.applied) : Games.failed(error));
    }

    // ---- teste e mapeamento ao vivo -------------------------------------------------
    property var pressed: ({})                // índice do botão → true
    property var axisValues: ({})             // índice do eixo → -1..1
    property int hat: 0
    property int buttonCount: 0
    property int axisCount: 0
    readonly property var targets: [
        ["a", "A / ✕  (botão de baixo)"], ["b", "B / ○  (botão da direita)"], ["x", "X / □  (botão da esquerda)"], ["y", "Y / △  (botão de cima)"],
        ["back", "Select / Back"], ["guide", "Home / Guide"], ["start", "Start"],
        ["leftshoulder", "LB / L1"], ["rightshoulder", "RB / R1"], ["lefttrigger", "LT / L2"], ["righttrigger", "RT / R2"],
        ["leftstick", "L3  (aperte o analógico esquerdo)"], ["rightstick", "R3  (aperte o analógico direito)"],
        ["dpup", "direcional ↑"], ["dpdown", "direcional ↓"], ["dpleft", "direcional ←"], ["dpright", "direcional →"],
        ["leftx", "analógico esquerdo  ← →"], ["lefty", "analógico esquerdo  ↑ ↓"], ["rightx", "analógico direito  ← →"], ["righty", "analógico direito  ↑ ↓"]]
    property int step: 0
    property var binds: []                    // ["a=b0", ...]
    property double quietUntil: 0             // espera soltar antes do próximo passo

    function startTest() { if (!pad) { Games.failed("nenhum controle conectado"); return; } pressed = {}; axisValues = {}; hat = 0; mode = "test"; }
    function startMap() { if (!pad) { Games.failed("nenhum controle conectado"); return; } step = 0; binds = []; quietUntil = 0; mode = "map"; }
    function stopLive() { mode = ""; }
    function used(value) { return binds.some(b => b.split("=")[1] === value); }
    function capture(value) {
        if (used(value)) return;
        binds = binds.concat([targets[step][0] + "=" + value]);
        quietUntil = Date.now() + 450;
        nextStep();
    }
    function nextStep() {
        if (step + 1 < targets.length) { step++; return; }
        mode = "";
        if (!binds.length) { Games.failed("nenhum botão mapeado"); return; }
        Games.run(["emu", "pad-save", pad.guid, pad.name].concat(binds), (ok, data, error) => {
            if (!ok) { Games.failed(error); return; }
            Games.changed("🎮 mapeamento salvo: " + data.saved + " (vale no próximo jogo)");
            if (root) root.loadPads();
        });
    }
    // Um evento do controle: atualiza o teste e, no mapeamento, decide se é a resposta do passo.
    function onPadEvent(ev) {
        if (ev.error) { Games.failed(ev.error); mode = ""; return; }
        if (ev.ready) { buttonCount = ev.buttons; axisCount = ev.axes; return; }
        if (ev.t === "b") { const p = Object.assign({}, pressed); p[ev.i] = ev.v === 1; pressed = p; }
        else if (ev.t === "a") { const a = Object.assign({}, axisValues); a[ev.i] = ev.v; axisValues = a; }
        else if (ev.t === "h") hat = ev.v;
        if (mode !== "map" || Date.now() < quietUntil) return;
        const target = targets[step][0];
        const stick = ["leftx", "lefty", "rightx", "righty"].indexOf(target) >= 0;
        const trigger = target === "lefttrigger" || target === "righttrigger";
        if (stick) { if (ev.t === "a" && Math.abs(ev.v) > 0.6) capture("a" + ev.i); return; }
        if (ev.t === "b" && ev.v === 1) capture("b" + ev.i);
        else if (ev.t === "h" && [1, 2, 4, 8].indexOf(ev.v) >= 0) capture("h0." + ev.v);
        else if (trigger && ev.t === "a" && ev.v > 0.5) capture("a" + ev.i);
    }
    Process {
        running: root.mode !== "" && !!root.pad && !!root.pad.event
        command: Theme.lw.concat(["emu", "pad-watch", root.pad ? root.pad.event : ""])
        stdout: SplitParser { onRead: line => { try { root.onPadEvent(JSON.parse(line)); } catch (e) {} } }
    }

    // ---- teclas ------------------------------------------------------------------------
    function handleKey(event) {
        const t = event.text;
        if (mode === "map") {
            if (event.key === Qt.Key_Escape) { stopLive(); Games.changed("mapeamento cancelado"); }
            else if (t === "s") nextStep();
            return true;
        }
        if (mode === "test") { if (event.key === Qt.Key_Escape || t === "t") stopLive(); return true; }
        if (event.key === Qt.Key_Down) { selected = Math.min(emus.length - 1, selected + 1); return true; }
        if (event.key === Qt.Key_Up) { selected = Math.max(0, selected - 1); return true; }
        if (event.key === Qt.Key_Left) { stepRes(-1); return true; }
        if (event.key === Qt.Key_Right) { stepRes(1); return true; }
        if (t === "f") { toggle("fullscreen"); return true; }
        if (t === "v") { toggle("vsync"); return true; }
        if (t === "p") { toggle("fps"); return true; }
        if (t === "c") { applyPad(emu); return true; }
        if (t === "t") { startTest(); return true; }
        if (t === "m") { startMap(); return true; }
        return false;
    }

    Component.onCompleted: load()
    onVisibleChanged: if (visible) load(); else stopLive()
    // Controles entram e saem: confere a cada 3 s enquanto a tela está aberta.
    Timer { interval: 3000; repeat: true; running: root.visible && root.mode === ""; onTriggered: root.loadPads() }

    component Label: RiceText { color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5; bottomPadding: 6 }

    // ================= HEADER =================
    RiceText {
        id: titleText
        textFormat: Text.StyledText
        text: "emuladores<font color='" + Theme.accent + "'>.</font> <font color='" + Theme.dim + "' size='2'>" + root.emus.filter(e => e.installed).length + " instalados</font>"
        font.pixelSize: 26
        font.weight: Font.ExtraBold
    }

    // ================= LEFT: emuladores =================
    Flickable {
        id: list
        anchors.top: titleText.bottom
        anchors.topMargin: 20
        anchors.bottom: parent.bottom
        width: parent.width * 0.58
        contentHeight: rows.implicitHeight
        clip: true
        Column {
            id: rows
            width: parent.width
            spacing: 8
            Repeater {
                model: root.emus
                Rectangle {
                    id: row
                    required property var modelData
                    required property int index
                    readonly property bool current: index === root.selected
                    readonly property bool editable: modelData.installed && modelData.has_config
                    width: rows.width
                    height: body.implicitHeight + 20
                    color: current ? Theme.raise : Theme.panel
                    border.width: 1
                    border.color: current ? Theme.accent : Theme.line
                    MouseArea { anchors.fill: parent; onClicked: root.selected = row.index }
                    Column {
                        id: body
                        x: 12
                        y: 10
                        width: parent.width - 24
                        spacing: 8
                        Item {
                            width: parent.width
                            height: nameText.implicitHeight
                            RiceText {
                                id: nameText
                                textFormat: Text.StyledText
                                text: row.modelData.name + "  <font color='" + Theme.dim + "'>" + row.modelData.system + "</font>"
                                font.weight: Font.Bold
                            }
                            RiceText {
                                anchors.right: parent.right
                                text: !row.modelData.installed ? "[ -- ] não instalado" : !row.modelData.has_config ? "[ -- ] abra uma vez" : ""
                                color: Theme.faint
                                font.pixelSize: Theme.small
                            }
                        }
                        // Resolução: chips; liga/desliga: chips também.
                        Flow {
                            visible: row.modelData.settings.length > 0
                            width: parent.width
                            spacing: 6
                            opacity: row.editable ? 1 : 0.45
                            Repeater {
                                model: (root.setting(row.modelData, "res") || { choices: [] }).choices
                                Chip {
                                    required property var modelData
                                    label: modelData.label
                                    on: root.setting(row.modelData, "res").value === modelData.v
                                    onClicked: { root.selected = row.index; if (row.editable) root.setValue(row.modelData, "res", modelData.v); }
                                }
                            }
                            Item { width: 10; height: 1; visible: !!root.setting(row.modelData, "res") }
                            Repeater {
                                model: row.modelData.settings.filter(s => s.kind === "bool")
                                Chip {
                                    required property var modelData
                                    label: (modelData.value ? "✓ " : "") + modelData.label
                                    on: modelData.value
                                    onClicked: { root.selected = row.index; if (row.editable) root.setValue(row.modelData, modelData.key, !modelData.value); }
                                }
                            }
                        }
                        Item {
                            width: parent.width
                            height: Math.max(padNote.implicitHeight, padButton.height)
                            RiceText { id: padNote; anchors.verticalCenter: parent.verticalCenter; text: "controle: " + row.modelData.pad_note; color: Theme.faint; font.pixelSize: Theme.small }
                            AccentButton {
                                id: padButton
                                visible: row.modelData.pad === "apply"
                                anchors.right: parent.right
                                ghost: true
                                enabledState: row.editable
                                label: "APLICAR CONTROLE (c)"
                                onClicked: { root.selected = row.index; root.applyPad(row.modelData); }
                            }
                        }
                    }
                }
            }
        }
    }

    // ================= RIGHT: controle =================
    Column {
        anchors.top: titleText.bottom
        anchors.topMargin: 20
        anchors.right: parent.right
        width: parent.width * 0.42 - 24
        spacing: 10

        Label { text: "CONTROLE" }
        RiceText { visible: !root.pad; text: "[ -- ] nenhum controle conectado"; color: Theme.dim }
        Repeater {
            model: root.pads
            Column {
                required property var modelData
                width: parent.width
                spacing: 2
                RiceText { width: parent.width; elide: Text.ElideRight; text: modelData.name; font.weight: Font.Bold }
                RiceText {
                    width: parent.width
                    elide: Text.ElideRight
                    textFormat: Text.StyledText
                    font.pixelSize: Theme.small
                    color: Theme.dim
                    text: modelData.id + (modelData.battery !== null ? " · bateria " + modelData.battery + "%" : "")
                          + " · " + (modelData.mapped ? "<font color='" + Theme.ok + "'>mapeado em controllers.txt</font>" : "sem linha em controllers.txt (o SDL usa o que conhece)")
                }
            }
        }
        Row {
            visible: !!root.pad && root.mode === ""
            spacing: 8
            AccentButton { ghost: true; label: "TESTAR (t)"; onClicked: root.startTest() }
            AccentButton { ghost: true; label: "MAPEAR (m)"; onClicked: root.startMap() }
        }

        // Mapeamento: o passo atual.
        Column {
            visible: root.mode === "map"
            width: parent.width
            spacing: 6
            Label { text: "MAPEAR · " + (root.step + 1) + "/" + root.targets.length }
            RiceText { width: parent.width; wrapMode: Text.Wrap; text: "aperte: " + (root.targets[root.step] || ["", ""])[1]; color: Theme.accent; font.pixelSize: 16; font.weight: Font.Bold }
            RiceText { width: parent.width; wrapMode: Text.Wrap; text: root.binds.map(b => b.replace("=", " ")).join("  ·  ") || "—"; color: Theme.faint; font.pixelSize: Theme.small }
        }

        // Teste (e o que o mapeamento está vendo): botões, eixos e direcional.
        Column {
            visible: root.mode !== ""
            width: parent.width
            spacing: 8
            Label { text: "AO VIVO · " + root.buttonCount + " botões · " + root.axisCount + " eixos" }
            Flow {
                width: parent.width
                spacing: 4
                Repeater {
                    model: root.buttonCount
                    Rectangle {
                        required property int index
                        width: 30
                        height: 22
                        color: root.pressed[index] ? Theme.accent : "transparent"
                        border.width: 1
                        border.color: root.pressed[index] ? Theme.accent : Theme.line2
                        RiceText { anchors.centerIn: parent; text: "b" + index; font.pixelSize: 10; color: root.pressed[index] ? Theme.bg : Theme.dim }
                    }
                }
                Rectangle {
                    width: 46
                    height: 22
                    color: root.hat ? Theme.accent : "transparent"
                    border.width: 1
                    border.color: root.hat ? Theme.accent : Theme.line2
                    RiceText {
                        anchors.centerIn: parent
                        font.pixelSize: 10
                        color: root.hat ? Theme.bg : Theme.dim
                        text: root.hat ? ((root.hat & 1 ? "↑" : "") + (root.hat & 4 ? "↓" : "") + (root.hat & 8 ? "←" : "") + (root.hat & 2 ? "→" : "")) : "h0"
                    }
                }
            }
            Repeater {
                model: root.axisCount
                Row {
                    id: axisRow
                    required property int index
                    readonly property real v: root.axisValues[index] || 0
                    spacing: 8
                    RiceText { width: 24; text: "a" + index; font.pixelSize: 10; color: Theme.dim }
                    Item {
                        width: 160
                        height: 10
                        anchors.verticalCenter: parent.verticalCenter
                        Rectangle { y: 4; width: parent.width; height: 2; color: Theme.line2 }
                        Rectangle { x: parent.width / 2 - 1; width: 2; height: 10; color: Theme.line2 }
                        Rectangle {
                            x: axisRow.v < 0 ? parent.width / 2 * (1 + axisRow.v) : parent.width / 2
                            y: 3
                            width: Math.abs(axisRow.v) * parent.width / 2
                            height: 4
                            color: Theme.accent
                        }
                    }
                    RiceText { text: v.toFixed(2); font.pixelSize: 10; color: Theme.faint }
                }
            }
        }
    }
}
