.pragma library
// Readable text for Hyprland binds. Only presentation: nothing here is written to binds.lua.

var GROUPS = ["JANELA", "FOCO", "MOVER", "WORKSPACE", "APPS", "SHELL", "ZOOM", "RICE"];
var MODS = ["SUPER", "CONTROL", "ALT", "SHIFT"];
var SYMBOL = {
    SUPER: "◆", CONTROL: "⌃", CTRL: "⌃", ALT: "⌥", SHIFT: "⇧",
    Left: "←", Right: "→", Up: "↑", Down: "↓",
    Escape: "Esc", Return: "⏎", BackSpace: "⌫", Space: "Space", Tab: "Tab",
    mouse_up: "scroll ↑", mouse_down: "scroll ↓", "mouse:272": "LMB", "mouse:273": "RMB",
    Minus: "−", Plus: "+", equal: "=/+", period: ".", comma: ",", Print: "PrtSc",
    "code:82": "KP −", "code:86": "KP +"
};
var ARROW = { left: "←", l: "←", right: "→", r: "→", up: "↑", u: "↑", down: "↓", d: "↓" };
var SIDE = { left: "à esquerda", l: "à esquerda", right: "à direita", r: "à direita", up: "acima", u: "acima", down: "abaixo", d: "abaixo" };

// Divide a combinação em partes ("SUPER + Q" → ["SUPER", "Q"]).
function tokens(key) {
    return key.split("+").map(function (t) { return t.trim(); }).filter(function (t) { return t !== ""; });
}

// Símbolo curto de uma tecla especial.
function symbol(token) {
    return SYMBOL[token] || SYMBOL[token.toUpperCase()] || token;
}

// True se é modificador (Super, Shift, Ctrl, Alt).
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

// Lê um campo nomeado da ação Lua.
function field(action, name) {
    var m = new RegExp(name + "\\s*=\\s*\"([^\"]*)\"").exec(action);
    return m ? m[1] : null;
}

