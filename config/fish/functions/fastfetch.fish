# fastfetch no tom do wallpaper: o rice exporta a cor em $rice_accent_sgr.
function fastfetch --wraps fastfetch --description 'fastfetch com a cor do rice'
	if set -q rice_accent_sgr
		command fastfetch --logo-color-1 $rice_accent_sgr --color-keys $rice_accent_sgr --color-title $rice_accent_sgr $argv
	else
		command fastfetch $argv
	end
end
