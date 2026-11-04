#!/usr/bin/env bash
# Installs omarchy-desktop-icons into ~/.local/share and puts the launcher on
# $PATH. Run it from inside the source directory:  ./install.sh
#
#   ./install.sh            install or upgrade
#   ./install.sh --check    report whether the install matches this source AND
#                           whether your icons are where the app will read them
#   ./install.sh --where    print the destinations and where each came from
#
# Vendored into desktop-manager as profiles/omarchy-desktop-icons, so it is also
# what Desktop Manager → Apps → Utilities → "Desktop icons → Install" runs.
#
# Destinations are resolved from the SESSION's environment, not this shell's —
# see ../../scripts/xdg-session-paths.sh for why that distinction matters.
set -euo pipefail

SRC="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"

CHECK=0
WHERE=0
for arg in "$@"; do
    case "$arg" in
        --check) CHECK=1 ;;
        --where) WHERE=1 ;;
        -h|--help) sed -n '2,13p' "$(readlink -f "$0")"; exit 0 ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

REFERENCE="${ODI_REFERENCE_BUILD:-}"

# The resolver lives at the top of desktop-manager when this runs from the
# repo, and next to the profile when the profile is shipped on its own.
for candidate in "$SRC/../../scripts/xdg-session-paths.sh" "$SRC/xdg-session-paths.sh"; do
    if [ -r "$candidate" ]; then
        # shellcheck source=../../scripts/xdg-session-paths.sh
        . "$candidate"
        break
    fi
done
command -v xdg_session_paths_resolve >/dev/null 2>&1 \
    || { echo "xdg-session-paths.sh not found next to this script" >&2; exit 1; }
xdg_session_paths_resolve

DEST="$XDGS_DATA_HOME/omarchy-desktop-icons"
BIN="$XDGS_BIN_DIR"
# The app itself (Config.qml, and bin/omarchy-desktop-icons) reads its config
# from the session's $XDG_CONFIG_HOME. Jan's session sets that to
# ~/.config-ii, so icons seeded into a hardcoded ~/.config are invisible to
# the app: it would start with no config, write fresh defaults, and his own
# icon layout would simply be gone (JAN-78).
CONFDIR="$XDGS_CONFIG_HOME/omarchy-desktop-icons"
# NOT $XDGS_CONFIG_HOME/systemd/user. systemd --user starts at login, before
# the session sets XDG_CONFIG_HOME, so its unit search path never moves with
# it — a unit written under the session's config root is never enumerated.
UNITS="$XDGS_SYSTEMD_USER_DIR"

if [ "$WHERE" = 1 ]; then
    echo "omarchy-desktop-icons destinations:"
    xdg_session_paths_report
    echo
    printf '  %-14s %s\n' 'payload' "$DEST"
    printf '  %-14s %s\n' 'command' "$BIN/omarchy-desktop-icons"
    printf '  %-14s %s\n' 'icons'   "$CONFDIR/config.json"
    printf '  %-14s %s\n' 'service' "$UNITS/omarchy-desktop-icons.service"
    exit 0
fi

