#!/usr/bin/env bash
# install.sh — on-screen "Keyboard shortcuts" cheat-sheet: a Quickshell widget
# listing every keybinding, in two variants — the Hyprland one (reads
# `hyprctl binds`) and the KDE one (reads kglobalshortcutsrc, with a yad
# fallback). Both payloads are deployed; only the detected desktop is wired up.
#
#   ./install.sh            install or upgrade
#   ./install.sh --check    report whether the install matches this source AND
#                           whether it is where your session will find it
#   ./install.sh --where    print the destinations and where each came from
#
# Vendored into desktop-manager as profiles/keybinds, so it is also what
# Desktop Manager → Apps → Utilities → "Keyboard shortcuts → Install" runs.
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
    -h|--help) sed -n '2,16p' "$(readlink -f "${BASH_SOURCE[0]}")"; exit 0 ;;
    *) die "unknown option: $arg" ;;
  esac
done

# A reference build (--check) runs this same script into a throwaway tree. It
# must not touch the real session: no hyprctl reload, no widget launch, no
# migration out of the user's real config root.
REFERENCE="${KEYBINDS_REFERENCE_BUILD:-}"

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

# Quickshell resolves `qs -c keybinds` under the session's $XDG_CONFIG_HOME.
# Jan's session sets that to ~/.config-ii, so a widget installed into a
# hardcoded ~/.config is one `qs` never finds (JAN-78).
QS_DIR="$XDGS_CONFIG_HOME/quickshell/keybinds"
KDE_QS_DIR="$XDGS_CONFIG_HOME/quickshell/kde-keybinds"
# The toggle scripts are commands bound to keys, so they go on $PATH rather
# than into hypr/scripts: a keybind then names one absolute path that does not
# move when the session's config root does.
BIN_DIR="$XDGS_BIN_DIR"
APPS="$XDGS_DATA_HOME/applications"
HYPR_DIR="$XDGS_CONFIG_HOME/hypr"

if [[ "$WHERE" == 1 ]]; then
  echo "Keyboard shortcuts destinations:"
  xdg_session_paths_report
  echo
  printf '  %-14s %s\n' 'widget'   "$QS_DIR"
  printf '  %-14s %s\n' 'kde widget' "$KDE_QS_DIR"
  printf '  %-14s %s\n' 'commands' "$BIN_DIR/keybinds-toggle.sh"
  printf '  %-14s %s\n' 'menu'     "$APPS"
  printf '  %-14s %s\n' 'hypr'     "$HYPR_DIR"
  exit 0
fi

detect_de() {
  local d="${XDG_CURRENT_DESKTOP:-}:${DESKTOP_SESSION:-}"
  if [[ "$d" == *[Hh]yprland* ]] || pgrep -x Hyprland >/dev/null 2>&1; then echo hyprland
  elif [[ "$d" == *KDE* || "$d" == *plasma* ]] || [[ -n "${KDE_FULL_SESSION:-}" ]] \
       || pgrep -x plasmashell >/dev/null 2>&1; then echo kde
  else echo other; fi
}

# The keys the widget wants, written literally and never as `mod .. " + slash"`:
# `mod` is a Caelestia-ism, and in the end-4 / ii Lua layout it is undefined, so
# that line raises at config load.
TOGGLE_KEY="SUPER + Slash"
LIST_KEY="SUPER + SHIFT + Slash"
# ...and the pattern that finds the toggle key in someone else's config. It is
# NOT "$TOGGLE_KEY" passed to grep -E: `+` is a quantifier there, so that
# pattern matches `"SUPER  Slash"` and never the literal key — which silently
# turns the conflict check below into a no-op and adds the second bind anyway.
# The spacing around the plus varies between configs, so it stays flexible.
TOGGLE_KEY_RE='"SUPER *\+ *Slash"'

# The yad fallback's Exec is an absolute path into the KDE widget directory,
# which moves with the session's config root — so it is written at install time
# rather than shipped frozen to one home.
fix_desktop_exec() { # fix_desktop_exec <installed .desktop>
  sed -i "s|^Exec=.*/kde-keybinds/keybinds-yad.sh|Exec=$KDE_QS_DIR/keybinds-yad.sh|" "$1"
}

