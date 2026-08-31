# Shakefree Mouse

A hand-tremor mouse filter for Linux — smooths shaky pointer motion and steadies
clicks (evdev/uinput, works on any desktop, no root).

<p align="center"><img src="assets/screenshot.png" alt="Shakefree Mouse control panel" width="320"></p>

**This is now its own standalone project** — the code, docs, and packaging live at:

- **Repo:** https://github.com/janszafranski/shakefree-mouse
- **AUR:** `shakefree-mouse` (`paru -S shakefree-mouse`)

desktop-manager no longer bundles a copy; [`install.sh`](install.sh) just installs
the package (from the AUR, or built from the GitHub release with `makepkg`). This
keeps a single source of truth so there's nothing to keep in sync.
