// Modules.qml — singleton com os módulos ativos, na ordem da barra lateral (contrato em docs/modulos.md).
// Vem pronto do `lw gui` em LW_MODULES. Sem a variável (`qs -p gui`), a janela nasce só com SISTEMA,
// que é obrigatório, e os outros entram quando `lw modules list --json` responde.
pragma Singleton
import QtQuick
import Quickshell
import qs.components

Singleton {
    id: root

    // Igual ao modules/system/module.toml (um teste confere): é o que dá para mostrar sem esperar ninguém.
    readonly property var system: ({
        "id": "system", "name": "SISTEMA", "folder": "screens", "hook": "SystemModule.qml",
        "screens": [
            { "name": "WALLPAPERS", "file": "WallpaperScreen.qml" },
            { "name": "SHORTCUTS", "file": "ShortcutsScreen.qml" },
            { "name": "PROFILES", "file": "ProfilesScreen.qml" },
            { "name": "PALETTE", "file": "PaletteScreen.qml" },
            { "name": "DOCTOR", "file": "DoctorScreen.qml" },
            { "name": "BACKUPS", "file": "BackupsScreen.qml" },
            { "name": "LOCK", "file": "LockScreen.qml" },
            { "name": "GREETER", "file": "GreeterScreen.qml" }
        ],
        "config": {}
    })
    readonly property var given: parse(Quickshell.env("LW_MODULES"))
    // Cada um: id, name, folder, hook, screens e config (o `data` de `lw modules list`). Nunca vazia.
    property var active: given.length ? given : [system]

    // O texto da variável → lista de módulos; vazia se não veio ou não presta.
    function parse(text) {
        try {
            const list = JSON.parse(text || "[]");
            return Array.isArray(list) ? list : [];
        } catch (error) {
            console.warn("LW_MODULES:", error);
            return [];
        }
    }
    // Valor de config de um módulo: Modules.config("music", "dir").
    function config(id, key) {
        const module = active.find(m => m.id === id);
        return module ? module.config[key] : undefined;
    }

    RiceCommand {
        onSucceeded: data => { if (data.length) root.active = data; }
        onFailed: message => console.warn("modules:", message)
        Component.onCompleted: if (!root.given.length) call(["modules", "list", "--json"])
    }
}