// O primeiro texto entre aspas da ação.
function quoted(action) {
    var m = /"([^"]*)"\s*\)?\s*$/.exec(action) || /"([^"]*)"/.exec(action);
    return m ? m[1] : null;
}

// Nome do programa de um comando.
function program(command) {
    var words = command.trim().split(/\s+/);
    var e = words.indexOf("-e");
    var name = e >= 0 && words[e + 1] ? words[e + 1] : words[0];
    return name.split("/").pop();
}

// Descrição de uma ação de workspace ("ir para o workspace 3").
function workspaceText(target, moving) {
    var verb = moving ? "Mover p/ " : "";
    if (target === "m+1" || target === "+1" || target === "e+1") return moving ? "Mover p/ próximo workspace" : "Próximo workspace";
    if (target === "m-1" || target === "-1" || target === "e-1") return moving ? "Mover p/ workspace anterior" : "Workspace anterior";
    if (target === "emptym" || target === "empty") return moving ? "Mover p/ workspace vazio" : "Workspace vazio";
    if (target === "special") return "Mover p/ scratchpad";
    return verb + (moving ? "workspace " : "Ir para workspace ") + target;
}

// ---- plain Portuguese in the COMANDO field -------------------------------------------
// A phrase becomes a real command when saved. `noct` is a `noctalia msg` subcommand (it
// shows the OSD), `cmd` a plain program. Matching ignores accents, articles, word order
// and verb forms (aumenta / aumentar / subir / mais).
var PHRASES = [
    { say: "Aumentar o som", key: "aumentar som", noct: "volume-up", group: "SHELL" },
    { say: "Diminuir o som", key: "diminuir som", noct: "volume-down", group: "SHELL" },
    { say: "Mutar o som", key: "mutar som", alt: ["mutar"], noct: "volume-mute", group: "SHELL" },
    { say: "Mutar o microfone", key: "microfone mutar", noct: "mic-mute", group: "SHELL" },
    { say: "Aumentar o brilho", key: "aumentar brilho", noct: "brightness-up", group: "SHELL" },
    { say: "Diminuir o brilho", key: "brilho diminuir", noct: "brightness-down", group: "SHELL" },
    { say: "Tocar/pausar música", key: "musica tocar", alt: ["tocar", "musica pausar", "pausar"], noct: "media toggle", group: "SHELL" },
    { say: "Próxima música", key: "musica proxima", alt: ["proxima"], noct: "media next", group: "SHELL" },
    { say: "Música anterior", key: "anterior musica", alt: ["anterior"], noct: "media previous", group: "SHELL" },
    { say: "Captura de tela", key: "print", alt: ["print tela"], noct: "screenshot-fullscreen", group: "SHELL" },
    { say: "Captura de uma área", key: "area print", alt: ["print recorte", "print regiao"], noct: "screenshot-region", group: "SHELL" },
    { say: "Captura da janela", key: "janela print", noct: "screenshot-window", group: "SHELL" },
    { say: "Bloquear tela", key: "bloquear tela", alt: ["bloquear"], noct: "session lock", group: "SHELL" },
    { say: "Liga/desliga Wi-Fi", key: "wifi", noct: "wifi-toggle", group: "SHELL" },
    { say: "Liga/desliga Bluetooth", key: "bluetooth", noct: "bluetooth-toggle", group: "SHELL" },
    { say: "Não perturbe", key: "nao perturbe", noct: "notification-dnd-toggle", group: "SHELL" },
    { say: "Luz noturna", key: "luz noturna", noct: "nightlight-toggle", group: "SHELL" },
    { say: "Notificações", key: "notificacoes", noct: "panel-toggle control-center notifications", group: "SHELL" },
    { say: "Histórico do clipboard", key: "clipboard", alt: ["area transferencia"], noct: "panel-toggle clipboard", group: "SHELL" },
    { say: "Seletor de emoji", key: "emoji", noct: "panel-toggle launcher /emo", group: "SHELL" },
    { say: "Abrir launcher", key: "launcher", alt: ["abrir launcher"], noct: "panel-toggle launcher", group: "SHELL" },
    { say: "Abrir navegador", key: "abrir navegador", alt: ["navegador", "abrir firefox", "firefox"], cmd: "firefox", group: "APPS" },
    { say: "Abrir terminal", key: "abrir terminal", alt: ["terminal"], cmd: "kitty", group: "APPS" },
    { say: "Abrir arquivos", key: "abrir arquivos", alt: ["arquivos"], cmd: "nemo", group: "APPS" },
    { say: "Arquivos no terminal (yazi)", key: "yazi", alt: ["arquivos terminal"], cmd: "kitty --class yazi -e yazi", group: "APPS" },
    { say: "Conta-gotas de cor", key: "cor seletor", alt: ["conta-gotas cor", "contagotas cor", "conta gotas cor"], cmd: "hyprpicker -a -n", group: "APPS" }
];
var STOP = ["o", "a", "os", "as", "do", "da", "dos", "das", "de", "um", "uma", "e", "para", "pra", "no", "na", "ao", "em"];
var SAME = {
    aumentar: ["aumenta", "aumente", "subir", "sobe", "suba", "mais", "up"],
    diminuir: ["diminui", "diminua", "abaixar", "abaixa", "baixar", "baixa", "descer", "desce", "menos", "down"],
    som: ["volume", "audio"],
    mutar: ["muta", "mute", "silenciar", "silencia", "mudo"],
    microfone: ["mic"],
    musica: ["midia", "video", "faixa"],
    tocar: ["toca", "play", "continuar", "toggle"],
    pausar: ["pausa", "pause", "parar"],
    proxima: ["proximo", "avancar", "pular", "next"],
    anterior: ["voltar", "volta", "previous"],
    print: ["captura", "capturar", "screenshot", "printar", "foto"],
    tela: ["monitor"],
    area: ["selecao"],
    bloquear: ["bloqueia", "travar", "trava", "lock"],
    abrir: ["abre", "abra", "iniciar"],
    wifi: ["wi-fi", "internet", "rede"],
    clipboard: ["copiados"],
    notificacoes: ["notificacao"],
    cor: ["cores"],
    emoji: ["emojis"]
};
var ALIAS = (function () {
    var out = {};
    for (var word in SAME) { out[word] = word; SAME[word].forEach(function (w) { out[w] = word; }); }
    return out;
})();
// Words that only switch something on or off: "ligar wifi" is the same toggle as "wifi".
var TOGGLE = ["ligar", "liga", "desligar", "desliga", "ativar", "ativa", "desativar", "desativa", "alternar"];

// Chave de busca de uma frase pronta.
function phraseKey(text) {
    return String(text).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "")
        .split(/[^a-z0-9\/-]+/).filter(function (w) { return w && STOP.indexOf(w) < 0 && TOGGLE.indexOf(w) < 0; })
        .map(function (w) { return ALIAS[w] || w; }).sort().join(" ");
}

