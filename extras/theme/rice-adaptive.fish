# rice-adaptive.fish — carrega as cores do wallpaper no Fish (colors.fish da geração atual).
# É chamado a cada prompt, então trocar o wallpaper muda as cores sem abrir outro terminal.
# Reload small color assignments at the next prompt; never run a generator here.
function rice_theme_refresh
    set -l colors "$HOME/.local/state/rice-minimal/theme/current/colors.fish"
    if test -r "$colors"
        source "$colors"
    else
        set -g rice_prompt_color a6b898
        set -g rice_error_color d6aaa1
    end
end
rice_theme_refresh
