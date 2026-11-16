-- rice-minimal.lua — base do rice no Hyprland: tudo reto e sem efeitos (o perfil Refined liga
-- as animações depois, em rice-appearance.lua). Monitores, regras e UWSM do sistema ficam como estão.
-- Local overrides; existing monitors, rules and UWSM preserved.
hl.config({
    animations = { enabled = false },
    decoration = {
        rounding = 0,
        active_opacity = 1.0, inactive_opacity = 1.0,
        blur = { enabled = false }, shadow = { enabled = false },
    },
})
