pragma Singleton
import QtQuick
import Quickshell

// What the status bar says right now, besides the action log.
// busy: an ASCII progress bar runs until it is cleared.
// say(): a short message (favorited, copied...) until the next log entry.
Singleton {
    id: root

    property string busy: ""
    property string message: ""
    property color color: Theme.ok
    property int stamp: 0
    // The applied wallpaper, for previews (set by the shell from `rice status`).
    property string wallpaper: ""

    function say(text, tint) {
        message = text;
        color = tint || Theme.ok;
        stamp++;
    }
    function start(label) { busy = label; }
    function stop() { busy = ""; }
}
