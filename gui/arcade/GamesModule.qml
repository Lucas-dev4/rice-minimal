import QtQuick
import qs
import qs.components

// GamesModule.qml — o gancho de JOGOS: a sessão na seção fechada, fontes e sessão na barra lateral,
// a ficha do jogo, INSTALAR e a tela de lançamento por cima da janela, o último scan no rodapé e as
// mensagens do que os jogos fazem. Quem chama os comandos é o Games.qml.
LwModule {
    id: root

    // A tela aberta de JOGOS (null nas outras seções) e as fichas (a camada por cima da janela).
    property Item screenItem: null
    property Item sheets: null
    // O scan roda uma vez por janela, ao entrar em JOGOS.
    property bool scanned: false

    summary: Games.session ? "<font color='" + Theme.ok + "'>● " + elapsed(Games.sessionSeconds) + "</font> " + (Games.sessionGame ? Games.sessionGame.title : "") : ""
    context: Games.scanning ? "scan…" : Games.lastScan ? "scan: " + Games.lastScan.total + " · " + Games.lastScan.new + " novos" : "—"
    bootStep: ({ label: "reading games.json: " + Games.games.length + " games", done: Games.loaded })

    // Uma sessão que ficou aberta volta ao abrir a janela, em qualquer seção.
    function started() { Games.recover(); }
    function entered() { if (!scanned) { scanned = true; Games.scan(true); } }
    // Sair de JOGOS fecha as fichas.
    function exited() { if (sheets) { sheets.sheet.close(); sheets.installSheet.close(); } }
    function screenLoaded(item) { screenItem = item; }

    // Fecha a ficha e inicia o jogo.
    function launchGame(id) { sheets.sheet.close(); Games.launch(id); }
    // Segundos → "m:ss" ou "h:mm:ss".
    function elapsed(t) {
        return (t >= 3600 ? Math.floor(t / 3600) + ":" + String(Math.floor(t % 3600 / 60)).padStart(2, "0") : Math.floor(t / 60)) + ":" + String(t % 60).padStart(2, "0");
    }

    // Com uma camada aberta, as teclas são dela: nada chega à tela de trás.
    function overlayKey(event) {
        const open = !sheets ? null : [sheets.launchScreen, sheets.installSheet, sheets.sheet].find(x => x.shown);
        if (!open) return false;
        open.handleKey(event);
        return true;
    }

    // ---- IPC dos testes
    function state() {
        const sheet = sheets && sheets.sheet.shown ? { id: sheets.sheet.gameId, hours: sheets.sheet.hoursShown } : null;
        // As horas do primeiro jogo, como a tela aberta as escreve.
        const hours = screenItem && screenItem.hours && Games.games.length ? screenItem.hours(Games.hoursOf(Games.games[0])) : null;
        return { games: Games.games.length, scanning: Games.scanning, session: Games.session, sheet: sheet, hours: hours };
    }
    function act(op, arg) {
        switch (op) {
        // Abre a ficha de um jogo (vazio fecha).
        case "openSheet": if (arg) sheets.sheet.openGame(arg); else sheets.sheet.close(); break;
        case "installer": openSection(); sheets.installSheet.openSheet(); break;
        default: return false;
        }
        return true;
    }

    // ---- o que as telas pedem
    Connections {
        target: root.screenItem
        ignoreUnknownSignals: true
        function onOpen(id) { root.sheets.sheet.openGame(id); }
        function onLaunch(id) { root.launchGame(id); }
        function onInstaller() { root.sheets.installSheet.openSheet(); }
    }

    // ---- mensagens curtas no rodapé
    Connections {
        target: Games
        function onFailed(message) { Status.say("[ !! ] " + message, Theme.red); }
        function onChanged(message) { Status.say(message, Theme.ok); }
        function onSessionEnded(title, hours) { Status.say(Games.hoursText(hours) + " em " + title, Theme.ok); }
    }

    // ---- barra lateral: de onde vêm os jogos e a sessão
    sidebar: Component {
        Column {
            spacing: 2
            RiceText { text: "SOURCES"; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5; bottomPadding: 4 }
            Repeater {
                model: [["steam", "steam"], ["wine / .exe", "wine"], ["hydra", "hydra"], ["roms", "rom"]]
                Item {
                    required property var modelData
                    readonly property int count: Games.games.filter(g => g.source === modelData[1] && !g.missing).length
                    width: parent.width
                    height: gameSrc.implicitHeight + 2
                    RiceText {
                        id: gameSrc
                        textFormat: Text.StyledText
                        text: (parent.count ? "<font color='" + Theme.ok + "'>●</font> " : "<font color='" + Theme.faint + "'>○</font> ") + parent.modelData[0]
                        color: parent.count ? Theme.fg : Theme.dim
                    }
                    RiceText { anchors.right: parent.right; text: parent.count; color: Theme.faint }
                }
            }
            Item { width: 1; height: 14 }
            // SESSÃO: ● jogo mm:ss enquanto roda (o vigia conta mesmo com o LW fechado).
            RiceText { text: "SESSÃO"; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5; bottomPadding: 2 }
            RiceText {
                width: parent.width
                elide: Text.ElideRight
                textFormat: Text.StyledText
                text: Games.session ? "<font color='" + Theme.ok + "'>● " + root.elapsed(Games.sessionSeconds) + "</font>  " + (Games.sessionGame ? Games.sessionGame.title : "") : "nenhum jogo rodando"
                color: Games.session ? Theme.fg : Theme.dim
                font.pixelSize: Games.session ? Theme.fontSize : Theme.small
            }
            RiceText {
                visible: !!Games.session
                text: "■ PARAR"
                color: stopMouse.containsMouse ? Theme.fg : Theme.red
                font.pixelSize: Theme.small
                MouseArea { id: stopMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: Games.stop(Games.session.id) }
            }
        }
    }

    // ---- por cima da janela, em qualquer seção
    overlay: Component {
        Item {
            id: layers
            readonly property alias sheet: sheet
            readonly property alias installSheet: installSheet
            readonly property alias launchScreen: launchScreen
            Component.onCompleted: root.sheets = layers
            GameSheet {
                id: sheet
                anchors.fill: parent
                keyTarget: root.keyTarget
                bottomInset: root.footerHeight
                onLaunch: id => root.launchGame(id)
            }
            InstallSheet {
                id: installSheet
                anchors.fill: parent
                keyTarget: root.keyTarget
                bottomInset: root.footerHeight
            }
            LaunchScreen {
                id: launchScreen
                anchors.fill: parent
            }
        }
    }
}
