import QtQuick
import qs
import qs.components

Item {
    id: root

    property var results: []
    property string error: ""
    property int expanded: -1

    function count(status) {
        return results.filter(r => r.status === status).length;
    }

    function run() {
        error = "";
        expanded = -1;
        doctor.call(["doctor", "--json"]);
    }

    Component.onCompleted: run()

    RiceCommand {
        id: doctor
        onSucceeded: data => {
            const problems = data.filter(r => r.status === "FAIL").concat(data.filter(r => r.status === "WARN"));
            root.results = problems.concat(data.filter(r => r.status === "OK"));
        }
        onFailed: message => root.error = message
    }

    RiceHeader {
        id: title
        title: "LW // DOCTOR"
    }

    Row {
        id: summary
        anchors.top: title.bottom
        anchors.topMargin: 12
        spacing: 20
        height: runButton.height

        Repeater {
            model: ["OK", "WARN", "FAIL"]
            RiceText {
                required property string modelData
                anchors.verticalCenter: parent.verticalCenter
                text: "[ " + modelData + " ] " + root.count(modelData)
                color: Theme.statusColor(modelData)
                font.bold: true
            }
        }
    }

    RiceButton {
        id: runButton
        anchors.right: parent.right
        anchors.verticalCenter: summary.verticalCenter
        label: doctor.running ? "RUNNING" : "RUN AGAIN"
        enabledState: !doctor.running
        onClicked: root.run()
    }

    RiceText {
        id: failure
        anchors.top: summary.bottom
        anchors.topMargin: 10
        width: parent.width
        visible: root.error !== ""
        text: "[ FAIL ] " + root.error
        color: Theme.fail
        wrapMode: Text.Wrap
    }

    ListView {
        anchors.top: failure.visible ? failure.bottom : summary.bottom
        anchors.topMargin: 14
        anchors.bottom: parent.bottom
        width: parent.width
        clip: true
        spacing: 2
        boundsBehavior: Flickable.StopAtBounds
        model: root.results

        delegate: Rectangle {
            id: row

            required property var modelData
            required property int index
            readonly property bool open: root.expanded === index

            width: ListView.view.width
            height: line.height + 10
            color: hover.containsMouse ? Theme.surfaceAlt : "transparent"

            RiceText {
                id: tag
                x: 6
                y: 5
                text: "[ " + row.modelData.status + " ]"
                color: Theme.statusColor(row.modelData.status)
                font.bold: row.modelData.status !== "OK"
            }

            RiceText {
                id: line
                x: 84
                y: 5
                width: parent.width - 90
                text: row.modelData.name + (row.modelData.detail ? " — " + row.modelData.detail : "")
                color: row.modelData.status === "OK" ? Theme.muted : Theme.text
                wrapMode: row.open ? Text.Wrap : Text.NoWrap
                elide: row.open ? Text.ElideNone : Text.ElideRight
                maximumLineCount: row.open ? 40 : 1
            }

            MouseArea {
                id: hover
                anchors.fill: parent
                hoverEnabled: true
                onClicked: root.expanded = row.open ? -1 : row.index
            }
        }
    }
}
