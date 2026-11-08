# zoxide aprende as pastas visitadas; o yazi usa isso na tecla z.
if status is-interactive; and command -q zoxide
	zoxide init fish | source
end