# --- --check -----------------------------------------------------------------
# Two questions. The second one is the one that was never asked: every payload
# can match this source exactly and `qs -c keybinds` still find nothing,
# because the session's $XDG_CONFIG_HOME and a hardcoded ~/.config are
# different directories here.
if [[ "$CHECK" == 1 ]]; then
  STALE=()   # things that mean the cheat-sheet does not work in this session
  NOTES=()   # true, worth saying, but not this session's problem

  WORK="$(mktemp -d "${TMPDIR:-/tmp}/keybinds-check.XXXXXX")"
  trap 'rm -rf "$WORK"' EXIT

  if ! KEYBINDS_REFERENCE_BUILD=1 \
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
  # new payloads automatically.
  compare_tree() { # compare_tree <reference root> <live root>
    local reference="$1" live="$2" file relative
    [[ -d "$reference" ]] || return 0
    while IFS= read -r -d '' file; do
      relative="${file#"$reference/"}"
      if [[ ! -e "$live/$relative" ]]; then
        STALE+=("$live/$relative is missing")
      elif ! cmp -s "$file" "$live/$relative"; then
        STALE+=("$live/$relative is not the version in this source")
      fi
    done < <(find "$reference" -type f -print0)
  }

  # The desktop entries embed the widget path, so compare them after rewriting
  # the reference's throwaway paths to the real ones.
  if [[ -d "$WORK/share/applications" ]]; then
    find "$WORK/share/applications" -type f -exec \
      sed -i "s|$WORK/config|$XDGS_CONFIG_HOME|g; s|$WORK|$XDGS_HOME|g" {} +
  fi

  compare_tree "$WORK/config/quickshell/keybinds"     "$QS_DIR"
  compare_tree "$WORK/config/quickshell/kde-keybinds" "$KDE_QS_DIR"
  compare_tree "$WORK/bin"                            "$BIN_DIR"
  compare_tree "$WORK/share/applications"             "$APPS"

  # --- the destination question ----------------------------------------------
  for dir in "$QS_DIR" "$KDE_QS_DIR"; do
    if [[ ! -d "$dir" ]]; then
      STALE+=("$dir is missing, so \`qs -c $(basename -- "$dir")\` cannot find it")
    elif [[ -L "$dir" ]]; then
      STALE+=("$dir is a symlink to $(readlink -f -- "$dir") — a stopgap, not an install; re-run ./install.sh")
    fi
  done

  # Payload left behind in a root the session does not read is dead weight that
  # looks installed — including the toggle scripts the old keybind named.
  for orphan in "$XDGS_HOME"/.config*/quickshell/keybinds \
                "$XDGS_HOME"/.config*/quickshell/kde-keybinds \
                "$XDGS_HOME"/.config*/hypr/scripts/keybinds.sh \
                "$XDGS_HOME"/.config*/hypr/scripts/keybinds-toggle.sh; do
    [[ "$orphan" == "$QS_DIR" || "$orphan" == "$KDE_QS_DIR" ]] && continue
    if [[ -e "$orphan" && ! -L "$orphan" ]]; then
      STALE+=("$orphan is in a root your session does not read (it reads $XDGS_CONFIG_HOME) — re-run ./install.sh to clear it")
    fi
  done

  # The KDE widget shells out to its own helper; if it resolves a different
  # root from the one it was installed into, the list comes back empty.
  if [[ -f "$KDE_QS_DIR/shell.qml" ]] \
     && grep -qF '/.config/quickshell/kde-keybinds' "$KDE_QS_DIR/shell.qml"; then
    STALE+=("$KDE_QS_DIR/shell.qml hardcodes a ~/.config root for list-shortcuts.sh")
  fi

  # --- autostart -------------------------------------------------------------
  if [[ "$(detect_de)" == hyprland ]]; then
    if [[ ! -f "$HYPR_DIR/hyprland.lua" ]]; then
      STALE+=("no Hyprland Lua config in $HYPR_DIR — the widget will not start at login")
    elif ! grep -rqF "qs -c keybinds" "$HYPR_DIR" 2>/dev/null; then
      STALE+=("nothing in $HYPR_DIR starts the keybinds widget at login")
    fi
    # No toggle bind is installed when the key is already taken, so its absence
    # is not a fault. Say which state we are in, so "no bind" is never a silent
    # surprise.
    if ! grep -rqE "$TOGGLE_KEY_RE" "$HYPR_DIR" --include='*.lua' 2>/dev/null; then
      NOTES+=("Nothing in $HYPR_DIR binds $TOGGLE_KEY. Either your config already uses it (the installer reports the conflict rather than doubling up) or you unbound it. Toggle the cheat-sheet with: $BIN_DIR/keybinds-toggle.sh")
    fi
    for other in "$XDGS_HOME"/.config*/hypr; do
      [[ -d "$other" && "$other" != "$HYPR_DIR" ]] || continue
      if grep -rqF "qs -c keybinds" "$other" --include='*.lua' 2>/dev/null; then
        NOTES+=("$other also wires up the cheat-sheet, for a different session. The widget is installed in $XDGS_CONFIG_HOME; log into that session and re-run ./install.sh to have it there too.")
      fi
    done
  fi

  if [[ "${#STALE[@]}" -eq 0 ]]; then
    echo "The keybinds cheat-sheet matches this source and is where your session looks:"
    xdg_session_paths_report
    printf '  %-14s %s\n' 'widget'   "$QS_DIR"
    printf '  %-14s %s\n' 'commands' "$BIN_DIR/keybinds-toggle.sh"
    for note in "${NOTES[@]+"${NOTES[@]}"}"; do printf '\nnote: %s\n' "$note"; done
    exit 0
  fi

  echo "The keybinds cheat-sheet is NOT correctly installed for your session:" >&2
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
DE="$(detect_de)"
if [[ -z "$REFERENCE" ]]; then
  command -v qs >/dev/null 2>&1 || warn "Quickshell (qs) not found — install 'quickshell'."
  log "Desktop environment: $DE"
  log "Installing for your session:"
  xdg_session_paths_report
