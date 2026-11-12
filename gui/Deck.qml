pragma Singleton
import QtQuick
import Quickshell

// Shared state of the LW window's glass: `backdrop` is the blurred wallpaper every Glass
// panel samples from; `tick` changes while something scrolls or slides, so the panels
// re-read where they sit over the wallpaper (only then: a still window costs nothing).
Singleton {
    property Item backdrop: null
    property Item root: null
    property int tick: 0
    property int moving: 0          // how many things are moving now (scroll, page slide)
    function bump() { tick++; }
}
