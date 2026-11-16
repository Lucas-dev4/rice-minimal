// Status.qml — singleton da barra de status do rodapé: mensagem e "ocupado".
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

    // Mostra uma mensagem no rodapé (cor opcional).
    function say(text, tint) {
        message = text;
        color = tint || Theme.ok;
        stamp++;
    }
    // Marca que uma ação está em andamento (mostra o rótulo).
    function start(label) { busy = label; }
    // Termina o estado de ocupado.
    function stop() { busy = ""; }
}
