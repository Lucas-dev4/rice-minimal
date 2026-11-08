pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// Every color, the font and every animation time live here (the prototype's :root,
// docs/lw-prototype.html). Colors come only from the wallpaper's palette:
// reload_components() replaces RiceMinimal.json atomically after every palette
// change, so its stable path is watchable; STATE/current is a symlink to
// immutable directories and would never fire.
Singleton {
    id: root

    readonly property string palettePath: Quickshell.env("RICE_GUI_PALETTE")
        || Quickshell.env("HOME") + "/.config/noctalia/palettes/RiceMinimal.json"
    // Quickshell kills its child processes on exit, ignoring any signal handling.
    // The fork keeps a change running if this window closes halfway through.
    readonly property var rice: ["setsid", "--fork", "--wait", "/usr/bin/python3", Quickshell.shellDir + "/../extras/rice.py"]
    readonly property string statePath: Quickshell.env("RICE_THEME_STATE")
        || Quickshell.env("HOME") + "/.local/state/rice-minimal/theme"
    // GUI-only preferences (favorites, shortcut descriptions); never read by the backend.
    readonly property string guiStatePath: Quickshell.env("HOME") + "/.local/state/rice-minimal/gui"

    // ---- type --------------------------------------------------------------
    readonly property string font: "JetBrains Mono"
    readonly property int fontSize: 13
    readonly property int small: 11

    // ---- motion ------------------------------------------------------------
    // The profile is the reduced-motion switch: minimal is instant, refined animates.
    property string profile: profileFile.text().trim()
    readonly property bool motion: Quickshell.env("RICE_GUI_MOTION") === "1" || (profile === "refined" && Quickshell.env("RICE_GUI_MOTION") !== "0")
    readonly property int tFast: motion ? 140 : 0
    readonly property int tMed: motion ? 240 : 0
    readonly property int ease: Easing.OutCubic

    // ---- palette -----------------------------------------------------------
    property var dark: ({})
    // The vivid terminal colors, so this window matches what the shell shows.
    property var terminal: ({})
    readonly property var term: dark.terminal ? dark.terminal.normal : ({})

    function mix(a, b, t) {
        return Qt.rgba(a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t, 1);
    }

    readonly property color bg: dark.mSurface || "#12100e"
    readonly property color fg: dark.mOnSurface || "#c9c1b6"
    readonly property color variant: dark.mOnSurfaceVariant || "#8f8a87"
    readonly property color panel: mix(bg, fg, 0.025)
    readonly property color raise: mix(bg, fg, 0.05)
    readonly property color line: mix(bg, fg, 0.11)
    readonly property color line2: mix(bg, fg, 0.18)
    readonly property color dim: mix(bg, variant, 0.85)
    readonly property color faint: mix(bg, variant, 0.55)
    readonly property color accent: terminal.accent || dark.mPrimary || "#e8a46b"
    readonly property color accentA: Qt.alpha(accent, 0.09)
    readonly property color ok: terminal.green || term.green || "#b5d97a"
    readonly property color yel: terminal.yellow || term.yellow || "#e8c86b"
    readonly property color red: terminal.red || dark.mError || "#e86b6b"
    readonly property color blue: terminal.blue || term.blue || "#8ab4e8"
    readonly property color magenta: terminal.magenta || term.magenta || "#b8a6e8"
    readonly property color cyan: terminal.cyan || term.cyan || "#86eac8"

    // Older names, still used by screens that have not been redesigned yet.
    readonly property color surface: bg
    readonly property color surfaceAlt: raise
    readonly property color text: fg
    readonly property color muted: dim
    readonly property color outline: line2
    readonly property color onAccent: bg
    readonly property color rule: line
    readonly property color warn: yel
    readonly property color fail: red

    function statusColor(status) {
        return status === "OK" ? ok : status === "WARN" ? yel : status === "FAIL" ? red : dim;
    }

    FileView {
        id: profileFile
        path: root.statePath + "/profile"
        blockLoading: true
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
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
