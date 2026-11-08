source /usr/share/cachyos-fish-config/cachyos-config.fish

# overwrite greeting
# potentially disabling fastfetch
#function fish_greeting
#    # smth smth
#end

# Rice minimal: preserve CachyOS setup; replace only greeting and prompt.
function fish_greeting
end
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
function fish_right_prompt
end
