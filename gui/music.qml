import QtQuick
import Quickshell
import Quickshell.Io
import qs

// LW // MUSIC — controller and visualizer for cliamp (rice music). Separate instance from
// the control GUI, same theme and components. Phase 1: the control layer only.
ShellRoot {
    // Scriptable hooks: `qs ipc -p gui/music.qml call music <fn>`.
    IpcHandler {
        target: "music"
        function state(): string {
            return JSON.stringify({
                online: Music.online, status: Music.status, title: Music.title, artist: Music.artist,
                album: Music.album, position: Math.round(Music.position * 10) / 10, duration: Music.duration,
                live: Music.live, volume: Music.volumePercent, volumeDb: Music.volumeDb, muted: Music.muted,
                shuffle: Music.shuffle, repeat: Music.repeat, index: Music.currentIndex,
                playlist: Music.playlist.map(t => t.title || Music.fileName(t.path)),
                eq: Music.eqBands, error: Music.lastError
            });
        }
        function act(op: string, arg: string): string {
            const n = parseFloat(arg);
            switch (op) {
            case "toggle": Music.toggle(); break;
            case "next": Music.next(); break;
            case "prev": Music.previous(); break;
            case "seek": Music.seekTo(n); break;
            case "seekby": Music.seekBy(n); break;
            case "volume": Music.setVolumePercent(n); break;
            case "mute": Music.toggleMute(); break;
            case "shuffle": Music.setShuffle(!Music.shuffle); break;
            case "repeat": Music.cycleRepeat(); break;
            case "play": Music.playIndex(n); break;
            case "move": Music.moveTrack(parseInt(arg.split(",")[0]), parseInt(arg.split(",")[1])); break;
            case "remove": Music.removeTrack(n); break;
            case "add": Music.addPath(arg); break;
            case "band": Music.setBand(parseInt(arg.split(",")[0]), parseFloat(arg.split(",")[1])); break;
            case "preset": Music.setPreset(arg); break;
            case "start": Music.start(); break;
            case "quit": Qt.quit(); break;
            case "bad": Music.call("queue.play", { index: 999 }); break;
            default: return "unknown " + op;
            }
            return "ok";
        }
    }
    Connections {
        target: Music
        function onFailed(op, message) { console.warn("music:", op, "failed:", message); }
    }
}
