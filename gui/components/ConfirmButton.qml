import QtQuick

// Needs a second click within three seconds.
RiceButton {
    id: root

    property string action: ""
    property bool armed: false
    signal confirmed()

    label: armed ? "CONFIRM?" : action
    onClicked: {
        if (armed) {
            armed = false;
            confirmed();
        } else {
            armed = true;
            disarm.restart();
        }
    }

    Timer {
        id: disarm
        interval: 3000
        onTriggered: root.armed = false
    }
}
