#!/usr/bin/env bash
# install.sh — install Shakefree Mouse (hand-tremor mouse filter).
#
# Shakefree Mouse is its own project now — the single source of truth lives at
#   https://github.com/janszafranski/shakefree-mouse   (AUR: shakefree-mouse)
# so this desktop-manager profile no longer bundles a copy; it just installs the
# package. Prefers the AUR (via an AUR helper); otherwise builds from the GitHub
# release with makepkg.
set -euo pipefail
log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
[[ ${EUID:-$(id -u)} -eq 0 ]] && { echo "Run as your normal user, not root." >&2; exit 1; }

if pacman -Q shakefree-mouse >/dev/null 2>&1; then
  log "Shakefree Mouse is already installed ($(pacman -Q shakefree-mouse))."
else
  if command -v paru >/dev/null 2>&1; then
    log "Installing from the AUR via paru"; paru -S --needed shakefree-mouse
  elif command -v yay >/dev/null 2>&1; then
    log "Installing from the AUR via yay"; yay -S --needed shakefree-mouse
  else
    log "No AUR helper found — building from the GitHub release with makepkg"
    tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
    base="https://raw.githubusercontent.com/janszafranski/shakefree-mouse/main/packaging/aur"
    curl -fsSL -o "$tmp/PKGBUILD"                "$base/PKGBUILD"
    curl -fsSL -o "$tmp/shakefree-mouse.install" "$base/shakefree-mouse.install"
    ( cd "$tmp" && makepkg -si )
  fi
fi

# one-time permissions (idempotent)
if ! id -nG | grep -qw input; then
  warn "Adding you to the 'input' group (needed to filter the mouse) — requires sudo + re-login."
  sudo usermod -aG input "$USER" || true
fi
sudo modprobe uinput 2>/dev/null || true

log "Done. Launch 'Shakefree Mouse' from your app menu, or run: shakefree-mouse"
log "Toggle with a keybind bound to: shakefree-mouse-toggle"
