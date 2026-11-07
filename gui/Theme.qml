pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// Live colors. reload_components() replaces this file atomically after every
// palette change, so its stable path is watchable; STATE/current is a symlink
// to immutable directories and would never fire.
Singleton {
    id: root

    readonly property string palettePath: Quickshell.env("RICE_GUI_PALETTE")
        || Quickshell.env("HOME") + "/.config/noctalia/palettes/RiceMinimal.json"
    // Quickshell kills its child processes on exit, ignoring any signal handling.
    // The fork keeps a change running if this window closes halfway through.
    readonly property var rice: ["setsid", "--fork", "--wait", "/usr/bin/python3", Quickshell.shellDir + "/../extras/rice.py"]
    readonly property string statePath: Quickshell.env("RICE_THEME_STATE")
        || Quickshell.env("HOME") + "/.local/state/rice-minimal/theme"
    readonly property string font: "DejaVu Sans Mono"
    readonly property int fontSize: 13

    property var dark: ({})
    // The vivid terminal colors, so this window matches what the shell shows.
    property var terminal: ({})
    readonly property var term: dark.terminal ? dark.terminal.normal : ({})

    readonly property color surface: dark.mSurface || "#111612"
    readonly property color surfaceAlt: dark.mSurfaceVariant || "#1d231e"
    readonly property color text: dark.mOnSurface || "#d9dfd5"
    readonly property color muted: dark.mOnSurfaceVariant || "#929b8d"
    readonly property color outline: dark.mOutline || "#929b8d"
    readonly property color accent: terminal.accent || dark.mPrimary || "#a6b898"
    readonly property color onAccent: surface
    readonly property color rule: Qt.alpha(outline, 0.35)
    readonly property color ok: terminal.green || term.green || "#a9bc9c"
    readonly property color warn: terminal.yellow || term.yellow || "#c9bd98"
    readonly property color fail: terminal.red || dark.mError || "#d6aaa1"

    function statusColor(status) {
        return status === "OK" ? ok : status === "WARN" ? warn : status === "FAIL" ? fail : muted;
    }

    FileView {
        path: root.palettePath
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try {
                const parsed = JSON.parse(text());
                if (parsed.dark)
                    root.dark = parsed.dark;
            } catch (error) {
                console.warn("Theme: keeping last palette:", error);
            }
        }
    }
}
