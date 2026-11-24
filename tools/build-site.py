#!/usr/bin/env python3
"""Build docs/ — the site at janszafranski.github.io/desktop-manager.

A sibling of the "just a... CREATORsuite" site: same bones, tinted Nord-blue to
mark this as the *desktop* side of the family. The landing page is a container
for Desktop Manager itself and the small tools it installs; every card links to
a detail page with a screenshot, what it does, and how to install it.

    python3 tools/build-site.py

Copies/optimises the screenshots already in the repo into docs/assets. Uses
Pillow if present (to down-size), otherwise copies the files as-is.
"""
from __future__ import annotations

import html
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"
SITE = "Desktop Manager"
TAGLINE = "Save, restore and re-theme your Linux desktop — plus the small tools that smooth the day."
REPO = "https://github.com/janszafranski/desktop-manager"
TREE = REPO + "/tree/master"
SUITE = "https://janszafranski.github.io/just-a-collection-of-apps/"
BASE = "https://janszafranski.github.io/desktop-manager/"  # trailing slash; GitHub Pages root
AUTHOR = "Jan Szafranski"
OG_DEFAULT = "assets/og-default.png"
TODAY = date.today().isoformat()

# One-line, plain-text SEO descriptions (≈155 chars) keyed by page. Written fresh
# rather than stripped from the HTML blurbs so they read cleanly in search results.
DESC = {
    "index": "Desktop Manager saves, restores and re-themes a whole Linux desktop — KDE Plasma, "
             "SDDM login screens and Hyprland rices — and installs a handful of friendly utilities. For Arch and CachyOS.",
    "desktop-manager": "A graphical picker that restores this machine's KDE / Hyprland look and configuration "
             "on a fresh Linux install, in dry-runnable stages, and installs its companion tools and apps.",
    "shakefree-mouse": "A tremor-smoothing filter for the mouse pointer on Linux, with a tray toggle, so clicks "
             "land where you mean them without making the pointer feel sluggish.",
    "openclaw-flyout": "An AI assistant in a slide-in side panel for your Linux desktop — ask a question without "
             "leaving what you're doing.",
    "app-launcher": "A categorised, Omarchy-style application launcher for Linux, opened with Super + Space: "
             "browse by category or type-to-filter and press Enter.",
    "keybinds": "An on-screen keyboard-shortcut cheat-sheet overlay for your Linux desktop, grouped by what the "
             "shortcuts do — summon it, read the one you want, carry on.",
    "desktop-icons": "Clickable app icons on the wallpaper for a tiling Linux desktop — double-click to open, drag "
             "to arrange, on a setup that normally has no desktop of its own.",
    "mic-fixer": "A quick microphone tester for Linux with a live level meter, to track down a too-quiet mic and set it right.",
    "themes": "Restore a complete Linux desktop look — Nordic KDE Plasma 6, SDDM login screens, Hyprland rices and "
             "matching shell/editor configs — from one picker.",
}
# schema.org applicationCategory per tool page.
CATEGORY = {
    "desktop-manager": "SystemUtilities", "shakefree-mouse": "UtilitiesApplication",
    "openclaw-flyout": "UtilitiesApplication", "app-launcher": "UtilitiesApplication",
    "keybinds": "UtilitiesApplication", "desktop-icons": "DesktopEnhancementApplication",
    "mic-fixer": "UtilitiesApplication", "themes": "DesktopEnhancementApplication",
}

try:
    from PIL import Image
    HAVE_PIL = True
except Exception:  # pragma: no cover - Pillow is optional
    HAVE_PIL = False


