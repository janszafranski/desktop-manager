#!/usr/bin/env bash
# install.sh — omarchy-launcher: an Omarchy-style categorised app launcher for
# Hyprland (Quickshell). Deploys the launcher QML + wrapper + categories config,
# starts the warm daemon, and wires up autostart and a toggle key.
#
#   ./install.sh            install or upgrade
#   ./install.sh --check    report whether the install matches this source AND
#                           whether your categories are where the launcher reads
#   ./install.sh --where    print the destinations and where each came from
#
# Vendored into desktop-manager as profiles/omarchy-launcher, so it is also what
# Desktop Manager → Apps → "App launcher → Install" runs.
#
# Destinations are resolved from the SESSION's environment, not this shell's —
# see ../../scripts/xdg-session-paths.sh for why that distinction is load-bearing.
set -euo pipefail
SELF="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }
[[ ${EUID:-$(id -u)} -eq 0 ]] && die "Run as your normal user, not root."

CHECK=0
WHERE=0
for arg in "$@"; do
  case "$arg" in
    --check) CHECK=1 ;;
    --where) WHERE=1 ;;
    -h|--help) sed -n '2,15p' "$(readlink -f "${BASH_SOURCE[0]}")"; exit 0 ;;
    *) die "unknown option: $arg" ;;
  esac
done

# A reference build (--check) runs this same script into a throwaway tree. It
# must not touch the real session: no hyprctl reload, no daemon restart, no
# migration of the user's real categories.
REFERENCE="${OMARCHY_LAUNCHER_REFERENCE_BUILD:-}"

# --- where everything goes ---------------------------------------------------
# The resolver lives at the top of desktop-manager when this runs from the
# repo, and next to the profile when the profile is shipped on its own.
for candidate in "$SELF/../../scripts/xdg-session-paths.sh" "$SELF/xdg-session-paths.sh"; do
  if [[ -r "$candidate" ]]; then
    # shellcheck source=../../scripts/xdg-session-paths.sh
    . "$candidate"
    break
  fi
done
command -v xdg_session_paths_resolve >/dev/null 2>&1 \
  || die "xdg-session-paths.sh not found next to this script"
xdg_session_paths_resolve

BIN_DIR="$XDGS_BIN_DIR"
# Quickshell resolves `qs -c omarchy-launcher` under the session's
# $XDG_CONFIG_HOME. Jan's session sets that to ~/.config-ii, so a panel
# installed into a hardcoded ~/.config is one `qs` never finds (JAN-78).
QS_DIR="$XDGS_CONFIG_HOME/quickshell/omarchy-launcher"
# categories.json and appearance.json are the user's own data, and the one
# place the wrapper (`omarchy-launcher edit`) and shell.qml MUST agree on. They
# did not: the wrapper read ${XDG_CONFIG_HOME:-$HOME/.config} while shell.qml
# hardcoded $HOME/.config, so in this session `edit` opened a different file
# from the one the panel displayed, and App List Config saved into the file the
# panel ignored (JAN-82).
CFG_DIR="$XDGS_CONFIG_HOME/omarchy-launcher"
HYPR_DIR="$XDGS_CONFIG_HOME/hypr"

if [[ "$WHERE" == 1 ]]; then
  echo "omarchy-launcher destinations:"
  xdg_session_paths_report
  echo
  printf '  %-14s %s\n' 'panel'      "$QS_DIR/shell.qml"
  printf '  %-14s %s\n' 'command'    "$BIN_DIR/omarchy-launcher"
  printf '  %-14s %s\n' 'categories' "$CFG_DIR/categories.json"
  printf '  %-14s %s\n' 'appearance' "$CFG_DIR/appearance.json"
  printf '  %-14s %s\n' 'hypr'       "$HYPR_DIR"
  exit 0
fi

