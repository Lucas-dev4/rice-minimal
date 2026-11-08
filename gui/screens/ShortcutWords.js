.pragma library
// Readable text for Hyprland binds. Only presentation: nothing here is written to binds.lua.

var GROUPS = ["JANELA", "FOCO", "MOVER", "WORKSPACE", "APPS", "SHELL", "ZOOM", "RICE"];
var MODS = ["SUPER", "CONTROL", "ALT", "SHIFT"];
var SYMBOL = {
    SUPER: "◆", CONTROL: "⌃", CTRL: "⌃", ALT: "⌥", SHIFT: "⇧",
    Left: "←", Right: "→", Up: "↑", Down: "↓",
    Escape: "Esc", Return: "⏎", BackSpace: "⌫", Space: "Space", Tab: "Tab",
    mouse_up: "scroll ↑", mouse_down: "scroll ↓", "mouse:272": "LMB", "mouse:273": "RMB",
    Minus: "−", Plus: "+", period: ".", comma: ",", Print: "PrtSc",
    "code:82": "KP −", "code:86": "KP +"
};
var ARROW = { left: "←", l: "←", right: "→", r: "→", up: "↑", u: "↑", down: "↓", d: "↓" };
var SIDE = { left: "à esquerda", l: "à esquerda", right: "à direita", r: "à direita", up: "acima", u: "acima", down: "abaixo", d: "abaixo" };

function tokens(key) {
    return key.split("+").map(function (t) { return t.trim(); }).filter(function (t) { return t !== ""; });
}

function symbol(token) {
    return SYMBOL[token] || SYMBOL[token.toUpperCase()] || token;
}

function isMod(token) {
    return MODS.indexOf(token.toUpperCase()) >= 0 || token.toUpperCase() === "CTRL";
}

// Same combination whatever the spelling or order: "super + shift + x" == "SHIFT + SUPER + X".
function normal(key) {
    var parts = tokens(key).map(function (t) {
        var u = t.toUpperCase();
        return u === "CTRL" ? "CONTROL" : u;
    });
    var mods = parts.filter(function (t) { return MODS.indexOf(t) >= 0; }).sort();
    var rest = parts.filter(function (t) { return MODS.indexOf(t) < 0; });
    return mods.concat(rest).join("+");
}

function field(action, name) {
    var m = new RegExp(name + "\\s*=\\s*\"([^\"]*)\"").exec(action);
    return m ? m[1] : null;
}

