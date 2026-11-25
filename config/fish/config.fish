# config.fish — Fish do rice. Mantém a configuração do CachyOS e troca só a saudação e o prompt.
# Instalado em ~/.config/fish/config.fish. As cores vêm de rice_theme_refresh (rice-adaptive.fish).
test -f /usr/share/cachyos-fish-config/cachyos-config.fish; and source /usr/share/cachyos-fish-config/cachyos-config.fish

# overwrite greeting
# potentially disabling fastfetch
#function fish_greeting
#    # smth smth
#end

# Rice minimal: preserve CachyOS setup; replace only greeting and prompt.
# Sem mensagem de boas-vindas.
function fish_greeting
end
# Prompt: pasta atual na cor do wallpaper, código de erro entre colchetes se o último comando falhou, e " > ".
function fish_prompt
    set -l last_status $status
    rice_theme_refresh
    set_color $rice_prompt_color
    printf '%s' (prompt_pwd)
    if test $last_status -ne 0
        set_color $rice_error_color
        printf ' [%s]' $last_status
        set_color $rice_prompt_color
    end
    printf ' > '
    set_color normal
end
# Nada no lado direito.
function fish_right_prompt
end