detect_de() {
  local d="${XDG_CURRENT_DESKTOP:-}:${DESKTOP_SESSION:-}"
  if [[ "$d" == *[Hh]yprland* ]] || pgrep -x Hyprland >/dev/null 2>&1; then echo hyprland
  elif [[ "$d" == *KDE* || "$d" == *plasma* ]] || [[ -n "${KDE_FULL_SESSION:-}" ]] \
       || pgrep -x plasmashell >/dev/null 2>&1; then echo kde
  else echo other; fi
}

# The key the launcher wants, written literally and never as
# `mod .. " + Space"`: `mod` is a Caelestia-ism, and in the end-4 / ii Lua
# layout it is undefined, so that line raises at config load.
TOGGLE_KEY="SUPER + Space"
# ...and the pattern that finds it in someone else's config. It is NOT
# "$TOGGLE_KEY" passed to grep -E: `+` is a quantifier there, so that pattern
# matches `"SUPER  Space"` and never the literal key — which silently turns
# the conflict check below into a no-op and adds the second bind anyway. The
# spacing around the plus varies between configs, so it stays flexible.
TOGGLE_KEY_RE='"SUPER *\+ *Space"'

# --- --check -----------------------------------------------------------------
# Three questions, because answering only the first is how this shipped
# "installed" over a session that could not see any of it:
#
#   1. Does every payload match this source? Built as a pristine reference
#      install into a throwaway tree and compared payload by payload, so a file
#      added to this script tomorrow is covered the day it is added.
#   2. Is each payload where the SESSION resolves it? On 4 Nov 2026 the panel
#      and 10 KB of Jan's own categories sat under ~/.config while his session
#      read ~/.config-ii, so `qs -c omarchy-launcher` found nothing at all.
#   3. Do the wrapper and the panel agree on ONE config root? They did not —
#      and that split brain is invisible to both questions above, because every
#      file can be present and current while `omarchy-launcher edit` edits a
#      file the panel never reads.
if [[ "$CHECK" == 1 ]]; then
  STALE=()   # things that mean the launcher does not work in this session
  NOTES=()   # true, worth saying, but not this session's problem

  WORK="$(mktemp -d "${TMPDIR:-/tmp}/omarchy-launcher-check.XXXXXX")"
  trap 'rm -rf "$WORK"' EXIT

  if ! OMARCHY_LAUNCHER_REFERENCE_BUILD=1 \
       XDG_SESSION_PATHS_HOME="$WORK" \
       XDG_SESSION_PATHS_XDG_CONFIG_HOME="$WORK/config" \
       XDG_SESSION_PATHS_XDG_DATA_HOME="$WORK/share" \
       XDG_SESSION_PATHS_SYSTEMD_USER_DIR="$WORK/units" \
       XDG_SESSION_PATHS_BIN_DIR="$WORK/bin" \
       bash "$SELF/install.sh" >"$WORK/log" 2>&1; then
    echo "could not build a reference install from $SELF:" >&2
    cat "$WORK/log" >&2
    exit 1
  fi

  # Every file the reference install wrote must be present and identical at the
  # live destination the session resolves to. Asking it in that direction covers
  # new payloads automatically, and stays quiet about files the app writes for
  # itself (appearance.json, from App List Config) which are not ours to compare.
  compare_tree() { # compare_tree <reference root> <live root>
    local reference="$1" live="$2" file relative
    [[ -d "$reference" ]] || return 0
    while IFS= read -r -d '' file; do
      relative="${file#"$reference/"}"
      # Seeded-only-if-absent user data: presence is checked, content is not.
      case "$relative" in categories.json)
        [[ -e "$live/$relative" ]] || STALE+=("$live/$relative is missing")
        continue ;;
      esac
      if [[ ! -e "$live/$relative" ]]; then
        STALE+=("$live/$relative is missing")
      elif ! cmp -s "$file" "$live/$relative"; then
        STALE+=("$live/$relative is not the version in this source")
      fi
    done < <(find "$reference" -type f -print0)
  }

  compare_tree "$WORK/config/quickshell/omarchy-launcher" "$QS_DIR"
  compare_tree "$WORK/config/omarchy-launcher"            "$CFG_DIR"
  compare_tree "$WORK/bin"                                "$BIN_DIR"

  # --- the destination question ----------------------------------------------
  if [[ ! -d "$QS_DIR" ]]; then
    STALE+=("the panel is not in $QS_DIR, so \`qs -c omarchy-launcher\` cannot find it")
  elif [[ -L "$QS_DIR" ]]; then
    STALE+=("$QS_DIR is a symlink to $(readlink -f -- "$QS_DIR") — a stopgap, not an install; re-run ./install.sh")
  fi
  if [[ -L "$CFG_DIR" ]]; then
    STALE+=("$CFG_DIR is a symlink to $(readlink -f -- "$CFG_DIR") — a stopgap, not an install; re-run ./install.sh")
  fi

  # Config left behind in a root the session does not read is orphaned, and the
  # user's own categories may be sitting in it.
  for orphan in "$XDGS_HOME"/.config*/quickshell/omarchy-launcher \
                "$XDGS_HOME"/.config*/omarchy-launcher; do
    [[ "$orphan" == "$QS_DIR" || "$orphan" == "$CFG_DIR" ]] && continue
    if [[ -e "$orphan" && ! -L "$orphan" ]]; then
      STALE+=("$orphan is in a root your session does not read (it reads $XDGS_CONFIG_HOME) — re-run ./install.sh to move it")
    fi
  done

  # --- the split-brain question ----------------------------------------------
  # The wrapper's own answer, not this script's guess about it.
  wrapper_config="$(XDG_CONFIG_HOME="$XDGS_CONFIG_HOME" HOME="$XDGS_HOME" \
    bash -c 'printf %s "${XDG_CONFIG_HOME:-$HOME/.config}/omarchy-launcher"')"
  if [[ "$wrapper_config" != "$CFG_DIR" ]]; then
    STALE+=("\`omarchy-launcher edit\` opens $wrapper_config/categories.json but this script installs to $CFG_DIR")
  fi
  # And the panel's. A hardcoded root here is JAN-82 coming back, and comparing
  # files cannot catch it, because the file compares fine.
  if [[ -f "$QS_DIR/shell.qml" ]]; then
    if grep -qF '/.config/omarchy-launcher' "$QS_DIR/shell.qml"; then
      STALE+=("$QS_DIR/shell.qml hardcodes a ~/.config config root, so the panel reads a different file from \`omarchy-launcher edit\`")
    elif ! grep -qF 'Quickshell.env("XDG_CONFIG_HOME")' "$QS_DIR/shell.qml"; then
      STALE+=("$QS_DIR/shell.qml does not resolve its config from \$XDG_CONFIG_HOME")
    fi
  fi
  # The categories are the point of the app; an empty rail is a broken install.
  if [[ ! -s "$CFG_DIR/categories.json" ]]; then
    STALE+=("$CFG_DIR/categories.json is missing or empty — the launcher would open on an empty rail")
  fi

  # --- autostart -------------------------------------------------------------
  if [[ "$(detect_de)" == hyprland ]]; then
    if [[ ! -f "$HYPR_DIR/hyprland.lua" ]]; then
      STALE+=("no Hyprland Lua config in $HYPR_DIR — the daemon will not start at login")
    elif ! grep -rqF "omarchy-launcher daemon" "$HYPR_DIR" 2>/dev/null; then
      STALE+=("nothing in $HYPR_DIR starts the launcher daemon at login")
    fi
    # No toggle bind is installed when the key is already taken, so its absence
    # is not a fault. Say which state we are in, so "no bind" is never a silent
    # surprise.
    if ! grep -rqE "$TOGGLE_KEY_RE" "$HYPR_DIR" --include='*.lua' 2>/dev/null; then
      NOTES+=("Nothing in $HYPR_DIR binds $TOGGLE_KEY. Either your config already uses it (the installer reports the conflict rather than doubling up) or you unbound it. Open the launcher from anywhere with: omarchy-launcher")
    fi
    # Another config root wiring up the launcher is a second session profile,
    # not a fault in this one — but its categories have moved into this
    # session's root, so say so rather than leave it a mystery.
    for other in "$XDGS_HOME"/.config*/hypr; do
      [[ -d "$other" && "$other" != "$HYPR_DIR" ]] || continue
      if grep -rqF "omarchy-launcher" "$other" 2>/dev/null; then
        NOTES+=("$other also wires up the launcher, for a different session. The config now lives in $CFG_DIR; log into that session and re-run ./install.sh to have it there too.")
      fi
    done
  fi

  if [[ "${#STALE[@]}" -eq 0 ]]; then
    echo "omarchy-launcher matches this source and reads the categories you have:"
    xdg_session_paths_report
    printf '  %-14s %s\n' 'panel'      "$QS_DIR"
    printf '  %-14s %s\n' 'categories' "$CFG_DIR/categories.json"
    for note in "${NOTES[@]+"${NOTES[@]}"}"; do printf '\nnote: %s\n' "$note"; done
    exit 0
  fi

  echo "omarchy-launcher is NOT correctly installed for your session:" >&2
  shown=0
  for problem in "${STALE[@]}"; do
    if [[ "$shown" -ge 12 ]]; then
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
if [[ -z "$REFERENCE" ]]; then
  command -v qs >/dev/null 2>&1 || warn "Quickshell (qs) not found — install 'quickshell'."
  log "Installing for your session:"
  xdg_session_paths_report
