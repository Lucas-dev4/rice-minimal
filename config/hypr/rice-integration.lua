-- Additional bindings; original bindings remain in config.binds.
hl.bind("SUPER + CONTROL + ALT + W", hl.dsp.exec_cmd("waypaper"))
hl.bind("SUPER + CONTROL + ALT + B", hl.dsp.exec_cmd("python3 /home/lucas/Projetos/rice-minimal/scripts/session.py"))
hl.bind("SUPER + CONTROL + ALT + S", hl.dsp.exec_cmd("kitty -e /home/lucas/.local/bin/supers"))
hl.bind("SUPER + CONTROL + ALT + N", hl.dsp.exec_cmd("kitty -e nvim"))
hl.bind("SUPER + BackSpace", hl.dsp.exec_cmd("/home/lucas/.local/bin/rice gui"))
hl.bind("SUPER + M", hl.dsp.exec_cmd("/home/lucas/.local/bin/rice music"))
hl.bind("SUPER + G", hl.dsp.exec_cmd("/home/lucas/.local/bin/rice games"))
hl.window_rule({ match = { class = "^(org\\.quickshell)$", title = "^(LW // CONTROL)$" }, float = true, center = true, size = { "monitor_w*0.62", "monitor_h*0.72" } })
hl.window_rule({ match = { class = "^(org\\.quickshell)$", title = "^(LW // MUSIC)$" }, float = true, center = true, size = { "monitor_w*0.62", "monitor_h*0.72" } })
hl.window_rule({ match = { class = "^(org\\.quickshell)$", title = "^(LW // GAMES)$" }, float = true, center = true, size = { "monitor_w*0.62", "monitor_h*0.72" } })

-- LW // SHORTCUTS recording: an empty submap, so every combination (Super included)
-- reaches the GUI instead of running. Esc leaves it; the GUI also resets it itself.
hl.define_submap("lw-record", function()
    hl.bind("Escape", hl.dsp.submap("reset"))
end)
