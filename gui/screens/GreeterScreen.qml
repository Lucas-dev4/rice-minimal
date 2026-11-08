import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.components

// LW // GREETER — preview of the login screen with the image that WAS SENT,
// built from config/greeter/greeter.toml (clock above the panel, user, session).
Item {
    id: root

    property Item keyTarget: null
    property var info: ({})
    property var greeter: ({})
    property date now: new Date()
    property bool syncing: false

    readonly property var hints: [["s", "sync"], ["a", "auto"]]
    readonly property bool imageMatch: info.image_match === true

    function refresh() { reader.call(["greeter", "status", "--json"]); }
    function sync() {
        if (syncing) return;
        syncing = true;
        Status.start("syncing greeter");
        syncer.call(["greeter", "sync", "--json"]);
    }
    function toggleAuto() { toggler.call(["greeter", "auto", info.auto_sync ? "off" : "on", "--json"]); }
    function ago(ns) {
        if (!ns) return "";
        const m = Math.floor((now.getTime() - ns / 1e6) / 60000);
        if (m < 1) return "agora mesmo";
        if (m < 60) return "há " + m + " min";
        if (m < 1440) return "há " + Math.floor(m / 60) + "h " + (m % 60) + "min";
        return "há " + Math.floor(m / 1440) + " d";
    }
    // strftime subset used by greeter.toml: %d %m %Y %H %M
    function strftime(format, d) {
        return String(format || "").replace(/%d/g, Qt.formatDate(d, "dd")).replace(/%m/g, Qt.formatDate(d, "MM"))
            .replace(/%Y/g, Qt.formatDate(d, "yyyy")).replace(/%H/g, Qt.formatTime(d, "hh")).replace(/%M/g, Qt.formatTime(d, "mm"));
    }

    function handleKey(event) {
        switch (event.key) {
        case Qt.Key_S: sync(); return true;
        case Qt.Key_A: toggleAuto(); return true;
        }
        return false;
    }

    Component.onCompleted: refresh()
    Timer { interval: 1000; running: true; repeat: true; onTriggered: root.now = new Date() }
    // The sync finishes in the background after the command returns.
    Timer { id: settle; interval: 1500; onTriggered: root.refresh() }
    // Called for every log entry, so SYNC ALL and other front-ends show up here too.
    function externalChange() { settle.restart(); }

    // Only a few display keys are read: [clock] date_format, [user] default, [session] default.
    FileView {
        path: Quickshell.shellDir + "/../config/greeter/greeter.toml"
        printErrors: false
        onLoaded: {
            const out = {};
            let section = "";
            for (const line of text().split("\n")) {
                const head = /^\s*\[(\w+)\]/.exec(line);
                if (head) { section = head[1]; continue; }
                const kv = /^\s*(\w+)\s*=\s*"([^"]*)"/.exec(line);
                if (kv) out[section + "." + kv[1]] = kv[2];
            }
            root.greeter = out;
        }
    }

    RiceCommand {
        id: reader
        onSucceeded: data => {
            root.info = data;
            if (root.syncing && !syncer.running) {
                root.syncing = false;
                Status.stop();
                Status.say(data.image_match && data.colors_match ? "[ OK ] greeter — sent to the login screen" : "[ WARN ] greeter ainda diferente do tema", data.image_match ? Theme.ok : Theme.yel);
            }
        }
        onFailed: message => Status.say("[ FAIL ] " + message, Theme.red)
    }
    RiceCommand {
        id: syncer
        onSucceeded: settle.restart()
        onFailed: message => { root.syncing = false; Status.stop(); Status.say("[ FAIL ] " + message, Theme.red); }
    }
    RiceCommand {
        id: toggler
        onSucceeded: data => { root.refresh(); Status.say("[ OK ] auto sync " + (data.auto_sync ? "on" : "off")); }
        onFailed: message => Status.say("[ FAIL ] " + message, Theme.red)
    }

    RiceHeader {
        id: title
        title: "LW // GREETER"
    }

    // ================= PREVIEW =================
    Rectangle {
        id: preview
        anchors.top: title.bottom
        anchors.topMargin: 14
        anchors.bottom: foot.top
        anchors.bottomMargin: 12
        anchors.left: parent.left
        anchors.right: panel.left
        anchors.rightMargin: 20
        color: Theme.raise
        border.width: 1
        border.color: Theme.line
        clip: true

        // The staged copy is what the login screen will show; reload it after each sync.
        Image {
            anchors.fill: parent
            anchors.margins: 1
            source: root.info.image ? "file://" + root.info.image + "?" + (root.info.last_sync_ns || 0) : ""
            sourceSize.width: 900
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            cache: false
            Behavior on opacity { NumberAnimation { duration: Theme.tMed } }
        }

        Column {
            anchors.centerIn: parent
            spacing: 12
            RiceText {
                anchors.horizontalCenter: parent.horizontalCenter
                text: Qt.formatTime(root.now, "hh:mm")
                font.pixelSize: 30
                font.bold: true
                color: Theme.accent
            }
            RiceText {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.strftime(root.greeter["clock.date_format"] || "%d/%m/%Y", root.now)
                color: Theme.fg
                font.pixelSize: Theme.small
            }
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                width: card.width + 68
                height: card.height + 44
                color: Qt.alpha(Theme.bg, 0.84)
                border.width: 1
                border.color: Theme.line2
                Column {
                    id: card
                    anchors.centerIn: parent
                    spacing: 9
                    RiceText { anchors.horizontalCenter: parent.horizontalCenter; text: root.greeter["user.default"] || Quickshell.env("USER") }
                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 180
                        height: 24
                        color: Qt.alpha(Theme.bg, 0.6)
                        border.width: 1
                        border.color: Qt.alpha(Theme.fg, 0.25)
                        RiceText { anchors.centerIn: parent; text: "password"; color: Theme.dim; font.pixelSize: Theme.small }
                    }
                    RiceText {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: (root.greeter["session.default"] || "Hyprland") + " ▾"
                        color: Theme.faint
                        font.pixelSize: Theme.small
                    }
                }
            }
        }

        RiceText {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 10
            text: "imagem enviada para a tela de login"
            color: Qt.alpha(Theme.fg, 0.45)
            font.pixelSize: 10
        }
    }

    // ================= PANEL =================
    Rectangle {
        id: panel
        anchors.top: title.bottom
        anchors.topMargin: 14
        anchors.bottom: foot.top
        anchors.bottomMargin: 12
        anchors.right: parent.right
        width: 320
        color: Theme.panel
        border.width: 1
        border.color: Theme.line

        component Check: Row {
            property string status: "OK"
            property string text: ""
            spacing: 10
            RiceText {
                text: parent.status === "OK" ? "[ OK ]" : parent.status === "NA" ? "[ -- ]" : "[" + parent.status + "]"
                color: parent.status === "NA" ? Theme.dim : Theme.statusColor(parent.status)
            }
            RiceText { text: parent.text; width: 230; wrapMode: Text.Wrap }
        }
        component Label: RiceText { color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5 }

        Column {
            x: 16
            y: 16
            width: parent.width - 32
            spacing: 6

            Label { text: "STATUS"; bottomPadding: 4 }
            Check { status: root.info.colors_match ? "OK" : "WARN"; text: root.info.colors_match ? "Colors match the theme" : "Colors differ — sync pending" }
            Check { status: root.imageMatch ? "OK" : "WARN"; text: root.imageMatch ? "Image matches the wallpaper" : "Image differs — sync pending" }
            Check { status: root.info.auto_sync ? "OK" : "NA"; text: "Automatic sync: " + (root.info.auto_sync ? "on" : "off") }
            Check { status: "NA"; text: "Passwordless rule: root only, check in a terminal" }

            Item { width: 1; height: 14 }
            Label { text: "AUTO SYNC" }
            // Toggle switch
            Row {
                spacing: 10
                Rectangle {
                    width: 34
                    height: 16
                    color: root.info.auto_sync ? Theme.accentA : "transparent"
                    border.width: 1
                    border.color: root.info.auto_sync ? Theme.accent : Theme.line2
                    Rectangle {
                        x: root.info.auto_sync ? 20 : 2
                        y: 2
                        width: 10
                        height: 10
                        color: root.info.auto_sync ? Theme.accent : Theme.dim
                        Behavior on x { NumberAnimation { duration: Theme.tMed; easing.type: Theme.ease } }
                    }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.toggleAuto() }
                }
                RiceText {
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.info.auto_sync ? "sincroniza ao trocar wallpaper" : "só manual"
                    color: Theme.dim
                    font.pixelSize: Theme.small
                }
            }

            Item { width: 1; height: 14 }
            Label { text: "LAST SENT" }
            RiceText {
                textFormat: Text.StyledText
                text: !root.info.last_sync_ns ? "nunca" :
                      Qt.formatDateTime(new Date(root.info.last_sync_ns / 1e6), "dd/MM hh:mm:ss")
                      + " <font color='" + Theme.dim + "'>(" + root.ago(root.info.last_sync_ns) + ")</font>"
            }
        }
    }

    // ================= FOOTER =================
    Item {
        id: foot
        anchors.bottom: parent.bottom
        width: parent.width
        height: syncButton.height + 10
        Rectangle { width: parent.width; height: 1; color: Theme.line }
        RiceText {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 4
            color: Theme.dim
            text: root.imageMatch ? "" : "a tela de login ainda mostra o wallpaper anterior"
        }
        AccentButton {
            id: syncButton
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            label: root.syncing ? "SYNCING" : "SYNC NOW"
            enabledState: !root.syncing
            onClicked: root.sync()
        }
    }
}
