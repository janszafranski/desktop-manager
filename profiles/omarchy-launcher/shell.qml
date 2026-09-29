// omarchy-launcher — an Omarchy-style categorised app launcher for Caelestia / Hyprland.
//
// Runs as its OWN Quickshell instance (`qs -c omarchy-launcher`) rather than as a patch to
// caelestia-shell, because caelestia-shell is a pacman package living in /etc/xdg/quickshell
// — any edit there is destroyed by the next `pacman -Syu`. This config only *reads* Caelestia's
// generated colour scheme (~/.local/state/caelestia/scheme.json), so it tracks the system theme
// live (wallpaper recolour, blacken.sh, light/dark) without being coupled to the package.
//
// Chrome follows the Omarchy launcher: one narrow portrait column, one line per row, tight
// rows, a selection pill barely lighter than the card, no footer.
//
// Categories are NOT a second pane and NOT a separate menu you have to summon. They are the
// first few rows of the one list, drawn as folders with a chevron; opening one swaps the rows
// under the same search line for that category's apps, inside the same popup. That is Omarchy's
// root-menu pattern. The default category (Favourites) gets no folder of its own — its apps
// *are* the rest of the root list, under a hairline.
//
//   root        Home › Work › Church › … then the Favourites apps
//   a folder    that category's apps; Backspace / ← / Esc walks back out to root
//
// Toggle over IPC:   qs -c omarchy-launcher ipc call launcher toggle
// Wrapper (starts the daemon on first use):   omarchy-launcher
//
// Categories are user data, not code: ~/.config/omarchy-launcher/categories.json
// The file is watched, so edits appear on the next open — no restart needed.

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Widgets