fi

# --- rescue config from a root the session does not read ---------------------
# Earlier versions of this script wrote to a hardcoded ~/.config. Where that is
# not the session's config root, the panel went somewhere Quickshell never
# looks — and 10 KB of hand-written categories went with it. Move them rather
# than orphan them, and replace the symlink stopgap carrying this meanwhile.
if [[ -z "$REFERENCE" && "$XDGS_HOME/.config" != "$XDGS_CONFIG_HOME" ]]; then
  xdg_session_paths_migrate "$XDGS_HOME/.config/quickshell/omarchy-launcher" "$QS_DIR"  "launcher panel"
  xdg_session_paths_migrate "$XDGS_HOME/.config/omarchy-launcher"            "$CFG_DIR" "categories and appearance"

  # Autostart wiring left in another config root would start a daemon for a
  # config directory that is no longer there. Only the block THIS script wrote
  # (between its own markers) is removed — never a line the user wrote by hand.
  for stale_hypr in "$XDGS_HOME"/.config*/hypr; do
    [[ -d "$stale_hypr" && "$stale_hypr" != "$HYPR_DIR" ]] || continue
    while IFS= read -r stale_lua; do
      sed -i '/-- >>> omarchy-launcher (desktop-manager) >>>/,/-- <<< omarchy-launcher (desktop-manager) <<</d' "$stale_lua"
      printf '  retracted the autostart wiring in %s (your session reads %s)\n' \
        "$stale_lua" "$HYPR_DIR"
    done < <(grep -rlF -e "-- >>> omarchy-launcher (desktop-manager) >>>" "$stale_hypr" --include='*.lua' 2>/dev/null)
  done
