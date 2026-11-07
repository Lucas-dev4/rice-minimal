import QtQuick
import Quickshell.Io
import qs

// Live view of STATE/actions.jsonl; every front-end appends to the same file.
Rectangle {
    id: root

    property var entries: []
    readonly property var last: entries.length > 0 ? entries[entries.length - 1] : null
    readonly property string lastLine: last ? format(last) : ""
    readonly property string lastStatus: last ? last.status : ""

    function format(entry) {
        const time = new Date(entry.time_ns / 1e6).toLocaleTimeString(Qt.locale(), "HH:mm:ss");
        return time + "  [ " + entry.status + " ] " + entry.action + (entry.detail ? " — " + entry.detail : "");
    }

    color: Theme.surface

    Rectangle { width: parent.width; height: 1; color: Theme.rule }

    FileView {
        path: Theme.statePath + "/actions.jsonl"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            const parsed = [];
            for (const line of text().split("\n").slice(-200)) {
                try {
                    if (line)
                        parsed.push(JSON.parse(line));
                } catch (error) {
                    console.warn("LogPanel: skipping line:", error);
                }
            }
            root.entries = parsed;
            list.positionViewAtEnd();
        }
    }

    ListView {
        id: list
        anchors.fill: parent
        anchors.margins: 10
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: root.entries

        delegate: RiceText {
            required property var modelData
            width: ListView.view.width
            elide: Text.ElideRight
            text: root.format(modelData)
            color: Theme.statusColor(modelData.status)
        }
    }
}
