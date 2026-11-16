// Spectrum.qml — singleton do visualizador de áudio (barras), alimentado pelo cava.
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// cava on cliamp's own PipeWire stream (alsa_playback.cliamp), shared by every window
// that draws a visualizer (LW, LW // MUSIC). 56 log-spaced bands (30 Hz–16 kHz), 60 fps,
// 0..1 per band. It runs only while cliamp plays; empty means the visualizers idle.
// Other sounds of the system never reach it.
Singleton {
    id: root

    property var levels: []
    property string source: "idle"
    property bool enabled: true
    readonly property string config: Quickshell.env("XDG_RUNTIME_DIR") + "/lw-music-cava.conf"
    property bool ready: false

    FileView {
        path: root.config
        printErrors: false
        onSaved: root.ready = true
        Component.onCompleted: setText([
            "[general]", "bars = 56", "framerate = 60", "lower_cutoff_freq = 30", "higher_cutoff_freq = 16000",
            "[input]", "method = pipewire", "source = alsa_playback.cliamp",
            "[output]", "method = raw", "channels = mono", "raw_target = /dev/stdout", "data_format = ascii",
            "ascii_max_range = 1000", "bar_delimiter = 59", "frame_delimiter = 10", ""
        ].join("\n"))
    }
    Process {
        id: cava
        command: ["cava", "-p", root.config]
        running: root.ready && root.enabled && Music.playing && !retry.running
        stdout: SplitParser {
            onRead: line => {
                const out = [];
                for (const v of line.split(";")) if (v !== "") out.push(parseInt(v) / 1000);
                root.levels = out;
                root.source = "cava";
            }
        }
        onRunningChanged: if (!running) { root.levels = []; root.source = "idle"; }
        // No cava, or cliamp's stream not there yet: try again shortly.
        onExited: code => { if (Music.playing) retry.restart(); }
    }
    Timer { id: retry; interval: 3000 }
}
