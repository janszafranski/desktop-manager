# shellcheck shell=bash
# xdg-session-paths.sh — resolve install destinations from the desktop
# SESSION's environment, not the installing shell's.
#
# Vendored, identical copy. Version below; if you change it, change every copy.
# Canonical home: openclaw-flyout/tools/xdg-session-paths.sh
XDG_SESSION_PATHS_VERSION=1
#
# Why this file exists
# --------------------
# Jan's Hyprland session runs with XDG_CONFIG_HOME=/home/jan/.config-ii.
# Installers that hardcoded "$HOME/.config" wrote their config into a root
# his session never reads, so an app would install and then be unfindable:
# `qs -c openclaw-sidebar` had nothing to load, and link2ctl's restore
# service read an empty config directory while his camera presets sat in the
# other root (JAN-78).
#
# "Honour $XDG_CONFIG_HOME" is necessary but NOT sufficient, which is the
# part that keeps biting. An installer is very often run by an agent, and an
# agent run exports XDG_CONFIG_HOME *and HOME* into a /tmp sandbox that is
# deleted when the run ends:
#
#   HOME=/tmp/paperclip-ai-.../            XDG_CONFIG_HOME=/tmp/.../config
#
# A script that trusted its own shell would write config into a directory
# that is both wrong and temporary, and report success. So this file trusts
# neither $XDG_CONFIG_HOME nor $HOME from the environment it is sourced in.
#
# The real home comes from the passwd database, and every destination is
# resolved from the live session:
#
#   1. XDG_SESSION_PATHS_* overrides      (tests, and --check reference builds)
#   2. the running compositor's own /proc/<pid>/environ
#   3. systemctl --user show-environment  (the session imports its env there)
#   4. this shell's environment, but only if it points inside the real home
#   5. the plain XDG defaults
#
# A candidate outside the real home is rejected at every step. That is the
# agent sandbox, and it is never where the session will look.
#
# Destination classes are deliberately NOT all the same variable:
#
#   config consumed by session processes -> session $XDG_CONFIG_HOME
#   systemd --user unit files           -> the user manager's OWN unit path
#   desktop entries / icons / MIME      -> session $XDG_DATA_HOME
#   executables                         -> <home>/.local/bin
#
# The systemd one is the subtle case and it is measured, not assumed. The
# user manager is started by pam_systemd at login, BEFORE the session sets
# XDG_CONFIG_HOME, so its unit search path is fixed at ~/.config/systemd/user
# even in Jan's session — but the session later pushes its environment into
# the manager, so the services it spawns DO see XDG_CONFIG_HOME=.config-ii.
# Units therefore go where the manager reads; the config those units' processes
# load goes where the session points. Resolving both from one variable puts a
# unit somewhere systemd will never enumerate.
#
# Usage:
#   . "$SELF/tools/xdg-session-paths.sh"
#   xdg_session_paths_resolve
#   echo "$XDGS_HOME"               # e.g. /home/jan      (never the sandbox)
#   echo "$XDGS_CONFIG_HOME"        # e.g. /home/jan/.config-ii
#   echo "$XDGS_DATA_HOME"          # e.g. /home/jan/.local/share
#   echo "$XDGS_SYSTEMD_USER_DIR"   # e.g. /home/jan/.config/systemd/user
#   echo "$XDGS_BIN_DIR"            # e.g. /home/jan/.local/bin
#   xdg_session_paths_report        # one line per destination, with its source

# Compositors and shells whose environment represents "the session". Ordered:
# the first one running wins, so a Wayland compositor beats a stray X11 shell.
XDG_SESSION_PATHS_COMPOSITORS=(
    Hyprland sway river niri labwc wayfire cosmic-comp
    kwin_wayland gnome-shell plasmashell
)

# The user's real home directory. $HOME is not trusted: an agent run rewrites
# it to a sandbox under /tmp, and installing relative to that silently
# produces an install that disappears with the run.
_xdgs_real_home() {
    local home
    home="$(getent passwd "$(id -u)" 2>/dev/null | cut -d: -f6)"
    if [ -n "$home" ] && [ -d "$home" ]; then
        printf '%s' "$home"
    else
        printf '%s' "$HOME"
    fi
}

# An absolute path under the real home that is not the home itself. Anything
# else is a sandbox, a typo, or a system path, and is not a user config root.
_xdgs_usable() {
    case "$1" in
        "$XDGS_HOME"/?*) [ "${1#*$'\n'}" = "$1" ] ;;
        *) return 1 ;;
    esac
}

