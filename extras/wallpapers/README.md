# Wallpapers

`wallpapers` opens the standard-library curses selector. No thumbnails, graphical toolkit or daemon is needed to browse. Applying requires the existing Wayland/Noctalia session.

- `j`/Down and `k`/Up move; `/` filters names, Enter finishes the search.
- Enter outside search applies; `r` selects a random item; `q`/Esc exits.
- `*` marks the effective wallpaper, comparing resolved paths so existing symbolic links work.
- `wallpapers --list` prints the folder, current selection and image paths without changing anything.
- `wallpapers --apply '/path/with spaces/image.png'` uses the same application function as Enter.

The folder is read from `~/.config/waypaper/config.ini`: currently `~/Imagens/Wallpapers`. Existing links resolve into `~/Pictures/Wallpapers`; an existing JPG also resides directly in the configured folder. No image library was created or copied. Recursive discovery follows Waypaper's existing subfolder settings.

The selector calls Waypaper with an argument list and `--no-post-command`, then runs the shared theme hook synchronously. Waypaper saves the choice in its own configuration; there is no separate selector state. The GUI calls that same hook asynchronously. The configured hook reads Waypaper's saved selection rather than interpolating file names into a shell string. Spaces, quotes, semicolons and dollar expressions were exercised through the real Waypaper command.

Noctalia remains the only wallpaper renderer (`backend = none` in Waypaper). Hyprpaper stays installed but is not started. See [theme behavior and recovery](../theme/README.md).