fi

# --- clear payload from a root the session does not read ---------------------
# Earlier versions of this script wrote to a hardcoded ~/.config. Where that is
# not the session's config root the widget was installed where Quickshell never
# looks, and the Super+/ keybind pointed at a script under that same dead root.
# None of it is user data — it is all redeployed below — but it is moved rather
# than deleted, because deciding someone's config directory is disposable is
# not this script's call.
if [[ -z "$REFERENCE" && "$XDGS_HOME/.config" != "$XDGS_CONFIG_HOME" ]]; then
  xdg_session_paths_migrate "$XDGS_HOME/.config/quickshell/keybinds"     "$QS_DIR"     "keybinds widget"
  xdg_session_paths_migrate "$XDGS_HOME/.config/quickshell/kde-keybinds" "$KDE_QS_DIR" "KDE keybinds widget"
  for old in keybinds.sh keybinds-toggle.sh; do
    xdg_session_paths_migrate "$XDGS_HOME/.config/hypr/scripts/$old" "$BIN_DIR/$old" "$old"
  done

  # Keybinds left in another config root name a script that has moved. Only the
  # block THIS script wrote (between its own markers) is removed — never a line
  # the user wrote by hand.
  for stale_hypr in "$XDGS_HOME"/.config*/hypr; do
    [[ -d "$stale_hypr" && "$stale_hypr" != "$HYPR_DIR" ]] || continue
    while IFS= read -r stale_lua; do
      sed -i '/-- >>> keybinds-widget (desktop-manager) >>>/,/-- <<< keybinds-widget (desktop-manager) <<</d' "$stale_lua"
      printf '  retracted the keybind wiring in %s (your session reads %s)\n' \
        "$stale_lua" "$HYPR_DIR"
    done < <(grep -rlF -e "-- >>> keybinds-widget (desktop-manager) >>>" "$stale_hypr" --include='*.lua' 2>/dev/null)
  done
fi

# --- deploy ------------------------------------------------------------------
# Both variants' payload, on every desktop. Deployment is DE-independent and
# cheap (one QML file and two helpers each); only the wiring below is not. An
# installer that deploys a different set of files depending on which shell ran
# it is also an installer whose --check cannot be deterministic.
log "Deploying the keybinds widgets"
install -Dm644 "$SELF/shell.qml"          "$QS_DIR/shell.qml"
install -Dm755 "$SELF/keybinds.sh"        "$BIN_DIR/keybinds.sh"
install -Dm755 "$SELF/keybinds-toggle.sh" "$BIN_DIR/keybinds-toggle.sh"