# ---------------------------------------------------------------- assets ----
def place(src: str, dst_name: str, maxw: int = 1100) -> str:
    """Copy repo image into docs/assets, down-sizing with Pillow if available.
    Returns the asset path for use in <img src>."""
    src_path = ROOT / src
    out = ASSETS / dst_name
    if HAVE_PIL and src_path.suffix.lower() in (".png", ".jpg", ".jpeg"):
        im = Image.open(src_path)
        if im.width > maxw:
            im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
        if out.suffix.lower() in (".jpg", ".jpeg"):
            im.convert("RGB").save(out, "JPEG", quality=84, optimize=True, progressive=True)
        else:
            im.save(out, optimize=True)
    else:
        shutil.copy2(src_path, out)
    return f"assets/{dst_name}"


# ------------------------------------------------------------------ data ----
# Each tool: card on the index + its own detail page.
TOOLS = [
    dict(
        key="desktop-manager", name="Desktop Manager", lead=True,
        kind="the app",
        src="assets/desktop-manager-gui.png", shot="shot-gui.jpg",
        tag="Pick a desktop configuration, choose which stages to run, go.",
        blurb="A self-contained snapshot of this machine's look and configuration, with a "
              "graphical picker to restore it on a fresh install. Choose a desktop "
              "configuration and which stages to deploy — with a dry-run option — and it "
              "runs the work in a terminal window so <code>sudo</code> prompts and live "
              "output still work. It also installs every tool on this page, and the "
              "Creative apps, from one <b>Apps</b> list.",
        does=[
            "Restore themes and rices: KDE Plasma (Nordic), SDDM login screens, Hyprland (Caelestia / end4)",
            "Deploy in stages — <code>files</code> (no sudo), <code>packages</code>, <code>services</code>, <code>sddm</code>",
            "Dry-run first: preview everything, change nothing",
            "Snapshot <i>your</i> machine back into the repo with <code>collect.sh</code>",
            "Install the standalone utilities and the just a… apps from its Apps list",
        ],
        deps="Built for KDE Plasma 6 (Wayland) on Arch / CachyOS; the GUI is GTK and runs on any desktop.",
        install=[
            "git clone https://github.com/janszafranski/desktop-manager.git ~/system-replica",
            "cd ~/system-replica",
            "./scripts/install-launcher.sh    # add “Desktop Manager” to your app menu",
            "./scripts/gui.sh                 # …or just open the picker now",
        ],
        source=REPO,
    ),
    dict(
        key="shakefree-mouse", name="Shakefree Mouse",
        kind="utility",
        src="profiles/shakefree-mouse/assets/screenshot.png", shot="shot-shakefree.jpg",
        tag="A steadier pointer for a shaky hand.",
        blurb="A tremor-smoothing filter for the mouse pointer, with a tray toggle. It damps "
              "small involuntary movements so clicks land where you mean them, without making "
              "the pointer feel sluggish for ordinary use.",
        does=[
            "Real-time smoothing of pointer tremor",
            "Tray icon to turn it on and off and tune the strength",
            "Leaves fast, deliberate movement untouched",
        ],
        deps=None,
        install=[
            "git clone https://github.com/janszafranski/desktop-manager.git ~/system-replica",
            "~/system-replica/profiles/shakefree-mouse/install.sh",
        ],
        source="https://github.com/janszafranski/shakefree-mouse",
    ),
    dict(
        key="openclaw-flyout", name="OpenClaw flyout",
        kind="utility",
        src="profiles/openclaw-flyout/assets/screenshot.png", shot="shot-openclaw.jpg",
        tag="An AI assistant in a side panel.",
        blurb="An AI assistant that slides in from the edge of the screen — ask a question or "
              "hand off a task without leaving whatever you were doing. The panel tucks away "
              "again when you are done.",
        does=[
            "Slide-in side panel bound to a key",
            "Stays out of the way until you summon it",
            "Talks to your OpenClaw gateway",
        ],
        deps=None,
        install=[
            "git clone https://github.com/janszafranski/desktop-manager.git ~/system-replica",
            "~/system-replica/profiles/openclaw-flyout/install.sh",
        ],
        source=TREE + "/profiles/openclaw-flyout",
    ),
    dict(
        key="app-launcher", name="App launcher",
        kind="utility",
        src="profiles/omarchy-launcher/assets/screenshot.png", shot="shot-launcher.jpg",
        tag="Type a few letters and go — on Super + Space.",
        blurb="An Omarchy-style, categorised application launcher that opens on "
              "<code>Super + Space</code>. Browse your apps by category or just start typing "
              "the name and press Enter.",
        does=[
            "Opens on <code>Super + Space</code>",
            "Apps grouped into tidy categories",
            "Type-to-filter, Enter to launch",
        ],
        deps=None,
        install=[
            "git clone https://github.com/janszafranski/desktop-manager.git ~/system-replica",
            "~/system-replica/profiles/omarchy-launcher/install.sh",
        ],
        source=TREE + "/profiles/omarchy-launcher",
    ),
    dict(
        key="keybinds", name="Keybinds cheat-sheet",
        kind="utility",
        src="profiles/keybinds/assets/screenshot.png", shot="shot-keybinds.jpg",
        tag="Every shortcut, a tap away.",
        blurb="An on-screen cheat-sheet of your keyboard shortcuts, for the moment you know "
              "there is a shortcut but cannot remember which keys. Summon it, read the one you "
              "want, carry on.",
        does=[
            "Full-screen overlay of your current keybindings",
            "Grouped by what the shortcuts do",
            "One key to show, one to dismiss",
        ],
        deps=None,
        install=[
            "git clone https://github.com/janszafranski/desktop-manager.git ~/system-replica",
            "~/system-replica/profiles/keybinds/install.sh",
        ],
        source=TREE + "/profiles/keybinds",
    ),
    dict(
        key="desktop-icons", name="Desktop icons",
        kind="utility",
        src="profiles/omarchy-desktop-icons/docs/screenshot.png", shot="shot-desktopicons.jpg",
        tag="App icons on the wallpaper, double-click to open.",
        blurb="Puts app icons back on the wallpaper, double-click to open — the desktop you "
              "remember, on a tiling Linux setup that normally has none. Arrange them where you "
              "like and they stay put.",
        does=[
            "Clickable app icons on the desktop background",
            "Double-click to launch, drag to arrange",
            "Works on a tiling window manager that has no desktop of its own",
        ],
        deps=None,
        install=[
            "git clone https://github.com/janszafranski/desktop-manager.git ~/system-replica",
            "~/system-replica/profiles/omarchy-desktop-icons/install.sh",
        ],
        source=TREE + "/profiles/omarchy-desktop-icons",
    ),
    dict(
        key="mic-fixer", name="Mic Fixer",
        kind="utility", noshot=True,
        src=None, shot=None,
        tag="Test your microphone, and fix it when it's too quiet.",
        blurb="A quick microphone tester — speak and watch the level — that helps track down "
              "the usual culprit of a too-quiet mic and set it right. Ships the same way as the "
              "other tools and lives in <code>profiles/mic-fixer</code>.",
        does=[
            "Live input-level meter so you can see the mic working",
            "Helps find a wrong default device or a gain set too low",
            "Installs from Desktop Manager's Apps list, or on its own",
        ],
        deps=None,
        install=[
            "git clone https://github.com/janszafranski/desktop-manager.git ~/system-replica",
            "~/system-replica/profiles/mic-fixer/install.sh",
        ],
        source=TREE + "/profiles/mic-fixer",
    ),
]

