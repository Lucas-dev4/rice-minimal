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
opt.relativenumber = false    -- números fixos
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
		"StatusLine", "StatusLineNC", "MsgArea", "WinSeparator", "TabLine", "TabLineFill", "WinBar", "WinBarNC",
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
-- Salva ao sair do modo inserção, ao trocar de buffer ou de janela, depois de
-- qualquer edição no modo normal e 300 ms depois de parar de digitar (sem sair do insert).
-- Salva só arquivos reais, com nome, alterados e graváveis.
local function autosave(buf)
	local bo = vim.bo[buf]
	if bo.modified and bo.buftype == "" and bo.modifiable and not bo.readonly
		and vim.api.nvim_buf_get_name(buf) ~= "" then
		vim.api.nvim_buf_call(buf, function() vim.cmd("silent! lockmarks update") end)
	end
end

local autosave_group = vim.api.nvim_create_augroup("RiceAutosave", { clear = true })
vim.api.nvim_create_autocmd({ "InsertLeave", "BufLeave", "FocusLost", "TextChanged" }, {
	group = autosave_group,
	callback = function(args) autosave(args.buf) end,
})

-- Enquanto digita: cada tecla reinicia a contagem; 300 ms sem digitar, salva.
local typing = vim.uv.new_timer()
vim.api.nvim_create_autocmd("TextChangedI", {
	group = autosave_group,
	callback = function(args)
		typing:stop()
		typing:start(300, 0, vim.schedule_wrap(function()
			if vim.api.nvim_buf_is_valid(args.buf) then autosave(args.buf) end
		end))
	end,
})

