import QtQuick
import Quickshell
import qs
import qs.components

// LW // PALETTE — colors by role, compare with the previous generation, matugen scheme
// chips that really regenerate, and a preview painted with the colors Waybar and Kitty use.
Item {
    id: root

    property Item keyTarget: null
    property var current: ({})
    property bool compare: false
    property bool armedRestore: false

    readonly property var hints: [["c", "compare"], ["g", "regenerate"], ["r", "restore"]]
    readonly property bool busy: regenerate.running || restore.running
    readonly property var groups: [
        { name: "BASE", keys: ["background", "foreground", "muted", "accent"] },
        { name: "ANSI", keys: ["red", "green", "yellow", "blue", "magenta", "cyan"] },
        { name: "BAR", keys: ["bar_foreground", "bar_window", "bar_workspace", "bar_accent", "bar_clock", "bar_cpu", "bar_memory", "bar_volume"] }
    ]
    readonly property var colors: current.colors || ({})
    readonly property var before: current.previous ? current.previous.colors || ({}) : ({})
    readonly property int changed: Object.keys(colors).filter(k => before[k] && before[k].toLowerCase() !== colors[k].toLowerCase()).length

    function stem(path) { return String(path || "").split("/").pop().replace(/\.[^.]+$/, ""); }
    function differs(key) { return !!before[key] && before[key].toLowerCase() !== String(colors[key]).toLowerCase(); }

    function run(args, label) {
        if (busy)
            return;
        Status.start(label);
        regenerate.call(args);
    }
    function doRestore() {
        if (busy || current.can_restore !== true)
            return;
        Status.start("restoring palette");
        restore.call(["palette", "restore", "--json"]);
    }
    function finished(data, warnings) {
        Status.stop();
        if (warnings.length > 0)
            Status.say("[ WARN ] " + warnings.join("; "), Theme.yel);
        else
            Status.say("[ OK ] palette " + data.result);
        show.call(["palette", "show", "--json"]);
    }
    function copy(key) {
        Quickshell.execDetached(["wl-copy", "--", colors[key]]);
        Status.say("[ OK ] " + key + " " + colors[key] + " copiado");
    }

    function handleKey(event) {
        switch (event.key) {
        case Qt.Key_C: compare = !compare; return true;
        case Qt.Key_G: run(["palette", "regenerate", "--json"], "regenerating"); return true;
        case Qt.Key_R: doRestore(); return true;
        }
        return false;
    }

    Component.onCompleted: show.call(["palette", "show", "--json"])
    Connections {
        target: Theme
        function onDarkChanged() { show.call(["palette", "show", "--json"]); }
    }

    RiceCommand {
        id: show
        onSucceeded: data => root.current = data
        onFailed: message => Status.say("[ FAIL ] " + message, Theme.red)
    }
    RiceCommand {
        id: regenerate
        onSucceeded: (data, warnings) => root.finished(data, warnings)
        onFailed: message => { Status.stop(); Status.say("[ FAIL ] " + message, Theme.red); }
    }
    RiceCommand {
        id: restore
        onSucceeded: (data, warnings) => root.finished(data, warnings)
        onFailed: message => { Status.stop(); Status.say("[ FAIL ] " + message, Theme.red); }
    }
    Timer { id: disarm; interval: 3000; onTriggered: root.armedRestore = false }

    RiceHeader {
        id: title
        title: "LW // PALETTE"
        note: root.current.emergency ? "emergency" : ""
    }

    // CURRENT // matugen 4.2 · scheme-neutral · dark · wallpaper
    Item {
        id: meta
        anchors.top: title.bottom
        anchors.topMargin: 14
        width: parent.width
        height: metaText.implicitHeight
        RiceText {
            id: metaText
            width: parent.width - hint.width - 14
            elide: Text.ElideRight
            textFormat: Text.StyledText
            color: Theme.dim
            readonly property var parts: String(root.current.generator || "").split("/").map(s => s.trim())
            text: "CURRENT <font color='" + Theme.faint + "'>//</font> " + (parts[0] || "")
                  + " · <font color='" + Theme.fg + "'>scheme-" + (root.current.scheme || "?") + "</font>"
                  + " · <font color='" + Theme.fg + "'>" + (root.current.mode || "") + "</font>"
                  + " · " + root.stem(root.current.wallpaper)
        }
        RiceText {
            id: hint
            anchors.right: parent.right
            text: "clique na cor = copiar hex"
            color: Theme.faint
            font.pixelSize: Theme.small
        }
    }

    // SCHEME chips · MODE chips · COMPARE
    Item {
        id: chips
        anchors.top: meta.bottom
        anchors.topMargin: 8
        width: parent.width
        height: compareChip.height
        Row {
            spacing: 6
            RiceText { anchors.verticalCenter: parent.verticalCenter; text: "SCHEME "; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5 }
            Repeater {
                model: root.current.schemes || []
                Chip {
                    required property string modelData
                    label: modelData
                    on: root.current.scheme === modelData
                    opacity: root.busy && !on ? 0.5 : 1
                    onClicked: if (!on) root.run(["palette", "regenerate", "--scheme", modelData, "--json"], "regenerating scheme-" + modelData)
                }
            }
            Item { width: 14; height: 1 }
            RiceText { anchors.verticalCenter: parent.verticalCenter; text: "MODE "; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5 }
            Chip { label: "dark"; on: root.current.mode === "dark" }
            Chip {
                id: lightChip
                label: "light"
                opacity: 0.35
                onClicked: Status.say("[ -- ] light não existe: Kitty, Waybar e Noctalia do rice são só dark", Theme.dim)
            }
        }
        Chip {
            id: compareChip
            anchors.right: parent.right
            label: "COMPARE"
            on: root.compare
            onClicked: root.compare = !root.compare
        }
    }

    // ================= SWATCHES =================
    Flickable {
        id: swatches
        anchors.top: chips.bottom
        anchors.topMargin: 14
        anchors.bottom: foot.top
        anchors.bottomMargin: 12
        anchors.left: parent.left
        anchors.right: preview.left
        anchors.rightMargin: 20
        clip: true
        contentHeight: groupColumn.height
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: groupColumn
            width: parent.width
            spacing: 18

            Repeater {
                model: root.groups
                Column {
                    id: group
                    required property var modelData
                    width: groupColumn.width
                    spacing: 8
                    RiceText { text: group.modelData.name; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5 }
                    Grid {
                        id: grid
                        width: parent.width
                        columns: Math.max(1, Math.floor((width + 12) / 130))
                        columnSpacing: 12
                        rowSpacing: 12
                        Repeater {
                            model: group.modelData.keys
                            Item {
                                id: swatch
                                required property string modelData
                                readonly property bool changedHere: root.differs(modelData)
                                width: (grid.width - (grid.columns - 1) * 12) / grid.columns
                                height: square.height + names.height + 5

                                Rectangle {
                                    id: square
                                    width: parent.width
                                    height: 38
                                    color: root.colors[swatch.modelData] || "transparent"
                                    border.width: 1
                                    border.color: Theme.line2
                                    clip: true
                                    transform: Translate { y: swatchMouse.containsMouse ? -2 : 0 }
                                    Behavior on color { ColorAnimation { duration: Theme.tMed } }
                                    // COMPARE: the previous color fills the lower part.
                                    Rectangle {
                                        anchors.bottom: parent.bottom
                                        anchors.bottomMargin: 1
                                        x: 1
                                        width: parent.width - 2
                                        height: root.compare ? Math.round((parent.height - 2) * 0.42) : 0
                                        color: root.before[swatch.modelData] || parent.color
                                        Behavior on height { NumberAnimation { duration: Theme.tMed; easing.type: Theme.ease } }
                                    }
                                }
                                Column {
                                    id: names
                                    anchors.top: square.bottom
                                    anchors.topMargin: 5
                                    width: parent.width
                                    Row {
                                        RiceText { text: swatch.modelData; font.pixelSize: Theme.small }
                                        RiceText { visible: root.compare && swatch.changedHere; text: " •"; color: Theme.accent; font.pixelSize: Theme.small }
                                    }
                                    RiceText {
                                        width: parent.width
                                        elide: Text.ElideRight
                                        text: root.compare && swatch.changedHere ? root.colors[swatch.modelData] + " ← " + root.before[swatch.modelData] : (root.colors[swatch.modelData] || "")
                                        color: Theme.faint
                                        font.pixelSize: 10
                                    }
                                }
                                MouseArea {
                                    id: swatchMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.copy(swatch.modelData)
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ================= PREVIEW =================
    Rectangle {
        id: preview
        anchors.top: chips.bottom
        anchors.topMargin: 14
        anchors.bottom: foot.top
        anchors.bottomMargin: 12
        anchors.right: parent.right
        width: 300
        color: Theme.panel
        border.width: 1
        border.color: Theme.line

        readonly property var bar: root.current.waybar || ({})
        readonly property var kitty: root.current.kitty || ({})
        function tint(map, key, fallback) {
            const value = map[key];
            return value && value !== "transparent" ? value : fallback;
        }
        function span(color, text) { return "<font color='" + color + "'>" + text + "</font>"; }

        Column {
            x: 16
            y: 16
            width: parent.width - 32
            spacing: 5

            RiceText { text: "WAYBAR"; color: Theme.faint; font.pixelSize: 10; font.letterSpacing: 1.5 }
            Rectangle {
                width: parent.width
                height: 70
                color: Theme.raise
                border.width: 1
                border.color: Theme.line
                clip: true
                Image {
                    anchors.fill: parent
                    anchors.margins: 1
                    source: root.current.thumb ? "file://" + root.current.thumb : ""
                    fillMode: Image.PreserveAspectCrop
                    verticalAlignment: Image.AlignTop
                    asynchronous: true
                }
                // The same modules and separators as config/waybar, in its real colors.
                RiceText {
                    x: 8
                    y: 4
                    width: parent.width - 16
                    textFormat: Text.StyledText
                    font.pixelSize: 10
                    readonly property var b: preview.bar
                    text: preview.span(preview.tint(b, "active_fg", Theme.accent), "1") + " "
                          + preview.span(preview.tint(b, "workspace", Theme.fg), "2 3")
                }
                RiceText {
                    anchors.right: parent.right
                    anchors.rightMargin: 8
                    y: 4
                    textFormat: Text.StyledText
                    font.pixelSize: 10
                    readonly property var b: preview.bar
                    readonly property string sep: preview.span(Qt.alpha(preview.tint(b, "text", "#ffffff"), 0.4), " | ")
                    text: preview.span(preview.tint(b, "cpu", Theme.ok), "CPU 2%") + sep
                          + preview.span(preview.tint(b, "memory", Theme.yel), "RAM 3G") + sep
                          + preview.span(preview.tint(b, "volume", Theme.cyan), "VOL 40") + sep
                          + preview.span(preview.tint(b, "clock", Theme.accent), Qt.formatTime(new Date(), "hh:mm"))
                }
            }

            Item { width: 1; height: 7 }
            RiceText { text: "KITTY"; color: Theme.faint; font.pixelSize: 10; font.letterSpacing: 1.5 }
            Rectangle {
                width: parent.width
                height: term.implicitHeight + 20
                color: preview.tint(preview.kitty, "background", Theme.bg)
                border.width: 1
                border.color: Theme.line
                Behavior on color { ColorAnimation { duration: Theme.tMed } }
                RiceText {
                    id: term
                    x: 10
                    y: 10
                    width: parent.width - 20
                    textFormat: Text.StyledText
                    font.pixelSize: 11
                    lineHeight: 1.3
                    readonly property var k: preview.kitty
                    function c(n, text) { return preview.span(preview.tint(k, "color" + n, Theme.fg), text); }
                    color: preview.tint(k, "foreground", Theme.fg)
                    text: c(4, "~/rice") + " " + c(8, "&gt;") + " git status<br>"
                          + c(2, "  modified: hyprland.lua") + "<br>"
                          + c(1, "  deleted:  old.conf") + "<br>"
                          + c(3, "warning:") + " 2 files changed<br>"
                          + c(5, "fn") + " " + c(6, "main") + "() { " + c(8, "// todo") + " }"
                }
            }

            Item { width: 1; height: 7 }
            RiceText { text: "ACCENT"; color: Theme.faint; font.pixelSize: 10; font.letterSpacing: 1.5 }
            Row {
                spacing: 6
                Rectangle {
                    width: activeText.implicitWidth + 14
                    height: 22
                    color: "transparent"
                    border.width: 1
                    border.color: Theme.accent
                    RiceText { id: activeText; anchors.centerIn: parent; text: "[ 1 ] ATIVO"; color: Theme.accent; font.pixelSize: 11 }
                }
                Rectangle {
                    width: idleText.implicitWidth + 14
                    height: 22
                    color: "transparent"
                    border.width: 1
                    border.color: Theme.line2
                    RiceText { id: idleText; anchors.centerIn: parent; text: "[ 2 ] inativo"; color: Theme.dim; font.pixelSize: 11 }
                }
            }
        }
    }

    // Footer
    Item {
        id: foot
        anchors.bottom: parent.bottom
        width: parent.width
        height: regenerateButton.height + 10
        Rectangle { width: parent.width; height: 1; color: Theme.line }

        RiceText {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 4
            width: parent.width - buttons.width - 14
            elide: Text.ElideRight
            color: Theme.dim
            text: root.current.previous
                ? root.changed + " cores diferentes de " + root.stem(root.current.previous.wallpaper)
                : "sem paleta anterior"
        }
        Row {
            id: buttons
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            spacing: 8
            AccentButton {
                ghost: true
                label: root.armedRestore ? "CONFIRM?" : "RESTORE PREVIOUS"
                enabledState: !root.busy && root.current.can_restore === true
                onClicked: {
                    if (root.armedRestore) { root.armedRestore = false; root.doRestore(); }
                    else { root.armedRestore = true; disarm.restart(); }
                }
            }
            AccentButton {
                id: regenerateButton
                label: regenerate.running ? "RUNNING" : "REGENERATE"
                enabledState: !root.busy
                onClicked: root.run(["palette", "regenerate", "--json"], "regenerating")
            }
        }
    }
}
