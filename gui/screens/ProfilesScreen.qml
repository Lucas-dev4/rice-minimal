import QtQuick
import qs
import qs.components

// LW // PROFILES — two cards with a live mini preview and a table of the real differences.
Item {
    id: root

    property Item keyTarget: null
    property var info: ({})
    property int selected: 0
    property bool armedRestore: false

    readonly property var names: ["minimal", "refined"]
    readonly property var rows: (info.differences || []).concat([
        // This window follows the profile too (Theme.motion).
        { setting: "LW control animations", minimal: "off", refined: "on" }
    ])
    readonly property var hints: [["hl", "escolher"], ["⏎", "apply"], ["r", "restore"]]
    readonly property bool busy: changer.running

    function row(name) { return rows.find(r => r.setting === name) || null; }
    // Workspace slide duration in ms, from the real table ("slide 160 ms" -> 160).
    function slideMs(profile) {
        const r = row("workspace switch");
        const m = r ? /(\d+)\s*ms/.exec(r[profile]) : null;
        return m ? parseInt(m[1]) : 0;
    }
    function describe(profile) {
        const ws = row("workspace switch");
        const anim = profile === "minimal" ? "Shell animations off." : "Shell animations on.";
        if (!ws) return anim;
        return anim + "\n" + (ws[profile] === "instant" ? "Instant workspace changes." : ws[profile].replace(/^\w/, c => c.toUpperCase()) + " workspace transition.");
    }

    function apply() {
        const name = names[selected];
        if (busy || name === info.profile)
            return;
        Status.start("switching to " + name);
        changer.call(["profile", "set", name, "--json"]);
    }
    function restore() {
        if (busy || !info.previous || info.previous === info.profile)
            return;
        Status.start("restoring " + info.previous);
        changer.call(["profile", "restore", "--json"]);
    }

    function handleKey(event) {
        switch (event.key) {
        case Qt.Key_Left: case Qt.Key_H: selected = 0; return true;
        case Qt.Key_Right: case Qt.Key_L: selected = 1; return true;
        case Qt.Key_Return: case Qt.Key_Enter: apply(); return true;
        case Qt.Key_R: restore(); return true;
        }
        return false;
    }

    Component.onCompleted: reader.call(["profile", "get", "--json"])
    function externalChange() { reader.call(["profile", "get", "--json"]); }

    RiceCommand {
        id: reader
        onSucceeded: data => {
            const first = root.info.profile === undefined;
            root.info = data;
            if (first)
                root.selected = Math.max(0, root.names.indexOf(data.profile));
        }
        onFailed: message => Status.say("[ FAIL ] " + message, Theme.red)
    }
    RiceCommand {
        id: changer
        onSucceeded: data => {
            Status.stop();
            root.info = data;
            Status.say("[ OK ] profile " + data.profile + " applied");
        }
        onFailed: message => { Status.stop(); Status.say("[ FAIL ] " + message, Theme.red); }
    }
    Timer { id: disarm; interval: 3000; onTriggered: root.armedRestore = false }

    // Both previews switch workspace together, so the difference is side by side.
    property bool second: false
    Timer { running: true; interval: 1600; repeat: true; onTriggered: root.second = !root.second }

    RiceHeader {
        id: title
        title: "LW // PROFILES"
    }

    Row {
        id: cards
        anchors.top: title.bottom
        anchors.topMargin: 14
        width: parent.width
        spacing: 16

        Repeater {
            model: root.names

            Rectangle {
                id: card

                required property string modelData
                required property int index
                readonly property bool sel: root.selected === index
                readonly property bool active: root.info.profile === modelData
                readonly property int ms: root.slideMs(modelData)

                width: (parent.width - 16) / 2
                height: content.height + 28
                color: Theme.panel
                border.width: 1
                border.color: sel ? Theme.accent : mouse.containsMouse ? Theme.line2 : Theme.line
                transform: Translate { y: mouse.containsMouse && !card.sel ? -2 : 0 }
                Behavior on border.color { ColorAnimation { duration: Theme.tFast } }

                Column {
                    id: content
                    x: 14
                    y: 14
                    width: parent.width - 28
                    spacing: 10

                    Item {
                        width: parent.width
                        height: nameText.implicitHeight
                        RiceText {
                            id: nameText
                            text: card.modelData.toUpperCase()
                            font.bold: true
                            font.letterSpacing: 0.6
                            color: card.sel ? Theme.accent : Theme.fg
                        }
                        Tag {
                            anchors.right: parent.right
                            anchors.verticalCenter: nameText.verticalCenter
                            visible: card.active
                            label: "● ACTIVE"
                            tint: Theme.ok
                        }
                    }

                    // Mini desktop: workspace 1 (two windows) <-> workspace 2 (one window).
                    Rectangle {
                        width: parent.width
                        height: 140
                        color: Theme.raise
                        border.width: 1
                        border.color: Theme.line
                        clip: true

                        Image {
                            anchors.fill: parent
                            anchors.margins: 1
                            source: Status.wallpaper ? "file://" + Status.wallpaper : ""
                            sourceSize.width: 420
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                        }

                        Row {
                            id: track
                            height: parent.height
                            x: root.second ? -parent.width : 0
                            Behavior on x { NumberAnimation { duration: card.ms; easing.type: Easing.OutCubic } }

                            Repeater {
                                model: 2
                                Item {
                                    required property int index
                                    width: track.parent.width
                                    height: track.height
                                    Row {
                                        anchors.fill: parent
                                        anchors.margins: 4
                                        spacing: 4
                                        Repeater {
                                            model: parent.parent.index === 0 ? [0.58, 0.42] : [1]
                                            Rectangle {
                                                required property real modelData
                                                width: (parent.width - (parent.parent.index === 0 ? 4 : 0)) * modelData
                                                height: parent.height
                                                color: Qt.alpha(Theme.bg, 0.95)
                                                border.width: 1
                                                border.color: Theme.line2
                                                RiceText { x: 5; y: 2; text: "● ● ●"; color: Theme.faint; font.pixelSize: 6 }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Rectangle {
                            anchors.right: parent.right
                            anchors.rightMargin: 6
                            y: 5
                            width: wsLabel.implicitWidth + 10
                            height: wsLabel.implicitHeight
                            color: Qt.alpha(Theme.bg, 0.85)
                            RiceText {
                                id: wsLabel
                                anchors.centerIn: parent
                                text: root.second ? "ws 2" : "ws 1"
                                color: Theme.accent
                                font.pixelSize: 10
                            }
                        }
                    }

                    RiceText {
                        text: root.describe(card.modelData)
                        color: Theme.dim
                    }
                }

                MouseArea {
                    id: mouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: { root.selected = card.index; root.keyTarget.forceActiveFocus(); }
                    onDoubleClicked: root.apply()
                }
            }
        }
    }

    RiceText {
        id: diffLabel
        anchors.top: cards.bottom
        anchors.topMargin: 22
        text: "DIFERENÇAS"
        color: Theme.faint
        font.pixelSize: Theme.small
        font.letterSpacing: 1.5
    }

    // SETTING | MINIMAL | REFINED — only rows that differ, values read from the real files.
    Rectangle {
        id: table
        anchors.top: diffLabel.bottom
        anchors.topMargin: 8
        width: parent.width
        height: tableColumn.height
        color: "transparent"
        border.width: 1
        border.color: Theme.line

        Column {
            id: tableColumn
            width: parent.width
            Repeater {
                model: [{ setting: "SETTING", minimal: "MINIMAL", refined: "REFINED", head: true }].concat(root.rows)
                Item {
                    id: tr
                    required property var modelData
                    required property int index
                    width: tableColumn.width
                    height: 28
                    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line; visible: tr.index < root.rows.length }
                    Row {
                        anchors.fill: parent
                        Repeater {
                            model: ["setting", "minimal", "refined"]
                            Rectangle {
                                required property string modelData
                                required property int index
                                readonly property bool valueCell: index > 0 && !tr.modelData.head
                                readonly property bool on: index > 0 && root.names[index - 1] === root.names[root.selected]
                                width: index === 0 ? 320 : (tr.width - 320) / 2
                                height: tr.height - 1
                                color: valueCell ? Theme.accentA : "transparent"
                                RiceText {
                                    anchors.verticalCenter: parent.verticalCenter
                                    x: 12
                                    width: parent.width - 24
                                    elide: Text.ElideRight
                                    text: tr.modelData[parent.modelData]
                                    font.pixelSize: tr.modelData.head ? Theme.small : Theme.fontSize
                                    font.letterSpacing: tr.modelData.head ? 1.5 : 0
                                    color: tr.modelData.head ? (parent.on ? Theme.accent : Theme.faint)
                                         : parent.on ? Theme.accent : Theme.dim
                                    Behavior on color { ColorAnimation { duration: Theme.tFast } }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    RiceText {
        anchors.top: table.bottom
        anchors.topMargin: 8
        text: "Arredondamento, blur e opacidade são iguais nos dois perfis."
        color: Theme.faint
        font.pixelSize: Theme.small
    }

    // Footer
    Item {
        anchors.bottom: parent.bottom
        width: parent.width
        height: applyButton.height + 10
        Rectangle { width: parent.width; height: 1; color: Theme.line }

        RiceText {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 4
            text: root.names[root.selected] === root.info.profile ? "perfil já ativo" : "⏎ pra aplicar " + root.names[root.selected]
            color: Theme.dim
        }
        Row {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            spacing: 8
            AccentButton {
                ghost: true
                label: root.armedRestore ? "CONFIRM?" : "RESTORE PREVIOUS" + (root.info.previous ? ": " + root.info.previous.toUpperCase() : "")
                enabledState: !root.busy && !!root.info.previous && root.info.previous !== root.info.profile
                onClicked: {
                    if (root.armedRestore) { root.armedRestore = false; root.restore(); }
                    else { root.armedRestore = true; disarm.restart(); }
                }
            }
            AccentButton {
                id: applyButton
                label: root.busy ? "APPLYING" : "APPLY ⏎"
                enabledState: !root.busy && root.names[root.selected] !== root.info.profile
                onClicked: root.apply()
            }
        }
    }
}
