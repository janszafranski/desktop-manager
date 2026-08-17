# shellcheck shell=bash
# Shared manifest of what gets backed up / restored.
# Sourced by collect.sh (system -> repo) and install.sh (repo -> system).
#
# Each array entry is a path RELATIVE to the given root. Both files and
# directories are allowed. Missing sources are silently skipped on collect.

# --- files that live directly in $HOME ---------------------------------------
HOME_ITEMS=(
  .bashrc
  .bash_profile
  .zshrc
  .gtkrc-2.0
  .gtkrc-2.0.mine
)

# --- items under ~/.config ---------------------------------------------------
# App look & config only. Deliberately excludes heavyweight per-machine state
# (browsers, teams, libreoffice, chromium, VS Code, etc.).
CONFIG_ITEMS=(
  # shell / terminal / editors
  fish/config.fish
  fish/fish_variables
  alacritty
  micro/settings.json
  micro/colorschemes
  micro/bindings.json
  kate
  katerc
  kateschemarc

  # GTK / Qt / XSettings theming
  gtk-3.0/settings.ini
  gtk-4.0/settings.ini
  xsettingsd
  Trolltech.conf
  kdeglobals
  Kvantum

  # KDE Plasma / KWin
  kwinrc
  kwinrulesrc
  kglobalshortcutsrc
  kdeglobals
  plasmarc
  plasmashellrc
  plasma-org.kde.plasma.desktop-appletsrc
  kscreenlockerrc
  ksplashrc
  kcminputrc
  kdeconnect
  kdedefaults
  ksmserverrc
  dolphinrc

  # misc
  mimeapps.list
  libinput-gestures.conf
  autostart
  systemd/user/shelly-notifications.service
)

# --- items under ~/.local/share ---------------------------------------------
# Manually-installed themes / cursors / kwin scripts (not owned by any package).
LOCALSHARE_ITEMS=(
  icons/Nordic-bluish
  icons/Nordic-darker
  icons/Nordic-green
  color-schemes
  plasma/look-and-feel/Nordic-bluish
  plasma/desktoptheme/Nordic-bluish
  aurorae/themes/Nordic
  kwin/scripts/krohnkite
  kwin/scripts/ultrawidewindows
  wallpapers
)

# --- items under ~/.icons ----------------------------------------------------
ICONS_ITEMS=(
  Nordic-cursors
)

# --- items under ~/bin -------------------------------------------------------
# Small scripts only. The 162MB pandoc binary is intentionally NOT bundled;
# install it via `pacman -S pandoc-cli` instead.
BIN_ITEMS=(
  run_welcomers_rota.sh
  copyright.pandoc
)

# --- optional / large --------------------------------------------------------
# ~/Pictures/Wallpapers (~48MB). Set REPLICA_INCLUDE_PICTURES=1 to include.
PICTURES_ITEMS=(
  Pictures/Wallpapers
)
