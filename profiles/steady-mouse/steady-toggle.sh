#!/usr/bin/env bash
# Toggle the tremor-filter "steady mouse" daemon on/off (bound to SUPER+SHIFT+M).
# Tuning now lives in ~/.config/tremor-filter/config.json (edit via the GUI).
LOG="/tmp/tremor-filter.log"

if pkill -f "local/bin/tremor-filter.py"; then
    command -v notify-send >/dev/null && notify-send -t 2000 "Steady mouse: OFF" "Normal mouse restored"
    exit 0
fi

setsid -f python3 "$HOME/.local/bin/tremor-filter.py" >"$LOG" 2>&1
command -v notify-send >/dev/null && notify-send -t 2000 "Steady mouse: ON" "Tremor filter active — SUPER+SHIFT+M to toggle off"
