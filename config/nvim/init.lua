-- =============================================================================
-- init.lua — Neovim do RICE // minimal
-- Arquivo único, sem distro. Plugins: lazy.nvim, pywal.nvim e lualine.
-- Foco: C/C++ e Assembly (NASM x86-64 e ARM), mas serve para qualquer linguagem.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Opções gerais
-- -----------------------------------------------------------------------------
local opt = vim.opt

opt.number = true             -- número das linhas
opt.relativenumber = true     -- números relativos ajudam a pular linhas (5j, 3k)
opt.cursorline = true         -- destaca a linha do cursor
opt.signcolumn = "yes"        -- coluna lateral fixa: o texto não "pula"
opt.scrolloff = 6             -- mantém linhas visíveis acima/abaixo do cursor
opt.wrap = false              -- código longo não quebra a linha
opt.mouse = "a"               -- mouse em todos os modos
opt.termguicolors = true      -- cores de 24 bits (necessário para o pywal)
opt.shortmess:append("I")     -- sem tela de boas-vindas
opt.showmode = false          -- o modo já aparece na lualine
opt.undofile = true           -- desfazer continua funcionando depois de fechar
opt.swapfile = false          -- o autosave já protege o trabalho
opt.updatetime = 300
opt.ignorecase = true         -- busca sem diferenciar maiúsculas...
opt.smartcase = true          -- ...a não ser que você digite uma maiúscula
opt.splitright = true
opt.splitbelow = true

-- Indentação com TAB real, a convenção mais comum em C e Assembly.
opt.expandtab = false
opt.tabstop = 4
opt.shiftwidth = 4
opt.softtabstop = 0
opt.smartindent = true

-- Mostra TABs e espaços sobrando no fim da linha, para ver o que :Org vai mudar.
opt.list = true
opt.listchars = { tab = "→ ", trail = "·", nbsp = "␣" }

-- -----------------------------------------------------------------------------
-- 2. Tipos de arquivo: Assembly
-- -----------------------------------------------------------------------------
-- .asm/.nasm usam a sintaxe NASM (x86-64). .s/.S ficam como GAS, que cobre ARM.
vim.filetype.add({
	extension = { asm = "nasm", nasm = "nasm", s = "asm", S = "asm" },
})

-- Comentários corretos para "gc" (comentar linhas), nativo do Neovim.
vim.api.nvim_create_autocmd("FileType", {
	pattern = { "nasm" },
	callback = function() vim.bo.commentstring = "; %s" end,
})
vim.api.nvim_create_autocmd("FileType", {
	pattern = { "asm" },
	callback = function() vim.bo.commentstring = "// %s" end,
})

-- -----------------------------------------------------------------------------
-- 3. lazy.nvim (instala sozinho na primeira abertura)
-- -----------------------------------------------------------------------------
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not vim.uv.fs_stat(lazypath) then
	local out = vim.fn.system({
		"git", "clone", "--filter=blob:none", "--branch=stable",
		"https://github.com/folke/lazy.nvim.git", lazypath,
	})
	if vim.v.shell_error ~= 0 then
		vim.api.nvim_echo({ { "Falha ao instalar o lazy.nvim:\n" .. out, "ErrorMsg" } }, true, {})
		return
	end
end
opt.rtp:prepend(lazypath)

require("lazy").setup({
	spec = {
		{ "AlphaTechnolog/pywal.nvim", name = "pywal", lazy = false, priority = 1000 },
		{ "nvim-lualine/lualine.nvim", lazy = false },
	},
	install = { colorscheme = { "habamax" } },
	checker = { enabled = false },          -- não procura atualizações sozinho
	change_detection = { enabled = false },
	rocks = { enabled = false },            -- nenhum plugin aqui precisa de luarocks
})

-- -----------------------------------------------------------------------------
-- 4. Tema: cores do wallpaper + fundo transparente
-- -----------------------------------------------------------------------------
-- O rice escreve as cores do terminal neste arquivo a cada troca de wallpaper.
local wal_file = vim.fn.expand("~/.cache/wal/colors-wal.vim")

-- Tira o fundo dos grupos principais: aparece o fundo do Kitty atrás.
local function transparent()
	for _, group in ipairs({
		"Normal", "NormalNC", "NormalFloat", "FloatBorder", "FloatTitle",
		"SignColumn", "LineNr", "CursorLineNr", "FoldColumn", "EndOfBuffer",
		"StatusLine", "StatusLineNC", "MsgArea", "WinSeparator", "TabLine", "TabLineFill",
	}) do
		local hl = vim.api.nvim_get_hl(0, { name = group, link = false })
		hl.bg = nil
		hl.ctermbg = nil
		vim.api.nvim_set_hl(0, group, hl)
	end
end

