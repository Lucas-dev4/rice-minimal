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
    set_color normal
    printf '%s' (prompt_pwd)
    if test $last_status -ne 0
        printf ' [%s]' $last_status
    end
    printf ' > '
end
function fish_right_prompt
end