# Read one variable out of a process environment block.
# The group redirect covers both "the process exited between the glob and
# here" and "this is another user's process, or a sandbox denies the read" —
# `[ -r ]` answers yes to the latter and the read then fails anyway.
_xdgs_from_pid() { # _xdgs_from_pid <pid> <var>
    { tr '\0' '\n' < "/proc/$1/environ"; } 2>/dev/null \
        | sed -n "s/^$2=//p" | head -1
}

# Find the process whose environment is the session's. Sets _XDGS_SESSION_PID
# and _XDGS_SESSION_NAME (both empty if there is no session). Called once from
# xdg_session_paths_resolve — it walks /proc, and it must assign globals, so it
# is deliberately not a function whose result is captured in a subshell.
_xdgs_find_session() {
    _XDGS_SESSION_PID=""
    _XDGS_SESSION_NAME=""
    # One pgrep for the whole list: this runs on every install and check, and
    # ten /proc walks for one answer is ten too many.
    local pattern name pid
    pattern="$(IFS='|'; printf '%s' "${XDG_SESSION_PATHS_COMPOSITORS[*]}")"
    for pid in $(pgrep -x -u "$(id -u)" "$pattern" 2>/dev/null); do
        # A compositor whose HOME is not the real home is not this user's
        # login session (it is something an agent started in a sandbox).
        [ "$(_xdgs_from_pid "$pid" HOME)" = "$XDGS_HOME" ] || continue
        name="$(tr -d '\0' < "/proc/$pid/comm" 2>/dev/null)"
        _XDGS_SESSION_PID="$pid"
        _XDGS_SESSION_NAME="${name:-session}"
        return 0
    done
    return 0
}

# Ask the user manager for its imported session environment. The manager is
# reachable from a detached shell (an agent, a cron job) only once
# XDG_RUNTIME_DIR and the bus address are set, so set them locally.
_xdgs_systemctl_user() { # _xdgs_systemctl_user <args...>
    command -v systemctl >/dev/null 2>&1 || return 1
    local runtime="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    [ -d "$runtime" ] || return 1
    XDG_RUNTIME_DIR="$runtime" \
    DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$runtime/bus}" \
        systemctl --user "$@" 2>/dev/null
}

# Public: the session's display environment, as NAME=VALUE lines suitable for
# `env`. An installer run from a detached shell (an agent, ssh, a cron job)
# has no WAYLAND_DISPLAY and no XDG_RUNTIME_DIR, so anything it tries to
# launch on the user's screen dies immediately — and an installer that reports
# "launched" after that is the same lie this file exists to stop. Empty if
# there is no session, in which case do not pretend to launch anything.
xdg_session_display_env() {
    [ -n "$_XDGS_SESSION_PID" ] || return 1
    _xdgs_find_session_client
    local var value
    for var in WAYLAND_DISPLAY DISPLAY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS \
               XDG_CURRENT_DESKTOP XDG_SESSION_TYPE HYPRLAND_INSTANCE_SIGNATURE \
               XDG_CONFIG_HOME XDG_DATA_HOME HOME; do
        # The compositor first: its own environment is the authority on where
        # the session's config lives.
        value="$(_xdgs_from_pid "$_XDGS_SESSION_PID" "$var" || true)"
        # But a compositor does not set WAYLAND_DISPLAY or its own instance
        # signature for *itself* — it exports those to the clients it starts.
        # Reading only the compositor therefore yields an environment that
        # cannot connect to the compositor, which is a confusing way to fail.
        if [ -z "$value" ] && [ -n "$_XDGS_CLIENT_PID" ]; then
            value="$(_xdgs_from_pid "$_XDGS_CLIENT_PID" "$var" || true)"
        fi
        [ -n "$value" ] && printf '%s=%s\n' "$var" "$value"
    done
    return 0
}

