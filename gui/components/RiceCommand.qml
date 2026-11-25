// RiceCommand.qml — roda "lw ... --json" e entrega o resultado já decodificado (usado por todas as telas).
import QtQuick
import Quickshell.Io
import qs

// Runs `rice <args>` and hands back parsed JSON. All logic stays in the backend.
Process {
    id: root

    signal succeeded(var data, var warnings)
    signal failed(string message)

    // Theme.lw for a call that a signal must reach (cancel).
    property var program: Theme.rice
    property int pending: 0
    property int code: 0

    // Roda o comando lw com esses argumentos.
    function call(args) {
        if (running)
            return;
        command = program.concat(args);
        pending = 3;
        running = true;
    }

    // Lê uma linha do modo stream (uma resposta por linha).
    function step() {
        if (--pending > 0)
            return;
        let parsed;
        try {
            parsed = JSON.parse(out.text);
        } catch (error) {
            failed(err.text.trim() || "rice exited " + code + " without JSON");
            return;
        }
        // doctor --json is a bare list and exits 1 on FAIL findings, which is valid data.
        if (Array.isArray(parsed))
            succeeded(parsed, []);
        else if (parsed.ok)
            succeeded(parsed.data, parsed.warnings || []);
        else
            failed(parsed.error ? parsed.error.message : "unknown error");
    }

    stdout: StdioCollector { id: out; onStreamFinished: root.step() }
    stderr: StdioCollector { id: err; onStreamFinished: root.step() }
    onExited: exitCode => { code = exitCode; step(); }
}
