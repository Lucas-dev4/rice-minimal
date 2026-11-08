# Adaptive theme

Installed dependency: Matugen **4.2.0-1.1**, matching CachyOS's available package. No packages were installed. CLI syntax was checked against the installed binary and exercised with real images:

```sh
matugen image IMAGE --config extras/theme/matugen.toml --dry-run --json hex --mode dark --type scheme-neutral --source-color-index 0 --quiet
```

The isolated TOML has empty templates. Matugen never applies a wallpaper, runs user hooks or overwrites global application themes. Its dark neutral colors are desaturated further; ANSI colors retain subdued distinctions. Basic terminal foreground/background contrast is checked. Transparency makes actual contrast depend on the image beneath the window.

## Event flow

Waypaper GUI or `wallpapers` → save the selection through Waypaper → shared `theme.py wallpaper` hook → Noctalia applies the image → Matugen extracts colors once → generated files are validated → one atomic symlink publishes the generation → update the running components → ask Noctalia to sync the login screen (only when the palette changed; a failure does not fail the wallpaper change).

The hook takes an exclusive `flock` covering wallpaper application, generation and reload. It reads the latest saved Waypaper selection after acquiring the lock; queued duplicate events reuse the fingerprinted palette. The fingerprint includes the resolved image path, size, modification time and theme algorithm version. Menu option 4 intentionally forces regeneration. No polling, watcher or new daemon is used.

Runtime state is in `~/.local/state/rice-minimal/theme/`:

- `current` and `previous`: symlinks to immutable palette directories.
- Each directory contains `palette.json`, `colors.css`, `kitty.conf`, `hyprland.lua`, `colors.fish` and `nvim.lua`.
- `status.json`: last hook result and generator errors, if any.
- `generation.lock`: process lock, released by the OS when the process ends.

Generation failure preserves the last working palette. First startup or missing/corrupt cached files use the built-in static emergency palette. Generations are retained for recovery and are not treated as disposable backups.

## Component integration

| Component | Integration | Update |
| --- | --- | --- |
| Waybar | Existing CSS imports generated colors; all container/module/hover backgrounds transparent | SIGUSR2 reloads the existing process |
| Kitty | One color-only include appended to the existing config | SIGUSR1 reloads running user-owned Kitty processes |
| Hyprland | One `config.rice-adaptive` include, using `general.col.active_border` / `inactive_border` | `hyprctl eval` applies only generated border settings |
| Fish | Small conf.d helper; existing prompt shape and error status retained | Generated assignments are sourced at the next prompt |
| Neovim | One small Lua include, no plugins | FocusGained / BufEnter / VimResume reload if the generation changed; `:RiceTheme` forces it |

Kitty's `background_opacity 0.85`, padding and other settings remain intact. The compositor keeps blur, shadows, rounding and animations disabled; borders are 1 px. Menus use ASCII framing and the terminal's existing transparency and ANSI colors.

Fish shells already open before installation need `source ~/.config/fish/config.fish` once to load the new prompt hook. Neovim instances already open before installation need `:source ~/.config/nvim/init.lua` once. New instances load automatically. Nothing injects commands into an existing shell or editor.

The Waybar's text is chosen from muted light/dark/intermediate tones by sampling the image's visible top strip, assuming centered cover scaling. Separate module colors accommodate bright and dark parts of the same image. Active workspace text retains a contrast-adjusted wallpaper accent. `palette.json` records sampled contrast by module. Module bounds are estimates for the current 13 px monospace layout and focused monitor; very heterogeneous images, different scaling, multiple monitors or changing workspace/title widths can reduce local contrast. The implementation adjusts text only and introduces no background boxes or blur. Run menu option 4 after changing monitor geometry. This is a measured heuristic, not a guarantee of contrast at every pixel.

The Noctalia renderer, notifications, launcher and existing shortcuts remain intact. Its preexisting templates and own visual behavior remain its responsibility. GTK, Qt and btop follow Noctalia's own templates. Firefox, VS Code, games and other application-specific themes are not synchronized. The Noctalia wallpaper panel shortcut was removed because it bypassed the hook; a change made directly through Noctalia's IPC still does, and `SYNC ALL` (or `rice sync`) repairs it.

