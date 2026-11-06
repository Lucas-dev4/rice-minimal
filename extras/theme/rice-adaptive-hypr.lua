-- Generated module contains colors and a 1px border only.
local path = os.getenv("HOME") .. "/.local/state/rice-minimal/theme/current/hyprland.lua"
local file = io.open(path, "r")
if file then
    file:close()
    dofile(path)
else
    hl.config({ general = { border_size = 1, col = {
        active_border = "rgba(a6b898ff)", inactive_border = "rgba(929b8dff)",
    } } })
end
