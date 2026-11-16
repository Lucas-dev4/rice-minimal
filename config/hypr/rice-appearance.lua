-- rice-appearance.lua — aparência do Hyprland conforme o perfil (minimal/refined).
-- Instalado em ~/.config/hypr/config/ pelo scripts/install.py e recarregado pelo profiles.py.
-- Minimal: sem animações, sem blur, sem sombra, cantos retos. Refined: liga as animações abaixo.
-- Shared appearance infrastructure. Loaded after the adaptive border colors.
local root = os.getenv("HOME") .. "/.local/state/rice-minimal/theme/"
local file = io.open(root .. "profile", "r")
local profile = file and file:read("*l") or "minimal"
if file then file:close() end
local refined = profile == "refined"
-- Vale para os dois perfis: cantos retos, janelas opacas, sem blur e sem sombra.
hl.config({
    animations = { enabled = refined },
    decoration = { rounding = 0, active_opacity = 1.0, inactive_opacity = 1.0,
        blur = { enabled = false }, shadow = { enabled = false } },
})
-- Só no Refined: curva de animação suave (riceEase) e a velocidade de cada tipo de animação
-- (speed é em décimos de segundo: 1.5 = 150 ms).
if refined then
    hl.curve("riceEase", { type = "bezier", points = { {0.16, 1}, {0.3, 1} } })
    hl.animation({ leaf = "global", enabled = true, speed = 1.5, bezier = "riceEase" })
    hl.animation({ leaf = "windows", enabled = true, speed = 1.5, bezier = "riceEase", style = "popin 98%" })
    hl.animation({ leaf = "windowsMove", enabled = true, speed = 1.2, bezier = "riceEase" })
    hl.animation({ leaf = "fade", enabled = true, speed = 1.2, bezier = "riceEase" })
    hl.animation({ leaf = "border", enabled = true, speed = 1.5, bezier = "riceEase" })
    hl.animation({ leaf = "borderangle", enabled = false })
    hl.animation({ leaf = "workspaces", enabled = true, speed = 1.6, bezier = "riceEase", style = "slide" })
    hl.animation({ leaf = "specialWorkspaceIn", enabled = true, speed = 1.5, bezier = "riceEase", style = "slide top" })
    hl.animation({ leaf = "specialWorkspaceOut", enabled = true, speed = 1.2, bezier = "riceEase", style = "slide bottom" })
    hl.animation({ leaf = "layers", enabled = true, speed = 1.2, bezier = "riceEase", style = "fade" })
end