-- Tema da lualine com as cores do pywal, sem nenhum fundo.
local function lualine_theme(c)
	local function mode(color)
		return {
			a = { fg = color, bg = "NONE", gui = "bold" },
			b = { fg = c.color7, bg = "NONE" },
			c = { fg = c.foreground, bg = "NONE" },
		}
	end
	return {
		normal = mode(c.color4),
		insert = mode(c.color2),
		visual = mode(c.color6),
		replace = mode(c.color1),
		command = mode(c.color5),
		inactive = mode(c.color8),
	}
end

local function lualine_setup(colors)
	require("lualine").setup({
		options = {
			theme = colors and lualine_theme(colors) or "auto",
			icons_enabled = false,
			section_separators = "",
			component_separators = "|",
			globalstatus = true,
		},
		sections = {
			lualine_a = { "mode" },
			lualine_b = { "branch", "diff" },
			lualine_c = { { "filename", path = 1, symbols = { modified = "[+]", readonly = "[ro]" } } },
			lualine_x = {
				"diagnostics",
				-- Mostra se o buffer indenta com TAB ou espaços.
				function() return vim.bo.expandtab and "SPC" or "TAB" end,
				"filetype",
			},
			lualine_y = { "progress" },
			lualine_z = { "location" },
		},
	})
end

-- O pywal.nvim pinta comentários, setas de TAB e o número da linha com a color1.
-- No rice a color1 é o vermelho de erro, então esses grupos vão para tons calmos.
local function calm(c)
	for _, group in ipairs({ "Comment", "@comment", "TSComment" }) do
		vim.api.nvim_set_hl(0, group, { fg = c.color8, italic = true })
	end
	vim.api.nvim_set_hl(0, "Whitespace", { fg = c.color8 })
	vim.api.nvim_set_hl(0, "NonText", { fg = c.color8 })
	vim.api.nvim_set_hl(0, "LineNr", { fg = c.color8 })
	vim.api.nvim_set_hl(0, "CursorLineNr", { fg = c.color4, bold = true })
end

local function apply_theme()
	if vim.fn.filereadable(wal_file) == 1 then
		require("pywal").setup()
		local colors = require("pywal.core").get_colors()
		calm(colors)
		lualine_setup(colors)
	else
		-- Sem o arquivo do rice, usa um tema embutido em vez de quebrar.
		vim.cmd.colorscheme("habamax")
		lualine_setup(nil)
	end
	transparent()
end

apply_theme()

-- Recarrega as cores na hora em que o rice reescreve o arquivo.
-- Observa a pasta, porque o arquivo é trocado de forma atômica (rename).
local watcher = vim.uv.new_fs_event()
if watcher and vim.fn.isdirectory(vim.fn.fnamemodify(wal_file, ":h")) == 1 then
	watcher:start(vim.fn.fnamemodify(wal_file, ":h"), {}, function(_, name)
		if name == "colors-wal.vim" then
			vim.schedule(apply_theme)
		end
	end)
end
vim.api.nvim_create_user_command("RiceTheme", apply_theme, { desc = "Recarrega as cores do wallpaper" })

-- -----------------------------------------------------------------------------
-- 5. Autosave
-- -----------------------------------------------------------------------------
-- Salva só arquivos reais, com nome, alterados e graváveis.
local function autosave(buf)
	local bo = vim.bo[buf]
	if bo.modified and bo.buftype == "" and bo.modifiable and not bo.readonly
		and vim.api.nvim_buf_get_name(buf) ~= "" then
		vim.api.nvim_buf_call(buf, function() vim.cmd("silent! lockmarks update") end)
	end
end

vim.api.nvim_create_autocmd({ "InsertLeave", "BufLeave" }, {
	group = vim.api.nvim_create_augroup("RiceAutosave", { clear = true }),
	callback = function(args) autosave(args.buf) end,
})

