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

    // The reference's selection is a *whisper* — measured at +13/255 per channel over the card,
    // i.e. about a 5% text-coloured wash. Deriving it from the scheme instead of naming a colour
    // keeps that relationship in light mode and after every wallpaper recolour.
    readonly property color colSel: Qt.tint(colBg, Qt.rgba(colText.r, colText.g, colText.b, 0.075))
    readonly property color colHover: Qt.tint(colBg, Qt.rgba(colText.r, colText.g, colText.b, 0.04))
    readonly property color colBorder: Qt.rgba(colSubtle.r, colSubtle.g, colSubtle.b, 0.5)

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
                root.configError = "";
                root.goRoot();
            } catch (e) {
                root.configError = "categories.json is not valid: " + e;
                root.cats = [];
            }
        }
    }

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
    readonly property var rows: {
        const q = trimmedQuery;

        if (view === "cat") {
            const inCat = filterApps(catApps, q);
            const use = (q.length > 0 && inCat.length === 0 && currentCat?.all !== true) ? filterApps(allApps, q) : inCat;
            return use.map(a => ({
                kind: "app",
                app: a
            }));
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

                        // Restore a clean field every time the launcher maps.
                        Connections {
                            target: root
                            function onShownChanged() {
                                if (root.shown) {
                                    input.text = "";
                                    input.forceActiveFocus();
                                }
                            }
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
                                        visible: !rowRoot.isFolder
                                        asynchronous: true
                                        implicitSize: body.iconSize
                                        source: rowRoot.isFolder ? "" : Quickshell.iconPath(rowRoot.modelData.app.icon, "application-x-executable")
                                    }

                                    Text {
                                        anchors.fill: parent
                                        visible: rowRoot.isFolder
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                        text: rowRoot.isFolder ? (rowRoot.modelData.cat.icon ?? "folder") : ""
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
                                    text: rowRoot.isFolder ? rowRoot.modelData.cat.name : rowRoot.modelData.app.name
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
                                    visible: rowRoot.isFolder

                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: rowRoot.isFolder ? (root.catCounts[rowRoot.modelData.cat.id] ?? "") : ""
                                        color: root.colSubtle
                                        opacity: 0.7
                                        font.family: root.uiFont
                                        font.pixelSize: body.metaSize
                                    }

                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: "chevron_right"
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
                                return name + " is empty — add desktop ids to it in\n~/.config/omarchy-launcher/categories.json";
                            }
                        }
                    }
                }
            }
        }
    }
}