install -Dm644 "$SELF/kde/shell.qml" "$KDE_QS_DIR/shell.qml"
for s in list-shortcuts.sh keybinds-yad.sh; do
  [[ -f "$SELF/kde/$s" ]] && install -Dm755 "$SELF/kde/$s" "$KDE_QS_DIR/$s"
done
for d in kde-keybinds-toggle.desktop kde-keybinds-yad.desktop; do
  [[ -f "$SELF/kde/$d" ]] || continue
  install -Dm644 "$SELF/kde/$d" "$APPS/$d"
  fix_desktop_exec "$APPS/$d"
done
[[ -z "$REFERENCE" ]] && command -v update-desktop-database >/dev/null \
  && update-desktop-database "$APPS" 2>/dev/null || true

# --- desktop integration -----------------------------------------------------
MARK_A="-- >>> keybinds-widget (desktop-manager) >>>"
MARK_B="-- <<< keybinds-widget (desktop-manager) <<<"

# Append a marked block to a Lua config file, replacing any block we wrote
# before. Idempotent, and it never touches a line the user wrote.
lua_block() { # lua_block <file> <body...>
  local file="$1"; shift
  mkdir -p "$(dirname -- "$file")"
  [[ -f "$file" ]] || : > "$file"
  if grep -qF -e "$MARK_A" "$file"; then
    sed -i '/-- >>> keybinds-widget (desktop-manager) >>>/,/-- <<< keybinds-widget (desktop-manager) <<</d' "$file"
  fi
  # Removing the old block leaves the blank line that separated it. Strip
  # trailing blank lines before re-appending, or every re-install grows the
  # file by one.
  printf '%s' "$(< "$file")" > "$file.xdgs-tmp" && mv "$file.xdgs-tmp" "$file"
  { printf '\n%s\n' "$MARK_A"; printf '%s\n' "$@"; printf '%s\n' "$MARK_B"; } >> "$file"
}

# A bind on a key the session already uses gives two cheat-sheets on one
# keypress, so the conflict is reported instead of created. The end-4 / ii
# shell ships its own cheat-sheet on SUPER + Slash, which is exactly that case.
report_toggle_conflict() { # report_toggle_conflict <keybinds file>
  warn "$TOGGLE_KEY is already bound by your Hyprland config, so no toggle was added."
  warn "Your desktop may already have a cheat-sheet on that key. If you want this"
  warn "one instead, replace that bind yourself; or bind a free key in $1:"
  warn "  hl.bind(\"SUPER + ALT + Slash\", hl.dsp.exec_cmd(\"$BIN_DIR/keybinds-toggle.sh\"), { description = \"Keybindings (widget)\" })"
}