## Login

The existing XDG autostart still starts `scripts/session.py`. It waits for Noctalia, validates/reuses `current`, restores Waypaper's saved wallpaper through Noctalia and starts Waybar. **Matugen is never run during login.** If Waybar stops, the existing supervisor shows Noctalia's bar again. New Fish, Kitty and Neovim instances read the cached files; Hyprland loads its generated module when reading its normal configuration.

The cached startup/restore function was tested in the current session, with an assertion that it did not replace the palette generation. An actual logout/login was intentionally not performed.

## Commands and recovery

`rice` offers Wallpapers, Super, palette inspection, forced regeneration and restoration of the previous theme. It exits completely when closed. `Restore previous theme` swaps the two saved generations and reloads components, keeping the selected wallpaper unchanged. Running it again returns to the other generation.

Equivalent commands from the project directory:

```sh
python3 extras/theme/theme.py show
python3 extras/theme/theme.py regenerate
python3 extras/theme/theme.py restore
```

To revert **all Phase 3 integration**, the prepared backup is:

```sh
python3 ~/Projetos/rice-minimal/restore.py ~/Projetos/rice-minimal/backups/phase3-20261105-220201-094267
hyprctl reload config-only
pkill -USR1 -u "$USER" -x kitty
pkill -USR2 -u "$USER" -x waybar
```

The restorer saves the current files before restoring originals, removes the new launchers/includes registered in the manifest and does not restart the graphical session. Open a fresh Fish shell afterward. In an already-open Neovim, remove the old adaptive autocmds with `:lua pcall(vim.api.nvim_del_augroup_by_name, 'RiceAdaptive')`, then use `:colorscheme default`. Runtime palette history and new source files in `extras/` remain on disk but are no longer loaded. Previous backups and `backups/LATEST` were not replaced.

## Validation

- Nine unit tests: generation failure, first-run emergency theme, corrupt cache, duplicate-event cache, exclusive lock, rollback, unsafe color rejection, special names and light/dark/mixed wallpaper contrast.
- Original Super safety tests pass from both the canonical and compatibility paths; 52 static bindings validate.
- Real curses PTYs exercised search, movement, random selection, menu navigation and exit without image changes.
- Real session: TUI Enter changed an existing image, Waypaper recognized it, the hook generated colors, GUI-equivalent CLI selection and `--restore` worked, and the original image was recovered.
- Generated Lua/Fish syntax and GTK CSS parse; Kitty parser confirms opacity; headless Neovim confirms highlights/settings; Hyprland runtime assertions confirm border size, no blur, square corners and no animations.
- `VALIDACAO-FASE3.json` contains the session results. No partitions, bootloader, kernel, drivers or Linux Mint were modified.

Primary references checked alongside installed help and `/usr/share/hypr/stubs/hl.meta.lua`: [Matugen usage](https://github.com/InioX/matugen/wiki/Usage), [Hyprland Lua configuration](https://wiki.hypr.land/configuring/core/config-options/), [Kitty includes and reload](https://sw.kovidgoyal.net/kitty/conf/).

Terminal text is the one exception to the subdued palette: Kitty's ANSI colors, Fish highlighting and `LS_COLORS`/`EZA_COLORS` use `vivid()`, which keeps each color's hue but raises saturation, and lightness only as far as a 4.5:1 contrast needs. Open Fish shells pick these up at the next prompt. Bars and Noctalia keep the subdued colors.

The terminal accent comes from the image's most present hue (`image_hue`), not from Matugen's choice, which can be unrelated to what the image looks like. Hues next to red move aside so commands never read as errors, and nearly gray images get a softer accent. Palettes generated before this keep working through their Matugen accent.

Waybar modules each keep a hue (CPU green, RAM yellow, VOL cyan, clock and active workspace in the terminal accent). `bar_contrast` darkens or lightens each one only as far as its own strip of the wallpaper needs for 4.5:1, so a module is never less readable than plain white or black would be. Where no single color reaches that, a faint halo turns on for that module only. Separators are drawn at 40% opacity with Pango markup.