# A client of the session, i.e. a process the compositor started. Used only to
# recover the display variables the compositor does not set for itself. Cached
# because it walks every readable environ under /proc.
_xdgs_find_session_client() {
    [ -n "${_XDGS_CLIENT_PID+set}" ] && return 0
    _XDGS_CLIENT_PID=""
    local proc pid env_file
    for env_file in /proc/[0-9]*/environ; do
        [ -r "$env_file" ] || continue
        pid="${env_file#/proc/}"; pid="${pid%/environ}"
        [ "$pid" = "$_XDGS_SESSION_PID" ] && continue
        # Must be this user's session, and must actually hold a display.
        [ "$(_xdgs_from_pid "$pid" HOME)" = "$XDGS_HOME" ] || continue
        [ -n "$(_xdgs_from_pid "$pid" WAYLAND_DISPLAY || true)" ] || continue
        # Prefer a client that agrees with the compositor about the config
        # root: a process an agent spawned carries a sandbox environment, and
        # handing that back out is the bug this file exists to prevent.
        if [ "$(_xdgs_from_pid "$pid" XDG_CONFIG_HOME || true)" = "$XDGS_CONFIG_HOME" ]; then
            _XDGS_CLIENT_PID="$pid"
            return 0
        fi
        [ -z "$_XDGS_CLIENT_PID" ] && _XDGS_CLIENT_PID="$pid"
    done
    return 0
}

# Public: start a detached command inside the session, or fail loudly. Returns
# non-zero without running anything when there is no session to start it in.
xdg_session_spawn() { # xdg_session_spawn <command> [args...]
    local line
    local -a session_env=()
    while IFS= read -r line; do session_env+=("$line"); done < <(xdg_session_display_env)
    [ "${#session_env[@]}" -gt 0 ] || return 1
    setsid -f env "${session_env[@]}" "$@" >/dev/null 2>&1
}

# Public: run systemctl --user against the session's manager. An installer run
# by an agent or a cron job has neither XDG_RUNTIME_DIR nor a bus address, and
# a bare `systemctl --user daemon-reload` there fails with "Failed to connect
# to user scope bus" — which looks exactly like "you have no systemd session"
# and gets shrugged off, leaving the unit installed and never loaded.
xdg_session_systemctl_user() { _xdgs_systemctl_user "$@"; }

# Resolve one XDG base directory. Sets <out_var> and <out_var>_SOURCE.
_xdgs_resolve_one() { # _xdgs_resolve_one <var name> <default> <out var>
    local var="$1" default="$2" out="$3" value source pid

    value="$(eval "printf '%s' \"\${XDG_SESSION_PATHS_$var:-}\"")"
    if [ -n "$value" ]; then
        # An explicit override is trusted as given: --check points it at a
        # throwaway tree on purpose, and the tests point it outside the home.
        eval "$out=\$value; ${out}_SOURCE='XDG_SESSION_PATHS_$var override'"
        return 0
    fi

    pid="$_XDGS_SESSION_PID"
    if [ -n "$pid" ]; then
        value="$(_xdgs_from_pid "$pid" "$var" || true)"
        if [ -n "$value" ] && _xdgs_usable "$value"; then
            eval "$out=\$value; ${out}_SOURCE='the $_XDGS_SESSION_NAME session (pid $pid)'"
            return 0
        fi
        # The compositor is running and does not usefully set it. That is an
        # answer: the session uses the default, and this shell's value is noise.
        if [ -n "$value" ]; then
            source="$_XDGS_SESSION_NAME (pid $pid) sets $var=$value, outside $XDGS_HOME — using the default"
        else
            source="$_XDGS_SESSION_NAME (pid $pid) does not set $var — using the default"
        fi
        eval "$out=\$default; ${out}_SOURCE=\$source"
        return 0
    fi

    value="$(_xdgs_systemctl_user show-environment | sed -n "s/^$var=//p" | head -1)"
    if [ -n "$value" ] && _xdgs_usable "$value"; then
        eval "$out=\$value; ${out}_SOURCE='systemd --user imported session environment'"
        return 0
    fi

    value="$(eval "printf '%s' \"\${$var:-}\"")"
    if [ -n "$value" ] && _xdgs_usable "$value"; then
        eval "$out=\$value; ${out}_SOURCE='this shell (no session found, and it points inside $XDGS_HOME)'"
        return 0
    fi
    if [ -n "$value" ]; then
        eval "$out=\$default; ${out}_SOURCE='this shell sets $var=$value, outside $XDGS_HOME — ignored'"
        return 0
    fi

    eval "$out=\$default; ${out}_SOURCE='XDG default'"
}