THEMES = dict(
    key="themes", name="Themes & rices",
    src="preview.png", shot="shot-desktop.jpg",
    tag="The whole look, bundled — restore it in one picker.",
    blurb="Desktop Manager is, first of all, a snapshot of a complete desktop: the Nordic / "
          "Nordic-bluish KDE Plasma 6 theme, the matching GTK/Qt styling, window decorations "
          "and KWin tiling scripts, the SDDM login screen, and Hyprland rices — bundled so a "
          "fresh machine can be made to look like this one from a single picker.",
    does=[
        "<b>KDE Plasma 6</b> (Wayland) — Nordic / Nordic-bluish look-and-feel, icons, cursors, Krohnkite tiling",
        "<b>SDDM login screens</b> — the White-Tiger theme, plus an optional Hello-Kitty theme",
        "<b>Hyprland rices</b> — Caelestia and end4 (illogical-impulse) sessions",
        "<b>macOS profile</b> — an optional WhiteSur / Monterey look, user-level, no sudo",
        "Terminal, shell and editor configs to match (Alacritty · Fish/Zsh · Micro)",
    ],
    deps="Theme restore targets KDE Plasma 6 and Hyprland on Arch / CachyOS. The SDDM stage needs sudo.",
    install=[
        "git clone https://github.com/janszafranski/desktop-manager.git ~/system-replica",
        "cd ~/system-replica",
        "./scripts/install.sh --dry-run   # preview everything, change nothing",
        "./scripts/install.sh             # packages + files + sddm + services",
    ],
    source=REPO,
)