fi

# --- deploy ------------------------------------------------------------------
log "Deploying the omarchy-launcher"
install -Dm755 "$SELF/omarchy-launcher" "$BIN_DIR/omarchy-launcher"
install -Dm644 "$SELF/shell.qml"        "$QS_DIR/shell.qml"
# Never clobber an existing (user-edited) categories file; only seed it if absent.
if [[ ! -f "$CFG_DIR/categories.json" ]]; then
  install -Dm644 "$SELF/categories.json" "$CFG_DIR/categories.json"
  [[ -z "$REFERENCE" ]] && log "Seeded categories.json"
else
  [[ -z "$REFERENCE" ]] && warn "Kept your existing $CFG_DIR/categories.json"
fi

# --- desktop integration -----------------------------------------------------
DE="$(detect_de)"
[[ -z "$REFERENCE" ]] && log "Desktop environment: $DE"

MARK_A="-- >>> omarchy-launcher (desktop-manager) >>>"
MARK_B="-- <<< omarchy-launcher (desktop-manager) <<<"

# Append a marked block to a Lua config file, replacing any block we wrote
# before. Idempotent, and it never touches a line the user wrote.
lua_block() { # lua_block <file> <body...>
  local file="$1"; shift
  mkdir -p "$(dirname -- "$file")"
  [[ -f "$file" ]] || : > "$file"
  if grep -qF -e "$MARK_A" "$file"; then
    sed -i '/-- >>> omarchy-launcher (desktop-manager) >>>/,/-- <<< omarchy-launcher (desktop-manager) <<</d' "$file"
  fi
  # Removing the old block leaves the blank line that separated it. Strip
  # trailing blank lines before re-appending, or every re-install grows the
  # file by one.
  printf '%s' "$(< "$file")" > "$file.xdgs-tmp" && mv "$file.xdgs-tmp" "$file"
  { printf '\n%s\n' "$MARK_A"; printf '%s\n' "$@"; printf '%s\n' "$MARK_B"; } >> "$file"
}

