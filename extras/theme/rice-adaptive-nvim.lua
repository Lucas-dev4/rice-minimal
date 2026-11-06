-- No plugins, RPC servers or timers: reload colors on natural editor events.
local root = vim.fn.expand("~/.local/state/rice-minimal/theme/current")
local last = nil
local function apply(force)
    local generation = vim.uv.fs_readlink(root)
    if force or generation ~= last then
        local ok = pcall(dofile, root .. "/nvim.lua")
        if ok then last = generation end
    end
end
apply(true)
local group = vim.api.nvim_create_augroup("RiceAdaptive", { clear = true })
vim.api.nvim_create_autocmd({ "FocusGained", "BufEnter", "VimResume" }, {
    group = group, callback = function() apply(false) end,
})
vim.api.nvim_create_user_command("RiceTheme", function() apply(true) end, { force = true })