# --------------------------------------------------------------- styling ----
CSS = """
:root {
  color-scheme: light dark;
  --bg: #ffffff; --fg: #1b1d1f; --mute: #5c6368;
  --line: #e2e5e8; --card: #f6f8fa; --accent: #3c6694; --accent-soft: #e7eef6;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #14181c; --fg: #e8eaec; --mute: #9aa3a9;
          --line: #262c32; --card: #1b2127; --accent: #88c0d0; --accent-soft: #1d2a33; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.6
       system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", sans-serif; }
.wrap { max-width: 1120px; margin: 0 auto; padding: 0 24px 72px; }
header.top { border-bottom: 1px solid var(--line); margin-bottom: 40px;
             background: linear-gradient(180deg, var(--accent-soft), transparent); }
header.top .wrap { padding-top: 30px; padding-bottom: 26px; }
h1 { font-size: 2.1rem; margin: 0 0 .2em; letter-spacing: -.01em; }
h2 { font-size: 1.4rem; margin: 2.4em 0 .6em; }
h3 { font-size: 1.05rem; margin: 0 0 .3em; }
a { color: var(--accent); }
p { max-width: 70ch; }
.lede { font-size: 1.12rem; color: var(--fg); }
.mute { color: var(--mute); }
.small { font-size: .88rem; }
nav.crumbs { font-size: .9rem; margin-bottom: 1rem; }
ul { max-width: 70ch; }
img.shot { width: 100%; border: 1px solid var(--line); border-radius: 10px;
           display: block; margin: 1.5rem 0; }
pre { background: var(--card); border: 1px solid var(--line); border-radius: 8px;
      padding: 14px 16px; overflow-x: auto; font-size: .9rem; }
code { font-family: ui-monospace, "JetBrains Mono", Menlo, monospace; font-size: .92em; }
.cards { display: grid; gap: 22px; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }
.card { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: var(--card);
        display: flex; flex-direction: column; text-decoration: none; color: inherit;
        transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease; }
.card:hover { transform: translateY(-3px); box-shadow: 0 16px 34px -22px rgba(20,30,45,.55);
              border-color: var(--accent); }
.card .thumb { aspect-ratio: 16 / 10; background: #0e1620; display: block; }
.card .thumb img { width: 100%; height: 100%; object-fit: cover; object-position: top center; display: block; }
.card .noimg { aspect-ratio: 16 / 10; display: grid; place-items: center;
               background: var(--accent-soft); color: var(--accent); font-size: 2.2rem; }
.card .body { padding: 14px 16px 16px; }
.card .name { font-weight: 600; font-size: 1.08rem; }
.card .kind { color: var(--mute); font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; }
.card .tag { color: var(--mute); font-size: .92rem; margin-top: .35em; }
.card.lead { grid-column: 1 / -1; flex-direction: row; }
.card.lead .thumb { flex: 1 1 56%; aspect-ratio: auto; }
.card.lead .body { flex: 1 1 44%; align-self: center; padding: 24px 26px; }
.card.lead .name { font-size: 1.5rem; letter-spacing: -.01em; }
.card.lead .tag { font-size: 1rem; margin-top: .5em; }
.ribbon { display: inline-block; font-size: .7rem; letter-spacing: .14em; text-transform: uppercase;
          color: #fff; background: var(--accent); padding: 3px 9px; border-radius: 20px; margin-bottom: .6em;
          font-family: ui-monospace, Menlo, monospace; }
@media (prefers-color-scheme: dark) { .ribbon { color: #10161b; } }
@media (max-width: 680px) { .card.lead { flex-direction: column; } .card.lead .thumb { aspect-ratio: 16 / 10; } }
footer { border-top: 1px solid var(--line); margin-top: 56px; padding-top: 20px;
         color: var(--mute); font-size: .88rem; }
.crosslink { border: 1px solid var(--line); border-left: 4px solid var(--accent); border-radius: 10px;
             background: var(--card); padding: 18px 20px; margin: 2em 0; }
.crosslink h3 { margin-top: 0; }
"""


