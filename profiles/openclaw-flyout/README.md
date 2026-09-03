# OpenClaw flyout — AI assistant side panel

<p align="center"><img src="assets/screenshot.png" alt="OpenClaw flyout side panel" width="300"></p>

A pinnable Quickshell side panel (`qs -c openclaw-sidebar`, **Super+O**) that
chats with your OpenClaw agent through a local OpenAI-compatible bridge on
`127.0.0.1:8787`.

## Now its own project

The flyout lives in its own repo — the single source of truth is:

**https://github.com/janszafranski/openclaw-flyout**

This desktop-manager profile no longer bundles a copy. `install.sh` clones (or
updates) that repo into `~/.cache/desktop-manager/openclaw-flyout` and runs the
project's own installer; `uninstall.sh` runs the project's uninstaller. To pin a
version, set `OPENCLAW_FLYOUT_REF=<tag>` (defaults to `master`).

## Install
Desktop Manager → Apps → **OpenClaw flyout → Install**, or `./install.sh`.
Requires **git**, plus the flyout's own dependencies (**node**, **quickshell**,
**sqlite3**, and the **openclaw** CLI). See the upstream README for details.