# A bind on a key the session already uses gives two actions on one keypress,
# so the conflict is reported instead of created. Jan's ii session binds
# SUPER + Space to fuzzel; which of the two belongs there is his call, not this
# script's.
report_toggle_conflict() { # report_toggle_conflict <keybinds file>
  warn "$TOGGLE_KEY is already bound by your Hyprland config, so no toggle was added."
  warn "To give it to the launcher, replace that bind yourself; or bind a free key in $1:"
  warn "  hl.bind(\"SUPER + ALT + Space\", hl.dsp.exec_cmd(\"$BIN_DIR/omarchy-launcher\"), { description = \"App launcher (categories)\" })"
}

if [[ "$DE" == hyprland ]]; then
  LUA="$HYPR_DIR/hyprland.lua"
  if [[ ! -f "$LUA" ]]; then
    warn "No Hyprland Lua config at $LUA. If you use a plain hyprland.conf, wire it manually:"
    warn "  exec-once = $BIN_DIR/omarchy-launcher daemon"
    warn "  bind = SUPER, Space, exec, $BIN_DIR/omarchy-launcher"
  elif grep -q 'require("custom\.execs")' "$LUA"; then
    # end-4 / ii layout: hyprland.lua is a list of require()s and `custom/` is
    # the documented place for your own additions. Appending to hyprland.lua
    # here would be wrong twice over — a dots update overwrites it, and the
    # block would run before hyprland.lib defines `hl`.
    log "Wiring into the end-4 custom config in $HYPR_DIR/custom"
    lua_block "$HYPR_DIR/custom/execs.lua" \
      '-- Keep the desktop-entry index warm so the first open is instant. The' \
      '-- wrapper no-ops if a daemon is already up, so a repeated fire is safe.' \
      "hl.exec_cmd(\"$BIN_DIR/omarchy-launcher daemon\")"
    # --exclude-dir=custom so our own previous block is not a conflict with
    # itself, which would make the bind disappear on the second install.
    if grep -rqE "$TOGGLE_KEY_RE" "$HYPR_DIR" --include='*.lua' --exclude-dir=custom 2>/dev/null; then
      report_toggle_conflict "$HYPR_DIR/custom/keybinds.lua"
      lua_block "$HYPR_DIR/custom/keybinds.lua" \
        "-- $TOGGLE_KEY is taken by this config, so the launcher has no toggle bind." \
        '-- Add one on a free key here; the daemon itself is started in execs.lua.'
    else
      lua_block "$HYPR_DIR/custom/keybinds.lua" \
        "hl.bind(\"$TOGGLE_KEY\", hl.dsp.exec_cmd(\"$BIN_DIR/omarchy-launcher\"), { description = \"App launcher (categories)\" })"
    fi
    [[ -z "$REFERENCE" ]] && command -v hyprctl >/dev/null && hyprctl reload >/dev/null 2>&1 || true
  elif grep -q "hl\." "$LUA"; then
    # Flat layout: the user's binds live in hyprland.lua itself.
    #
    # "Already wired" is NOT just "our marker is there". A hand-wired config
    # counts too: if the Lua already mentions omarchy-launcher, the user set
    # this up themselves, very likely on keys they chose. Appending our block
    # over that adds a second, conflicting bind.
    if grep -q "omarchy-launcher" "$LUA" && ! grep -qF -e "$MARK_A" "$LUA"; then
      log "hyprland.lua already wires up omarchy-launcher by hand — leaving it alone"
      warn "Your own binds are kept as they are. For this install's defaults"
      warn "($TOGGLE_KEY toggle + autostart), remove your lines and re-run."
    elif grep -rqE "$TOGGLE_KEY_RE" "$HYPR_DIR" --include='*.lua' 2>/dev/null \
         && ! grep -qF -e "$MARK_A" "$LUA"; then
      report_toggle_conflict "$LUA"
      lua_block "$LUA" \
        "-- $TOGGLE_KEY is taken by this config, so the launcher has no toggle bind." \
        '-- Add one on a free key; the daemon is started by the line below.' \
        "hl.exec_cmd(\"$BIN_DIR/omarchy-launcher daemon\")"
      [[ -z "$REFERENCE" ]] && command -v hyprctl >/dev/null && hyprctl reload >/dev/null 2>&1 || true
    else
      log "Adding the $TOGGLE_KEY toggle and autostart to $LUA"
      lua_block "$LUA" \
        "hl.exec_cmd(\"$BIN_DIR/omarchy-launcher daemon\")" \
        "hl.bind(\"$TOGGLE_KEY\", hl.dsp.exec_cmd(\"$BIN_DIR/omarchy-launcher\"), { description = \"App launcher (categories)\" })"
      [[ -z "$REFERENCE" ]] && command -v hyprctl >/dev/null && hyprctl reload >/dev/null 2>&1 || true
    fi
  else
    warn "$LUA does not look like a Lua config this script can extend."
    warn "Bind manually:  exec-once = $BIN_DIR/omarchy-launcher daemon"
  fi
