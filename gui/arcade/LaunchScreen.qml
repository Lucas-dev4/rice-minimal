import QtQuick
import qs
import qs.components

// The short launch screen: every line turns from [ .. ] into [ OK ] (or [FAIL]) only when
// that step really happened — wrappers decided, command started, game process detected.
// It closes by itself once the game is seen; a failure stays until a key or a click.
Rectangle {
    id: root

    readonly property var l: Games.launching
    readonly property bool shown: l !== null
    readonly property bool failed: !!(l && l.error)

    function dismiss() { Games.launching = null; }
    function handleKey(event) { if (!shown) return false; if (failed || (l && l.detected)) dismiss(); return true; }

    visible: opacity > 0
    opacity: shown ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 250; easing.type: Theme.ease } }
    color: Qt.alpha(Theme.bg, 0.94)
    MouseArea { anchors.fill: parent; onClicked: if (root.failed) root.dismiss() }

    // Wrapper line: what gamemoderun / mangohud will do for this launch.
    function wrappers() {
        if (!l) return "";
        if (l.source === "steam") return "steam: gamemoderun/mangohud ficam nas opções de lançamento da Steam";
        const t = l.tools || {};
        const one = (name, on, have) => name + ": " + (!on ? "desligado" : have === false ? "não instalado" : "ligado");
        return one("gamemoderun", l.gamemode, t.gamemode) + " · " + one("mangohud", l.mangohud, t.mangohud);
    }
    readonly property var steps: !l ? [] : [
        { text: wrappers(), state: "ok" },
        { text: l.ok ? "comando: " + l.command : "iniciando o comando…", state: l.ok ? "ok" : failed ? "fail" : "run" },
        { text: l.detected ? "processo do jogo detectado — sessão aberta" : l.ok && failed ? l.error : "aguardando o processo do jogo…",
          state: l.detected ? "ok" : l.ok && failed ? "fail" : l.ok ? "run" : "wait" }
    ]

    // Closes ~0.9 s after the game shows up.
    Timer { running: root.l !== null && root.l.detected; interval: 900; onTriggered: root.dismiss() }

    Column {
        anchors.centerIn: parent
        width: 560
        spacing: 6
        RiceText { text: "PLAY"; color: Theme.accent; font.weight: Font.ExtraBold; font.letterSpacing: 2; font.pixelSize: 16 }
        RiceText { width: parent.width; elide: Text.ElideRight; text: root.l ? root.l.title : ""; font.pixelSize: 20; font.weight: Font.ExtraBold; bottomPadding: 14 }
        Repeater {
            model: root.steps
            Row {
                required property var modelData
                spacing: 10
                visible: modelData.state !== "wait"
                RiceText {
                    text: modelData.state === "ok" ? "[ OK ]" : modelData.state === "fail" ? "[FAIL]" : "[ .. ]"
                    color: modelData.state === "ok" ? Theme.ok : modelData.state === "fail" ? Theme.red : Theme.accent
                }
                RiceText { width: 480; wrapMode: Text.WrapAnywhere; text: modelData.text; color: modelData.state === "fail" ? Theme.red : Theme.dim }
            }
        }
        RiceText {
            visible: root.failed
            topPadding: 14
            text: "o log do lançamento fica em ~/.local/share/lw/last-launch.log · qualquer tecla fecha"
            color: Theme.faint
            font.pixelSize: Theme.small
        }
    }
}