# --------------------------------------------------------------- render  ----
import json


def head(title: str, desc: str, slug: str, og_image: str, jsonld: str = "") -> str:
    """The full <head>: unique title/description, canonical, Open Graph, Twitter,
    favicon and optional JSON-LD structured data."""
    canonical = BASE + ("" if slug == "index.html" else slug)
    og_abs = BASE + og_image
    e = html.escape
    tags = [
        f'<title>{e(title)}</title>',
        f'<meta name="description" content="{e(desc)}">',
        '<meta name="robots" content="index, follow">',
        f'<meta name="author" content="{e(AUTHOR)}">',
        f'<link rel="canonical" href="{e(canonical)}">',
        '<meta name="theme-color" content="#3c6694">',
        '<link rel="icon" href="assets/icon.svg" type="image/svg+xml">',
        '<link rel="icon" href="assets/icon.png" sizes="any">',
        '<link rel="apple-touch-icon" href="assets/icon.png">',
        '<link rel="stylesheet" href="style.css">',
        # Open Graph
        '<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{e(SITE)}">',
        f'<meta property="og:title" content="{e(title)}">',
        f'<meta property="og:description" content="{e(desc)}">',
        f'<meta property="og:url" content="{e(canonical)}">',
        f'<meta property="og:image" content="{e(og_abs)}">',
        '<meta property="og:locale" content="en_GB">',
        # Twitter
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{e(title)}">',
        f'<meta name="twitter:description" content="{e(desc)}">',
        f'<meta name="twitter:image" content="{e(og_abs)}">',
    ]
    if jsonld:
        tags.append(f'<script type="application/ld+json">{jsonld}</script>')
    return "\n".join(tags)


def jsonld_app(t: dict, url: str, img_abs: str | None) -> str:
    data = {
        "@context": "https://schema.org", "@type": "SoftwareApplication",
        "name": t["name"], "description": DESC.get(t["key"], t["tag"]),
        "applicationCategory": CATEGORY.get(t["key"], "UtilitiesApplication"),
        "operatingSystem": "Linux", "url": url,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        "author": {"@type": "Person", "name": AUTHOR},
        "isAccessibleForFree": True,
    }
    if img_abs:
        data["screenshot"] = img_abs
    return json.dumps(data, ensure_ascii=False)


def jsonld_site() -> str:
    data = {
        "@context": "https://schema.org", "@type": "WebSite",
        "name": SITE, "url": BASE, "description": DESC["index"],
        "author": {"@type": "Person", "name": AUTHOR},
    }
    return json.dumps(data, ensure_ascii=False)