// Frase pronta para um comando conhecido.
function findPhrase(text) {
    var key = phraseKey(text);
    if (!key) return null;
    for (var i = 0; i < PHRASES.length; i++) {
        var p = PHRASES[i];
        var keys = [p.key].concat(p.alt || []).map(phraseKey);
        if (keys.indexOf(key) >= 0) return p;
    }
    return null;
}

// What a COMANDO entry really saves. `noctPrefix`: the bind already prepends `noctalia msg`.
// { command, say } for a phrase, { error } when it cannot fit this bind, null for a raw command.
function translate(text, noctPrefix) {
    var p = findPhrase(text);
    if (!p) return null;
    if (p.noct) return { command: noctPrefix ? p.noct : "noctalia msg " + p.noct, say: p.say };
    if (noctPrefix) return { error: "este atalho chama o Noctalia; \"" + p.say + "\" precisa de um atalho de app (ex.: ◆ B, ◆ P)" };
    return { command: p.cmd, say: p.say };
}

// The reverse, for the description of a saved bind.
function phraseFor(command) {
    var c = String(command || "").trim().replace(/^noctalia msg\s+/, "");
    for (var i = 0; i < PHRASES.length; i++)
        if (PHRASES[i].noct === c || PHRASES[i].cmd === c) return [PHRASES[i].say, PHRASES[i].group];
    return null;
}

// Exemplos para a ajuda.
function phraseExamples() {
    return ["aumentar o som", "diminuir o som", "mutar", "pausar música", "próxima música", "print da tela", "abrir navegador"];
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
        return known[what] || phraseFor(what) || ["Shell: " + what, "SHELL"];
    }
    if (/exec_cmd/.test(a)) {
        if (/TERMINAL/.test(a)) return ["Abrir terminal", "APPS"];
        if (/EDITOR/.test(a)) return ["Abrir editor", "APPS"];
        if (/CALCULATOR/.test(a)) return ["Abrir calculadora", "APPS"];
        if (bind.command && phraseFor(bind.command)) return phraseFor(bind.command);
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

// Modificadores ativos → nomes.
function modifierNames(modifiers) {
    var out = [];
    if (modifiers & 0x10000000) out.push("SUPER");     // Qt.MetaModifier
    if (modifiers & 0x04000000) out.push("CONTROL");   // Qt.ControlModifier
    if (modifiers & 0x08000000) out.push("ALT");       // Qt.AltModifier
    if (modifiers & 0x02000000) out.push("SHIFT");     // Qt.ShiftModifier
    return out;
}

// True se a tecla pressionada é só um modificador.
function isModifierKey(k) {
    // Shift, Control, Meta, Alt, Super_L/R, Hyper
    return [0x01000020, 0x01000021, 0x01000022, 0x01000023, 0x01000053, 0x01000054, 0x01000056, 0x01001103].indexOf(k) >= 0;
}