function quoted(action) {
    var m = /"([^"]*)"\s*\)?\s*$/.exec(action) || /"([^"]*)"/.exec(action);
    return m ? m[1] : null;
}

function program(command) {
    var words = command.trim().split(/\s+/);
    var e = words.indexOf("-e");
    var name = e >= 0 && words[e + 1] ? words[e + 1] : words[0];
    return name.split("/").pop();
}

function workspaceText(target, moving) {
    var verb = moving ? "Mover p/ " : "";
    if (target === "m+1" || target === "+1" || target === "e+1") return moving ? "Mover p/ próximo workspace" : "Próximo workspace";
    if (target === "m-1" || target === "-1" || target === "e-1") return moving ? "Mover p/ workspace anterior" : "Workspace anterior";
    if (target === "emptym" || target === "empty") return moving ? "Mover p/ workspace vazio" : "Workspace vazio";
    if (target === "special") return "Mover p/ scratchpad";
    return verb + (moving ? "workspace " : "Ir para workspace ") + target;
}

// [description, group] for one bind.
function describe(bind) {
    var a = bind.action || "";
    var dir = field(a, "direction"), ws = field(a, "workspace"), mon = field(a, "monitor");
    if (!bind.editable) return [bind.command ? "Abrir " + program(bind.command) : a, "RICE"];
    if (/hyprctl kill/.test(a)) return ["Forçar fechar (kill)", "JANELA"];
    if (/window\.close/.test(a)) return ["Fechar janela", "JANELA"];
    if (/window\.float/.test(a)) return ["Alternar flutuante", "JANELA"];
    if (/window\.fullscreen\(\{\s*mode\s*=\s*1/.test(a)) return ["Maximizar", "JANELA"];
    if (/window\.fullscreen/.test(a)) return ["Tela cheia", "JANELA"];
    if (/togglesplit/.test(a)) return ["Alternar split", "JANELA"];
    if (/window\.drag/.test(a)) return ["Arrastar janela", "JANELA"];
    if (/window\.resize/.test(a)) return ["Redimensionar janela", "JANELA"];
    if (/window\.move/.test(a) && dir) return ["Mover janela " + (ARROW[dir] || dir), "MOVER"];
    if (/window\.move/.test(a) && mon) return [mon.indexOf("-") === 0 ? "Mover p/ monitor anterior" : "Mover p/ próximo monitor", "MOVER"];
    if (/window\.move/.test(a) && ws) return [workspaceText(ws, true), "WORKSPACE"];
    if (/toggle_special|togglespecial/.test(a)) return ["Mostrar scratchpad", "WORKSPACE"];
    if (/focus/.test(a) && dir) return ["Focar " + (SIDE[dir] || dir), "FOCO"];
    if (/focus/.test(a) && ws) return [workspaceText(ws, false), "WORKSPACE"];
    var zoom = /zoomfunction\(\s*(-?[\d.]+)/.exec(a);
    if (zoom) return [parseFloat(zoom[1]) < 0 ? "Zoom −" : "Zoom +", "ZOOM"];
    if (/noctCall/.test(a)) {
        var what = quoted(a) || "";
        var known = {
            "window-switcher": ["Trocar janela", "FOCO"], "settings-toggle": ["Configurações do shell", "SHELL"],
            "panel-toggle control-center": ["Central de controle", "SHELL"], "panel-toggle launcher": ["Abrir launcher", "SHELL"],
            "panel-toggle launcher /emo": ["Seletor de emoji", "SHELL"], "session lock": ["Bloquear tela", "SHELL"],
            "panel-toggle session": ["Menu de sessão", "SHELL"], "screenshot-fullscreen": ["Captura de tela", "SHELL"],
            "panel-toggle clipboard": ["Histórico do clipboard", "SHELL"],
            "panel-toggle control-center notifications": ["Notificações", "SHELL"]
        };
        return known[what] || ["Shell: " + what, "SHELL"];
    }
    if (/exec_cmd/.test(a)) {
        if (/TERMINAL/.test(a)) return ["Abrir terminal", "APPS"];
        if (/EDITOR/.test(a)) return ["Abrir editor", "APPS"];
        if (/CALCULATOR/.test(a)) return ["Abrir calculadora", "APPS"];
        if (bind.command && /hyprpicker/.test(bind.command)) return ["Conta-gotas de cor", "APPS"];
        if (bind.command) return ["Abrir " + program(bind.command), "APPS"];
    }
    return [a.replace(/^hl\.dsp\./, ""), "JANELA"];
}

// Qt key event -> Hyprland key name. Unknown keys fall back to their xkb code, which
// binds.lua already uses (code:82).
function keyName(event) {
    var k = event.key;
    if (k >= 0x41 && k <= 0x5a) return String.fromCharCode(k);
    if (k >= 0x30 && k <= 0x39) return String.fromCharCode(k);
    if (k >= 0x01000030 && k <= 0x01000052) return "F" + (k - 0x01000030 + 1);
    var named = {
        0x01000012: "Left", 0x01000014: "Right", 0x01000013: "Up", 0x01000015: "Down",
        0x01000004: "Return", 0x01000005: "Return", 0x20: "Space", 0x01000001: "Tab",
        0x01000003: "BackSpace", 0x01000000: "Escape", 0x01000007: "Delete", 0x01000006: "Insert",
        0x01000010: "Home", 0x01000011: "End", 0x01000016: "Page_Up", 0x01000017: "Page_Down",
        0x01000009: "Print", 0x2d: "Minus", 0x2b: "Plus", 0x3d: "equal", 0x2c: "comma",
        0x2e: "period", 0x2f: "slash", 0x3b: "semicolon", 0x27: "apostrophe", 0x5b: "bracketleft",
        0x5d: "bracketright", 0x5c: "backslash", 0x60: "grave"
    };
    if (named[k]) return named[k];
    // Shifted digits arrive as symbols; xkb codes 10..19 are 1..9,0.
    var code = event.nativeScanCode || 0;
    if (code >= 10 && code <= 19) return String((code - 9) % 10);
    return code ? "code:" + code : "";
}

function modifierNames(modifiers) {
    var out = [];
    if (modifiers & 0x10000000) out.push("SUPER");     // Qt.MetaModifier
    if (modifiers & 0x04000000) out.push("CONTROL");   // Qt.ControlModifier
    if (modifiers & 0x08000000) out.push("ALT");       // Qt.AltModifier
    if (modifiers & 0x02000000) out.push("SHIFT");     // Qt.ShiftModifier
    return out;
}

function isModifierKey(k) {
    // Shift, Control, Meta, Alt, Super_L/R, Hyper
    return [0x01000020, 0x01000021, 0x01000022, 0x01000023, 0x01000053, 0x01000054, 0x01000056, 0x01001103].indexOf(k) >= 0;
}
