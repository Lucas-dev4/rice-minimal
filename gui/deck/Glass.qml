import QtQuick
import qs

// A glass panel: the blurred wallpaper right under it, a dark tint, a hairline border with
// an inner highlight, and (k) the two accent corner marks of the prototype.
Item {
    id: root

    property real tint: 0.62          // darker than the prototype's .46: light wallpapers need it
    property bool k: false
    default property alias content: inner.data

    // Where this panel sits over the backdrop; re-read whenever Deck.tick changes.
    readonly property rect area: {
        Deck.tick;
        if (!Deck.root || !visible) return Qt.rect(0, 0, 1, 1);
        const p = root.mapToItem(Deck.root, 0, 0);
        return Qt.rect(p.x, p.y, Math.max(1, width), Math.max(1, height));
    }
    Component.onCompleted: Deck.bump()
    onWidthChanged: Deck.bump()
    onHeightChanged: Deck.bump()

    ShaderEffectSource {
        anchors.fill: parent
        sourceItem: Deck.backdrop
        sourceRect: root.area
        visible: Deck.backdrop !== null
    }
    Rectangle { anchors.fill: parent; color: Qt.alpha(Theme.bg, root.tint) }
    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.08)
    }
    Rectangle { x: 1; y: 1; width: parent.width - 2; height: 1; color: Qt.rgba(1, 1, 1, 0.05) }
    // Accent corners: top-left and bottom-right.
    Item {
        visible: root.k
        anchors.fill: parent
        opacity: 0.7
        Rectangle { x: -1; y: -1; width: 10; height: 1; color: Theme.accent }
        Rectangle { x: -1; y: -1; width: 1; height: 10; color: Theme.accent }
        Rectangle { x: parent.width - 9; y: parent.height; width: 10; height: 1; color: Theme.accent }
        Rectangle { x: parent.width; y: parent.height - 9; width: 1; height: 10; color: Theme.accent }
    }
    Item { id: inner; anchors.fill: parent }
}
