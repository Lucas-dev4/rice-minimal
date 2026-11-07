import QtQuick
import qs

// Wallpaper preview plus one swatch per named color.
Item {
    id: root

    property var colors: ({})
    property string thumb: ""
    property string caption: ""

    implicitHeight: label.height + 8 + Math.max(preview.height, swatches.implicitHeight)

    RiceText {
        id: label
        width: parent.width
        elide: Text.ElideMiddle
        text: root.caption
        color: Theme.muted
    }

    Rectangle {
        id: preview
        anchors.top: label.bottom
        anchors.topMargin: 8
        width: 190
        height: 118
        color: Theme.surfaceAlt

        Image {
            anchors.fill: parent
            anchors.margins: 1
            source: root.thumb ? "file://" + root.thumb : ""
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            clip: true
        }
    }

    Flow {
        id: swatches
        anchors.top: preview.top
        anchors.left: preview.right
        anchors.leftMargin: 14
        anchors.right: parent.right
        spacing: 6

        Repeater {
            model: Object.keys(root.colors)

            Row {
                required property string modelData
                width: 172
                height: 22
                spacing: 6

                Rectangle {
                    width: 22
                    height: 22
                    color: root.colors[parent.modelData]
                    border.width: 1
                    border.color: Theme.rule
                }
                RiceText {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 144
                    elide: Text.ElideRight
                    text: parent.modelData
                    color: Theme.muted
                    font.pixelSize: Theme.fontSize - 2
                }
            }
        }
    }
}