if [[ "$DE" == hyprland ]]; then
  LUA="$HYPR_DIR/hyprland.lua"
  if [[ ! -f "$LUA" ]]; then
    warn "No Hyprland Lua config at $LUA. If you use a plain hyprland.conf, wire it manually:"
    warn "  exec-once = qs -c keybinds"
    warn "  bind = SUPER, slash, exec, $BIN_DIR/keybinds-toggle.sh"
  elif grep -q 'require("custom\.execs")' "$LUA"; then
    # end-4 / ii layout: hyprland.lua is a list of require()s and `custom/` is
    # the documented place for your own additions. Appending to hyprland.lua
    # here would be wrong twice over — a dots update overwrites it, and the
    # block would run before hyprland.lib defines `hl`.
    log "Wiring into the end-4 custom config in $HYPR_DIR/custom"
    lua_block "$HYPR_DIR/custom/execs.lua" \
      '-- The widget runs persistently (it also serves the hot corner), so the' \
      '-- toggle below only flips its pinned state.' \
      'hl.exec_cmd("qs -c keybinds")'
    # --exclude-dir=custom so our own previous block is not a conflict with
    # itself, which would make the bind disappear on the second install.
    if grep -rqE "$TOGGLE_KEY_RE" "$HYPR_DIR" --include='*.lua' --exclude-dir=custom 2>/dev/null; then
      report_toggle_conflict "$HYPR_DIR/custom/keybinds.lua"
      lua_block "$HYPR_DIR/custom/keybinds.lua" \
        "-- $TOGGLE_KEY is taken by this config, so the cheat-sheet has no toggle" \
        '-- bind. Add one on a free key here; the widget is started in execs.lua.'
    else
      lua_block "$HYPR_DIR/custom/keybinds.lua" \
        "hl.bind(\"$TOGGLE_KEY\", hl.dsp.exec_cmd(\"$BIN_DIR/keybinds-toggle.sh\"), { description = \"Keybindings (widget)\" })" \
        "hl.bind(\"$LIST_KEY\", hl.dsp.exec_cmd(\"$BIN_DIR/keybinds.sh\"), { description = \"Keybindings (fallback list)\" })"
    fi
    [[ -z "$REFERENCE" ]] && command -v hyprctl >/dev/null && hyprctl reload >/dev/null 2>&1 || true
  elif grep -q "hl\." "$LUA"; then
    # Flat layout: the user's binds live in hyprland.lua itself.
    if grep -rqE "$TOGGLE_KEY_RE" "$HYPR_DIR" --include='*.lua' 2>/dev/null \
       && ! grep -qF -e "$MARK_A" "$LUA"; then
      report_toggle_conflict "$LUA"
      lua_block "$LUA" \
        "-- $TOGGLE_KEY is taken by this config, so the cheat-sheet has no toggle" \
        '-- bind. Add one on a free key; the widget is started by the line below.' \
        'hl.exec_cmd("qs -c keybinds")'
    else
      log "Adding the $TOGGLE_KEY toggle and autostart to $LUA"
      lua_block "$LUA" \
        'hl.exec_cmd("qs -c keybinds")' \
        "hl.bind(\"$TOGGLE_KEY\", hl.dsp.exec_cmd(\"$BIN_DIR/keybinds-toggle.sh\"), { description = \"Keybindings (widget)\" })" \
        "hl.bind(\"$LIST_KEY\", hl.dsp.exec_cmd(\"$BIN_DIR/keybinds.sh\"), { description = \"Keybindings (fallback list)\" })"
    fi
    [[ -z "$REFERENCE" ]] && command -v hyprctl >/dev/null && hyprctl reload >/dev/null 2>&1 || true
  else
    warn "$LUA does not look like a Lua config this script can extend."
    warn "Bind manually:  exec-once = qs -c keybinds"
  fi
elif [[ "$DE" == kde ]]; then
  command -v yad >/dev/null 2>&1 || warn "For the fallback list, install 'yad'."
  warn "Launch it from your app menu (\"Keybindings\"), or bind a Custom Shortcut in"
  warn "  System Settings → Shortcuts to:  qs -c kde-keybinds ipc call cheatsheet toggle"
else
  warn "Neither Hyprland nor KDE — no autostart or keybind was written."
  warn "Toggle the cheat-sheet with:  $BIN_DIR/keybinds-toggle.sh"
fi

# --- start the widget --------------------------------------------------------
if [[ -z "$REFERENCE" && "$DE" == hyprland ]] && command -v qs >/dev/null 2>&1; then
  # A running widget still holds the shell.qml it was launched with, from
  # wherever it was launched — which, until this version, could be a config root
  # the session does not read.
  if ! xdg_session_display_env >/dev/null; then
    # No session to launch into: an agent shell, an ssh login, a cron job. Do
    # NOT kill a widget running for the logged-in user and then fail to bring
    # it back.
    warn "No graphical session found, so the widget was not (re)started."
    warn "It will come up at next login. To start it now, from your own session:"
    warn "  $BIN_DIR/keybinds-toggle.sh"
  else
    pkill -f '(^|/)qs -c keybinds( |$)' >/dev/null 2>&1 && sleep 0.3 || true
    xdg_session_spawn qs -c keybinds \
      || warn "Could not start the widget. From your own session: qs -c keybinds"
  fi
fi

if [[ -z "$REFERENCE" ]]; then
  cat <<DONE

Keyboard shortcuts installed into $XDGS_CONFIG_HOME.
  • Widget:  $QS_DIR
  • Toggle:  $BIN_DIR/keybinds-toggle.sh
  • Confirm it landed where your session looks:  ./install.sh --check
DONE
fi
