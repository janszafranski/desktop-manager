# OpenClaw flyout — AI assistant side panel

A pinnable Quickshell side panel (`qs -c openclaw-sidebar`, **Super+O**) that
chats with your OpenClaw agent through a local OpenAI-compatible bridge on
`127.0.0.1:8787` (a Node service run via systemd --user).

## Install
Desktop Manager → Apps → **OpenClaw flyout → Install**, or `./install.sh`.
Requires **node**, **quickshell**, and the **openclaw** CLI (the flyout answers
via your OpenClaw agent). Deploys the bridge + service + panel and wires
Super+O / autostart / blur-off into `~/.config/hypr/hyprland.lua` (guarded).

## Files
`openclaw-ai-bridge.js` (bridge) · `openclaw-ai-bridge.service` (systemd unit) ·
`openclaw-sidebar/` (panel QML + icons) · `openclaw-cli-chat.sh`, `openclaw-dashboard.sh` (helpers).