# --- --check -----------------------------------------------------------------
# Two questions. The second one is the one that was never asked: the payload
# can match this source exactly and the app can still start with no config,
# because `Quickshell.env("XDG_CONFIG_HOME")` and a hardcoded ~/.config are
# different directories in this session.
if [ "$CHECK" = 1 ]; then
    STALE=()

    WORK="$(mktemp -d "${TMPDIR:-/tmp}/odi-check.XXXXXX")"
    trap 'rm -rf "$WORK"' EXIT

    if ! ODI_REFERENCE_BUILD=1 \
         XDG_SESSION_PATHS_HOME="$WORK" \
         XDG_SESSION_PATHS_XDG_CONFIG_HOME="$WORK/config" \
         XDG_SESSION_PATHS_XDG_DATA_HOME="$WORK/share" \
         XDG_SESSION_PATHS_SYSTEMD_USER_DIR="$WORK/units" \
         XDG_SESSION_PATHS_BIN_DIR="$WORK/bin" \
         bash "$SRC/install.sh" >"$WORK/log" 2>&1; then
        echo "could not build a reference install from $SRC:" >&2
        cat "$WORK/log" >&2
        exit 1
    fi

    while IFS= read -r -d '' file; do
        relative="${file#"$WORK/share/omarchy-desktop-icons/"}"
        if [ ! -e "$DEST/$relative" ]; then
            STALE+=("$DEST/$relative is missing")
        elif ! cmp -s "$file" "$DEST/$relative"; then
            STALE+=("$DEST/$relative is not the version in this source")
        fi
    done < <(find "$WORK/share/omarchy-desktop-icons" -type f -print0)

    if [ ! -f "$UNITS/omarchy-desktop-icons.service" ]; then
        STALE+=("omarchy-desktop-icons.service is not in $UNITS, where systemd --user looks")
    fi
    for orphan in "$XDGS_HOME"/.config*/systemd/user/omarchy-desktop-icons.service; do
        if [ -e "$orphan" ] && [ "$orphan" != "$UNITS/omarchy-desktop-icons.service" ]; then
            STALE+=("$orphan is a unit systemd --user does not read")
        fi
    done

    if [ "$(readlink -f -- "$BIN/omarchy-desktop-icons" 2>/dev/null)" \
         != "$DEST/bin/omarchy-desktop-icons" ]; then
        STALE+=("the omarchy-desktop-icons command does not point at $DEST/bin")
    fi

    # --- the destination question --------------------------------------------
    # The app's own answer, not this script's guess about it.
    app_config="$(XDG_CONFIG_HOME="$XDGS_CONFIG_HOME" HOME="$XDGS_HOME" \
        bash -c 'printf %s "${XDG_CONFIG_HOME:-$HOME/.config}/omarchy-desktop-icons"')"
    if [ "$app_config" != "$CONFDIR" ]; then
        STALE+=("the app reads its icons from $app_config but this script installs them to $CONFDIR")
    fi
    if [ -L "$CONFDIR" ]; then
        STALE+=("$CONFDIR is a symlink to $(readlink -f -- "$CONFDIR") — a stopgap, not an install; re-run ./install.sh")
    fi
    for orphan in "$XDGS_HOME"/.config*/omarchy-desktop-icons; do
        if [ -e "$orphan" ] && [ ! -L "$orphan" ] && [ "$orphan" != "$CONFDIR" ]; then
            STALE+=("$orphan holds your icon layout in a root the app does not read (it reads $XDGS_CONFIG_HOME) — re-run ./install.sh to move it")
        fi
    done

    if [ "${#STALE[@]}" -eq 0 ]; then
        echo "omarchy-desktop-icons matches this source and reads the icons you have:"
        xdg_session_paths_report
        printf '  %-14s %s\n' 'icons' "$CONFDIR"
        exit 0
    fi

    echo "omarchy-desktop-icons is NOT correctly installed for your session:" >&2
    shown=0
    for problem in "${STALE[@]}"; do
        if [ "$shown" -ge 12 ]; then
            printf '  - ... and %s more\n' "$(( ${#STALE[@]} - shown ))" >&2
            break
        fi
        printf '  - %s\n' "$problem" >&2
        shown=$(( shown + 1 ))
    done
    echo >&2
    xdg_session_paths_report >&2
    echo >&2
    echo "Fix it with:  ./install.sh" >&2
    exit 1
fi

# --- install -----------------------------------------------------------------
if ! command -v qs >/dev/null 2>&1; then
    echo "quickshell is not installed. On Omarchy / Arch:"
    echo "    yay -S quickshell        # or: yay -S quickshell-git"
    exit 1
fi

if [ -z "$REFERENCE" ]; then
    echo "Installing for your session:"
    xdg_session_paths_report
fi

echo "Installing to $DEST"
mkdir -p "$DEST" "$BIN" "$UNITS"
cp -r "$SRC"/*.qml "$SRC"/bin "$SRC"/packaging "$SRC"/docs \
      "$SRC"/config.example.json "$SRC"/uninstall.sh "$SRC"/VERSION "$DEST"/
# The app's own manual ships in this profile as APP-README.md (README.md here is
# the Desktop Manager-facing one); install it under its upstream name, because
# the uninstall instructions tell you to cd into $DEST and read it.
cp "$SRC/APP-README.md" "$DEST/README.md"
chmod +x "$DEST"/bin/omarchy-desktop-icons "$DEST"/uninstall.sh
ln -sf "$DEST/bin/omarchy-desktop-icons" "$BIN/omarchy-desktop-icons"

# Your icon layout is real work — four icons and a custom grid position, in
# Jan's case. An earlier version of this script seeded and left it under a
# hardcoded ~/.config; where that is not the session's config root the app
# cannot see it, and would quietly start from defaults instead. Move it rather
# than orphan it.
if [ -z "$REFERENCE" ] && [ "$XDGS_HOME/.config" != "$XDGS_CONFIG_HOME" ]; then
    xdg_session_paths_migrate "$XDGS_HOME/.config/omarchy-desktop-icons" "$CONFDIR" \
        "icon layout"
fi

cp "$SRC/packaging/omarchy-desktop-icons.service" "$UNITS/"
[ -z "$REFERENCE" ] && { xdg_session_systemctl_user daemon-reload || true; }

if [ -z "$REFERENCE" ]; then
cat <<EOF

Installed.

Your icons:  $CONFDIR/config.json
Start it now:
    omarchy-desktop-icons

Start it every login — pick ONE:

  A) Hyprland autostart (recommended on Omarchy)
     Lua config  ($XDGS_CONFIG_HOME/hypr/autostart.lua):
         o.launch_on_start("omarchy-desktop-icons")
     Older .conf ($XDGS_CONFIG_HOME/hypr/hyprland.conf):
         exec-once = omarchy-desktop-icons

  B) systemd user unit (only if your session reaches graphical-session.target,
     e.g. you start Hyprland through uwsm)
         systemctl --user enable --now omarchy-desktop-icons

If $BIN is not on your PATH, add it to your shell rc:
    export PATH="$BIN:\$PATH"

Confirm it landed where your session looks:
    ./install.sh --check
EOF
fi
