#!/usr/bin/env bash
# apply.sh — transform the KDE Plasma desktop into a macOS (WhiteSur) look.
# Idempotent; installs WhiteSur at user level (no sudo) if it's missing.
# Undo with revert.sh (which uses the restore point captured on first apply).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LNF=com.github.vinceliuice.WhiteSur

# 0. capture a restore point once, so revert.sh can undo this on any machine
if [[ ! -f "$HERE/restore/state.env" ]]; then
  echo ":: saving restore point"
  mkdir -p "$HERE/restore"
  for f in kdeglobals kwinrc kcminputrc plasma-org.kde.plasma.desktop-appletsrc plasmashellrc; do
    [[ -f ~/.config/$f ]] && cp -a ~/.config/"$f" "$HERE/restore/$f"
  done
  cat > "$HERE/restore/state.env" <<EOF
LOOKANDFEEL=$(kreadconfig6 --file kdeglobals --group KDE --key LookAndFeelPackage)
ICONS=$(kreadconfig6 --file kdeglobals --group Icons --key Theme)
CURSOR=$(kreadconfig6 --file kcminputrc --group Mouse --key cursorTheme)
COLORSCHEME=$(kreadconfig6 --file kdeglobals --group General --key ColorScheme)
EOF
fi

# 1. ensure WhiteSur themes are installed (user-level clone + installers)
if ! kpackagetool6 --list --type Plasma/LookAndFeel 2>/dev/null | grep -q "$LNF"; then
  echo ":: installing WhiteSur themes (user-level, no sudo)"
  tmp="$(mktemp -d)"
  git clone --depth 1 https://github.com/vinceliuice/WhiteSur-kde.git        "$tmp/kde"
  git clone --depth 1 https://github.com/vinceliuice/WhiteSur-icon-theme.git "$tmp/icons"
  git clone --depth 1 https://github.com/vinceliuice/WhiteSur-cursors.git    "$tmp/cursors"
  ( cd "$tmp/kde"     && ./install.sh )
  ( cd "$tmp/cursors" && ./install.sh )
  ( cd "$tmp/icons"   && ./install.sh -t default )
  rm -rf "$tmp"
fi

# 1b. ensure the Punchi Dock plasmoid (bundled in this profile) is installed
PLASMOID="$(ls "$HERE"/*.plasmoid 2>/dev/null | head -1)"
if [[ -n "$PLASMOID" ]]; then
  echo ":: installing Punchi Dock plasmoid"
  kpackagetool6 --type Plasma/Applet --install "$PLASMOID" 2>/dev/null \
    || kpackagetool6 --type Plasma/Applet --upgrade "$PLASMOID" 2>/dev/null || true
fi

# 2. apply global theme + supporting pieces
echo ":: applying macOS (WhiteSur) global theme"
plasma-apply-lookandfeel -a "$LNF" --resetLayout
plasma-apply-colorscheme WhiteSur       2>/dev/null || true
plasma-apply-cursortheme WhiteSur-cursors 2>/dev/null || true
kwriteconfig6 --file kdeglobals --group Icons --key Theme WhiteSur
kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key library org.kde.kwin.aurorae
kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key theme __aurorae__svg__WhiteSur
[[ -x /usr/lib/plasma-changeicons ]] && /usr/lib/plasma-changeicons WhiteSur 2>/dev/null || true

# 3. restart the shell so layout + decoration take effect
echo ":: restarting Plasma shell"
qdbus6 org.kde.KWin /KWin reconfigure 2>/dev/null || true
kquitapp6 plasmashell 2>/dev/null || killall plasmashell 2>/dev/null || true
(setsid plasmashell >/dev/null 2>&1 &)

# 4. wait for the shell's scripting API, then set wallpaper + add the dock
for _ in $(seq 1 30); do
  qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "true" >/dev/null 2>&1 && break
  sleep 0.5
done

# calm macOS Monterey Light wallpaper (the WhiteSur default is oversaturated)
if [[ -f "$HERE/wallpaper.jpg" ]]; then
  echo ":: setting Monterey Light wallpaper"
  mkdir -p ~/.local/share/wallpapers
  cp -f "$HERE/wallpaper.jpg" ~/.local/share/wallpapers/Monterey-Light.jpg
  plasma-apply-wallpaperimage ~/.local/share/wallpapers/Monterey-Light.jpg 2>/dev/null || true
fi

echo ":: adding dock"
DOCK_ID="$(qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "$(cat "$HERE/add-dock.js")" 2>/dev/null | tr -d '[:space:]')"

# 5. make the dock translucent (panelOpacity=2) so it matches the rest of the
# desktop; this key only takes effect from the config file, so write it to the
# dock's containment and restart the shell once more to render it.
if [[ "$DOCK_ID" =~ ^[0-9]+$ ]]; then
  echo ":: making dock translucent"
  kwriteconfig6 --file plasma-org.kde.plasma.desktop-appletsrc \
    --group Containments --group "$DOCK_ID" --group General --key panelOpacity 2
  kquitapp6 plasmashell 2>/dev/null || killall plasmashell 2>/dev/null || true
  (setsid plasmashell >/dev/null 2>&1 &)
fi

echo ":: macOS look applied. Undo with: $HERE/revert.sh"