# Where `systemd --user` actually looks for unit files. Ground truth, because
# the manager's search path is fixed at login and does not follow the
# session's XDG_CONFIG_HOME.
_xdgs_resolve_systemd_user_dir() {
    if [ -n "${XDG_SESSION_PATHS_SYSTEMD_USER_DIR:-}" ]; then
        XDGS_SYSTEMD_USER_DIR="$XDG_SESSION_PATHS_SYSTEMD_USER_DIR"
        XDGS_SYSTEMD_USER_DIR_SOURCE='XDG_SESSION_PATHS_SYSTEMD_USER_DIR override'
        return 0
    fi

    local entry
    for entry in $(_xdgs_systemctl_user show -p UnitPath --value); do
        # The plain per-user directory, not .control / .attached, which
        # systemd owns and rewrites.
        case "$entry" in
            "$XDGS_HOME"/*/systemd/user)
                XDGS_SYSTEMD_USER_DIR="$entry"
                XDGS_SYSTEMD_USER_DIR_SOURCE='systemd --user UnitPath'
                return 0 ;;
        esac
    done

    XDGS_SYSTEMD_USER_DIR="$XDGS_HOME/.config/systemd/user"
    XDGS_SYSTEMD_USER_DIR_SOURCE='systemd --user default (manager not reachable)'
}

xdg_session_paths_resolve() {
    XDGS_HOME="${XDG_SESSION_PATHS_HOME:-$(_xdgs_real_home)}"
    _xdgs_find_session
    _xdgs_resolve_one XDG_CONFIG_HOME "$XDGS_HOME/.config"      XDGS_CONFIG_HOME
    _xdgs_resolve_one XDG_DATA_HOME   "$XDGS_HOME/.local/share" XDGS_DATA_HOME
    _xdgs_resolve_one XDG_STATE_HOME  "$XDGS_HOME/.local/state" XDGS_STATE_HOME
    _xdgs_resolve_systemd_user_dir
    XDGS_BIN_DIR="${XDG_SESSION_PATHS_BIN_DIR:-$XDGS_HOME/.local/bin}"
}

xdg_session_paths_report() {
    printf '  %-14s %s\n' 'home'    "$XDGS_HOME"
    printf '  %-14s %s\n' 'config'  "$XDGS_CONFIG_HOME"
    printf '  %-14s   %s\n' ''      "from: $XDGS_CONFIG_HOME_SOURCE"
    printf '  %-14s %s\n' 'data'    "$XDGS_DATA_HOME"
    printf '  %-14s   %s\n' ''      "from: $XDGS_DATA_HOME_SOURCE"
    printf '  %-14s %s\n' 'units'   "$XDGS_SYSTEMD_USER_DIR"
    printf '  %-14s   %s\n' ''      "from: $XDGS_SYSTEMD_USER_DIR_SOURCE"
    printf '  %-14s %s\n' 'commands' "$XDGS_BIN_DIR"
}

# Move a config directory or file from a root the session does not read into
# the one it does. Config already in the right place is the user's and is
# left alone; this only ever rescues config that was orphaned.
xdg_session_paths_migrate() { # xdg_session_paths_migrate <old> <new> <what>
    local old="$1" new="$2" what="$3" target

    [ -e "$old" ] || return 0
    [ "$old" = "$new" ] && return 0

    # Jan's stopgap for this bug was a symlink from the session root to the
    # other one. Replacing it with the real directory is the point of the
    # migration, so a symlinked destination is not "already installed".
    if [ -L "$new" ]; then
        target="$(readlink -f -- "$new" 2>/dev/null || true)"
        if [ "$target" = "$(readlink -f -- "$old" 2>/dev/null || true)" ]; then
            rm -f -- "$new"
            printf '  removed the stopgap symlink %s -> %s\n' "$new" "$target"
        else
            printf '  %s is a symlink to %s — leaving it alone\n' "$new" "$target"
            return 0
        fi
    fi

    if [ -e "$new" ]; then
        if [ -d "$new" ] && [ -z "$(ls -A -- "$new" 2>/dev/null)" ]; then
            rmdir -- "$new"
        else
            printf '  kept the %s already in %s (%s left in place)\n' "$what" "$new" "$old"
            return 0
        fi
    fi

    mkdir -p -- "$(dirname -- "$new")"
    if mv -- "$old" "$new" 2>/dev/null; then
        printf '  moved your %s: %s -> %s\n' "$what" "$old" "$new"
    else
        cp -a -- "$old" "$new"
        rm -rf -- "$old"
        printf '  copied your %s: %s -> %s\n' "$what" "$old" "$new"
    fi
}
