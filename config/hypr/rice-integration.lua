-- rice-integration.lua — atalhos e regras de janela do projeto (os atalhos originais ficam em binds.lua).
-- Instalado em ~/.config/hypr/config/; os caminhos /home/lucas são trocados pelo do usuário na instalação.
-- Additional bindings; original bindings remain in config.binds.
-- Super+Ctrl+Alt+W Waypaper · +B reinicia a Waybar do rice · +S editor de atalhos · +N Neovim
hl.bind("SUPER + CONTROL + ALT + W", hl.dsp.exec_cmd("waypaper"))
hl.bind("SUPER + CONTROL + ALT + B", hl.dsp.exec_cmd("python3 /home/lucas/Projetos/rice-minimal/scripts/session.py"))
hl.bind("SUPER + CONTROL + ALT + S", hl.dsp.exec_cmd("kitty -e /home/lucas/.local/bin/supers"))
hl.bind("SUPER + CONTROL + ALT + N", hl.dsp.exec_cmd("kitty -e nvim"))
-- O LW: cada atalho abre a janela na sua seção (de novo na mesma seção fecha).
hl.bind("SUPER + BackSpace", hl.dsp.exec_cmd("/home/lucas/.local/bin/lw gui"))
hl.bind("SUPER + M", hl.dsp.exec_cmd("/home/lucas/.local/bin/lw music"))
hl.bind("SUPER + G", hl.dsp.exec_cmd("/home/lucas/.local/bin/lw games"))
-- Music (cliamp, wherever LW is) and the system mute.
hl.bind("SUPER + N", hl.dsp.exec_cmd("/home/lucas/.local/bin/cliamp next"))
hl.bind("SUPER + SHIFT + N", hl.dsp.exec_cmd("/home/lucas/.local/bin/cliamp prev"))
hl.bind("SUPER + SHIFT + Space", hl.dsp.exec_cmd("/home/lucas/.local/bin/cliamp toggle"))
hl.bind("SUPER + SHIFT + M", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"))
-- A janela do LW flutua, centralizada, com 64% x 78% do monitor.
hl.window_rule({ match = { class = "^(org\\.quickshell)$", title = "^(LW)$" }, float = true, center = true, size = { "monitor_w*0.64", "monitor_h*0.78" } })

-- LW // SHORTCUTS recording: an empty submap, so every combination (Super included)
-- reaches the GUI instead of running. Esc leaves it; the GUI also resets it itself.
hl.define_submap("lw-record", function()
    hl.bind("Escape", hl.dsp.submap("reset"))
end)
