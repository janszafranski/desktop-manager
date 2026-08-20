#!/usr/bin/env bash
# Set the Caelestia wallpaper, keeping the black surfaces.
# Usage: set-wallpaper.sh [image]   (default: Hyprland's "cats" wallpaper)
# The three Hyprland built-in wallpapers live in /usr/share/hypr/wall{0,1,2}.png
# (wall2 = anime girl + cats). These are what you see before the shell loads.
set -euo pipefail
wall="${1:-/usr/share/hypr/wall2.png}"

caelestia wallpaper -f "$wall"

# caelestia re-reads the catppuccin theme colours on a wallpaper change, which
# undoes the black surfaces -- re-apply them (single source of truth).
"$(dirname "$(readlink -f "$0")")/blacken.sh"
echo "Wallpaper: $wall  (black surfaces preserved)"