def page(title: str, body: str, *, desc: str, slug: str,
         og_image: str = OG_DEFAULT, jsonld: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en-GB">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{head(title, desc, slug, og_image, jsonld)}
<header class="top"><div class="wrap">
<h1><a href="index.html" style="color:inherit;text-decoration:none">{SITE}</a></h1>
<p class="mute" style="margin:0">{TAGLINE}</p>
</div></header>
<div class="wrap">
{body}
<footer>Built from the source in
<a href="{REPO}">janszafranski/desktop-manager</a> on {TODAY}.
Part of the <a href="{SUITE}">just a&hellip;</a> family.</footer>
</div>
</html>
"""


def install_block(t: dict) -> str:
    out = ["<h2>Install</h2>"]
    if t.get("deps"):
        out.append(f'<p class="small mute">{t["deps"]}</p>')
    out.append("<pre><code>" + "\n".join(html.escape(c) for c in t["install"]) + "</code></pre>")
    out.append('<p class="small mute">Prefer clicking? Everything here also installs from '
               '<b>Desktop Manager &rsaquo; Apps</b>. Each tool has an '
               '<code>uninstall.sh</code> beside its installer.</p>')
    if t.get("source"):
        out.append(f'<p class="small mute">Source: <a href="{t["source"]}">{html.escape(t["source"])}</a></p>')
    return "\n".join(out)


def detail_page(t: dict, shots: dict) -> str:
    does = "".join(f"<li>{d}</li>" for d in t["does"])
    body = [f'<nav class="crumbs mute"><a href="index.html">{SITE}</a> &rsaquo; {html.escape(t["name"])}</nav>',
            f'<h2 style="margin-top:0">{html.escape(t["name"])}</h2>']
    if shots.get(t["key"]):
        body.append(f'<img class="shot" src="{shots[t["key"]]}" alt="{html.escape(t["name"])}">')
    body.append(f'<p class="lede">{t["blurb"]}</p>')
    body.append(f"<h2>What it does</h2><ul>{does}</ul>")
    body.append(install_block(t))
    body.append('<p class="small mute"><a href="index.html">&lsaquo; Back to Desktop Manager</a></p>')
    slug = f'{t["key"]}.html'
    og = shots.get(t["key"], OG_DEFAULT)
    img_abs = (BASE + shots[t["key"]]) if shots.get(t["key"]) else None
    return page(f'{t["name"]} · {SITE}', "\n".join(body),
                desc=DESC.get(t["key"], t["tag"]), slug=slug, og_image=og,
                jsonld=jsonld_app(t, BASE + slug, img_abs))


def card(t: dict, shots: dict) -> str:
    href = f'{t["key"]}.html'
    if shots.get(t["key"]):
        thumb = f'<span class="thumb"><img src="{shots[t["key"]]}" alt="{html.escape(t["name"])}"></span>'
    else:
        thumb = '<span class="noimg">\U0001F3A4</span>'
    lead = " lead" if t.get("lead") else ""
    ribbon = '<span class="ribbon">Start here</span>' if t.get("lead") else ""
    kind = html.escape(t.get("kind", "utility"))
    return (f'<a class="card{lead}" href="{href}">{thumb}'
            f'<span class="body">{ribbon}<span class="kind">{kind}</span>'
            f'<div class="name">{html.escape(t["name"])}</div>'
            f'<div class="tag">{t["tag"]}</div></span></a>')


def build():
    ASSETS.mkdir(parents=True, exist_ok=True)
    (DOCS / "style.css").write_text(CSS)

    # Favicon + default Open Graph / Twitter share image.
    shutil.copy2(ROOT / "icon.svg", ASSETS / "icon.svg")
    place("icon.png", "icon.png", maxw=256)
    place("assets/social-preview.png", "og-default.png", maxw=1200)

    # Copy screenshots, record the asset paths actually written.
    shots: dict[str, str] = {}
    for t in TOOLS + [THEMES]:
        if t.get("src"):
            shots[t["key"]] = place(t["src"], t["shot"],
                                    1400 if t["key"] in ("themes",) else 1100)

    # Detail pages
    for t in TOOLS + [THEMES]:
        (DOCS / f'{t["key"]}.html').write_text(detail_page(t, shots))

    # Index / container page
    lead = next(t for t in TOOLS if t.get("lead"))
    rest = [t for t in TOOLS if not t.get("lead")]
    cards = card(lead, shots) + "".join(card(t, shots) for t in rest)

    body = f"""
<p class="lede">{SITE} keeps a whole Linux desktop in one place. It is a snapshot of this
machine&rsquo;s look and configuration &mdash; themes, login screen, window rules, shell and
editor &mdash; with a one-click picker to restore it on a fresh install. Below it are the small,
single-purpose tools it can install for you.</p>

<img class="shot" src="{shots['desktop-manager']}" alt="The Desktop Manager picker">

<h2>What it installs</h2>
<div class="cards">
{cards}
</div>

<h2 style="margin-top:2.2em">The desktop itself</h2>
<p>Before any of the tools, Desktop Manager restores the <b>look</b>: the KDE Plasma theme, the
SDDM login screen, Hyprland rices and the configs to match &mdash; in stages, with a dry-run so
you can see what it will do before it does anything.</p>
<a class="card lead" href="themes.html" style="margin:1.2em 0">
<span class="thumb"><img src="{shots['themes']}" alt="The restored desktop"></span>
<span class="body"><span class="kind">themes &amp; rices</span>
<div class="name">{THEMES['name']}</div>
<div class="tag">{THEMES['tag']}</div></span></a>

<div class="crosslink">
<h3>Looking for the creative apps?</h3>
<p style="margin-bottom:.4em">Desktop Manager also installs <b>just a&hellip; CREATORsuite</b> &mdash;
ground-up recreations of the Serif creative line (WEBcreator, PAGEdesigner, PAINTcanvas,
DRAWmaster). They live in their own project.</p>
<p class="small" style="margin:0"><a href="{SUITE}welcome.html">See the whole family on one page &rsaquo;</a>
&nbsp;&middot;&nbsp; <a href="{SUITE}">Browse the Creative suite &rsaquo;</a></p>
</div>

<h2>Restore a whole machine</h2>
<p class="small mute">On a fresh Arch / CachyOS install, clone once and run the installer &mdash;
<code>--dry-run</code> first to preview, then for real. Individual stages
(<code>files</code>, <code>packages</code>, <code>services</code>, <code>sddm</code>) can be run
on their own; only <code>sddm</code> needs sudo.</p>
<pre><code>git clone https://github.com/janszafranski/desktop-manager.git ~/system-replica
cd ~/system-replica
./scripts/install.sh --dry-run   # preview everything, change nothing
./scripts/install.sh             # packages + files + sddm + services
./scripts/install-launcher.sh    # add "Desktop Manager" to your app menu</code></pre>
"""
    (DOCS / "index.html").write_text(page(
        f"{SITE} — save, restore & re-theme your Linux desktop", body,
        desc=DESC["index"], slug="index.html",
        og_image=shots.get("desktop-manager", OG_DEFAULT), jsonld=jsonld_site()))

    # sitemap.xml + robots.txt
    pages = sorted(p.name for p in DOCS.glob("*.html"))
    urls = "".join(
        f"  <url><loc>{BASE}{'' if p == 'index.html' else p}</loc>"
        f"<lastmod>{TODAY}</lastmod>"
        f"<priority>{'1.0' if p == 'index.html' else '0.7'}</priority></url>\n"
        for p in pages)
    (DOCS / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}</urlset>\n")
    (DOCS / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {BASE}sitemap.xml\n")

    print(f"docs/ built with Pillow={HAVE_PIL}:")
    for p in pages:
        print("  ", p)
    print("  +", "sitemap.xml, robots.txt")
    print("  assets:", ", ".join(sorted(f.name for f in ASSETS.iterdir())))


if __name__ == "__main__":
    build()
