#!/usr/bin/env bash
# openclaw-cli-chat.sh — flyout ↗ hand-off.
#
# Launched by the OpenClaw sidebar's ↗ button. Runs the CLI chat on the same
# session as the flyout, and — however the chat exits (type /exit, Ctrl+D, or
# Ctrl+C) — brings the flyout back, shown + pinned ("locked"), with the same
# conversation. The `trap ... EXIT` guarantees the return even on Ctrl+C.
set -u
trap 'qs -c openclaw-sidebar ipc call sidebar lock >/dev/null 2>&1' EXIT
openclaw chat --session ai-flyout "$@"