ShellRoot {
    id: root

    // ------------------------------------------------------------------ state
    property bool shown: false
    property string query: ""
    property string focusedScreen: ""

    // Which level the single column is showing.
    //   "root"  folders first, then the default category's apps
    //   "cat"   one category's apps, drilled into from a folder row
    property string view: "root"

    // Index into `cats` of the drilled-into category; -1 while at root.
    property int catIndex: -1

    // Selected row of whatever `rows` currently holds.
    property int index: 0

    // categories.json contents
    property var cats: []
    property string defaultCategoryId: ""
    property string configError: ""

    // ------------------------------------------------------------------ theme
    // Caelestia regenerates scheme.json from the wallpaper; watching it keeps us in lockstep.
    property var scheme: ({})
    readonly property bool lightMode: (scheme.mode ?? "dark") === "light"

    function c(name, fallback) {
        const cols = scheme.colours;
        if (cols && cols[name])
            return "#" + cols[name];
        return fallback;
    }

    readonly property color colBg: c("surfaceContainer", lightMode ? "#f2eff5" : "#0d0d0d")
    readonly property color colText: c("onSurface", lightMode ? "#1c1b1f" : "#e5e1e7")
    readonly property color colSubtle: c("outline", lightMode ? "#77767f" : "#918f9a")
    readonly property color colAccent: c("primary", lightMode ? "#595992" : "#c2c1ff")
    readonly property color colOnAccent: c("onPrimary", lightMode ? "#ffffff" : "#2a2a60")
    readonly property color colError: c("error", "#ffb4ab")

    // ------------------------------------------------------- appearance knobs
    // The selection pill is a *whisper* — measured off the reference at +13/255 per channel over
    // the card, about a 7.5% text-coloured wash — and the card border is a half-opacity outline.
    // Both used to be hard-coded numbers. They are user data now (appearance.json, written by the
    // App List Config popup), so the highlight and the faint outline can be re-pointed at any
    // colour in the live scheme without editing QML. The defaults below reproduce the original
    // look, so an absent or unreadable file changes nothing.
    readonly property var appDefaults: ({
            highlight: {
                source: "text",
                strength: 0.075,
                custom: ""
            },
            outline: {
                source: "outline",
                strength: 0.5,
                custom: ""
            }
        })
    // What is on disk, and what App List Config is currently proposing. Reading through the draft
    // while the popup is up is what makes the colour controls a live preview: the launcher behind
    // the popup — and the popup itself — repaint as the sliders move, and closing without saving
    // drops straight back to the saved values with nothing to undo.
    property var savedAppearance: appDefaults
    property var draftAppearance: appDefaults
    readonly property var appearance: configShown ? draftAppearance : savedAppearance

    function appPart(which) {
        const p = (appearance ?? {})[which] ?? {};
        const d = appDefaults[which];
        const s = p.strength;
        return {
            source: p.source ?? d.source,
            strength: (typeof s === "number" && isFinite(s)) ? Math.max(0, Math.min(1, s)) : d.strength,
            custom: p.custom ?? d.custom
        };
    }

    // "Match the desktop theme" is the default rather than an option you have to go and find:
    // every source except `custom` is read live out of Caelestia's scheme, so a wallpaper
    // recolour or a light/dark flip moves the highlight and the outline with it.
    function sourceColour(src, custom) {
        if (src === "custom" && /^#[0-9a-fA-F]{6}$/.test(String(custom ?? "").trim()))
            return String(custom).trim();
        switch (src) {
        case "accent":
            return colAccent;
        case "outline":
            return colSubtle;
        case "surface":
            return c("surfaceContainerHighest", colSubtle);
        default:
            return colText;
        }
    }

    readonly property var hlPart: appPart("highlight")
    readonly property var outPart: appPart("outline")
    readonly property color hlBase: sourceColour(hlPart.source, hlPart.custom)
    readonly property color outBase: sourceColour(outPart.source, outPart.custom)

    // A wash over the card, not an opaque fill, so the pill stays subtle at low strengths in both
    // light and dark. Hover is a fixed fraction of the selection — the ratio the two hard-coded
    // values used to have (0.04 / 0.075) — so tuning one keeps the pair in proportion.
    readonly property color colSel: Qt.tint(colBg, Qt.rgba(hlBase.r, hlBase.g, hlBase.b, hlPart.strength))
    readonly property color colHover: Qt.tint(colBg, Qt.rgba(hlBase.r, hlBase.g, hlBase.b, hlPart.strength * 0.53))
    readonly property color colBorder: Qt.rgba(outBase.r, outBase.g, outBase.b, outPart.strength)

    // Caelestia ships Google Sans Flex inside its package; use it when present so the launcher
    // is typographically identical to the rest of the shell, else fall back to the system sans.
    FontLoader {
        id: gsf
        source: "file:///etc/xdg/quickshell/caelestia/assets/google-sans-flex/GoogleSansFlex-VariableFont_GRAD%2CROND%2Copsz%2Cslnt%2Cwdth%2Cwght.ttf"
    }
    readonly property string uiFont: gsf.status === FontLoader.Ready ? gsf.name : "Noto Sans"
    readonly property string iconFont: "Material Symbols Rounded"

    FileView {
        id: schemeFile
        path: Quickshell.env("HOME") + "/.local/state/caelestia/scheme.json"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try {
                root.scheme = JSON.parse(text());
            } catch (e) {
                root.scheme = ({});
            }
        }
    }

    // Written by App List Config. Watched like the scheme and the categories, so accepting a
    // change in the popup repaints the launcher behind it without a restart.
    FileView {
        id: apprFile
        path: Quickshell.env("HOME") + "/.config/omarchy-launcher/appearance.json"
        printErrors: false
        watchChanges: true
        onFileChanged: reload()
        onLoadFailed: root.savedAppearance = root.appDefaults
        onLoaded: {
            try {
                const cfg = JSON.parse(text());
                root.savedAppearance = {
                    highlight: cfg.highlight ?? root.appDefaults.highlight,
                    outline: cfg.outline ?? root.appDefaults.outline
                };
            } catch (e) {
                root.savedAppearance = root.appDefaults;
            }
        }
    }

    // ------------------------------------------------------------- categories
    FileView {
        id: catsFile
        path: Quickshell.env("HOME") + "/.config/omarchy-launcher/categories.json"
        watchChanges: true
        onFileChanged: reload()
        onLoadFailed: {
            root.configError = "Could not read ~/.config/omarchy-launcher/categories.json";
            root.cats = [];
        }
        onLoaded: {
            try {
                const cfg = JSON.parse(text());
                const list = (cfg.categories ?? []).filter(x => x && x.id && x.name);
                if (list.length === 0)
                    throw new Error("no categories defined");
                root.defaultCategoryId = cfg.defaultCategory ?? list[0].id;
                root.cats = list;
                // Keep the hand-written header comment and the schema version so that saving from
                // the config popup rewrites the lists without eating the file's own documentation.
                root.catsPreamble = {
                    _readme: cfg._readme,
                    version: cfg.version
                };
                root.configError = "";
                root.goRoot();
            } catch (e) {
                root.configError = "categories.json is not valid: " + e;
                root.cats = [];
            }
        }
    }

    property var catsPreamble: ({})

    // Which folder carries the pinned "App List Config" row. It is a flag in the data
    // (`"configEntry": true`) rather than a hard-coded id, so renaming or moving the settings
    // category doesn't strand the entry point; the id fallbacks below only matter for a config
    // written before this flag existed.
    readonly property var settingsCat: cats.find(x => x.configEntry === true) ?? cats.find(x => x.id === "settings") ?? cats.find(x => x.id === "system") ?? null

    // The one synthetic row in the launcher: it opens a window instead of an app.
    readonly property var configRow: ({
            kind: "action",
            id: "config",
            name: "App List Config",
            icon: "tune"
        })

    // The folders shown at the top of root. The default category is deliberately absent — it has
    // no folder because you are already standing inside it.
    readonly property var folderCats: cats.filter(x => x.id !== defaultCategoryId)
    readonly property var defaultCat: cats.find(x => x.id === defaultCategoryId) ?? (cats.length > 0 ? cats[0] : null)

    // ------------------------------------------------------------------- apps
    readonly property var allApps: {
        const out = (DesktopEntries.applications?.values ?? []).filter(a => a && a.name && a.noDisplay !== true);
        out.sort((a, b) => a.name.localeCompare(b.name, undefined, {
            sensitivity: "base"
        }));
        return out;
    }

    // Desktop ids are matched case-insensitively (and with a stray ".desktop" tolerated) so a
    // hand-written categories.json doesn't silently drop entries over "Zoom" vs "zoom".
    readonly property var appsById: {
        const m = ({});
        for (const a of allApps)
            m[a.id.toLowerCase()] = a;
        return m;
    }

    function appById(id) {
        if (!id)
            return null;
        const k = String(id).toLowerCase();
        if (appsById[k])
            return appsById[k];
        // Only fall back to stripping ".desktop" if the literal id missed — plenty of real ids
        // genuinely end in it (org.telegram.desktop, com.bitwarden.desktop).
        if (k.endsWith(".desktop"))
            return appsById[k.slice(0, -8)] ?? null;
        return null;
    }

    // Apps belonging to a category, in a deliberate order:
    //   explicit `apps` ids first (config order — this is the user's own ranking),
    //   then anything matched by `xdgCategories`, alphabetically.
    function appsFor(cat) {
        if (!cat)
            return [];
        if (cat.all === true)
            return allApps;

        const seen = ({});
        const out = [];
        const exclude = (cat.exclude ?? []).map(x => String(x).toLowerCase());

        for (const id of (cat.apps ?? [])) {
            const a = appById(id);
            if (a && !seen[a.id] && exclude.indexOf(a.id.toLowerCase()) < 0) {
                seen[a.id] = true;
                out.push(a);
            }
        }

        const xdg = cat.xdgCategories ?? [];
        if (xdg.length > 0) {
            for (const a of allApps) {
                if (seen[a.id] || exclude.indexOf(a.id.toLowerCase()) >= 0)
                    continue;
                const acats = a.categories ?? [];
                for (const want of xdg) {
                    if (acats.indexOf(want) >= 0) {
                        seen[a.id] = true;
                        out.push(a);
                        break;
                    }
                }
            }
        }

        return out;
    }

    readonly property var currentCat: (catIndex >= 0 && catIndex < cats.length) ? cats[catIndex] : null
    readonly property var catApps: appsFor(currentCat)
    readonly property var rootApps: appsFor(defaultCat)

    // Computed once per (cats, allApps) change instead of once per delegate per repaint —
    // appsFor() is a full scan of every desktop entry.
    readonly property var catCounts: {
        const m = ({});
        for (const x of cats)
            m[x.id] = appsFor(x).length;
        return m;
    }

    // Root-level search ranks every installed app, but nudges the default category's own apps up
    // so "sig" still lands on your Signal ahead of anything that merely contains those letters.
    readonly property var rootBoost: {
        const m = ({});
        for (const a of rootApps)
            m[a.id] = true;
        return m;
    }

    // ----------------------------------------------------------------- search
    // Small self-contained fuzzy scorer: prefix > word-start > substring > subsequence.
    // Returns -1 for no match. Keeps the launcher dependency-free.
    //
    // `fuzzy` is only enabled for the app *name*. Letting a subsequence match run over the
    // description turns every long comment into a match for any short query (searching "kate"
    // hit WhatSie via "...using the Qt framewor[k]..."), which both buries the real result and
    // stops the all-apps fallback from ever kicking in. Descriptions are substring-only.
    function scoreText(text, q, fuzzy) {
        if (!text)
            return -1;
        const t = text.toLowerCase();
        const i = t.indexOf(q);
        if (i === 0)
            return 1000 - t.length;
        if (i > 0)
            return ((" ./-_".indexOf(t[i - 1]) >= 0) ? 800 : 620) - t.length;
        if (!fuzzy)
            return -1;

        let pos = 0;
        let run = 0;
        let score = 0;
        for (let k = 0; k < q.length; k++) {
            const p = t.indexOf(q[k], pos);
            if (p < 0)
                return -1;
            run = (p === pos && k > 0) ? run + 1 : 0;
            score += 3 + run * 2 + ((p === 0 || " ./-_".indexOf(t[p - 1]) >= 0) ? 4 : 0);
            pos = p + 1;
        }
        return 300 + score - t.length * 0.2;
    }

    function scoreApp(app, q) {
        let best = scoreText(app.name, q, true);
        const gn = scoreText(app.genericName, q, false);
        if (gn >= 0)
            best = Math.max(best, gn - 120);
        const id = scoreText(app.id, q, false);
        if (id >= 0)
            best = Math.max(best, id - 180);
        const cm = scoreText(app.comment, q, false);
        if (cm >= 0)
            best = Math.max(best, cm - 260);
        for (const kw of (app.keywords ?? [])) {
            const k = scoreText(kw, q, false);
            if (k >= 0)
                best = Math.max(best, k - 150);
        }
        return best;
    }

    // `boost` is an optional id→true map whose members are lifted by roughly one tier.
    function filterApps(list, q, boost) {
        if (!q)
            return list;
        const scored = [];
        for (const a of list) {
            let s = scoreApp(a, q);
            if (s < 0)
                continue;
            if (boost && boost[a.id])
                s += 140;
            scored.push({
                a,
                s
            });
        }
        scored.sort((x, y) => y.s - x.s || x.a.name.localeCompare(y.a.name));
        return scored.map(x => x.a);
    }

    readonly property string trimmedQuery: query.trim().toLowerCase()

    // A search inside a folder that finds nothing widens to every app rather than showing a dead
    // end — the common case is "I typed a name that lives in another category".
    readonly property bool widened: view === "cat" && trimmedQuery.length > 0 && currentCat?.all !== true && filterApps(catApps, trimmedQuery).length === 0

    // ------------------------------------------------------------------- rows
    // The one model behind the one column. Every entry is either
    //   { kind: "folder", cat }   a nested category — opens in place, does not launch
    //   { kind: "app",    app }   a launchable desktop entry
    // `gap` marks the first row after the folder block, which draws the hairline.
    // "App List Config" answers to more than its own name — the words people actually reach for
    // when they want to change what is in the launcher.
    readonly property var configKeywords: ["app list config", "app list", "config", "configure", "settings", "preferences", "edit apps", "favourites", "favorites", "categories", "launcher settings", "customise", "customize", "colours", "colors"]

    // Substring, never fuzzy. "App List Config" is a long name, so a subsequence match makes it
    // answer to almost any short query — "sig" hits it through app li[s]t conf[i]... [g] — and it
    // would then sit above Signal holding the default selection. Matching here has to be
    // deliberate, because this row does not launch an app.
    function configMatches(q) {
        if (!q)
            return false;
        for (const k of configKeywords)
            if (k.indexOf(q) === 0)
                return true;
        return scoreText(configRow.name, q, false) >= 0;
    }

    readonly property var rows: {
        const q = trimmedQuery;

        if (view === "cat") {
            const inCat = filterApps(catApps, q);
            const use = (q.length > 0 && inCat.length === 0 && currentCat?.all !== true) ? filterApps(allApps, q) : inCat;
            const catOut = use.map(a => ({
                kind: "app",
                app: a
            }));

            // Pinned to the top of the settings folder, above its apps and under its own
            // hairline — it stays put while you type rather than being filtered away, because
            // it is the door out of the launcher and not one more search result.
            if (settingsCat && currentCat && currentCat.id === settingsCat.id) {
                if (catOut.length > 0)
                    catOut[0] = Object.assign({}, catOut[0], {
                        gap: true
                    });
                return [configRow].concat(catOut);
            }
            return catOut;
        }

        // Root: the folders, then the default category's apps. Typing filters the folders by
        // name and searches every installed app, so nothing is more than one query away.
        const folders = q ? folderCats.filter(x => scoreText(x.name, q, true) >= 0) : folderCats;
        const apps = q ? filterApps(allApps, q, rootBoost) : rootApps;

        const out = folders.map(x => ({
            kind: "folder",
            cat: x
        }));
        for (let i = 0; i < apps.length; i++)
            out.push({
                kind: "app",
                app: apps[i],
                gap: i === 0 && folders.length > 0
            });

        // From root the config is reachable by name too, so you never have to remember that it
        // lives inside System. Only while searching — an unsearched root stays exactly as it was.
        //
        // It trails the apps here rather than leading them, under its own hairline. Leading looks
        // tidier but means "con" puts it on the default selection, and Enter opens a settings
        // window instead of Konsole. Inside the settings folder it is pinned to the top, because
        // there it *is* the thing you came for; at root it is only a shortcut, and a shortcut
        // that hijacks Return is a trap.
        if (configMatches(q))
            out.push(Object.assign({}, configRow, {
                gap: out.length > 0
            }));
        return out;
    }

    onRowsChanged: index = 0

    // ------------------------------------------------------------------ verbs
    function open() {
        query = "";
        goRoot();

        // Resolve the focused monitor before mapping the window. A stale probe (hyprctl wedged,
        // or a previous open that never finished) used to swallow the assignment and leave the
        // launcher permanently unopenable, so cancel any in-flight probe and arm a fallback that
        // maps the window anyway if the answer doesn't arrive promptly.
        if (focusProc.running)
            focusProc.running = false;
        focusProc.running = true;
        openFallback.restart();
    }

    Timer {
        id: openFallback
        interval: 300
        onTriggered: root.shown = true
    }

    function close() {
        shown = false;
        goRoot();
        // Each type-to-open burst numbers itself from 1, so the ordering window has to end with
        // the launcher — otherwise the next burst would look stale and be dropped entirely.
        lastSeedSeq = 0;
        pendingSeed = "";
    }

    function toggle() {
        if (shown)
            close();
        else
            open();
    }

    function launch(app) {
        if (!app)
            return;
        close();
        if (app.runInTerminal)
            Quickshell.execDetached(["alacritty", "-e"].concat(app.command ?? []));
        else
            app.execute();
    }

    // ---- the single-column drill: root <-> a folder --------------------------
    function goRoot() {
        query = "";
        view = "root";
        catIndex = -1;
        index = 0;
    }

    // Walking back out lands on the folder you came from rather than at the top, so browsing two
    // categories in a row is two keystrokes and not a re-scroll.
    function leaveCat() {
        const from = currentCat?.id ?? "";
        goRoot();
        if (!from)
            return;
        Qt.callLater(() => {
            const i = rows.findIndex(r => r.kind === "folder" && r.cat.id === from);
            if (i >= 0)
                index = i;
        });
    }

    function enterCat(cat) {
        if (!cat)
            return;
        const i = cats.findIndex(x => x.id === cat.id);
        if (i < 0)
            return;
        query = "";
        catIndex = i;
        view = "cat";
        index = 0;
    }

    function activate(row) {
        if (!row)
            return;
        if (row.kind === "folder")
            enterCat(row.cat);
        else if (row.kind === "action")
            openConfig();
        else
            launch(row.app);
    }

    function selectedRow() {
        const n = rows.length;
        return n > 0 ? rows[Math.max(0, Math.min(index, n - 1))] : null;
    }

    function activateSelected() {
        activate(selectedRow());
    }

    // ↑↓ / PgUp / PgDn drive the column.
    function step(delta) {
        const n = rows.length;
        if (n > 0)
            index = (index + delta + n) % n;
    }

    // Tab / Ctrl+←→ move between *categories*. Inside a folder it swaps to the next one; at root
    // it hops the selection down the folder block, so the same key means "next category" in both.
    function stepCat(delta) {
        const n = folderCats.length;
        if (n === 0)
            return;

        if (view === "cat") {
            const here = folderCats.findIndex(x => x.id === (currentCat?.id ?? ""));
            enterCat(folderCats[((here < 0 ? 0 : here) + delta + n) % n]);
            return;
        }

        const shown = rows.filter(r => r.kind === "folder").length;
        if (shown === 0)
            return;
        // Below the folder block, Tab means "back up to the first folder", not "wrap around".
        const at = index < shown ? index + delta : (delta > 0 ? 0 : shown - 1);
        index = (at + shown) % shown;
    }

    // Multi-monitor: map the popup on whichever monitor Hyprland says has focus.
    Process {
        id: focusProc
        command: ["hyprctl", "-j", "monitors"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const mons = JSON.parse(text);
                    const f = mons.find(m => m.focused);
                    root.focusedScreen = f ? f.name : "";
                } catch (e) {
                    root.focusedScreen = "";
                }
                root.shown = true;
            }
        }
        onExited: if (!root.shown)
            root.shown = true
    }

    IpcHandler {
        target: "launcher"

        function toggle(): void {
            root.toggle();
        }
        function open(): void {
            // Unconditional: re-opening an already-open launcher resets it to the default view,
            // which is also how it heals itself if `shown` ever gets out of step with the window.
            root.open();
        }
        function close(): void {
            root.close();
        }

        // Open straight into one folder, e.g. `ipc call launcher category media`. Now that
        // categories are folders rather than a hidden rail they are worth addressing directly —
        // bind Super+Alt+M to this and you land in Media with the search line already live.
        // An unknown id just opens at root rather than failing shut.
        function category(id: string): void {
            root.open();
            const cat = root.cats.find(x => x.id === id);
            if (cat && cat.id !== root.defaultCategoryId)
                root.enterCat(cat);
        }

        // The config popup is its own window, so it gets its own verbs — `omarchy-launcher config`
        // opens it without going through the launcher at all.
        function config(): void {
            root.openConfig();
        }

        // Type-to-open from the desktop: we open with the search already seeded, so the
        // keystrokes that summoned the launcher are not thrown away. `seq` orders a burst — see
        // typeOpen(). A hand-typed `omarchy-launcher type foo` passes no seq and always applies.
        function typed(text: string, seq: string): void {
            root.typeOpen(String(text ?? ""), parseInt(seq) || 0);
        }
    }

    // The character that summoned the launcher, waiting for the window to map. Mapping is
    // asynchronous (the monitor probe runs first) and the search field wipes itself on the way
    // in, so the seed has to be applied *after* that, not before.
    property string pendingSeed: ""
    property int lastSeedSeq: 0

    // Mapping takes a beat, and a fast typist gets three or four characters out before the window
    // is up — each one firing its own keybind, its own process and its own IPC call. Those
    // processes race: typing "conf" on the desktop really did arrive here as "cofn".
    //
    // So Hyprland does not send characters, it sends the whole buffer so far, tagged with a
    // sequence number, and a message that lost the race is dropped instead of being appended out
    // of order. The last one to arrive is always the most complete, which is why this replaces
    // rather than accumulates.
    function typeOpen(s, seq) {
        if (seq > 0 && seq <= lastSeedSeq)
            return;
        lastSeedSeq = Math.max(lastSeedSeq, seq);
        pendingSeed = s;
        if (shown)
            applySeed();      // already up: no map to wait for
        else
            open();           // applied by the field when `shown` flips
    }

    // Installed by the search field, so the root hands off rather than reaching into the window.
    property var applySeed: function () {}

    // ==================================================================================
    //  App List Config — the editor behind the pinned row
    // ==================================================================================
    // Everything the launcher shows is already data on disk; this popup is a front end for that
    // data rather than a second source of truth. It edits a *draft* copy and only touches disk on
    // Save, so a half-finished edit can be walked away from — and because both files are watched,
    // saving repaints the launcher without a restart.

    property bool configShown: false
    property var draft: []                // deep copy of `cats`, edited in place
    property string draftDefault: ""      // proposed defaultCategory
    property int dSel: 0                  // which category the editor is showing
    property int configTab: 0             // 0 = App lists, 1 = Appearance
    property string addQuery: ""
    property string configNote: ""
    property bool configNoteBad: false
    property bool dirty: false

    // Deleting a category is destructive in a way nothing else in this window is — every other
    // edit is a list membership you can put straight back. So the button arms first: it holds the
    // id it is armed for, and any move off that category disarms it.
    property string dArmed: ""
    property bool dIconOpen: false

    // Emitted when a freshly created category needs the caret: the field owns its own focus, the
    // model doesn't reach into the window to set it.
    signal focusCategoryName

    // Emitted whenever the category under the editor changes identity — selected, created,
    // deleted, reverted. The name and icon boxes are TextInputs, and typing into a TextInput
    // breaks its `text` binding, so they cannot be left to re-derive themselves. Watching `dSel`
    // is not enough: deleting the last category in the list, or reverting, leaves `dSel` where it
    // was while pointing at a different category.
    signal syncCategoryFields

    // QML doesn't see mutations inside an array or an object, so every edit re-seats both the
    // array *and* the category that was edited. Re-seating only the array is not enough: a shallow
    // slice leaves `draft[dSel]` pointing at the same object, so `dCat` re-evaluates to an
    // identical value, QML suppresses the change, and everything hanging off `dCat` — the member
    // list, the tick marks in the add column — silently keeps rendering the pre-edit state while
    // the counts (which read `draft`) move. That split is exactly the bug this shape prevents.
    function touchDraft() {
        if (dSel >= 0 && dSel < draft.length)
            draft[dSel] = Object.assign({}, draft[dSel]);
        draft = draft.slice();
        dirty = true;
        configNote = "";
    }

    function touchAppearance() {
        draftAppearance = Object.assign({}, draftAppearance);
        dirty = true;
        configNote = "";
    }

    function resetDraft() {
        draft = JSON.parse(JSON.stringify(cats));
        draftDefault = defaultCategoryId;
        // Seeded from the *normalised* values, so an appearance.json with a missing or nonsense
        // field opens showing what the launcher is actually rendering.
        draftAppearance = {
            highlight: appPart("highlight"),
            outline: appPart("outline")
        };
        dSel = 0;
        addQuery = "";
        configTab = 0;
        dirty = false;
        configNote = "";
        configNoteBad = false;
        dArmed = "";
        dIconOpen = false;
        syncCategoryFields();
    }

    // Clicking the dim area is one pixel away from clicking the card, so an unsaved draft is kept
    // rather than thrown away: reopening puts you back where you were, still unsaved, with the
    // footer still saying so. Revert is the way to discard, and it is spelled out on a button.
    function openConfig() {
        if (!dirty)
            resetDraft();
        close();              // one exclusive-keyboard layer at a time
        configShown = true;
    }

    function closeConfig() {
        configShown = false;
        addQuery = "";
        dArmed = "";
        dIconOpen = false;
    }

    // Every route to a different category goes through here, so an armed delete and a half-open
    // icon picker can't survive the move and fire on the wrong category.
    function dSelect(i) {
        dSel = i;
        addQuery = "";
        dArmed = "";
        dIconOpen = false;
        syncCategoryFields();
    }

    readonly property var dCat: (dSel >= 0 && dSel < draft.length) ? draft[dSel] : null

    function sameId(a, b) {
        return String(a).toLowerCase() === String(b).toLowerCase();
    }

    // Would this app reappear on its own the moment it left `apps`? If so, "remove" has to mean
    // "exclude" — otherwise the row would come straight back and the button would look broken.
    function autoMember(cat, appId) {
        const a = appById(appId);
        const xdg = cat?.xdgCategories ?? [];
        if (!a || xdg.length === 0)
            return false;
        const acats = a.categories ?? [];
        for (const want of xdg)
            if (acats.indexOf(want) >= 0)
                return true;
        return false;
    }

    // What the middle column shows: the category's apps, each tagged with where it came from.
    //   pinned   listed in `apps` — hand-ordered, so it can be moved and removed
    //   auto     pulled in by `xdgCategories` — removable (by exclusion), but not orderable
    // `pos` is the index in `cat.apps`, which is not the row number once an id fails to resolve.
    function draftMembers(cat) {
        if (!cat)
            return [];
        if (cat.all === true)
            return allApps.map(a => ({
                        app: a,
                        pinned: false,
                        pos: -1
                    }));

        const exclude = (cat.exclude ?? []).map(x => String(x).toLowerCase());
        const seen = ({});
        const out = [];
        const ids = cat.apps ?? [];

        for (let i = 0; i < ids.length; i++) {
            const a = appById(ids[i]);
            if (!a || seen[a.id] || exclude.indexOf(a.id.toLowerCase()) >= 0)
                continue;
            seen[a.id] = true;
            out.push({
                app: a,
                pinned: true,
                pos: i
            });
        }

        for (const a of allApps) {
            if (seen[a.id] || exclude.indexOf(a.id.toLowerCase()) >= 0)
                continue;
            if (autoMember(cat, a.id)) {
                seen[a.id] = true;
                out.push({
                    app: a,
                    pinned: false,
                    pos: -1
                });
            }
        }
        return out;
    }

    // Ids in `apps` that no longer resolve to anything installed. The launcher drops these
    // silently; the editor shows them so they can actually be cleaned up.
    function draftStale(cat) {
        if (!cat || cat.all === true)
            return [];
        const out = [];
        for (const id of (cat.apps ?? []))
            if (!appById(id))
                out.push(id);
        return out;
    }

    readonly property var dMembers: draftMembers(dCat)
    readonly property var dStale: draftStale(dCat)

    // Counts for the category column. Computed once per draft change rather than once per
    // delegate repaint — draftMembers() walks every installed desktop entry.
    readonly property var dCounts: {
        const m = ({});
        for (const x of draft)
            m[x.id] = draftMembers(x).length;
        return m;
    }

    readonly property var addList: filterApps(allApps, addQuery.trim().toLowerCase())

    // Positions in `cat.apps` of the pinned rows, in display order — the ladder the ↑/↓ buttons
    // climb, so a move always lands next to the neighbour you can see rather than next to an id
    // that failed to resolve.
    readonly property var dPinnedPos: dMembers.filter(m => m.pinned).map(m => m.pos)

    function dInCat(appId) {
        const cat = dCat;
        if (!cat)
            return false;
        if (cat.all === true)
            return true;
        if ((cat.exclude ?? []).some(x => sameId(x, appId)))
            return false;
        return (cat.apps ?? []).some(x => sameId(x, appId)) || autoMember(cat, appId);
    }

    function dAdd(appId) {
        const cat = dCat;
        if (!cat || cat.all === true)
            return;
        // Adding something that was explicitly excluded means un-excluding it first, or the add
        // would be silently cancelled by the exclusion.
        cat.exclude = (cat.exclude ?? []).filter(x => !sameId(x, appId));
        if (!(cat.apps ?? []).some(x => sameId(x, appId)))
            cat.apps = (cat.apps ?? []).concat([appId]);
        touchDraft();
    }

    function dRemove(appId) {
        const cat = dCat;
        if (!cat || cat.all === true)
            return;
        cat.apps = (cat.apps ?? []).filter(x => !sameId(x, appId));
        if (autoMember(cat, appId) && !(cat.exclude ?? []).some(x => sameId(x, appId)))
            cat.exclude = (cat.exclude ?? []).concat([appId]);
        touchDraft();
    }

    function dToggle(appId) {
        if (dInCat(appId))
            dRemove(appId);
        else
            dAdd(appId);
    }

    function dDropStale(rawId) {
        const cat = dCat;
        if (!cat)
            return;
        cat.apps = (cat.apps ?? []).filter(x => x !== rawId);
        touchDraft();
    }

    // `rank` is the row's place among the pinned rows, not its index in `apps`.
    function dMove(rank, delta) {
        const cat = dCat;
        const ladder = dPinnedPos;
        const to = rank + delta;
        if (!cat || rank < 0 || to < 0 || rank >= ladder.length || to >= ladder.length)
            return;
        const ids = (cat.apps ?? []).slice();
        const a = ladder[rank];
        const b = ladder[to];
        const t = ids[a];
        ids[a] = ids[b];
        ids[b] = t;
        cat.apps = ids;
        touchDraft();
    }

    function dMakeDefault(id) {
        if (!id || draftDefault === id)
            return;
        draftDefault = id;
        dirty = true;
        configNote = "";
    }

    // ------------------------------------------------- categories themselves
    // The lists inside a category were editable here from the start; the list *of* categories was
    // not, so a new folder still meant opening categories.json in a text editor. These four
    // functions close that gap — add, rename, re-icon, delete — while keeping the same draft-then-
    // Save contract as everything else in the window.

    // Ids are the file's internal keys: `defaultCategory` points at one, `dCounts` is keyed on one,
    // and `omarchy-launcher category <id>` is the thing people bind a key to. So a rename does not
    // re-slug an id that has already been saved — a category's label is allowed to drift from its
    // id rather than silently breaking a keybind. The one exception is below.
    function dNewId(name, selfId) {
        let base = String(name ?? "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
        if (!base)
            base = "category";
        let id = base;
        let n = 2;
        while (draft.some(c => c.id === id && c.id !== selfId))
            id = base + "-" + (n++);
        return id;
    }

    function dNewCategory() {
        // Inserted next to the category you were standing on rather than appended, because the
        // order of this list *is* the order of the folder rows in the launcher — a new "Games"
        // next to "Media" is almost always what was meant, and it saves a reorder.
        const at = (dSel >= 0 && dSel < draft.length) ? dSel + 1 : draft.length;
        const next = draft.slice();
        next.splice(at, 0, {
            // `_fresh` marks a category that has never been written, so its id is still free to
            // track the name being typed over the placeholder. Stripped at save; `cleanCat` only
            // copies the keys it knows, so it never reaches the file either way.
            _fresh: true,
            id: dNewId("New category"),
            name: "New category",
            icon: "folder",
            apps: []
        });
        draft = next;
        dSelect(at);
        dirty = true;
        configNoteBad = false;
        configNote = "New category — name it, then add apps from the right.";
        focusCategoryName();
    }

    // Stored raw and trimmed at save: trimming on every keystroke would eat the space you just
    // typed in the middle of "Home Office" as the field re-syncs.
    function dRename(name) {
        const cat = dCat;
        if (!cat || cat.name === name)
            return;
        cat.name = name;
        // A category that has never been saved has nothing pointing at its id yet, so it can keep
        // one derived from the name — otherwise every category made here would be stuck with
        // `new-category`, which is what `omarchy-launcher category …` and the file would show.
        if (cat._fresh === true) {
            const nid = dNewId(name, cat.id);
            if (draftDefault === cat.id)
                draftDefault = nid;
            cat.id = nid;
        }
        touchDraft();
    }

    function dSetIcon(icon) {
        const cat = dCat;
        if (!cat || cat.icon === icon)
            return;
        cat.icon = icon;
        touchDraft();
    }

    // Deleting is guarded, not forbidden. The two things a delete could genuinely break — the
    // launcher's opening view, and the row that opens this window — are re-pointed at a surviving
    // category instead of making those two categories undeletable, and the footer names whoever
    // took them over. The only hard stop is the last category, because a launcher with no
    // categories has nothing to draw.
    function dDeleteCategory() {
        const gone = dCat;
        if (!gone || draft.length <= 1)
            return;

        const next = draft.filter((c, i) => i !== dSel);
        const moved = [];

        if (draftDefault === gone.id) {
            draftDefault = next[0].id;
            moved.push("opening view → " + (next[0].name || next[0].id));
        }

        if (gone.configEntry === true) {
            // Prefer a category that still gets a folder row: the default has no folder of its
            // own, so pinning App List Config there would strand it loose in the root list.
            const host = next.find(c => c.id !== draftDefault && c.all !== true) ?? next.find(c => c.all !== true) ?? next[0];
            host.configEntry = true;
            moved.push("App List Config → " + (host.name || host.id));
        }

        draft = next;
        dSelect(Math.max(0, Math.min(dSel, next.length - 1)));
        dirty = true;
        configNoteBad = false;
        configNote = "Deleted " + (gone.name || gone.id) + (moved.length > 0 ? " (" + moved.join(", ") + ")" : "") + " — not written until you save.";
    }

    // Offered for the icon picker. Material Symbols Rounded is the launcher's icon font, so any
    // name from fonts.google.com/icons works — these are just the ones a category is likely to
    // want, with the free-text field next to them for everything else.
    readonly property var catIcons: ["folder", "favorite", "home", "work", "church", "code", "terminal", "language", "mail", "chat", "description", "movie", "music_note", "photo_camera", "palette", "sports_esports", "school", "science", "calculate", "shopping_cart", "payments", "map", "fitness_center", "restaurant", "build", "settings", "lock", "cloud", "storage", "apps"]

    function dSetAppearance(which, key, value) {
        const part = Object.assign({}, draftAppearance[which] ?? appDefaults[which]);
        part[key] = value;
        draftAppearance[which] = part;
        touchAppearance();
    }

    function dAppearance(which) {
        return draftAppearance[which] ?? appDefaults[which];
    }

    // ---------------------------------------------------------------- saving
    // Key order is written out deliberately so a saved file still reads like the hand-written one
    // and a later diff is about what changed, not about the serialiser's whims.
    function cleanCat(cat) {
        const out = ({});
        out.id = cat.id;
        // The name is held raw while it is being typed, and the loader drops any category without
        // one — so a field left empty falls back to the id rather than quietly deleting a folder.
        out.name = String(cat.name ?? "").trim() || cat.id;
        if (cat.icon)
            out.icon = cat.icon;
        if (cat.configEntry === true)
            out.configEntry = true;
        if (cat.all === true)
            out.all = true;
        else
            out.apps = (cat.apps ?? []).slice();
        if ((cat.xdgCategories ?? []).length > 0)
            out.xdgCategories = cat.xdgCategories.slice();
        if ((cat.exclude ?? []).length > 0)
            out.exclude = cat.exclude.slice();
        return out;
    }

    readonly property string apprReadme: "Written by the launcher's App List Config popup. `source` is where the colour comes from: text (onSurface), accent (primary), outline, surface, or custom with a #rrggbb in `custom`. Every source but custom is read live from Caelestia's scheme, so the wallpaper still drives the theme. `strength` is the highlight's wash over the card and the outline's opacity, both 0..1."

    function saveConfig() {
        try {
            const obj = ({});
            if (catsPreamble._readme !== undefined)
                obj._readme = catsPreamble._readme;
            obj.version = catsPreamble.version ?? 1;
            obj.defaultCategory = draftDefault;
            obj.categories = draft.map(cleanCat);
            catsFile.setText(JSON.stringify(obj, null, 2) + "\n");

            apprFile.setText(JSON.stringify({
                _readme: apprReadme,
                version: 1,
                highlight: dAppearance("highlight"),
                outline: dAppearance("outline")
            }, null, 2) + "\n");

            // Don't wait for the watcher round-trip to stop previewing: adopt the saved values
            // now, so the launcher is correct even if the reload is slow or fails.
            savedAppearance = {
                highlight: dAppearance("highlight"),
                outline: dAppearance("outline")
            };
            // Those ids are now on disk, and a keybind may already name one. From here a rename is
            // just a label change.
            for (const c of draft)
                delete c._fresh;

            dirty = false;
            configNoteBad = false;
            configNote = "Saved to ~/.config/omarchy-launcher/";
        } catch (e) {
            configNoteBad = true;
            configNote = "Could not save: " + e;
        }
    }

    // Colours offered for "custom", taken straight out of Caelestia's generated scheme — picking
    // one is how you match the desktop theme by hand rather than by guessing a hex.
    readonly property var swatchKeys: ["primary", "secondary", "tertiary", "primaryContainer", "secondaryContainer", "tertiaryContainer", "onSurface", "outline", "surfaceContainerHighest", "error"]
    readonly property var swatches: {
        const cols = scheme.colours ?? {};
        const out = [];
        for (const k of swatchKeys)
            if (cols[k])
                out.push({
                    key: k,
                    hex: "#" + cols[k]
                });
        return out;
    }

    // ----------------------------------------------------------------- window
    PanelWindow {
        id: win

        visible: root.shown
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore

        screen: {
            if (!root.focusedScreen)
                return null;
            return Quickshell.screens.find(s => s.name === root.focusedScreen) ?? null;
        }

        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.namespace: "omarchy-launcher"
        // Exclusive so the launcher owns the keyboard the moment it maps — same as any
        // other popup launcher; released again as soon as `visible` goes false.
        WlrLayershell.keyboardFocus: root.shown ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

        anchors {
            top: true
            bottom: true
            left: true
            right: true
        }

        // dim + click-away
        Rectangle {
            anchors.fill: parent
            color: root.lightMode ? "#40000000" : "#99000000"
            opacity: root.shown ? 1 : 0
            Behavior on opacity {
                NumberAnimation {
                    duration: 120
                    easing.type: Easing.OutQuad
                }
            }

            MouseArea {
                anchors.fill: parent
                onClicked: root.close()
            }
        }

        // ------------------------------------------------------------ the card
        FocusScope {
            id: card

            focus: true
            anchors.centerIn: parent

            // One knob for the whole card. 1.0 is the original size; lower shrinks everything
            // together so the proportions and the visible row count hold.
            readonly property real uiScale: 0.88
            // Row geometry follows the card closely; type shrinks half as much, so the card can
            // come down a size without the names going spidery.
            readonly property real mScale: card.uiScale + (1 - card.uiScale) * 0.2
            readonly property real fScale: card.uiScale + (1 - card.uiScale) * 0.5

            // Narrow portrait, ~1:2.1 — the reference's proportions — and still sized from the
            // display rather than pinned, so it is not a postage stamp on the 3440px ultrawide
            // this runs on nor taller than a 1080p laptop screen.
            readonly property int cardH: Math.round(Math.min(parent.height * 0.78 * uiScale, parent.height - 96, 1160 * uiScale))
            width: Math.round(Math.max(360 * uiScale, Math.min(cardH / 2.1, parent.width - 64, 620 * uiScale)))
            height: cardH

            opacity: root.shown ? 1 : 0
            scale: root.shown ? 1 : 0.97
            Behavior on opacity {
                NumberAnimation {
                    duration: 130
                    easing.type: Easing.OutQuad
                }
            }
            Behavior on scale {
                NumberAnimation {
                    duration: 150
                    easing.type: Easing.OutBack
                    easing.overshoot: 1.1
                }
            }

            // eat clicks so they don't reach the dim layer
            MouseArea {
                anchors.fill: parent
            }

            Rectangle {
                anchors.fill: parent
                radius: 16
                color: root.colBg
                border.width: 2
                border.color: root.colBorder
                clip: true

                // ----------------------------------------- search / breadcrumb
                // No icon, no counter, no rule underneath: in the reference the query line is
                // just text sitting in the card's top padding.
                Item {
                    id: header
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    height: Math.round(56 * card.mScale)

                    TextInput {
                        id: input

                        anchors.left: parent.left
                        anchors.leftMargin: Math.round(30 * card.mScale)
                        anchors.right: parent.right
                        anchors.rightMargin: Math.round(24 * card.mScale)
                        anchors.verticalCenter: parent.verticalCenter

                        focus: true
                        text: root.query
                        onTextChanged: root.query = text
                        color: root.colText
                        selectionColor: root.colAccent
                        selectedTextColor: root.colOnAccent
                        font.family: root.uiFont
                        font.pixelSize: Math.round(17 * card.fScale)
                        clip: true

                        // Restore a clean field every time the launcher maps — unless a keystroke
                        // on the desktop is what opened it, in which case that character is the
                        // field's starting contents.
                        Connections {
                            target: root
                            function onShownChanged() {
                                if (root.shown)
                                    root.applySeed();
                            }
                        }

                        // Always a replace: an empty seed is the ordinary "clear the field on the
                        // way in", and a non-empty one is the full buffer typed on the desktop.
                        Component.onCompleted: root.applySeed = function () {
                            input.text = root.pendingSeed;
                            root.pendingSeed = "";
                            input.cursorPosition = input.text.length;
                            input.forceActiveFocus();
                        }

                        // The placeholder *is* the breadcrumb: "Apps…" at root, "Church…" once
                        // you have opened a folder.
                        Text {
                            id: breadcrumb
                            x: 2   // clear of the caret, which parks at x=0
                            anchors.verticalCenter: parent.verticalCenter
                            visible: input.text.length === 0
                            color: root.colSubtle
                            font: input.font
                            text: (root.view === "cat" && root.currentCat) ? root.currentCat.name + "…" : "Apps…"

                            // Clicking the breadcrumb is the discoverable way back out of a
                            // folder (Backspace / ← on an empty query does the same).
                            MouseArea {
                                anchors.fill: parent
                                anchors.margins: -6
                                enabled: root.view === "cat"
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    root.leaveCat();
                                    input.text = "";
                                    input.forceActiveFocus();
                                }
                            }
                        }

                        Keys.onPressed: event => {
                            switch (event.key) {
                            case Qt.Key_Escape:
                                if (input.text.length > 0)
                                    input.text = "";
                                else if (root.view === "cat")
                                    root.leaveCat();
                                else
                                    root.close();
                                event.accepted = true;
                                break;
                            case Qt.Key_Backspace:
                                // Walk back out of a folder, Omarchy-style.
                                if (input.text.length === 0 && root.view === "cat") {
                                    root.leaveCat();
                                    event.accepted = true;
                                }
                                break;
                            case Qt.Key_Down:
                                root.step(1);
                                event.accepted = true;
                                break;
                            case Qt.Key_Up:
                                root.step(-1);
                                event.accepted = true;
                                break;
                            case Qt.Key_PageDown:
                                root.step(8);
                                event.accepted = true;
                                break;
                            case Qt.Key_PageUp:
                                root.step(-8);
                                event.accepted = true;
                                break;
                            case Qt.Key_Home:
                                if (event.modifiers & Qt.ControlModifier) {
                                    root.index = 0;
                                    event.accepted = true;
                                }
                                break;
                            case Qt.Key_Return:
                            case Qt.Key_Enter:
                                // Enter on a folder opens it; Enter on an app launches it.
                                root.activateSelected();
                                input.text = root.query;
                                event.accepted = true;
                                break;
                            // Depending on the compositor and the virtual-keyboard path, Shift+Tab
                            // arrives either as Key_Backtab or as Key_Tab carrying ShiftModifier —
                            // handle both, or Shift+Tab silently steps forwards.
                            case Qt.Key_Tab:
                                root.stepCat((event.modifiers & Qt.ShiftModifier) ? -1 : 1);
                                input.text = root.query;
                                event.accepted = true;
                                break;
                            case Qt.Key_Backtab:
                                root.stepCat(-1);
                                input.text = root.query;
                                event.accepted = true;
                                break;
                            case Qt.Key_Right:
                                if (event.modifiers & Qt.ControlModifier) {
                                    root.stepCat(1);
                                    input.text = root.query;
                                    event.accepted = true;
                                } else if (input.cursorPosition === input.text.length && root.selectedRow()?.kind === "folder") {
                                    // → opens the folder under the cursor, ← walks back out.
                                    root.activateSelected();
                                    input.text = "";
                                    event.accepted = true;
                                }
                                break;
                            case Qt.Key_Left:
                                if (event.modifiers & Qt.ControlModifier) {
                                    root.stepCat(-1);
                                    input.text = root.query;
                                    event.accepted = true;
                                } else if (input.text.length === 0 && root.view === "cat") {
                                    root.leaveCat();
                                    event.accepted = true;
                                }
                                break;
                            default:
                                // Alt+1..9 opens the Nth folder straight from anywhere.
                                if ((event.modifiers & Qt.AltModifier) && event.key >= Qt.Key_1 && event.key <= Qt.Key_9) {
                                    const i = event.key - Qt.Key_1;
                                    if (i < root.folderCats.length) {
                                        root.enterCat(root.folderCats[i]);
                                        input.text = "";
                                    }
                                    event.accepted = true;
                                }
                                break;
                            }
                        }
                    }
                }

                // "your search widened", or a categories.json parse error. A plain line, not a
                // boxed banner. The error takes precedence and shows even when the widened
                // all-apps fallback has results, which is exactly the case a broken config hits.
                Text {
                    id: notice
                    anchors.top: header.bottom
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: Math.round(30 * card.mScale)
                    anchors.rightMargin: Math.round(24 * card.mScale)
                    text: {
                        if (root.configError)
                            return root.configError;
                        if (root.widened)
                            return "Nothing in " + (root.currentCat?.name ?? "this category") + " — all apps";
                        return "";
                    }
                    visible: text.length > 0
                    height: visible ? implicitHeight + 6 : 0
                    wrapMode: Text.WordWrap
                    color: root.configError ? root.colError : root.colSubtle
                    opacity: 0.85
                    font.family: root.uiFont
                    font.pixelSize: Math.round(12 * card.fScale)
                }

                // ------------------------------------------------- the column
                // One pane, one model. Folders and apps share the row geometry, so opening a
                // folder does not move anything sideways or resize the card.
                Item {
                    id: body
                    anchors.top: notice.bottom
                    anchors.bottom: parent.bottom
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: Math.round(26 * card.mScale)
                    anchors.rightMargin: Math.round(26 * card.mScale)
                    anchors.bottomMargin: Math.round(14 * card.mScale)

                    // shared row metrics — tight, reference-density, scaled with the card
                    readonly property int rowH: Math.round(42 * card.mScale)
                    readonly property int iconSize: Math.round(24 * card.mScale)
                    readonly property int padL: Math.round(14 * card.mScale)
                    readonly property int gap: Math.round(16 * card.mScale)
                    readonly property int splitH: Math.round(11 * card.mScale)
                    readonly property int titleSize: Math.round(16 * card.fScale)
                    readonly property int metaSize: Math.round(12 * card.fScale)
                    readonly property int chevronSize: Math.round(18 * card.fScale)

                    ListView {
                        id: list
                        anchors.fill: parent
                        clip: true
                        spacing: 2
                        model: root.rows
                        currentIndex: root.index
                        boundsBehavior: Flickable.StopAtBounds

                        onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)

                        delegate: Item {
                            id: rowRoot

                            required property int index
                            required property var modelData

                            readonly property bool isFolder: modelData.kind === "folder"
                            readonly property bool isAction: modelData.kind === "action"
                            // Folders and the config row share the symbol slot and the trailing
                            // affordance; only apps get a real icon and a bare row.
                            readonly property bool isSymbol: isFolder || isAction
                            readonly property bool selected: index === root.index
                            // Only the first app row under the folder block carries the split.
                            readonly property int splitH: modelData.gap === true ? body.splitH : 0

                            width: list.width
                            height: body.rowH + splitH

                            // hairline between the folders and the default category's apps
                            Rectangle {
                                visible: rowRoot.splitH > 0
                                anchors.top: parent.top
                                anchors.topMargin: Math.round(rowRoot.splitH / 2)
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.leftMargin: body.padL
                                anchors.rightMargin: body.padL
                                height: 1
                                color: root.colBorder
                                opacity: 0.4
                            }

                            Item {
                                anchors.bottom: parent.bottom
                                anchors.left: parent.left
                                anchors.right: parent.right
                                height: body.rowH

                                Rectangle {
                                    anchors.fill: parent
                                    radius: Math.round(10 * card.mScale)
                                    color: rowRoot.selected ? root.colSel : (rowMouse.containsMouse ? root.colHover : "transparent")

                                    Behavior on color {
                                        ColorAnimation {
                                            duration: 90
                                        }
                                    }
                                }

                                // A folder gets its Material symbol, an app its real icon. Both
                                // occupy the same box so the names line up down the column.
                                Item {
                                    id: rowIcon
                                    anchors.left: parent.left
                                    anchors.leftMargin: body.padL
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: body.iconSize
                                    height: body.iconSize

                                    IconImage {
                                        anchors.fill: parent
                                        visible: !rowRoot.isSymbol
                                        asynchronous: true
                                        implicitSize: body.iconSize
                                        source: rowRoot.isSymbol ? "" : Quickshell.iconPath(rowRoot.modelData.app.icon, "application-x-executable")
                                    }

                                    Text {
                                        anchors.fill: parent
                                        visible: rowRoot.isSymbol
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                        text: rowRoot.isFolder ? (rowRoot.modelData.cat.icon ?? "folder") : (rowRoot.isAction ? (rowRoot.modelData.icon ?? "tune") : "")
                                        font.family: root.iconFont
                                        font.pixelSize: body.iconSize - 2
                                        color: root.colAccent
                                    }
                                }

                                // One line. No description — the reference has none, and the old
                                // `comment || genericName` line printed the name twice for web apps.
                                Text {
                                    anchors.left: rowIcon.right
                                    anchors.leftMargin: body.gap
                                    anchors.right: rowTrail.left
                                    anchors.rightMargin: 8
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: rowRoot.isFolder ? rowRoot.modelData.cat.name : (rowRoot.isAction ? rowRoot.modelData.name : rowRoot.modelData.app.name)
                                    elide: Text.ElideRight
                                    color: root.colText
                                    font.family: root.uiFont
                                    font.pixelSize: body.titleSize
                                }

                                // Folders advertise what is inside them: a count, then a chevron
                                // that says "this opens in place" rather than "this launches".
                                Row {
                                    id: rowTrail
                                    anchors.right: parent.right
                                    anchors.rightMargin: Math.round(12 * card.mScale)
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 4
                                    visible: rowRoot.isSymbol

                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: rowRoot.isFolder ? (root.catCounts[rowRoot.modelData.cat.id] ?? "") : ""
                                        color: root.colSubtle
                                        opacity: 0.7
                                        font.family: root.uiFont
                                        font.pixelSize: body.metaSize
                                    }

                                    // A folder opens in place, so it gets a chevron; the config
                                    // opens a window of its own, so it gets the "leaves this box"
                                    // symbol instead. The difference is the only warning you get.
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: rowRoot.isAction ? "open_in_new" : "chevron_right"
                                        font.family: root.iconFont
                                        font.pixelSize: body.chevronSize
                                        color: root.colSubtle
                                        opacity: rowRoot.selected ? 0.95 : 0.55
                                    }
                                }

                                MouseArea {
                                    id: rowMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onPositionChanged: root.index = rowRoot.index
                                    onClicked: {
                                        root.activate(rowRoot.modelData);
                                        input.text = root.query;
                                        input.forceActiveFocus();
                                    }
                                }
                            }
                        }
                    }

                    // empty state / config error
                    Column {
                        anchors.centerIn: parent
                        width: parent.width - 32
                        spacing: 6
                        visible: root.rows.length === 0

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: root.configError ? "error" : "search_off"
                            font.family: root.iconFont
                            font.pixelSize: Math.round(28 * card.fScale)
                            color: root.configError ? root.colError : root.colSubtle
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            color: root.configError ? root.colError : root.colSubtle
                            font.family: root.uiFont
                            font.pixelSize: Math.round(13 * card.fScale)
                            text: {
                                if (root.configError)
                                    return root.configError;
                                if (root.trimmedQuery.length > 0)
                                    return "No apps match “" + root.query.trim() + "”";
                                const name = root.view === "cat" ? (root.currentCat?.name ?? "This category") : (root.defaultCat?.name ?? "This category");
                                // A brand-new category lands here the moment it is saved, so the
                                // hint points at the window that can fill it rather than at the
                                // file — the file is still there, it is just no longer the only way.
                                return name + " is empty — fill it from App List Config,\npinned at the top of " + (root.settingsCat?.name ?? "the settings folder");
                            }
                        }
                    }
                }
            }
        }
    }

    // ==================================================================================
    //  App List Config — the window
    // ==================================================================================
    // Deliberately landscape and roomy, the opposite of the launcher: this is a thing you sit in
    // for a minute, not a thing you flash open. It borrows every colour from the same live scheme,
    // so it is recognisably part of the launcher without pretending to be the same shape.

    component CfgButton: Rectangle {
        id: btn

        property string label: ""
        property string symbol: ""
        property bool accent: false
        // What "accent" is made of. Defaults to the theme accent; the armed delete points it at
        // the error colour, so a confirm that is about to destroy something doesn't look like a
        // Save.
        property color tint: root.colAccent
        signal clicked

        implicitHeight: 30
        implicitWidth: btnRow.implicitWidth + 24
        radius: 8
        opacity: enabled ? 1 : 0.35
        color: accent ? Qt.tint(root.colBg, Qt.rgba(tint.r, tint.g, tint.b, 0.2)) : (btnMouse.containsMouse ? root.colHover : "transparent")
        border.width: 1
        border.color: accent ? Qt.rgba(tint.r, tint.g, tint.b, 0.5) : root.colBorder

        Behavior on color {
            ColorAnimation {
                duration: 90
            }
        }

        Row {
            id: btnRow
            anchors.centerIn: parent
            spacing: 6

            Text {
                anchors.verticalCenter: parent.verticalCenter
                visible: btn.symbol.length > 0
                text: btn.symbol
                font.family: root.iconFont
                font.pixelSize: 16
                color: btn.accent ? btn.tint : root.colText
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                visible: btn.label.length > 0
                text: btn.label
                font.family: root.uiFont
                font.pixelSize: 13
                color: btn.accent ? btn.tint : root.colText
            }
        }

        MouseArea {
            id: btnMouse
            anchors.fill: parent
            hoverEnabled: true
            enabled: btn.enabled
            cursorShape: Qt.PointingHandCursor
            onClicked: btn.clicked()
        }
    }

    component CfgIconBtn: Rectangle {
        id: ib

        property string symbol: ""
        property color tone: root.colSubtle
        signal clicked

        implicitWidth: 26
        implicitHeight: 26
        radius: 6
        opacity: enabled ? 1 : 0.25
        color: ibMouse.containsMouse ? root.colHover : "transparent"

        Text {
            anchors.centerIn: parent
            text: ib.symbol
            font.family: root.iconFont
            font.pixelSize: 17
            color: ib.tone
        }

        MouseArea {
            id: ibMouse
            anchors.fill: parent
            hoverEnabled: true
            enabled: ib.enabled
            cursorShape: Qt.PointingHandCursor
            onClicked: ib.clicked()
        }
    }

    component CfgChip: Rectangle {
        id: chip

        property string label: ""
        property bool active: false
        signal clicked

        implicitHeight: 27
        implicitWidth: chipLbl.implicitWidth + 24
        radius: 13
        color: active ? Qt.tint(root.colBg, Qt.rgba(root.colAccent.r, root.colAccent.g, root.colAccent.b, 0.22)) : (chipMouse.containsMouse ? root.colHover : "transparent")
        border.width: 1
        border.color: active ? Qt.rgba(root.colAccent.r, root.colAccent.g, root.colAccent.b, 0.55) : root.colBorder

        Behavior on color {
            ColorAnimation {
                duration: 90
            }
        }

        Text {
            id: chipLbl
            anchors.centerIn: parent
            text: chip.label
            font.family: root.uiFont
            font.pixelSize: 13
            color: chip.active ? root.colAccent : root.colText
        }

        MouseArea {
            id: chipMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: chip.clicked()
        }
    }

    // Hand-rolled rather than QtQuick.Controls: the launcher has no Controls dependency and this
    // is the only slider in it.
    component CfgSlider: Item {
        id: sl

        property real value: 0
        property real from: 0
        property real to: 1
        signal moved(real v)

        implicitHeight: 26
        readonly property real frac: (to > from) ? Math.max(0, Math.min(1, (value - from) / (to - from))) : 0

        function valueAt(px) {
            const t = Math.max(0, Math.min(1, px / Math.max(1, track.width)));
            return sl.from + t * (sl.to - sl.from);
        }

        Rectangle {
            id: track
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            height: 4
            radius: 2
            color: Qt.rgba(root.colSubtle.r, root.colSubtle.g, root.colSubtle.b, 0.28)

            Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: parent.width * sl.frac
                radius: 2
                color: root.colAccent
            }
        }

        Rectangle {
            width: 14
            height: 14
            radius: 7
            x: track.width * sl.frac - width / 2
            anchors.verticalCenter: parent.verticalCenter
            color: root.colAccent
            border.width: 2
            border.color: root.colBg
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onPressed: e => sl.moved(sl.valueAt(e.x))
            onPositionChanged: e => {
                if (pressed)
                    sl.moved(sl.valueAt(e.x));
            }
        }
    }

    // One row of "where does this colour come from" chips plus the swatches that appear when the
    // answer is "custom". Used identically for the highlight and the outline.
    component CfgSourceRow: Column {
        id: src

        property string which: "highlight"
        readonly property var part: root.dAppearance(which)

        spacing: 10

        Row {
            spacing: 8

            Repeater {
                model: [
                    {
                        k: "text",
                        n: "Text"
                    },
                    {
                        k: "accent",
                        n: "Accent"
                    },
                    {
                        k: "outline",
                        n: "Outline"
                    },
                    {
                        k: "surface",
                        n: "Surface"
                    },
                    {
                        k: "custom",
                        n: "Custom"
                    }
                ]

                CfgChip {
                    required property var modelData
                    label: modelData.n
                    active: src.part.source === modelData.k
                    onClicked: root.dSetAppearance(src.which, "source", modelData.k)
                }
            }
        }

        // The swatches are the live scheme, so "match the desktop theme" is a click rather than a
        // hex you have to go and look up.
        Flow {
            width: src.width
            spacing: 8
            visible: src.part.source === "custom"

            Repeater {
                model: root.swatches

                Rectangle {
                    required property var modelData
                    width: 26
                    height: 26
                    radius: 7
                    color: modelData.hex
                    border.width: 2
                    border.color: src.part.custom === modelData.hex ? root.colText : root.colBorder

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.dSetAppearance(src.which, "custom", modelData.hex)
                    }
                }
            }

            Rectangle {
                width: 104
                height: 26
                radius: 7
                color: "transparent"
                border.width: 1
                border.color: root.colBorder

                TextInput {
                    id: hexField
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    verticalAlignment: TextInput.AlignVCenter
                    color: /^#[0-9a-fA-F]{6}$/.test(text) ? root.colText : root.colError
                    font.family: root.uiFont
                    font.pixelSize: 12
                    maximumLength: 7
                    text: src.part.custom
                    onEditingFinished: root.dSetAppearance(src.which, "custom", text)

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: hexField.text.length === 0
                        text: "#rrggbb"
                        color: root.colSubtle
                        font: hexField.font
                    }
                }
            }
        }
    }

    PanelWindow {
        id: cfgWin

        visible: root.configShown
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore

        screen: {
            if (!root.focusedScreen)
                return null;
            return Quickshell.screens.find(s => s.name === root.focusedScreen) ?? null;
        }

        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.namespace: "omarchy-launcher-config"
        WlrLayershell.keyboardFocus: root.configShown ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

        anchors {
            top: true
            bottom: true
            left: true
            right: true
        }

        Rectangle {
            anchors.fill: parent
            color: root.lightMode ? "#40000000" : "#99000000"

            MouseArea {
                anchors.fill: parent
                onClicked: root.closeConfig()
            }
        }

        FocusScope {
            id: cfgCard

            focus: true
            anchors.centerIn: parent
            width: Math.round(Math.min(parent.width - 120, 1180))
            height: Math.round(Math.min(parent.height - 110, 820))

            // Plain Tab belongs to the search field, so the window's own shortcuts all sit behind
            // Ctrl — otherwise the tabs and the save button would be mouse-only.
            Keys.onPressed: event => {
                const ctrl = (event.modifiers & Qt.ControlModifier) !== 0;
                switch (event.key) {
                case Qt.Key_Escape:
                    root.closeConfig();
                    event.accepted = true;
                    break;
                case Qt.Key_S:
                    if (ctrl) {
                        root.saveConfig();
                        event.accepted = true;
                    }
                    break;
                case Qt.Key_N:
                    // Only on the tab that has a category list to add to.
                    if (ctrl && root.configTab === 0) {
                        root.dNewCategory();
                        event.accepted = true;
                    }
                    break;
                case Qt.Key_Tab:
                case Qt.Key_Backtab:
                    if (ctrl) {
                        root.configTab = root.configTab === 0 ? 1 : 0;
                        event.accepted = true;
                    }
                    break;
                case Qt.Key_1:
                case Qt.Key_2:
                    if (ctrl) {
                        root.configTab = event.key - Qt.Key_1;
                        event.accepted = true;
                    }
                    break;
                }
            }

            MouseArea {
                anchors.fill: parent
            }

            Rectangle {
                anchors.fill: parent
                radius: 18
                color: root.colBg
                border.width: 2
                border.color: root.colBorder
                clip: true

                // ------------------------------------------------------ header
                Item {
                    id: cfgHeader
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: 26
                    anchors.rightMargin: 20
                    height: 62

                    Text {
                        id: cfgTitleIcon
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        text: "tune"
                        font.family: root.iconFont
                        font.pixelSize: 22
                        color: root.colAccent
                    }

                    Text {
                        id: cfgTitle
                        anchors.left: cfgTitleIcon.right
                        anchors.leftMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        text: "App List Config"
                        font.family: root.uiFont
                        font.pixelSize: 19
                        color: root.colText
                    }

                    Row {
                        anchors.centerIn: parent
                        spacing: 8

                        CfgChip {
                            label: "App lists"
                            active: root.configTab === 0
                            onClicked: root.configTab = 0
                        }

                        CfgChip {
                            label: "Appearance"
                            active: root.configTab === 1
                            onClicked: root.configTab = 1
                        }
                    }

                    CfgIconBtn {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        symbol: "close"
                        onClicked: root.closeConfig()
                    }
                }

                Rectangle {
                    id: cfgHeaderRule
                    anchors.top: cfgHeader.bottom
                    anchors.left: parent.left
                    anchors.right: parent.right
                    height: 1
                    color: root.colBorder
                    opacity: 0.5
                }

                // ------------------------------------------------------ footer
                Rectangle {
                    id: cfgFooterRule
                    anchors.bottom: cfgFooter.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    height: 1
                    color: root.colBorder
                    opacity: 0.5
                }

                Item {
                    id: cfgFooter
                    anchors.bottom: parent.bottom
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: 26
                    anchors.rightMargin: 20
                    height: 58

                    Text {
                        anchors.left: parent.left
                        anchors.right: cfgActions.left
                        anchors.rightMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        elide: Text.ElideRight
                        font.family: root.uiFont
                        font.pixelSize: 13
                        color: root.configNoteBad ? root.colError : root.colSubtle
                        text: {
                            if (root.configNote)
                                return root.configNote;
                            if (root.dirty)
                                return "Unsaved changes — Save writes ~/.config/omarchy-launcher/categories.json and appearance.json";
                            return "Changes are previewed live; nothing is written until you save.";
                        }
                    }

                    Row {
                        id: cfgActions
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 8

                        CfgButton {
                            label: "Revert"
                            symbol: "undo"
                            enabled: root.dirty
                            onClicked: root.resetDraft()
                        }

                        CfgButton {
                            label: "Save"
                            symbol: "check"
                            accent: true
                            enabled: root.dirty
                            onClicked: root.saveConfig()
                        }

                        CfgButton {
                            label: "Close"
                            onClicked: root.closeConfig()
                        }
                    }
                }

                // ------------------------------------------- body: app lists
                Item {
                    id: cfgBody
                    anchors.top: cfgHeaderRule.bottom
                    anchors.bottom: cfgFooterRule.top
                    anchors.left: parent.left
                    anchors.right: parent.right

                    // ---- tab 0 ------------------------------------------------
                    Item {
                        anchors.fill: parent
                        visible: root.configTab === 0

                        // column A: the categories
                        Item {
                            id: colCats
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            anchors.left: parent.left
                            anchors.topMargin: 16
                            anchors.bottomMargin: 16
                            anchors.leftMargin: 18
                            width: 222

                            Text {
                                id: catsLabel
                                anchors.top: parent.top
                                anchors.left: parent.left
                                anchors.leftMargin: 8
                                text: "CATEGORIES"
                                font.family: root.uiFont
                                font.pixelSize: 11
                                font.letterSpacing: 1.2
                                color: root.colSubtle
                                opacity: 0.8
                            }

                            ListView {
                                anchors.top: catsLabel.bottom
                                anchors.topMargin: 10
                                anchors.bottom: newCatBtn.top
                                anchors.bottomMargin: 10
                                anchors.left: parent.left
                                anchors.right: parent.right
                                clip: true
                                spacing: 2
                                model: root.draft
                                boundsBehavior: Flickable.StopAtBounds

                                delegate: Rectangle {
                                    id: catRow

                                    required property int index
                                    required property var modelData
                                    readonly property bool sel: index === root.dSel

                                    width: ListView.view.width
                                    height: 36
                                    radius: 9
                                    color: sel ? root.colSel : (catMouse.containsMouse ? root.colHover : "transparent")

                                    Text {
                                        id: catRowIcon
                                        anchors.left: parent.left
                                        anchors.leftMargin: 11
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: catRow.modelData.icon ?? "folder"
                                        font.family: root.iconFont
                                        font.pixelSize: 18
                                        color: root.colAccent
                                    }

                                    Text {
                                        anchors.left: catRowIcon.right
                                        anchors.leftMargin: 10
                                        anchors.right: catRowTrail.left
                                        anchors.rightMargin: 6
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: catRow.modelData.name
                                        elide: Text.ElideRight
                                        font.family: root.uiFont
                                        font.pixelSize: 14
                                        color: root.colText
                                    }

                                    Row {
                                        id: catRowTrail
                                        anchors.right: parent.right
                                        anchors.rightMargin: 10
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 5

                                        // The default category is the launcher's opening view —
                                        // worth showing here, because it is the one setting that
                                        // changes what you see before you type anything.
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            visible: root.draftDefault === catRow.modelData.id
                                            text: "star"
                                            font.family: root.iconFont
                                            font.pixelSize: 14
                                            color: root.colAccent
                                        }

                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: root.dCounts[catRow.modelData.id] ?? ""
                                            font.family: root.uiFont
                                            font.pixelSize: 12
                                            color: root.colSubtle
                                            opacity: 0.75
                                        }
                                    }

                                    MouseArea {
                                        id: catMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.dSelect(catRow.index)
                                    }
                                }
                            }

                            // The list of categories used to be fixed — this is the way into it.
                            // Deleting lives in the header of the middle column, next to the
                            // category's name, because that is the one place it is unambiguous
                            // which category is about to go.
                            CfgButton {
                                id: newCatBtn
                                anchors.bottom: parent.bottom
                                anchors.left: parent.left
                                anchors.right: parent.right
                                symbol: "create_new_folder"
                                label: "New category"
                                onClicked: root.dNewCategory()
                            }
                        }

                        Rectangle {
                            id: ruleA
                            anchors.left: colCats.right
                            anchors.leftMargin: 18
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            anchors.topMargin: 14
                            anchors.bottomMargin: 14
                            width: 1
                            color: root.colBorder
                            opacity: 0.45
                        }

                        // column C: add apps (anchored first so B can fill between)
                        Item {
                            id: colAdd
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            anchors.right: parent.right
                            anchors.topMargin: 16
                            anchors.bottomMargin: 16
                            anchors.rightMargin: 18
                            width: 316

                            Text {
                                id: addLabel
                                anchors.top: parent.top
                                anchors.left: parent.left
                                anchors.leftMargin: 8
                                text: "ADD AN APP"
                                font.family: root.uiFont
                                font.pixelSize: 11
                                font.letterSpacing: 1.2
                                color: root.colSubtle
                                opacity: 0.8
                            }

                            Rectangle {
                                id: addSearch
                                anchors.top: addLabel.bottom
                                anchors.topMargin: 10
                                anchors.left: parent.left
                                anchors.right: parent.right
                                height: 34
                                radius: 9
                                color: "transparent"
                                border.width: 1
                                border.color: root.colBorder

                                Text {
                                    id: addSearchIcon
                                    anchors.left: parent.left
                                    anchors.leftMargin: 10
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "search"
                                    font.family: root.iconFont
                                    font.pixelSize: 16
                                    color: root.colSubtle
                                }

                                TextInput {
                                    id: addInput
                                    anchors.left: addSearchIcon.right
                                    anchors.leftMargin: 8
                                    anchors.right: parent.right
                                    anchors.rightMargin: 10
                                    anchors.verticalCenter: parent.verticalCenter
                                    clip: true
                                    color: root.colText
                                    selectionColor: root.colAccent
                                    selectedTextColor: root.colOnAccent
                                    font.family: root.uiFont
                                    font.pixelSize: 14
                                    text: root.addQuery
                                    onTextChanged: root.addQuery = text

                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        visible: addInput.text.length === 0
                                        text: "Search all " + root.allApps.length + " apps…"
                                        color: root.colSubtle
                                        font: addInput.font
                                    }
                                }
                            }

                            ListView {
                                anchors.top: addSearch.bottom
                                anchors.topMargin: 10
                                anchors.bottom: parent.bottom
                                anchors.left: parent.left
                                anchors.right: parent.right
                                clip: true
                                spacing: 1
                                model: root.addList
                                boundsBehavior: Flickable.StopAtBounds

                                delegate: Rectangle {
                                    id: addRow

                                    required property var modelData
                                    readonly property bool present: root.dInCat(modelData.id)

                                    width: ListView.view.width
                                    height: 34
                                    radius: 8
                                    color: addMouse.containsMouse ? root.colHover : "transparent"

                                    IconImage {
                                        id: addRowIcon
                                        anchors.left: parent.left
                                        anchors.leftMargin: 9
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 20
                                        height: 20
                                        asynchronous: true
                                        implicitSize: 20
                                        source: Quickshell.iconPath(addRow.modelData.icon, "application-x-executable")
                                    }

                                    Text {
                                        anchors.left: addRowIcon.right
                                        anchors.leftMargin: 9
                                        anchors.right: addRowMark.left
                                        anchors.rightMargin: 6
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: addRow.modelData.name
                                        elide: Text.ElideRight
                                        font.family: root.uiFont
                                        font.pixelSize: 14
                                        color: addRow.present ? root.colSubtle : root.colText
                                    }

                                    Text {
                                        id: addRowMark
                                        anchors.right: parent.right
                                        anchors.rightMargin: 10
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: addRow.present ? "check" : "add"
                                        font.family: root.iconFont
                                        font.pixelSize: 17
                                        color: addRow.present ? root.colAccent : root.colSubtle
                                        opacity: addRow.present ? 0.9 : (addMouse.containsMouse ? 1 : 0.5)
                                    }

                                    MouseArea {
                                        id: addMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        enabled: root.dCat?.all !== true
                                        onClicked: root.dToggle(addRow.modelData.id)
                                    }
                                }
                            }
                        }

                        Rectangle {
                            id: ruleB
                            anchors.right: colAdd.left
                            anchors.rightMargin: 18
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            anchors.topMargin: 14
                            anchors.bottomMargin: 14
                            width: 1
                            color: root.colBorder
                            opacity: 0.45
                        }

                        // column B: what is in the selected category
                        Item {
                            id: colIn
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            anchors.left: ruleA.right
                            anchors.right: ruleB.left
                            anchors.topMargin: 16
                            anchors.bottomMargin: 16
                            anchors.leftMargin: 18
                            anchors.rightMargin: 18

                            // The other two columns keep a small-caps section label; this one no
                            // longer can, because the category's name stopped being a heading and
                            // became a field you type in. Everything that belongs to the category
                            // *as a category* — its name, its icon, whether it is the opening
                            // view, and whether it exists at all — sits on this one line, above
                            // the list of what is inside it.
                            Item {
                                id: inHeader
                                anchors.top: parent.top
                                anchors.left: parent.left
                                anchors.right: parent.right
                                height: inTitleRow.height + (iconPick.visible ? iconPick.height + 8 : 0)

                                Item {
                                    id: inTitleRow
                                    anchors.top: parent.top
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    height: 34

                                    CfgIconBtn {
                                        id: inIconBtn
                                        anchors.left: parent.left
                                        anchors.verticalCenter: parent.verticalCenter
                                        symbol: root.dCat?.icon ?? "folder"
                                        tone: root.colAccent
                                        enabled: root.dCat !== null
                                        onClicked: root.dIconOpen = !root.dIconOpen
                                    }

                                    Rectangle {
                                        id: inNameBox
                                        anchors.left: inIconBtn.right
                                        anchors.leftMargin: 4
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: Math.min(260, Math.max(120, parent.width - inIconBtn.width - inCatActions.width - inCount.width - 40))
                                        height: 30
                                        radius: 8
                                        color: "transparent"
                                        border.width: 1
                                        // Invisible until you go near it: the name is a label most
                                        // of the time and a field only when you want one.
                                        border.color: (nameField.activeFocus || nameMouse.containsMouse) ? root.colBorder : "transparent"

                                        TextInput {
                                            id: nameField
                                            anchors.fill: parent
                                            anchors.leftMargin: 8
                                            anchors.rightMargin: 8
                                            verticalAlignment: TextInput.AlignVCenter
                                            clip: true
                                            enabled: root.dCat !== null
                                            color: root.colText
                                            selectionColor: root.colAccent
                                            selectedTextColor: root.colOnAccent
                                            font.family: root.uiFont
                                            font.pixelSize: 15
                                            text: root.dCat?.name ?? ""
                                            onTextEdited: root.dRename(text)
                                            onAccepted: focus = false

                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                visible: nameField.text.trim().length === 0
                                                text: "Category name"
                                                color: root.colError
                                                font: nameField.font
                                                opacity: 0.8
                                            }

                                            // Typing breaks the `text` binding above, so the field
                                            // has to be told when the category under it changed —
                                            // otherwise renaming Work and then clicking Church
                                            // leaves Church wearing "Work". The unconditional sync
                                            // is the deliberate one: the field can still hold focus
                                            // when a delete moves the selection under it, so
                                            // skipping the resync while focused would leave the
                                            // deleted category's name sitting on its successor.
                                            Connections {
                                                target: root

                                                function onSyncCategoryFields() {
                                                    nameField.text = root.dCat?.name ?? "";
                                                }

                                                function onDCatChanged() {
                                                    if (!nameField.activeFocus)
                                                        nameField.text = root.dCat?.name ?? "";
                                                }

                                                function onFocusCategoryName() {
                                                    nameField.text = root.dCat?.name ?? "";
                                                    nameField.forceActiveFocus();
                                                    nameField.selectAll();
                                                }
                                            }
                                        }

                                        MouseArea {
                                            id: nameMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            acceptedButtons: Qt.NoButton
                                            cursorShape: Qt.IBeamCursor
                                        }
                                    }

                                    Text {
                                        id: inCount
                                        anchors.left: inNameBox.right
                                        anchors.leftMargin: 10
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: root.dMembers.length + (root.dMembers.length === 1 ? " app" : " apps")
                                        font.family: root.uiFont
                                        font.pixelSize: 11
                                        color: root.colSubtle
                                        opacity: 0.55
                                    }

                                    Row {
                                        id: inCatActions
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 8

                                        CfgButton {
                                            symbol: "star"
                                            label: root.draftDefault === (root.dCat?.id ?? "") ? "Opening view" : "Make opening view"
                                            accent: root.draftDefault === (root.dCat?.id ?? "")
                                            enabled: root.dCat !== null && root.draftDefault !== root.dCat.id
                                            onClicked: root.dMakeDefault(root.dCat?.id ?? "")
                                        }

                                        // Two clicks, because this is the only control in the
                                        // window that destroys a list rather than moving one entry
                                        // in or out of it. `dSelect` disarms, so the confirm can't
                                        // follow you to another category.
                                        CfgButton {
                                            id: delCatBtn
                                            readonly property bool armed: root.dArmed.length > 0 && root.dArmed === (root.dCat?.id ?? "")
                                            symbol: armed ? "delete_forever" : "delete"
                                            label: armed ? "Delete — click again" : "Delete"
                                            accent: armed
                                            tint: root.colError
                                            enabled: root.dCat !== null && root.draft.length > 1
                                            onClicked: {
                                                if (armed)
                                                    root.dDeleteCategory();
                                                else
                                                    root.dArmed = root.dCat?.id ?? "";
                                            }
                                        }
                                    }
                                }

                                // Categories have always carried an icon; until now the only way
                                // to set one was to look a Material Symbols name up and type it
                                // into the JSON. The grid is the common answer, the field next to
                                // it is every other name the font knows.
                                Flow {
                                    id: iconPick
                                    anchors.top: inTitleRow.bottom
                                    anchors.topMargin: 4
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    visible: root.dIconOpen && root.dCat !== null
                                    height: visible ? implicitHeight : 0
                                    spacing: 4

                                    Repeater {
                                        model: root.catIcons

                                        Rectangle {
                                            id: iconCell

                                            required property var modelData
                                            readonly property bool picked: (root.dCat?.icon ?? "") === modelData

                                            width: 30
                                            height: 30
                                            radius: 8
                                            color: picked ? root.colSel : (iconMouse.containsMouse ? root.colHover : "transparent")
                                            border.width: 1
                                            border.color: picked ? root.colBorder : "transparent"

                                            Text {
                                                anchors.centerIn: parent
                                                text: iconCell.modelData
                                                font.family: root.iconFont
                                                font.pixelSize: 18
                                                color: iconCell.picked ? root.colAccent : root.colText
                                                opacity: iconCell.picked ? 1 : 0.75
                                            }

                                            MouseArea {
                                                id: iconMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: root.dSetIcon(iconCell.modelData)
                                            }
                                        }
                                    }

                                    Rectangle {
                                        width: 136
                                        height: 30
                                        radius: 8
                                        color: "transparent"
                                        border.width: 1
                                        border.color: root.colBorder

                                        TextInput {
                                            id: iconField
                                            anchors.fill: parent
                                            anchors.leftMargin: 8
                                            anchors.rightMargin: 8
                                            verticalAlignment: TextInput.AlignVCenter
                                            clip: true
                                            color: root.colText
                                            selectionColor: root.colAccent
                                            selectedTextColor: root.colOnAccent
                                            font.family: root.uiFont
                                            font.pixelSize: 12
                                            text: root.dCat?.icon ?? ""
                                            onEditingFinished: root.dSetIcon(text.trim())

                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                visible: iconField.text.length === 0
                                                text: "icon name…"
                                                color: root.colSubtle
                                                font: iconField.font
                                            }

                                            // Same broken-binding problem as the name field: a
                                            // swatch click has to show up in the box.
                                            Connections {
                                                target: root

                                                function onSyncCategoryFields() {
                                                    iconField.text = root.dCat?.icon ?? "";
                                                }

                                                function onDCatChanged() {
                                                    if (!iconField.activeFocus)
                                                        iconField.text = root.dCat?.icon ?? "";
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            // Generated categories have no list to edit; say so rather than
                            // showing 168 rows with dead buttons on them.
                            Text {
                                anchors.top: inHeader.bottom
                                anchors.topMargin: 6
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.leftMargin: 8
                                visible: root.dCat?.all === true
                                wrapMode: Text.WordWrap
                                text: "All Apps is generated from everything installed — there is no list to edit here. Pick another category on the left."
                                font.family: root.uiFont
                                font.pixelSize: 13
                                color: root.colSubtle
                            }

                            ListView {
                                id: inList
                                anchors.top: inHeader.bottom
                                anchors.topMargin: 6
                                anchors.bottom: staleBox.top
                                anchors.bottomMargin: staleBox.visible ? 10 : 0
                                anchors.left: parent.left
                                anchors.right: parent.right
                                clip: true
                                spacing: 1
                                model: root.dCat?.all === true ? [] : root.dMembers
                                boundsBehavior: Flickable.StopAtBounds

                                // Every edit re-seats the model, which sends a ListView back to
                                // the top. Removing the fortieth row of System and being thrown
                                // to the first one makes tidying a long category miserable, so
                                // the scroll position is carried across the swap. It is recorded
                                // only when the user stops scrolling, because the swap itself
                                // zeroes contentY before the restore can run.
                                property real keepY: 0
                                onMovementEnded: keepY = contentY
                                onFlickEnded: keepY = contentY
                                onModelChanged: Qt.callLater(() => {
                                    contentY = Math.max(0, Math.min(keepY, Math.max(0, contentHeight - height)));
                                })

                                delegate: Rectangle {
                                    id: memRow

                                    required property int index
                                    required property var modelData

                                    readonly property bool pinned: modelData.pinned
                                    // Pinned rows are emitted first, so the row index doubles as
                                    // the rung this row sits on in the move ladder.
                                    readonly property int rank: pinned ? index : -1

                                    width: ListView.view.width
                                    height: 36
                                    radius: 8
                                    color: memMouse.containsMouse ? root.colHover : "transparent"

                                    IconImage {
                                        id: memIcon
                                        anchors.left: parent.left
                                        anchors.leftMargin: 9
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 21
                                        height: 21
                                        asynchronous: true
                                        implicitSize: 21
                                        source: Quickshell.iconPath(memRow.modelData.app.icon, "application-x-executable")
                                    }

                                    Text {
                                        id: memName
                                        anchors.left: memIcon.right
                                        anchors.leftMargin: 10
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: Math.max(0, memTools.x - x - (memTag.visible ? memTag.width + 14 : 10))
                                        text: memRow.modelData.app.name
                                        elide: Text.ElideRight
                                        font.family: root.uiFont
                                        font.pixelSize: 14
                                        color: root.colText
                                    }

                                    // An auto row is here because of a freedesktop tag, not
                                    // because anyone put it here — which is why it can't be
                                    // reordered, and why removing it has to write an exclusion.
                                    Rectangle {
                                        id: memTag
                                        anchors.left: memName.right
                                        anchors.leftMargin: 8
                                        anchors.verticalCenter: parent.verticalCenter
                                        visible: !memRow.pinned
                                        width: memTagText.implicitWidth + 12
                                        height: 18
                                        radius: 9
                                        color: "transparent"
                                        border.width: 1
                                        border.color: root.colBorder

                                        Text {
                                            id: memTagText
                                            anchors.centerIn: parent
                                            text: "auto"
                                            font.family: root.uiFont
                                            font.pixelSize: 10
                                            color: root.colSubtle
                                        }
                                    }

                                    Row {
                                        id: memTools
                                        anchors.right: parent.right
                                        anchors.rightMargin: 8
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 2
                                        opacity: memMouse.containsMouse ? 1 : 0.55

                                        CfgIconBtn {
                                            symbol: "keyboard_arrow_up"
                                            enabled: memRow.pinned && memRow.rank > 0
                                            onClicked: root.dMove(memRow.rank, -1)
                                        }

                                        CfgIconBtn {
                                            symbol: "keyboard_arrow_down"
                                            enabled: memRow.pinned && memRow.rank >= 0 && memRow.rank < root.dPinnedPos.length - 1
                                            onClicked: root.dMove(memRow.rank, 1)
                                        }

                                        CfgIconBtn {
                                            symbol: "close"
                                            tone: root.colError
                                            onClicked: root.dRemove(memRow.modelData.app.id)
                                        }
                                    }

                                    MouseArea {
                                        id: memMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        acceptedButtons: Qt.NoButton
                                    }
                                }
                            }

                            // Ids that no longer resolve. The launcher hides these; leaving them
                            // invisible here is how a categories.json quietly rots.
                            Column {
                                id: staleBox
                                anchors.bottom: parent.bottom
                                anchors.left: parent.left
                                anchors.right: parent.right
                                visible: root.dStale.length > 0
                                // A hidden Column still measures its children, and `inList`
                                // anchors to the top of this one — collapse it explicitly or it
                                // silently eats the bottom of the list.
                                height: visible ? implicitHeight : 0
                                spacing: 4

                                Text {
                                    text: root.dStale.length + (root.dStale.length === 1 ? " id in this list matches nothing installed" : " ids in this list match nothing installed")
                                    font.family: root.uiFont
                                    font.pixelSize: 11
                                    color: root.colError
                                    opacity: 0.9
                                }

                                Flow {
                                    width: staleBox.width
                                    spacing: 6

                                    Repeater {
                                        model: root.dStale

                                        Rectangle {
                                            required property var modelData
                                            width: staleLbl.implicitWidth + 34
                                            height: 24
                                            radius: 12
                                            color: "transparent"
                                            border.width: 1
                                            border.color: Qt.rgba(root.colError.r, root.colError.g, root.colError.b, 0.45)

                                            Text {
                                                id: staleLbl
                                                anchors.left: parent.left
                                                anchors.leftMargin: 10
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: parent.modelData
                                                font.family: root.uiFont
                                                font.pixelSize: 11
                                                color: root.colError
                                            }

                                            Text {
                                                anchors.right: parent.right
                                                anchors.rightMargin: 7
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: "close"
                                                font.family: root.iconFont
                                                font.pixelSize: 13
                                                color: root.colError
                                            }

                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: root.dDropStale(parent.modelData)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // ---- tab 1: appearance -----------------------------------
                    Flickable {
                        anchors.fill: parent
                        visible: root.configTab === 1
                        clip: true
                        contentHeight: Math.max(apprCol.implicitHeight, apprPreview.implicitHeight) + 56
                        boundsBehavior: Flickable.StopAtBounds

                        // Capped at a readable measure rather than stretched to the window: a
                        // 1100px slider is impossible to land a value on, and a 1100px line of
                        // explanation is impossible to read.
                        Column {
                            id: apprCol
                            x: 30
                            y: 24
                            width: Math.min(cfgBody.width - 460, 560)
                            spacing: 26

                            // ---- highlight ----
                            Column {
                                width: parent.width
                                spacing: 12

                                Text {
                                    text: "Highlight"
                                    font.family: root.uiFont
                                    font.pixelSize: 16
                                    color: root.colText
                                }

                                Text {
                                    width: parent.width
                                    wrapMode: Text.WordWrap
                                    text: "The pill behind the row you are on, and the fainter one under the mouse. Every source but Custom is read live from Caelestia's scheme, so it keeps matching the desktop theme through a wallpaper recolour."
                                    font.family: root.uiFont
                                    font.pixelSize: 13
                                    color: root.colSubtle
                                }

                                CfgSourceRow {
                                    width: parent.width
                                    which: "highlight"
                                }

                                Item {
                                    width: parent.width
                                    height: 30

                                    Text {
                                        id: hlLabel
                                        anchors.left: parent.left
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 74
                                        text: "Strength"
                                        font.family: root.uiFont
                                        font.pixelSize: 13
                                        color: root.colSubtle
                                    }

                                    CfgSlider {
                                        id: hlSlider
                                        anchors.left: hlLabel.right
                                        anchors.right: hlValue.left
                                        anchors.rightMargin: 14
                                        anchors.verticalCenter: parent.verticalCenter
                                        from: 0
                                        to: 0.30
                                        value: root.dAppearance("highlight").strength
                                        onMoved: v => root.dSetAppearance("highlight", "strength", Math.round(v * 1000) / 1000)
                                    }

                                    Text {
                                        id: hlValue
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 52
                                        horizontalAlignment: Text.AlignRight
                                        text: (root.dAppearance("highlight").strength * 100).toFixed(1) + "%"
                                        font.family: root.uiFont
                                        font.pixelSize: 13
                                        color: root.colText
                                    }
                                }
                            }

                            // ---- outline ----
                            Column {
                                width: parent.width
                                spacing: 12

                                Text {
                                    text: "Faint outline"
                                    font.family: root.uiFont
                                    font.pixelSize: 16
                                    color: root.colText
                                }

                                Text {
                                    width: parent.width
                                    wrapMode: Text.WordWrap
                                    text: "The card's border, the hairline under the folder block, and the rules in this window."
                                    font.family: root.uiFont
                                    font.pixelSize: 13
                                    color: root.colSubtle
                                }

                                CfgSourceRow {
                                    width: parent.width
                                    which: "outline"
                                }

                                Item {
                                    width: parent.width
                                    height: 30

                                    Text {
                                        id: outLabel
                                        anchors.left: parent.left
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 74
                                        text: "Opacity"
                                        font.family: root.uiFont
                                        font.pixelSize: 13
                                        color: root.colSubtle
                                    }

                                    CfgSlider {
                                        anchors.left: outLabel.right
                                        anchors.right: outValue.left
                                        anchors.rightMargin: 14
                                        anchors.verticalCenter: parent.verticalCenter
                                        from: 0
                                        to: 1
                                        value: root.dAppearance("outline").strength
                                        onMoved: v => root.dSetAppearance("outline", "strength", Math.round(v * 100) / 100)
                                    }

                                    Text {
                                        id: outValue
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 52
                                        horizontalAlignment: Text.AlignRight
                                        text: Math.round(root.dAppearance("outline").strength * 100) + "%"
                                        font.family: root.uiFont
                                        font.pixelSize: 13
                                        color: root.colText
                                    }
                                }
                            }

                            CfgButton {
                                label: "Reset to theme defaults"
                                symbol: "restart_alt"
                                onClicked: {
                                    root.draftAppearance = JSON.parse(JSON.stringify(root.appDefaults));
                                    root.dirty = true;
                                    root.configNote = "";
                                }
                            }

                            Text {
                                width: parent.width
                                wrapMode: Text.WordWrap
                                text: "Saved to ~/.config/omarchy-launcher/appearance.json. Delete that file and the launcher falls back to these defaults."
                                font.family: root.uiFont
                                font.pixelSize: 12
                                color: root.colSubtle
                                opacity: 0.75
                            }
                        }

                        // ---- preview ----
                        // This window is already a live preview of itself, but a launcher-shaped
                        // sample next to the controls is the comparison you actually care about —
                        // and it sits in the space the capped control column leaves free.
                        Column {
                            id: apprPreview
                            x: apprCol.x + apprCol.width + 48
                            y: 24
                            spacing: 12

                            Text {
                                text: "Preview"
                                font.family: root.uiFont
                                font.pixelSize: 16
                                color: root.colText
                            }

                            Rectangle {
                                    width: 340
                                    // 2 × 14 margin + 4 rows of 34 + 3 gaps of 2. Pinned rather
                                    // than derived because the sample rows are a fixed set.
                                    height: 170
                                    radius: 14
                                    color: root.colBg
                                    border.width: 2
                                    border.color: root.colBorder

                                    Column {
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 2

                                        Repeater {
                                            model: [
                                                {
                                                    n: "Development",
                                                    f: true,
                                                    s: false
                                                },
                                                {
                                                    n: "Media",
                                                    f: true,
                                                    s: false
                                                },
                                                {
                                                    n: "Signal",
                                                    f: false,
                                                    s: true
                                                },
                                                {
                                                    n: "Telegram",
                                                    f: false,
                                                    s: false
                                                }
                                            ]

                                            Rectangle {
                                                required property var modelData
                                                width: 312
                                                height: 34
                                                radius: 9
                                                color: modelData.s ? root.colSel : "transparent"

                                                Text {
                                                    id: pvIcon
                                                    anchors.left: parent.left
                                                    anchors.leftMargin: 12
                                                    anchors.verticalCenter: parent.verticalCenter
                                                    text: parent.modelData.f ? "folder" : "apps"
                                                    font.family: root.iconFont
                                                    font.pixelSize: 18
                                                    color: root.colAccent
                                                }

                                                Text {
                                                    anchors.left: pvIcon.right
                                                    anchors.leftMargin: 12
                                                    anchors.verticalCenter: parent.verticalCenter
                                                    text: parent.modelData.n
                                                    font.family: root.uiFont
                                                    font.pixelSize: 14
                                                    color: root.colText
                                                }
                                            }
                                        }
                                    }
                                }
                        }
                    }
                }
            }
        }
    }
}