else
  warn "Not a Hyprland session — no autostart or keybind was written."
  warn "Open the launcher with:  $BIN_DIR/omarchy-launcher"
fi

# --- (re)start the daemon ----------------------------------------------------
# A running daemon still holds the shell.qml it was launched with, from
# wherever it was launched — which, until this version, could be a config root
# the session does not read. Leaving it up would mean the install succeeded and
# the thing on screen was still the old one.
if [[ -z "$REFERENCE" ]] && command -v qs >/dev/null 2>&1; then
  if ! xdg_session_display_env >/dev/null; then
    # No session to launch into: an agent shell, an ssh login, a cron job. Do
    # NOT kill a daemon running for the logged-in user and then fail to bring
    # it back.
    warn "No graphical session found, so the daemon was not (re)started."
    warn "It will come up at next login. To start it now, from your own session:"
    warn "  omarchy-launcher restart"
  else
    pkill -f '(^|/)qs -c omarchy-launcher( |$)' >/dev/null 2>&1 && sleep 0.3 || true
    if xdg_session_spawn "$BIN_DIR/omarchy-launcher" daemon; then
      log "Launcher daemon started"
    else
      warn "Could not start the daemon. From your own session:  omarchy-launcher restart"
    fi
  fi
fi

if [[ -z "$REFERENCE" ]]; then
  cat <<DONE

omarchy-launcher installed into $XDGS_CONFIG_HOME.
  • Categories:  $CFG_DIR/categories.json   (or: omarchy-launcher edit)
  • Open it:     omarchy-launcher
  • Confirm it landed where your session looks:  ./install.sh --check
DONE
fi