-- -----------------------------------------------------------------------------
-- 5b. Modo inserção ao entrar
-- -----------------------------------------------------------------------------
-- Abrir o Neovim, um arquivo ou voltar para uma janela editável já entra no insert.
-- Janelas especiais (saída, ajuda, lazy) ficam no modo normal.
vim.api.nvim_create_autocmd({ "VimEnter", "BufEnter", "WinEnter" }, {
	callback = function(args)
		local bo = vim.bo[args.buf]
		if bo.buftype == "" and bo.modifiable and not bo.readonly then
			vim.cmd.startinsert()
		elseif bo.buftype ~= "" then
			vim.cmd.stopinsert()  -- saída, ajuda e afins não recebem digitação
		end
	end,
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

-- Alt+↑ / Alt+↓: move a linha (ou a seleção) sem mexer na indentação,
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

map({ "n", "i" }, "<A-Down>", function() move_line(1) end, { desc = "Mover linha para baixo" })
map({ "n", "i" }, "<A-Up>", function() move_line(-1) end, { desc = "Mover linha para cima" })
map("x", "<A-Down>", ":<C-u>silent! '<,'>move '>+1<CR>gv", { desc = "Mover seleção para baixo", silent = true })
map("x", "<A-Up>", ":<C-u>silent! '<,'>move '<-2<CR>gv", { desc = "Mover seleção para cima", silent = true })

-- Shift+setas: seleção. Para cima/baixo seleciona linhas inteiras.
-- No modo inserção, <C-o> abre a seleção e o Esc volta para o insert.
map("n", "<S-Up>", "Vk", { desc = "Selecionar linha acima" })
map("n", "<S-Down>", "Vj", { desc = "Selecionar linha abaixo" })
map("n", "<S-Left>", "vh", { desc = "Selecionar à esquerda" })
map("n", "<S-Right>", "vl", { desc = "Selecionar à direita" })
map("i", "<S-Up>", "<C-o>Vk", { desc = "Selecionar linha acima" })
map("i", "<S-Down>", "<C-o>Vj", { desc = "Selecionar linha abaixo" })
map("i", "<S-Left>", "<C-o>vh", { desc = "Selecionar à esquerda" })
map("i", "<S-Right>", "<C-o>vl", { desc = "Selecionar à direita" })
map("x", "<S-Up>", "k", { desc = "Estender seleção para cima" })
map("x", "<S-Down>", "j", { desc = "Estender seleção para baixo" })
map("x", "<S-Left>", "h", { desc = "Estender seleção à esquerda" })
map("x", "<S-Right>", "l", { desc = "Estender seleção à direita" })

-- -----------------------------------------------------------------------------
-- 8. Pares automáticos: ( [ { ' "
-- -----------------------------------------------------------------------------
local closing = { ["("] = ")", ["["] = "]", ["{"] = "}", ['"'] = '"', ["'"] = "'" }

-- Caracteres antes e depois do cursor.
local function around()
	local col = vim.api.nvim_win_get_cursor(0)[2]
	local line = vim.api.nvim_get_current_line()
	return line:sub(col, col), line:sub(col + 1, col + 1)
end

-- <C-g>U mantém o desfazer e o "." funcionando depois de mover o cursor.
local right, left = "<C-g>U<Right>", "<C-g>U<Left>"

for open, close in pairs(closing) do
	map("i", open, function()
		local before, after = around()
		if open == close then
			if after == close then return right end      -- pula a aspa que já fecha
			if before:match("[%w]") then return open end  -- it's, don't: só um apóstrofo
		end
		if after:match("[%w]") then return open end      -- antes de uma palavra, não fecha
		return open .. close .. left
	end, { expr = true, desc = "Par automático " .. open .. close })
end

-- Digitar o fechamento quando ele já está à direita só passa por cima.
for _, close in ipairs({ ")", "]", "}" }) do
	map("i", close, function()
		local _, after = around()
		return after == close and right or close
	end, { expr = true })
end

-- Backspace entre um par vazio apaga os dois.
map("i", "<BS>", function()
	local before, after = around()
	return closing[before] == after and after ~= "" and "<BS><Del>" or "<BS>"
end, { expr = true })

-- Enter entre { } abre um bloco com a linha do meio já indentada.
map("i", "<CR>", function()
	local before, after = around()
	return (before == "{" and after == "}") and "<CR><Esc>O" or "<CR>"
end, { expr = true })

-- -----------------------------------------------------------------------------
-- 9. Ctrl+R: compila e roda o arquivo, saída num painel à direita
-- -----------------------------------------------------------------------------
-- Não é um terminal: o teclado do programa vem da caixa de entrada (Alt+I).
local run = { buf = nil, win = nil, job = nil, input_win = nil, last_file = nil, code_win = nil }
local build = vim.fn.stdpath("cache") .. "/rice-run"
local inputs = vim.fn.stdpath("state") .. "/rice-run"

-- Cada arquivo de código tem sua própria entrada, guardada em disco.
local function input_path(file)
	return inputs .. "/" .. vim.fn.fnamemodify(file, ":t") .. "-" .. vim.fn.sha256(file):sub(1, 12) .. ".in"
end

-- Acha um buffer pelo caminho exato. vim.fn.bufnr() trata o nome como padrão:
-- em "[saida]", os colchetes casariam com qualquer letra s, a, i ou d.
local function find_buf(path)
	for _, buf in ipairs(vim.api.nvim_list_bufs()) do
		if vim.api.nvim_buf_get_name(buf) == path then return buf end
	end
	return -1
end

-- O arquivo de código a rodar: o dono da caixa de entrada, o buffer atual se for
-- um arquivo de verdade ou, no painel de saída, o último arquivo de código usado.
-- Arquivos de entrada são reconhecidos pela pasta: ao abrir um, o Neovim avisa
-- que entrou no buffer antes de ele ser marcado como entrada.
local function is_code(buf)
	local name = vim.api.nvim_buf_get_name(buf)
	return vim.bo[buf].buftype == "" and name ~= "" and not vim.b[buf].rice_target
		and name:sub(1, #inputs + 1) ~= inputs .. "/"
end

local function code_file()
	if vim.b.rice_target then return vim.b.rice_target end
	local name = vim.api.nvim_buf_get_name(0)
	if vim.bo.buftype == "" and name ~= "" then return name end
	return run.last_file
end

vim.api.nvim_create_autocmd({ "BufEnter", "WinEnter" }, {
	callback = function(args)
		if is_code(args.buf) then
			run.last_file = vim.api.nvim_buf_get_name(args.buf)
			run.code_win = vim.api.nvim_get_current_win()
		end
	end,
})

-- Coluna da direita: entrada em cima (maior) e saída embaixo (40%).
-- Só ajusta alturas com as duas na mesma coluna; sozinha, a janela ocupa tudo.
local function balance()
	if run.win and vim.api.nvim_win_is_valid(run.win) and run.input_win and vim.api.nvim_win_is_valid(run.input_win) then
		local total = vim.api.nvim_win_get_height(run.win) + vim.api.nvim_win_get_height(run.input_win)
		vim.api.nvim_win_set_height(run.win, math.max(5, math.floor(total * 0.4)))
	end
end

-- Trocas internas de janela sem eventos: passar pela saída (que tira do insert)
-- no meio do caminho não pode decidir o modo da janela onde o cursor termina.
local function quietly(fn)
	local saved = vim.o.eventignore
	vim.o.eventignore = "all"
	local ok, err = pcall(fn)
	vim.o.eventignore = saved
	if not ok then error(err) end
end

-- Divide sem eventos: a janela nova nasce mostrando o código e seria tomada por ele.
local function new_column()
	vim.cmd("noautocmd botright vsplit")
	vim.api.nvim_win_set_width(0, math.max(40, math.floor(vim.o.columns * 0.35)))
end

-- O texto da entrada: do buffer aberto (mesmo sem salvar) ou do disco.
local function input_text(file)
	local path = input_path(file)
	local buf = find_buf(path)
	local lines = buf ~= -1 and vim.api.nvim_buf_get_lines(buf, 0, -1, false)
		or (vim.fn.filereadable(path) == 1 and vim.fn.readfile(path) or {})
	local text = table.concat(lines, "\n")
	return text:match("%S") and (text .. "\n") or nil
end

local function has(tool) return vim.fn.executable(tool) == 1 end

-- Passos (comandos em sequência) para o arquivo atual, ou nil e um motivo.
local function steps_for(file, buf)
	local ft, bin = vim.bo[buf].filetype, build .. "/" .. vim.fn.fnamemodify(file, ":t:r")
	local text = table.concat(vim.api.nvim_buf_get_lines(buf, 0, -1, false), "\n")
	if ft == "c" then
		return { { "gcc", "-std=c17", "-Wall", "-Wextra", "-g", file, "-o", bin, "-lm" }, { bin } }
	elseif ft == "cpp" then
		return { { "g++", "-std=c++20", "-Wall", "-Wextra", "-g", file, "-o", bin }, { bin } }
	elseif ft == "nasm" then
		if not has("nasm") then return nil, "nasm não está instalado: sudo pacman -S nasm" end
		-- Com "global main" o programa usa a libc e é ligado pelo gcc; com _start, pelo ld.
		local link = text:match("global%s+main") and { "gcc", "-no-pie", bin .. ".o", "-o", bin } or { "ld", bin .. ".o", "-o", bin }
		return { { "nasm", "-f", "elf64", "-g", "-F", "dwarf", file, "-o", bin .. ".o" }, link, { bin } }
	elseif ft == "asm" then
		local start = text:match("_start") and { "-nostdlib", "-static" } or {}
		if has("aarch64-linux-gnu-gcc") and has("qemu-aarch64") and (text:match("%f[%w]x[0-9]+%f[^%w]") or text:match("svc")) then
			return { vim.list_extend({ "aarch64-linux-gnu-gcc", "-static", file, "-o", bin }, start), { "qemu-aarch64", bin } }
		elseif text:match("svc") or text:match("%f[%w]x[0-9]+,") then
			return nil, "ARM precisa de aarch64-linux-gnu-gcc e qemu-user (qemu-aarch64)"
		end
		return { vim.list_extend({ "gcc", file, "-o", bin }, start), { bin } }
	elseif ft == "python" then return { { "python3", file } }
	elseif ft == "lua" then return { { "lua", file } }
	elseif ft == "sh" or ft == "bash" then return { { "bash", file } }
	end
	return nil, "sem regra para rodar arquivos do tipo '" .. (ft ~= "" and ft or "?") .. "'"
end

-- Abre (ou reaproveita) o painel à direita sem tirar o foco do código.
local function panel()
	if not (run.buf and vim.api.nvim_buf_is_valid(run.buf)) then
		run.buf = vim.api.nvim_create_buf(false, true)
		vim.bo[run.buf].bufhidden = "hide"
		vim.api.nvim_buf_set_name(run.buf, "[saida]")
		-- q fecha o painel e para o programa, se ainda estiver rodando.
		vim.keymap.set("n", "q", function()
			if run.job then vim.fn.jobstop(run.job) end
			if run.win and vim.api.nvim_win_is_valid(run.win) then vim.api.nvim_win_close(run.win, true) end
		end, { buffer = run.buf, desc = "Fechar a saída" })
	end
	if not (run.win and vim.api.nvim_win_is_valid(run.win)) then quietly(function()
		local code = vim.api.nvim_get_current_win()
		if run.input_win and vim.api.nvim_win_is_valid(run.input_win) then
			-- Com a entrada aberta, a saída fica logo abaixo dela.
			vim.api.nvim_set_current_win(run.input_win)
			vim.cmd("noautocmd belowright split")
		else
			new_column()
		end
		run.win = vim.api.nvim_get_current_win()
		vim.api.nvim_win_set_buf(run.win, run.buf)
		balance()
		for option, value in pairs({ number = false, relativenumber = false, signcolumn = "no",
			wrap = true, list = false, cursorline = false, winfixwidth = true }) do
			vim.wo[run.win][option] = value
		end
		vim.api.nvim_set_current_win(code)
	end) end
	vim.bo[run.buf].modifiable = true
	vim.api.nvim_buf_set_lines(run.buf, 0, -1, false, {})
	vim.bo[run.buf].modifiable = false
end

local ns = vim.api.nvim_create_namespace("rice-run")

local function write(lines, group)
	if not vim.api.nvim_buf_is_valid(run.buf) then return end
	local first = vim.api.nvim_buf_line_count(run.buf)
	if first == 1 and vim.api.nvim_buf_get_lines(run.buf, 0, 1, false)[1] == "" then first = 0 end
	vim.bo[run.buf].modifiable = true    -- a saída só muda por aqui; ninguém digita nela
	vim.api.nvim_buf_set_lines(run.buf, first, -1, false, lines)
	vim.bo[run.buf].modifiable = false
	if group then
		for i = first, first + #lines - 1 do
			vim.api.nvim_buf_set_extmark(run.buf, ns, i, 0, { line_hl_group = group })
		end
	end
	if run.win and vim.api.nvim_win_is_valid(run.win) then
		vim.api.nvim_win_set_cursor(run.win, { vim.api.nvim_buf_line_count(run.buf), 0 })
	end
end

local function run_file()
	local file = code_file()
	if not file then return vim.notify("Salve o arquivo antes de rodar", vim.log.levels.WARN) end
	local buf = find_buf(file)
	if buf == -1 then buf = vim.fn.bufadd(file); vim.fn.bufload(buf) end
	run.last_file = file
	vim.cmd("silent! update")
	vim.api.nvim_buf_call(buf, function() vim.cmd("silent! update") end)
	local steps, reason = steps_for(file, buf)
	local stdin = input_text(file)
	if run.job then vim.fn.jobstop(run.job) end
	panel()
	if not steps then return write({ "[ !! ] " .. reason }, "WarningMsg") end
	vim.fn.mkdir(build, "p")
	local started = vim.uv.hrtime()
	if stdin then
		-- Mostra o que vai para o programa; strtrans deixa caracteres invisíveis à vista.
		local lines = vim.split(stdin, "\n", { trimempty = true })
		local shown = vim.fn.strtrans(lines[1] or ""):sub(1, 40)
		write({ string.format("< entrada: %s%s", shown, #lines > 1 and string.format("  (+%d linhas)", #lines - 1) or "") }, "Comment")
	end

	local function step(index)
		local cmd = steps[index]
		-- Mostra só os nomes dos arquivos; o caminho completo não cabe no painel.
		local shown = vim.tbl_map(function(arg)
			return (arg == file or arg:find(build, 1, true) == 1) and vim.fn.fnamemodify(arg, ":t") or arg
		end, cmd)
		write({ "$ " .. table.concat(shown, " ") }, "Comment")
		local function output(_, data)
			if data then
				if data[#data] == "" then table.remove(data) end
				if #data > 0 then write(data) end
			end
		end
		run.job = vim.fn.jobstart(cmd, {
			cwd = vim.fn.fnamemodify(file, ":h"),
			on_stdout = output,
			on_stderr = output,
			on_exit = function(_, code)
				run.job = nil
				if code == 0 and index < #steps then return step(index + 1) end
				local ms = (vim.uv.hrtime() - started) / 1e6
				write({ "", string.format("[ %s ] saiu com %d em %.2f s", code == 0 and "OK" or "FAIL", code, ms / 1000) },
					code == 0 and "DiagnosticOk" or "DiagnosticError")
			end,
		})
		if run.job <= 0 then
			run.job = nil
			write({ "[ FAIL ] não foi possível executar " .. cmd[1] }, "DiagnosticError")
		else
			-- Só o programa (último passo) recebe a entrada; o compilador não.
			if index == #steps and stdin then vim.fn.chansend(run.job, stdin) end
			vim.fn.chanclose(run.job, "stdin")
		end
	end
	step(1)
end

map({ "n", "i", "x" }, "<C-r>", run_file, { desc = "Compilar e rodar o arquivo" })

-- Alt+I abre (ou fecha) a caixa de entrada do arquivo atual, abaixo da saída.
local function toggle_input()
	if run.input_win and vim.api.nvim_win_is_valid(run.input_win) then
		local was_here = vim.api.nvim_get_current_win() == run.input_win
		quietly(function()
			vim.api.nvim_win_close(run.input_win, true)
			-- Fechada de dentro, volta para o código em vez de cair na saída.
			if was_here and run.code_win and vim.api.nvim_win_is_valid(run.code_win) then
				vim.api.nvim_set_current_win(run.code_win)
			end
		end)
		run.input_win = nil
		if was_here then vim.cmd.startinsert() end
		return
	end
	local file = code_file()
	if not file then return vim.notify("Abra um arquivo de código antes de criar a entrada", vim.log.levels.WARN) end
	vim.fn.mkdir(inputs, "p")
	-- A entrada fica em cima da saída, na mesma coluna; sem saída, ocupa a coluna toda.
	quietly(function()
		if run.win and vim.api.nvim_win_is_valid(run.win) then
			vim.api.nvim_set_current_win(run.win)
			vim.cmd("aboveleft split")
		else
			new_column()
		end
	end)
	run.input_win = vim.api.nvim_get_current_win()
	vim.cmd("edit " .. vim.fn.fnameescape(input_path(file)))
	local buf = vim.api.nvim_get_current_buf()
	vim.b[buf].rice_target = file
	vim.bo[buf].filetype = "text"
	vim.wo[run.input_win].number = false
	vim.wo[run.input_win].signcolumn = "no"
	vim.wo[run.input_win].winbar = " entrada: " .. vim.fn.fnamemodify(file, ":t")
	balance()
	vim.cmd.startinsert()
end

map({ "n", "i", "x" }, "<A-i>", toggle_input, { desc = "Caixa de entrada do Ctrl+R" })

-- Alt+1 código, Alt+2 entrada, Alt+3 saída (de cima para baixo na coluna).
-- Se a janela não existe, o atalho cria. Na saída, sai do modo inserção.
local function go(which)
	if which == 1 then
		local win = run.code_win
		if not (win and vim.api.nvim_win_is_valid(win)) then
			for _, w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
				if is_code(vim.api.nvim_win_get_buf(w)) then win = w break end
			end
		end
		if win then vim.api.nvim_set_current_win(win); vim.cmd.startinsert() end
	elseif which == 2 then
		if run.input_win and vim.api.nvim_win_is_valid(run.input_win) then
			vim.api.nvim_set_current_win(run.input_win)
			vim.cmd.startinsert()
		else
			toggle_input()
		end
	else
		if not (run.win and vim.api.nvim_win_is_valid(run.win)) then panel() end
		vim.api.nvim_set_current_win(run.win)
		vim.cmd.stopinsert()
	end
end

for i = 1, 3 do
	map({ "n", "i", "x" }, "<A-" .. i .. ">", function() go(i) end, { desc = ({ "Ir para o código", "Ir para a entrada", "Ir para a saída" })[i] })
end

-- -----------------------------------------------------------------------------
-- 10. Terminal externo (sem terminal embutido)
-- -----------------------------------------------------------------------------
-- Ctrl+T abre um Kitty separado em ~/Vscode; a pasta é criada se não existir.
local function external_terminal()
	local dir = vim.fn.expand("~/Vscode")
	vim.fn.mkdir(dir, "p")
	vim.fn.jobstart({ "kitty", "--directory", dir }, { detach = true })
end

map({ "n", "i", "x" }, "<C-t>", external_terminal, { desc = "Terminal externo em ~/Vscode" })
