#!/usr/bin/env bash
# Toggle the Caelestia-styled QuickShell keybind widget open/closed.
#
# The widget runs persistently (for the top-right hot corner), so this just flips
# its pinned state over Quickshell IPC. If it isn't running yet, launch it.
#
# Safe process matching: this ONLY ever targets `qs -c keybinds`, never the bare
# `qs` binary — the Caelestia shell itself runs as `qs -c caelestia`, so matching
# the full config name avoids killing the shell.
if pgrep -f 'qs -c keybinds' >/dev/null; then
    qs -c keybinds ipc call keybinds toggle
else
    setsid qs -c keybinds >/dev/null 2>&1 &
fi