-- -----------------------------------------------------------------------------
-- 6. :Org — reindenta o arquivo inteiro com TAB real
-- -----------------------------------------------------------------------------
-- Converte a indentação de cada linha para TABs.
-- Com regra de indentação, sobras de espaço são alinhamento (ex.: argumentos) e ficam.
-- Sem regra, cada nível vira um TAB, arredondando sobras como "  mov".
local function tabify_leading_whitespace(keep_alignment)
	local ts = vim.bo.tabstop
	for lnum = 1, vim.api.nvim_buf_line_count(0) do
		local line = vim.api.nvim_buf_get_lines(0, lnum - 1, lnum, false)[1]
		local lead = line:match("^[ \t]*")
		if lead ~= "" and line ~= lead then
			local width = vim.fn.indent(lnum)
			local new
			if keep_alignment then
				new = string.rep("\t", math.floor(width / ts)) .. string.rep(" ", width % ts)
			else
				new = string.rep("\t", math.max(1, math.floor((width + ts / 2) / ts)))
			end
			if new ~= lead then
				vim.api.nvim_buf_set_lines(0, lnum - 1, lnum, false, { new .. line:sub(#lead + 1) })
			end
		end
	end
end

vim.api.nvim_create_user_command("Org", function()
	local view = vim.fn.winsaveview()
	vim.bo.expandtab = false
	-- Só reindenta quando a linguagem tem regra de indentação (C/C++ têm).
	-- Assembly não tem: lá, reindentar empurraria os rótulos; só troca os espaços por TAB.
	local has_rules = vim.bo.indentexpr ~= "" or vim.bo.cindent or vim.bo.lisp
	if has_rules then
		vim.cmd("silent keepjumps normal! gg=G")
	end
	tabify_leading_whitespace(has_rules)
	vim.fn.winrestview(view)
	vim.notify(has_rules and "Org: reindentado com TAB" or "Org: indentação convertida para TAB (sem regra de indentação)")
end, { desc = "Reindenta o arquivo inteiro com TAB real" })

-- -----------------------------------------------------------------------------
-- 7. Atalhos estilo VSCode
-- -----------------------------------------------------------------------------
local map = vim.keymap.set

-- Ctrl+A: selecionar tudo.
map("n", "<C-a>", "ggVG", { desc = "Selecionar tudo" })
map({ "i", "x" }, "<C-a>", "<Esc>ggVG", { desc = "Selecionar tudo" })

-- Ctrl+C / Ctrl+X: sem seleção, agem na linha inteira (como no VSCode).
map("x", "<C-c>", '"+ygv', { desc = "Copiar seleção" })
map("n", "<C-c>", '"+yy', { desc = "Copiar linha" })
map("i", "<C-c>", '<Cmd>normal! "+yy<CR>', { desc = "Copiar linha" })
map("x", "<C-x>", '"+d', { desc = "Recortar seleção" })
map("n", "<C-x>", '"+dd', { desc = "Recortar linha" })
map("i", "<C-x>", '<Cmd>normal! "+dd<CR>', { desc = "Recortar linha" })

-- Ctrl+V: cola do clipboard do sistema; no modo inserção continua inserindo.
map("n", "<C-v>", '"+P', { desc = "Colar" })
map("x", "<C-v>", '"+P', { desc = "Colar sobre a seleção" })
map("i", "<C-v>", "<C-r><C-o>+", { desc = "Colar" })

-- Ctrl+Z / Ctrl+Y: desfazer e refazer.
map("n", "<C-z>", "u", { desc = "Desfazer" })
map("i", "<C-z>", "<Cmd>undo<CR>", { desc = "Desfazer" })
map("x", "<C-z>", "<Esc>u", { desc = "Desfazer" })
map("n", "<C-y>", "<C-r>", { desc = "Refazer" })
map("i", "<C-y>", "<Cmd>redo<CR>", { desc = "Refazer" })
map("x", "<C-y>", "<Esc><C-r>", { desc = "Refazer" })

-- Ctrl+S salva, Ctrl+Q sai (pergunta se algo não foi salvo).
map({ "n", "i", "x" }, "<C-s>", "<Cmd>update<CR>", { desc = "Salvar" })
map({ "n", "i", "x" }, "<C-q>", "<Cmd>confirm qa<CR>", { desc = "Sair" })

-- Alt+j / Alt+k: move a linha (ou a seleção) sem mexer na indentação,
-- para não deslocar rótulos de Assembly. Use :Org para arrumar depois.
local function move_line(dir)
	local lnum = vim.fn.line(".")
	if (dir > 0 and lnum == vim.fn.line("$")) or (dir < 0 and lnum == 1) then
		return
	end
	local col = vim.api.nvim_win_get_cursor(0)[2]
	vim.cmd(dir > 0 and "silent move .+1" or "silent move .-2")
	vim.api.nvim_win_set_cursor(0, { vim.fn.line("."), col })
end

map({ "n", "i" }, "<A-j>", function() move_line(1) end, { desc = "Mover linha para baixo" })
map({ "n", "i" }, "<A-k>", function() move_line(-1) end, { desc = "Mover linha para cima" })
map("x", "<A-j>", ":<C-u>silent! '<,'>move '>+1<CR>gv", { desc = "Mover seleção para baixo", silent = true })
map("x", "<A-k>", ":<C-u>silent! '<,'>move '<-2<CR>gv", { desc = "Mover seleção para cima", silent = true })

-- -----------------------------------------------------------------------------
-- 8. Terminal externo (sem terminal embutido)
-- -----------------------------------------------------------------------------
-- Ctrl+T abre um Kitty separado em ~/Vscode; a pasta é criada se não existir.
local function external_terminal()
	local dir = vim.fn.expand("~/Vscode")
	vim.fn.mkdir(dir, "p")
	vim.fn.jobstart({ "kitty", "--directory", dir }, { detach = true })
end

map({ "n", "i", "x" }, "<C-t>", external_terminal, { desc = "Terminal externo em ~/Vscode" })
