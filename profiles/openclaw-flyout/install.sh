#!/usr/bin/env bash
# install.sh — install the OpenClaw flyout (AI assistant side panel).
#
# The OpenClaw flyout is its own project now — the single source of truth lives at
#   https://github.com/janszafranski/openclaw-flyout
# so this desktop-manager profile no longer bundles a copy; it clones (or updates)
# that repo into a local cache and runs the project's own install.sh.
set -euo pipefail
log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }
[[ ${EUID:-$(id -u)} -eq 0 ]] && die "Run as your normal user, not root."

REPO_URL="${OPENCLAW_FLYOUT_REPO:-https://github.com/janszafranski/openclaw-flyout.git}"
REF="${OPENCLAW_FLYOUT_REF:-master}"   # pin a tag here to freeze the version
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/desktop-manager/openclaw-flyout"

command -v git >/dev/null 2>&1 || die "git is required to fetch the OpenClaw flyout."

if [[ -d "$CACHE/.git" ]]; then
  log "Updating cached checkout ($CACHE)"
  git -C "$CACHE" fetch --depth 1 origin "$REF" && git -C "$CACHE" checkout -q FETCH_HEAD \
    || warn "Could not update the cache — using the existing checkout."
else
  log "Cloning $REPO_URL @ $REF"
  rm -rf "$CACHE"
  mkdir -p "$(dirname "$CACHE")"
  git clone --depth 1 --branch "$REF" "$REPO_URL" "$CACHE" \
    || git clone --depth 1 "$REPO_URL" "$CACHE" \
    || die "Clone failed. Check your network / the repo URL."
fi

[[ -x "$CACHE/install.sh" ]] || die "The fetched repo has no install.sh — unexpected layout."
log "Running the OpenClaw flyout installer"
exec "$CACHE/install.sh"
