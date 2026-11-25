import QtQuick
import qs
import qs.components

// SystemModule.qml — o gancho de SISTEMA: bloco CURRENT na barra lateral, SYNC ALL e LOG no rodapé
// e a última linha do log quando nada acontece.
LwModule {
    id: root

    idleText: Status.logLine
    context: Status.logOpen ? "LOG v" : "LOG ^"
    contextClickable: true
    // Abre/fecha o painel LOG.
    function contextClicked() { Status.logOpen = !Status.logOpen; }

    RiceCommand {
        id: syncCommand
        onFailed: message => Status.error = message
    }

    footerLeft: Component {
        StatusBlock {
            label: syncCommand.running ? "SYNCING" : "SYNC ALL"
            clickable: !syncCommand.running
            onClicked: {
                Status.error = "";
                syncCommand.call(["sync", "--json"]);
            }
        }
    }

    // CURRENT: o wallpaper, a paleta e o perfil aplicados agora.
    sidebar: Component {
        Column {
            spacing: 6
            RiceText { text: "CURRENT"; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5; bottomPadding: 2 }
            Rectangle {
                width: parent.width
                height: Math.round(width * 10 / 16)
                color: Theme.raise
                border.width: 1
                border.color: Theme.line2
                Image {
                    anchors.fill: parent
                    anchors.margins: 1
                    source: Status.wallpaper ? "file://" + Status.wallpaper : ""
                    sourceSize.width: 380
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    clip: true
                }
                Rectangle {
                    x: 6
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 5
                    width: Math.min(parent.width - 12, wallName.implicitWidth + 10)
                    height: wallName.implicitHeight
                    color: Qt.alpha(Theme.bg, 0.8)
                    visible: wallName.text !== ""
                    RiceText {
                        id: wallName
                        x: 5
                        width: parent.width - 10
                        elide: Text.ElideRight
                        font.pixelSize: 10
                        text: Status.wallpaper.split("/").pop().replace(/\.[^.]+$/, "")
                    }
                }
            }
            Row {
                width: parent.width
                spacing: 3
                Repeater {
                    model: [Theme.accent, Theme.red, Theme.yel, Theme.ok, Theme.cyan, Theme.blue]
                    Rectangle {
                        required property color modelData
                        width: (parent.width - 15) / 6
                        height: 14
                        color: modelData
                        Behavior on color { ColorAnimation { duration: Theme.tMed } }
                    }
                }
            }
            Item {
                width: parent.width
                height: profileLabel.implicitHeight + 4
                RiceText { id: profileLabel; y: 4; text: "profile"; color: Theme.dim }
                RiceText { y: 4; anchors.right: parent.right; text: Theme.profile || Status.profile || "--" }
            }
        }
    }
}
