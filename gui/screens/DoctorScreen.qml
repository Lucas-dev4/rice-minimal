// DoctorScreen.qml — tela Doctor (SISTEMA): roda "lw doctor --stream" e mostra cada checagem
// chegando ao vivo, agrupada (sessão, serviços, módulos...), com contagem de OK/WARN/FAIL.
// As dependências vêm com `module` e ficam no grupo do módulo; INFO é opcional que falta, não problema.
import QtQuick
import Quickshell.Io
import qs
import qs.components

// LW // DOCTOR — big counters, segmented health bar, problems first, OK groups folded.
// `rice doctor --stream` sends one line per check, so RUN AGAIN shows real progress.
Item {
    id: root

    property Item keyTarget: null
    property var results: []
    property bool running: false
    property var closed: groupOrder.slice()
    property string currentKey: ""
    property string error: ""

    readonly property var groupOrder: ["SESSION", "SERVICES", "CONFIG"].concat(Modules.active.map(m => m.name), ["INSTALAR"])
    readonly property var hints: [["↑↓", "move"], ["←→", "grupos"], ["r", "run"]]

    // Em qual grupo cada checagem aparece.
    function groupOf(item) {
        const name = item.name;
        if (item.module) return (Modules.active.find(m => m.id === item.module) || { name: "CONFIG" }).name;
        if (/^Pacotes /.test(name)) return "INSTALAR";
        if (["Hyprland version", "Hyprland Lua errors", "Lua appearance include", "UWSM graphical session",
             "Wayland portals", "Persistent appearance profile"].indexOf(name) >= 0) return "SESSION";
        if (/Waybar|Noctalia|PipeWire|NetworkManager|locker|Greeter|Lock|LOCKED/.test(name)) return "SERVICES";
        return "CONFIG";
    }

    // Two modules may need the same program: the name alone does not identify a line.
    function keyOf(item) { return (item.module || "") + "/" + item.name; }

    // Readable detail: JSON becomes a short summary, multi-line output one line.
    function detail(item) {
        const text = String(item.detail || "").trim();
        if (text.startsWith("{")) {
            try {
                const d = JSON.parse(text);
                if ("barVisible" in d || "locked" in d)
                    return "running · " + (d.barVisible ? "bar visível" : "bar oculta (Waybar em uso)")
                           + " · " + (d.panelOpen ? "painel " + (d.activePanelId || "aberto") : "painel fechado")
                           + " · " + (d.locked ? "bloqueado" : "desbloqueado");
                return Object.keys(d).map(k => k + ": " + d[k]).join(" · ");
            } catch (error) {}
        }
        return text;
    }

    // Quantas checagens têm esse status.
    function count(status) { return results.filter(r => r.status === status).length; }
    readonly property var issues: results.filter(r => r.status === "WARN" || r.status === "FAIL")
    readonly property var entries: {
        const out = [];
        const needle = "";
        if (issues.length) {
            out.push({ group: "ATTENTION", label: String(issues.length), attention: true });
            for (const r of issues) out.push({ item: r });
        }
        for (const g of groupOrder) {
            // By status, not identity: var lists may be copies.
            const rows = results.filter(r => groupOf(r) === g && r.status !== "WARN" && r.status !== "FAIL");
            if (!rows.length) continue;
            const ok = rows.filter(r => r.status === "OK").length;
            const info = rows.filter(r => r.status === "INFO").length;
            const shut = closed.indexOf(g) >= 0;
            out.push({ group: g, label: rows.length === info ? "opcional" : ok + "/" + (rows.length - info) + " ok" + (info ? " · " + info + (info > 1 ? " opcionais faltam" : " opcional falta") : ""), shut: shut });
            if (!shut) for (const r of rows) out.push({ item: r });
        }
        return out;
    }
    readonly property var visibleKeys: entries.filter(e => e.item).map(e => keyOf(e.item))

    // Roda o doctor de novo.
    function run() {
        if (running)
            return;
        error = "";
        running = true;
        // Every known check waits as [ .. ] until its line arrives.
        results = results.map(r => Object.assign({}, r, { status: "RUN", detail: "" }));
        closed = [];
        doctor.seen = [];
        doctor.running = true;
    }
    // Move a seleção.
    function move(step) {
        const keys = visibleKeys;
        if (!keys.length) return;
        const at = keys.indexOf(currentKey);
        currentKey = keys[Math.max(0, Math.min(keys.length - 1, at < 0 ? 0 : at + step))];
    }

    // Teclas da tela (setas, r rodar de novo).
    function handleKey(event) {
        switch (event.key) {
        case Qt.Key_Up: move(-1); return true;
        case Qt.Key_Down: move(1); return true;
        case Qt.Key_Right: closed = []; return true;
        case Qt.Key_Left: closed = groupOrder.slice(); return true;
        case Qt.Key_R: run(); return true;
        }
        return false;
    }

    Component.onCompleted: run()

    Process {
        id: doctor
        property var seen: []
        command: Theme.rice.concat(["doctor", "--stream"])
        stdout: SplitParser {
            onRead: line => {
                let item;
                try { item = JSON.parse(line); } catch (error) { return; }
                doctor.seen.push(root.keyOf(item));
                const next = root.results.slice();
                const at = next.findIndex(r => root.keyOf(r) === root.keyOf(item));
                if (at >= 0) next[at] = item; else next.push(item);
                root.results = next;
            }
        }
        stderr: StdioCollector { id: doctorErr }
        // Lines may still be in the pipe when the process exits; finish a moment later.
        onExited: code => { finishTimer.code = code; finishTimer.restart(); }
    }
    Timer {
        id: finishTimer
        property int code: 0
        interval: 60
        onTriggered: {
            const code = finishTimer.code;
            // Drop checks that no longer exist; fold the groups again.
            root.results = root.results.filter(r => doctor.seen.indexOf(root.keyOf(r)) >= 0);
            root.running = false;
            // What to install stays open.
            root.closed = root.groupOrder.filter(g => g !== "INSTALAR");
            if (root.visibleKeys.indexOf(root.currentKey) < 0)
                root.currentKey = root.visibleKeys[0] || "";
            if (root.results.length === 0)
                root.error = doctorErr.text.trim() || "doctor exited " + code;
            const bad = root.issues.length;
            Status.say(bad ? "[ !! ] doctor: " + bad + " item(s) pedem atenção" : "[ OK ] doctor: all checks passed",
                       bad ? Theme.yel : Theme.ok);
        }
    }

    RiceHeader {
        id: title
        title: "DOCTOR"
        note: root.count("OK") + "/" + (root.results.length - root.count("INFO"))
    }

    // Big counters
    Row {
        id: counters
        anchors.top: title.bottom
        anchors.topMargin: 14
        spacing: 28
        Repeater {
            model: [["OK", "ok"], ["WARN", "warn"], ["FAIL", "fail"]]
            Row {
                required property var modelData
                spacing: 6
                RiceText {
                    text: root.count(modelData[0])
                    font.pixelSize: 28
                    font.bold: true
                    color: Theme.statusColor(modelData[0])
                }
                RiceText { anchors.baseline: parent.children[0].baseline; text: modelData[1]; color: Theme.dim }
            }
        }
        RiceText {
            visible: root.running
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 6
            text: "running… " + root.results.filter(r => r.status !== "RUN").length + "/" + root.results.length
            color: Theme.accent
        }
    }

    // Segmented health bar: one segment per check.
    Row {
        id: health
        anchors.top: counters.bottom
        anchors.topMargin: 10
        width: parent.width
        height: 4
        spacing: 2
        Repeater {
            model: root.results
            Rectangle {
                required property var modelData
                width: (health.width - (root.results.length - 1) * 2) / Math.max(1, root.results.length)
                height: 4
                color: modelData.status === "RUN" ? Theme.line : Theme.statusColor(modelData.status)
                Behavior on color { ColorAnimation { duration: Theme.tFast } }
            }
        }
    }

    RiceText {
        id: failure
        anchors.top: health.bottom
        anchors.topMargin: 10
        width: parent.width
        visible: root.error !== ""
        text: "[ FAIL ] " + root.error
        color: Theme.red
        wrapMode: Text.Wrap
    }

    ListView {
        id: list
        anchors.top: failure.visible ? failure.bottom : health.bottom
        anchors.topMargin: 12
        anchors.bottom: foot.top
        anchors.bottomMargin: 10
        width: parent.width
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: root.entries

        delegate: Item {
            id: entry
            required property var modelData
            readonly property bool isGroup: modelData.group !== undefined
            readonly property var item: modelData.item || null
            readonly property bool current: !isGroup && root.keyOf(item) === root.currentKey

            width: ListView.view.width
            height: isGroup ? 30 : rowText.height + 8

            // ▾ GROUP  n/m ok
            Row {
                visible: entry.isGroup
                x: 10
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 6
                spacing: 8
                RiceText {
                    text: "▾"
                    color: Theme.faint
                    rotation: entry.modelData.shut ? -90 : 0
                    Behavior on rotation { NumberAnimation { duration: Theme.tFast; easing.type: Theme.ease } }
                }
                RiceText {
                    text: entry.modelData.group || ""
                    color: entry.modelData.attention ? Theme.yel : groupMouse.containsMouse ? Theme.dim : Theme.faint
                    font.pixelSize: Theme.small
                    font.letterSpacing: 1.5
                }
                RiceText { text: entry.modelData.label || ""; color: Theme.dim; font.pixelSize: Theme.small }
            }
            MouseArea {
                id: groupMouse
                visible: entry.isGroup && !entry.modelData.attention
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    const g = entry.modelData.group;
                    root.closed = root.closed.indexOf(g) >= 0 ? root.closed.filter(x => x !== g) : root.closed.concat([g]);
                }
            }

            // [ OK ]  name  detail
            Rectangle {
                visible: !entry.isGroup
                anchors.fill: parent
                color: entry.current ? Theme.accentA : rowMouse.containsMouse ? Qt.alpha(Theme.fg, 0.025) : "transparent"
                Rectangle { width: 2; height: parent.height; color: entry.current ? Theme.accent : "transparent" }
            }
            Item {
                id: rowText
                visible: !entry.isGroup
                y: 4
                width: parent.width
                height: Math.max(nameText.implicitHeight, detailText.implicitHeight)
                RiceText {
                    x: 10
                    text: !entry.item ? "" : entry.item.status === "RUN" ? "[ .. ]" : entry.item.status === "OK" ? "[ OK ]" : "[" + entry.item.status + "]"
                    color: !entry.item ? Theme.dim : entry.item.status === "RUN" ? Theme.accent : Theme.statusColor(entry.item.status)
                }
                RiceText {
                    id: nameText
                    x: 82
                    width: 240
                    elide: Text.ElideRight
                    text: entry.item ? entry.item.name : ""
                    color: entry.item && entry.item.status === "INFO" ? Theme.faint : Theme.text
                }
                RiceText {
                    id: detailText
                    x: 332
                    width: parent.width - x - 10
                    // Long text is cut; the row under the cursor shows all of it.
                    text: entry.item ? (entry.current ? String(entry.item.detail || "").trim() || root.detail(entry.item) : root.detail(entry.item).replace(/\s*\n\s*/g, " ")) : ""
                    wrapMode: entry.current ? Text.WrapAnywhere : Text.NoWrap
                    elide: entry.current ? Text.ElideNone : Text.ElideRight
                    maximumLineCount: entry.current ? 30 : 1
                    color: entry.current ? Theme.fg : entry.item && entry.item.status === "INFO" ? Theme.faint : Theme.dim
                }
            }
            MouseArea {
                id: rowMouse
                visible: !entry.isGroup
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: { root.currentKey = root.keyOf(entry.item); root.keyTarget.forceActiveFocus(); }
            }
        }
    }

    Item {
        id: foot
        anchors.bottom: parent.bottom
        width: parent.width
        height: runButton.height + 10
        Rectangle { width: parent.width; height: 1; color: Theme.line }
        RiceText {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 4
            color: Theme.dim
            text: root.running ? "" : root.issues.length ? root.issues.length + " item(s) pedem atenção" : "tudo certo"
        }
        AccentButton {
            id: runButton
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            label: root.running ? "RUNNING" : "RUN AGAIN"
            enabledState: !root.running
            onClicked: root.run()
        }
    }
}
