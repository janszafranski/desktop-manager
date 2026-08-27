//@ pragma UseQApplication
// OpenClaw sidebar — a standalone, pinnable left-docked chat panel that talks to
// the OpenClaw agent via the local bridge (127.0.0.1:8787).
// Shell-agnostic: runs as its own Quickshell instance (`qs -c openclaw-sidebar`),
// so it survives Caelestia/end4 package updates. Toggle over IPC:
//   qs -c openclaw-sidebar ipc call sidebar toggle
//
// v2: recent-chats drawer (☰), per-session history load, new chat, session-scoped
// sends — backed by bridge endpoints /sessions and /history.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Quickshell.Io

ShellRoot {
    id: root

    // --- state ---
    property bool shown: true
    property bool pinned: true            // pinned = reserve screen space (windows tile beside it)
    property int  panelWidth: 460         // matches end4; widen via IPC `widen`
    property int  scallop: 18             // concave corner radius = Hyprland decoration:rounding
    property bool remapping: false        // startup restack: unmap→remap to jump above the bar
    property int  restackCount: 0
    property bool busy: false
    property int  elapsed: 0              // seconds the current turn has been running
    readonly property string base: "http://127.0.0.1:8787"
    property string currentSession: "agent:main:ai-flyout"   // active chat
    property bool   sessionsOpen: false                       // recent-chats drawer open
    property string activity: ""                              // live tool/thinking status for the in-flight turn

    Timer {
        interval: 1000; repeat: true; running: root.busy
        onTriggered: root.elapsed += 1
    }

    // --- palette (Caelestia-ish: AMOLED black + catppuccin accents) ---
    readonly property color colBg:      "#ff000000"   // true black, fully opaque (Jan's call); blur disabled on this layer
    readonly property color colHeader:  "#ff000000"   // true black (was navy #cc1a1a26)
    readonly property color colUserBub: "#ff141414"   // near-black so user bubbles stay faintly visible (was navy #cb1e1e2e)
    readonly property color colAsstBub: "#00000000"
    readonly property color colAccent:  "#cba6f7"     // mauve
    readonly property color colText:    "#cdd6f4"
    readonly property color colSubtle:  "#9399b2"
    readonly property color colBorder:  "#ff222222"   // neutral dark grey separators (was navy #2a2a3c)
    readonly property color colInputBg: "#ff000000"   // true black (was navy #b316161f)

    ListModel { id: chatModel }
    ListModel { id: sessionsModel }

    // Persist the last-selected session to DISK so a full relaunch (process death, login,
    // caelestia restart) restores the chat you were on instead of resetting to the
    // hardcoded default above. An in-memory property can't survive process restart, which
    // is why the flyout kept reopening on the previous chat. (JsonAdapter <-> small file.)
    FileView {
        id: stateFile
        path: (Quickshell.env("XDG_STATE_HOME") || (Quickshell.env("HOME") + "/.local/state")) + "/quickshell/openclaw-sidebar.json"
        watchChanges: false
        JsonAdapter {
            id: stateAdapter
            property string lastSession: "agent:main:ai-flyout"
        }
        onLoaded: {
            if (stateAdapter.lastSession && stateAdapter.lastSession.length) {
                root.currentSession = stateAdapter.lastSession;
                root.loadHistory(root.currentSession);
            }
        }
        Component.onCompleted: reload()
    }

    // --- launcher shortcuts (buttons under the input; right-click → Preferences) ---
    property var  shortcuts: []           // [{label, cmd}]  cmd runs via `sh -lc`
    property bool prefsOpen: false

    // Human-editable JSON on disk so shortcuts survive relaunch and can be hand-tweaked.
    FileView {
        id: scFile
        path: (Quickshell.env("XDG_CONFIG_HOME") || (Quickshell.env("HOME") + "/.config")) + "/quickshell/openclaw-sidebar/shortcuts.json"
        watchChanges: false
        onLoaded: {
            try {
                var o = JSON.parse(scFile.text());
                root.shortcuts = (o && o.shortcuts && o.shortcuts.length) ? o.shortcuts : null;
                if (!root.shortcuts) root.seedShortcuts();
            } catch (e) { root.seedShortcuts(); }
        }
        onLoadFailed: root.seedShortcuts()
        Component.onCompleted: reload()
    }

    // icons live next to this config; terminal:true draws the icon in a "console" box
    readonly property string iconDir: (Quickshell.env("XDG_CONFIG_HOME") || (Quickshell.env("HOME") + "/.config")) + "/quickshell/openclaw-sidebar/icons/"
    function seedShortcuts() {
        // No native Linux Claude desktop app or `askgpt` binary exist → web app via xdg-open
        // (respects the Floorp default) and tgpt (free, no key) for the GPT CLI.
        root.shortcuts = [
            { "label": "Claude CLI",  "cmd": "kitty claude",                 "icon": iconDir + "claude.svg", "terminal": true },
            { "label": "Claude GUI",  "cmd": "xdg-open https://claude.ai",   "icon": iconDir + "claude.svg", "terminal": false },
            { "label": "AskGPT CLI",  "cmd": "kitty tgpt -i",                "icon": iconDir + "openai.svg", "terminal": true },
            { "label": "ChatGPT GUI", "cmd": "xdg-open https://chatgpt.com", "icon": iconDir + "openai.svg", "terminal": false },
            { "label": "Jan",         "cmd": "jan",                          "icon": iconDir + "jan.png",    "terminal": false }
        ];
        root.saveShortcuts();
    }
    function saveShortcuts() {
        scFile.setText(JSON.stringify({ "shortcuts": root.shortcuts }, null, 2));
    }
    function launch(cmd) {
        if (cmd && cmd.trim().length) Quickshell.execDetached(["sh", "-lc", cmd]);
    }
    function addShortcut(label, cmd) {
        if (!label.trim().length || !cmd.trim().length) return;
        root.shortcuts = root.shortcuts.concat([{ "label": label.trim(), "cmd": cmd.trim() }]);
        root.saveShortcuts();
    }
    function removeShortcut(i) {
        var a = root.shortcuts.slice();
        a.splice(i, 1);
        root.shortcuts = a;
        root.saveShortcuts();
    }

    // --- streaming chat turn ---
    // QML's XMLHttpRequest buffers the whole response and won't expose partial
    // text during LOADING, so SSE deltas can't render token-by-token through it.
    // Instead we run `curl -N` via a Process and parse stdout line-by-line as it
    // arrives (SplitParser), updating the message live.
    property string streamBuf: ""
    property int    curIdx: -1

    Process {
        id: chatProc
        stdout: SplitParser {
            splitMarker: "\n"
            // A segment may hold several lines or a stray leading blank line, so scan
            // every line for a `data:` payload rather than assuming one clean line.
            onRead: function(seg) {
                var lines = seg.split("\n");
                var changed = false;
                for (var i = 0; i < lines.length; i++) {
                    var ln = lines[i];
                    if (ln.indexOf("data:") !== 0) continue;
                    var data = ln.replace(/^data:\s*/, "");
                    if (data === "" || data === "[DONE]") continue;
                    try {
                        var j = JSON.parse(data);
                        var d = j.choices && j.choices[0] ? j.choices[0].delta : null;
                        if (!d) continue;
                        // Real assistant text: append to the bubble and clear the activity line.
                        if (typeof d.content === "string" && d.content.length) {
                            root.streamBuf += d.content;
                            root.activity = "";
                            changed = true;
                        // Tool/thinking activity (bridge-only field): show live, don't persist.
                        } else if (typeof d.status === "string") {
                            root.activity = d.status;
                        }
                    } catch (e) { /* partial line — completes on next read */ }
                }
                if (changed)
                    chatModel.set(root.curIdx, { "role": "assistant", "content": root.streamBuf });
            }
        }
        onExited: function(exitCode, exitStatus) {
            root.busy = false;
            root.activity = "";
            if (root.curIdx >= 0 && root.streamBuf.length === 0)
                chatModel.set(root.curIdx, { "role": "assistant",
                    "content": exitCode === 0 ? "(no reply)"
                        : "**Can't reach the bridge.** Is `openclaw-ai-bridge.service` running? (curl exit " + exitCode + ")" });
            root.loadSessions();   // refresh recent-chats
            root.pumpQueue();      // send next queued message, if any
        }
    }

    // On startup fetch history + recent chats. The bridge (systemd) may not be up
    // yet at login, so retry a few times until data arrives, then stop.
    property int bootTries: 0
    Timer {
        id: bootTimer
        interval: 1200; repeat: true; running: true
        onTriggered: {
            root.bootTries += 1;
            root.loadHistory(root.currentSession);
            root.loadSessions();
            if (sessionsModel.count > 0 || chatModel.count > 0 || root.bootTries >= 6)
                bootTimer.running = false;
        }
    }

    IpcHandler {
        target: "sidebar"
        function toggle(): void { root.shown = !root.shown }
        function show(): void   { root.shown = true; if (!root.busy) root.loadHistory(root.currentSession) }  // always reopen on the current chat
        function hide(): void   { root.shown = false }
        function pin(): void    { root.pinned = !root.pinned }
        function lock(): void   { root.shown = true; root.pinned = true }   // show + pin (CLI hand-off return)
        function widen(): void  { root.panelWidth = (root.panelWidth >= 620 ? 460 : 620) }
        function clear(): void  { chatModel.clear() }
        function reload(): void { root.loadHistory(root.currentSession); root.loadSessions() }  // re-sync after CLI edits
    }

    // ---- data layer (bridge /sessions, /history) --------------------------

    function loadSessions() {
        var xhr = new XMLHttpRequest();
        xhr.open("GET", root.base + "/sessions");
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== XMLHttpRequest.DONE || xhr.status !== 200) return;
            try {
                var d = JSON.parse(xhr.responseText);
                sessionsModel.clear();
                for (var i = 0; i < d.sessions.length; i++) {
                    var s = d.sessions[i];
                    sessionsModel.append({ "key": s.key, "title": s.title || s.key });
                }
            } catch (e) { /* ignore */ }
        };
        xhr.send();
    }

    function loadHistory(key) {
        var xhr = new XMLHttpRequest();
        xhr.open("GET", root.base + "/history?session=" + encodeURIComponent(key));
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== XMLHttpRequest.DONE || xhr.status !== 200) return;
            try {
                var d = JSON.parse(xhr.responseText);
                chatModel.clear();
                for (var i = 0; i < d.messages.length; i++)
                    chatModel.append({ "role": d.messages[i].role, "content": d.messages[i].content });
            } catch (e) { /* ignore */ }
        };
        xhr.send();
    }

    function switchSession(key) {
        root.currentSession = key;
        root.sessionsOpen = false;
        root.loadHistory(key);
        stateAdapter.lastSession = key;   // persist so a relaunch reopens THIS chat
        stateFile.writeAdapter();
    }

    function newChat() {
        root.currentSession = "agent:main:flyout-" + Date.now();
        chatModel.clear();
        root.sessionsOpen = false;
        stateAdapter.lastSession = root.currentSession;
        stateFile.writeAdapter();
    }

    // ---- send queue (input never blocks; sends run sequentially) -----------
    property var pending: []

    function sendMessage(text) {
        var t = (text || "").trim();
        if (t.length === 0) return;
        chatModel.append({ "role": "user", "content": t });
        root.pending.push(t);
        root.pumpQueue();
    }

    function pumpQueue() {
        if (root.busy || root.pending.length === 0) return;
        var t = root.pending.shift();
        root.busy = true;
        root.elapsed = 0;
        chatModel.append({ "role": "assistant", "content": "…" });
        root.curIdx = chatModel.count - 1;
        root.streamBuf = "";
        root.activity = "";

        var payload = JSON.stringify({
            "model": "openclaw",
            "session": root.currentSession,
            "messages": [{ "role": "user", "content": t }],
            "stream": true
        });
        // curl -N = unbuffered; payload passed as a single argv (no shell, no quoting issues)
        chatProc.command = ["curl", "-N", "-s", "-X", "POST",
            root.base + "/v1/chat/completions",
            "-H", "Content-Type: application/json",
            "-d", payload];
        chatProc.running = true;
    }

    PanelWindow {
        id: win
        visible: root.shown && !root.remapping
        color: "transparent"
        // extra `scallop` px on the right so the concave corner fillets can overhang the
        // desktop and give IT rounded corners. exclusiveZone still reserves only panelWidth.
        implicitWidth: root.panelWidth + root.scallop

        anchors { left: true; top: true; bottom: true }
        exclusiveZone: root.pinned ? root.panelWidth : 0
        // input only over the real panel; the overhang strip stays click-through to the desktop
        mask: Region { x: 0; y: 0; width: root.panelWidth; height: win.height }

        WlrLayershell.namespace: "openclaw-sidebar"
        WlrLayershell.layer: WlrLayer.Top
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand

        // Startup restack: the flyout autostarts before Caelestia's bar, and both live on the
        // `top` layer where z-order = map order — so the bar maps last and overlays us. Briefly
        // unmap→remap a couple of times over the first few seconds (after the bar has mapped) to
        // jump back to the top of the layer. This is the automated version of "close and reopen".
        Timer {
            id: restackTimer
            interval: 2500; running: true; repeat: true
            onTriggered: {
                root.remapping = true;
                unmapTimer.restart();
                root.restackCount++;
                if (root.restackCount >= 2) running = false;   // fires at ~2.5s and ~5s
            }
        }
        Timer {
            id: unmapTimer
            interval: 150; running: false; repeat: false
            onTriggered: root.remapping = false
        }

        // --- panel body: square right edge; the two right corners are drawn as concave
        //     fillets below so the adjacent desktop appears to have 18px rounded corners ---
        Rectangle {
            id: bg
            anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
            width: root.panelWidth
            color: root.colBg
            border.color: root.colBorder
            border.width: 1

            // top-right concave fillet (rounds the desktop's top-left corner)
            Canvas {
                width: root.scallop; height: root.scallop
                x: bg.width; y: 0
                onPaint: {
                    var c = getContext("2d");
                    c.clearRect(0, 0, width, height);
                    c.fillStyle = root.colBg;
                    c.fillRect(0, 0, width, height);
                    c.globalCompositeOperation = "destination-out";
                    c.beginPath(); c.arc(width, height, root.scallop, 0, 2 * Math.PI); c.fill();
                }
            }
            // bottom-right concave fillet (rounds the desktop's bottom-left corner)
            Canvas {
                width: root.scallop; height: root.scallop
                x: bg.width; y: bg.height - root.scallop
                onPaint: {
                    var c = getContext("2d");
                    c.clearRect(0, 0, width, height);
                    c.fillStyle = root.colBg;
                    c.fillRect(0, 0, width, height);
                    c.globalCompositeOperation = "destination-out";
                    c.beginPath(); c.arc(width, 0, root.scallop, 0, 2 * Math.PI); c.fill();
                }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 0
                spacing: 0

                // ---------- header ----------
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 48
                    color: root.colHeader
                    topRightRadius: 18   // match the panel's scalloped top-right corner
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 8
                        spacing: 6
                        // recent chats toggle
                        ToolButton {
                            text: "☰"
                            onClicked: { root.sessionsOpen = !root.sessionsOpen; if (root.sessionsOpen) root.loadSessions(); }
                            ToolTip.text: "Recent chats"; ToolTip.visible: hovered
                            contentItem: Label { text: parent.text; color: root.sessionsOpen ? root.colAccent : root.colSubtle; font.pixelSize: 16; horizontalAlignment: Text.AlignHCenter }
                            background: Rectangle { color: parent.hovered ? root.colBorder : "transparent"; radius: 6 }
                        }
                        Rectangle { width: 8; height: 8; radius: 4; color: root.colAccent }
                        Label {
                            text: "OpenClaw"
                            color: root.colText
                            font.pixelSize: 15
                            font.bold: true
                            Layout.fillWidth: true
                        }
                        Label {
                            visible: root.busy
                            text: "thinking… " + root.elapsed + "s" + (root.pending.length > 0 ? " · " + root.pending.length + " queued" : "")
                            color: root.colSubtle
                            font.pixelSize: 12
                        }
                        // new chat
                        ToolButton {
                            text: "✚"
                            onClicked: root.newChat()
                            ToolTip.text: "New chat"; ToolTip.visible: hovered
                            contentItem: Label { text: parent.text; color: root.colSubtle; font.pixelSize: 15; horizontalAlignment: Text.AlignHCenter }
                            background: Rectangle { color: parent.hovered ? root.colBorder : "transparent"; radius: 6 }
                        }
                        // pop the same conversation out to a terminal (CLI), then hide the flyout
                        ToolButton {
                            text: "↗"
                            onClicked: {
                                Quickshell.execDetached(["alacritty", "--title", "OpenClaw", "-e",
                                                         "/home/jan/.local/bin/openclaw-cli-chat.sh"]);
                                root.shown = false;
                            }
                            ToolTip.text: "Continue in terminal (CLI)"; ToolTip.visible: hovered
                            contentItem: Label { text: parent.text; color: root.colSubtle; font.pixelSize: 16; horizontalAlignment: Text.AlignHCenter }
                            background: Rectangle { color: parent.hovered ? root.colBorder : "transparent"; radius: 6 }
                        }
                        // pin
                        ToolButton {
                            text: root.pinned ? "📌" : "📍"
                            onClicked: root.pinned = !root.pinned
                            ToolTip.text: root.pinned ? "Pinned (reserving space)" : "Floating (overlay)"; ToolTip.visible: hovered
                            contentItem: Label { text: parent.text; color: root.pinned ? root.colAccent : root.colSubtle; font.pixelSize: 15; horizontalAlignment: Text.AlignHCenter }
                            background: Rectangle { color: parent.hovered ? root.colBorder : "transparent"; radius: 6 }
                        }
                    }
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: root.colBorder }

                // ---------- recent-chats drawer ----------
                Rectangle {
                    Layout.fillWidth: true
                    visible: root.sessionsOpen
                    color: root.colHeader
                    Layout.preferredHeight: root.sessionsOpen ? Math.min(sessionsList.contentHeight + 46, 300) : 0
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 6
                        RowLayout {
                            Layout.fillWidth: true
                            Label { text: "Recent chats"; color: root.colSubtle; font.pixelSize: 12; font.bold: true; Layout.fillWidth: true }
                            ToolButton {
                                text: "✚ New chat"
                                onClicked: root.newChat()
                                contentItem: Label { text: parent.text; color: root.colAccent; font.pixelSize: 12 }
                                background: Rectangle { color: parent.hovered ? root.colBorder : "transparent"; radius: 6 }
                            }
                        }
                        ListView {
                            id: sessionsList
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: sessionsModel
                            spacing: 2
                            boundsBehavior: Flickable.StopAtBounds
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            delegate: Rectangle {
                                width: ListView.view ? ListView.view.width : 0
                                implicitHeight: 34
                                radius: 8
                                color: model.key === root.currentSession ? root.colBorder : (sma.containsMouse ? "#1affffff" : "transparent")
                                Label {
                                    anchors.fill: parent
                                    anchors.leftMargin: 10; anchors.rightMargin: 10
                                    verticalAlignment: Text.AlignVCenter
                                    text: model.title
                                    color: model.key === root.currentSession ? root.colAccent : root.colText
                                    font.pixelSize: 13
                                    elide: Text.ElideRight
                                }
                                MouseArea {
                                    id: sma
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onClicked: root.switchSession(model.key)
                                }
                            }
                        }
                    }
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: root.colBorder; visible: root.sessionsOpen }

                // ---------- message list ----------
                ListView {
                    id: list
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: chatModel
                    spacing: 10
                    topMargin: 12
                    bottomMargin: 12
                    leftMargin: 12
                    rightMargin: 12
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    onCountChanged: Qt.callLater(function(){ list.positionViewAtEnd() })

                    delegate: Item {
                        width: ListView.view ? ListView.view.width - 24 : 0
                        implicitHeight: bubble.implicitHeight
                        property bool isUser: model.role === "user"

                        Rectangle {
                            id: bubble
                            width: Math.min(parent.width, parent.width * 0.92)
                            x: isUser ? parent.width - width : 0
                            implicitHeight: msg.implicitHeight + 18
                            radius: 12
                            color: isUser ? root.colUserBub : root.colAsstBub
                            border.color: isUser ? "transparent" : root.colBorder
                            border.width: isUser ? 0 : 1

                            TextEdit {
                                id: msg
                                anchors.fill: parent
                                anchors.margins: 9
                                text: model.content
                                textFormat: TextEdit.MarkdownText
                                color: root.colText
                                font.pixelSize: 14
                                wrapMode: TextEdit.Wrap
                                readOnly: true
                                selectByMouse: true
                                selectionColor: root.colAccent
                            }
                        }
                    }
                }
                // ---------- live activity (tool/thinking) ----------
                Rectangle {
                    Layout.fillWidth: true
                    visible: root.busy && root.activity.length > 0
                    color: root.colHeader
                    implicitHeight: visible ? actLabel.implicitHeight + 12 : 0
                    Label {
                        id: actLabel
                        anchors.fill: parent
                        anchors.leftMargin: 14; anchors.rightMargin: 14
                        anchors.topMargin: 6;  anchors.bottomMargin: 6
                        text: root.activity
                        color: root.colSubtle
                        font.pixelSize: 12
                        font.italic: true
                        elide: Text.ElideRight
                        verticalAlignment: Text.AlignVCenter
                    }
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: root.colBorder }

                // ---------- input ----------
                Rectangle {
                    Layout.fillWidth: true
                    color: root.colHeader
                    implicitHeight: inputRow.implicitHeight + 16
                    RowLayout {
                        id: inputRow
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8

                        Rectangle {
                            Layout.fillWidth: true
                            radius: 10
                            color: root.colInputBg
                            border.color: input.activeFocus ? root.colAccent : root.colBorder
                            border.width: 1
                            implicitHeight: Math.min(Math.max(input.implicitHeight + 14, 40), 160)

                            ScrollView {
                                anchors.fill: parent
                                anchors.margins: 6
                                TextArea {
                                    id: input
                                    placeholderText: "Message OpenClaw…"
                                    placeholderTextColor: root.colSubtle
                                    color: root.colText
                                    font.pixelSize: 14
                                    wrapMode: TextArea.Wrap
                                    background: null
                                    selectByMouse: true
                                    selectionColor: root.colAccent
                                    // input stays live even while a turn is in flight; sends queue
                                    // Enter sends, Shift+Enter = newline
                                    Keys.onPressed: function(ev) {
                                        if ((ev.key === Qt.Key_Return || ev.key === Qt.Key_Enter) && !(ev.modifiers & Qt.ShiftModifier)) {
                                            root.sendMessage(input.text);
                                            input.clear();
                                            ev.accepted = true;
                                        } else if (ev.key === Qt.Key_Escape) {
                                            if (!root.pinned) root.shown = false;
                                            ev.accepted = true;
                                        }
                                    }
                                }
                            }
                        }

                        Button {
                            text: "Send"
                            enabled: input.text.trim().length > 0
                            onClicked: { root.sendMessage(input.text); input.clear(); }
                            contentItem: Label {
                                text: parent.text
                                color: parent.enabled ? "#11111b" : root.colSubtle
                                font.pixelSize: 13; font.bold: true
                                horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle {
                                radius: 10
                                color: parent.enabled ? (parent.down ? Qt.darker(root.colAccent, 1.2) : root.colAccent) : root.colBorder
                            }
                            Layout.preferredHeight: 40
                        }
                    }
                }

                // ---------- launcher bar (icons launch; the + on the right edits shortcuts) ----------
                Rectangle {
                    Layout.fillWidth: true
                    color: root.colHeader
                    bottomRightRadius: 18   // now the panel's scalloped bottom-right corner
                    implicitHeight: Math.max(launchFlow.implicitHeight, 38) + 12

                    Flow {
                        id: launchFlow
                        anchors { left: parent.left; right: addBtn.left; verticalCenter: parent.verticalCenter }
                        anchors.leftMargin: 8; anchors.rightMargin: 6
                        spacing: 6

                        Repeater {
                            model: root.shortcuts
                            delegate: Button {
                                id: scBtn
                                required property var modelData
                                required property int index
                                readonly property bool hasIcon: modelData.icon !== undefined && ("" + modelData.icon).length > 0
                                readonly property bool isTerm: modelData.terminal === true
                                onClicked: root.launch(modelData.cmd)
                                ToolTip.text: modelData.label + " — " + modelData.cmd; ToolTip.visible: hovered; ToolTip.delay: 500
                                padding: 0
                                implicitWidth: 46; implicitHeight: 38
                                contentItem: Item {
                                    // text fallback for custom shortcuts that have no icon set
                                    Label {
                                        anchors.centerIn: parent
                                        visible: !scBtn.hasIcon
                                        text: modelData.label; color: root.colText; font.pixelSize: 12
                                    }
                                    // plain GUI icon
                                    Image {
                                        anchors.centerIn: parent
                                        visible: scBtn.hasIcon && !scBtn.isTerm
                                        source: scBtn.hasIcon ? "file://" + modelData.icon : ""
                                        sourceSize.width: 22; sourceSize.height: 22
                                        width: 22; height: 22; smooth: true; mipmap: true
                                    }
                                    // CLI: same icon inside a bordered box that reads as a console
                                    Rectangle {
                                        anchors.centerIn: parent
                                        visible: scBtn.hasIcon && scBtn.isTerm
                                        width: 30; height: 26; radius: 4
                                        color: "transparent"
                                        border.color: root.colSubtle; border.width: 1
                                        Image {
                                            anchors.centerIn: parent
                                            source: scBtn.hasIcon ? "file://" + modelData.icon : ""
                                            sourceSize.width: 15; sourceSize.height: 15
                                            width: 15; height: 15; smooth: true; mipmap: true
                                        }
                                        // tiny prompt glyph in the corner to sell the "terminal" read
                                        Text {
                                            anchors { left: parent.left; bottom: parent.bottom; leftMargin: 2 }
                                            text: "›"; color: root.colSubtle; font.pixelSize: 10; font.bold: true
                                        }
                                    }
                                }
                                background: Rectangle {
                                    radius: 8
                                    color: scBtn.down ? Qt.darker(root.colAccent, 1.3)
                                         : scBtn.hovered ? root.colBorder : "#ff141414"
                                    border.color: root.colBorder; border.width: 1
                                }
                            }
                        }
                    }

                    // add/edit shortcuts — pinned to the right edge of the bar
                    Button {
                        id: addBtn
                        anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                        anchors.rightMargin: 8
                        implicitWidth: 34; implicitHeight: 34
                        padding: 0
                        onClicked: root.prefsOpen = true
                        ToolTip.text: "Add / edit shortcuts"; ToolTip.visible: hovered; ToolTip.delay: 500
                        contentItem: Label {
                            text: "+"; color: root.colAccent
                            font.pixelSize: 20; font.bold: true
                            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle {
                            radius: 8
                            color: addBtn.down ? Qt.darker(root.colAccent, 1.3)
                                 : addBtn.hovered ? root.colBorder : "#ff141414"
                            border.color: root.colBorder; border.width: 1
                        }
                    }
                }
            }

            // ---------- preferences overlay (manage launcher shortcuts) ----------
            Rectangle {
                anchors.fill: parent
                visible: root.prefsOpen
                z: 100
                color: "#cc000000"          // scrim
                MouseArea { anchors.fill: parent; onClicked: {} }   // swallow clicks to the scrim

                Rectangle {
                    anchors.centerIn: parent
                    width: Math.min(parent.width - 32, root.panelWidth - 24)
                    implicitHeight: prefsCol.implicitHeight + 28
                    radius: 14
                    color: root.colBg
                    border.color: root.colBorder; border.width: 1

                    ColumnLayout {
                        id: prefsCol
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 10

                        Label { text: "Launcher shortcuts"; color: root.colText; font.pixelSize: 15; font.bold: true }
                        Label {
                            text: "Left-click a button to launch. Command runs via sh -lc."
                            color: root.colSubtle; font.pixelSize: 11
                            Layout.fillWidth: true; wrapMode: Text.Wrap
                        }

                        Repeater {
                            model: root.shortcuts
                            delegate: RowLayout {
                                required property var modelData
                                required property int index
                                Layout.fillWidth: true
                                spacing: 8

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 0
                                    Label { text: modelData.label; color: root.colText; font.pixelSize: 13; font.bold: true }
                                    Label {
                                        text: modelData.cmd; color: root.colSubtle; font.pixelSize: 11
                                        elide: Text.ElideRight; Layout.fillWidth: true
                                    }
                                }
                                Button {
                                    text: "✕"
                                    onClicked: root.removeShortcut(index)
                                    implicitWidth: 30; implicitHeight: 30
                                    contentItem: Label { text: parent.text; color: root.colSubtle; font.pixelSize: 14; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                    background: Rectangle { radius: 6; color: parent.hovered ? "#ff3a1420" : "transparent"; border.color: root.colBorder; border.width: 1 }
                                }
                            }
                        }

                        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: root.colBorder }

                        // add form
                        TextField {
                            id: newLabel
                            Layout.fillWidth: true
                            placeholderText: "Label (e.g. Btop)"
                            placeholderTextColor: root.colSubtle
                            color: root.colText; font.pixelSize: 13
                            background: Rectangle { radius: 8; color: root.colInputBg; border.color: newLabel.activeFocus ? root.colAccent : root.colBorder; border.width: 1 }
                        }
                        TextField {
                            id: newCmd
                            Layout.fillWidth: true
                            placeholderText: "Command (e.g. kitty btop)"
                            placeholderTextColor: root.colSubtle
                            color: root.colText; font.pixelSize: 13
                            background: Rectangle { radius: 8; color: root.colInputBg; border.color: newCmd.activeFocus ? root.colAccent : root.colBorder; border.width: 1 }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Button {
                                text: "Add"
                                enabled: newLabel.text.trim().length > 0 && newCmd.text.trim().length > 0
                                onClicked: { root.addShortcut(newLabel.text, newCmd.text); newLabel.clear(); newCmd.clear(); }
                                contentItem: Label { text: parent.text; color: parent.enabled ? "#11111b" : root.colSubtle; font.pixelSize: 13; font.bold: true; horizontalAlignment: Text.AlignHCenter }
                                background: Rectangle { radius: 8; color: parent.enabled ? root.colAccent : root.colBorder }
                                leftPadding: 16; rightPadding: 16; topPadding: 7; bottomPadding: 7
                            }
                            Item { Layout.fillWidth: true }
                            Button {
                                text: "Close"
                                onClicked: root.prefsOpen = false
                                contentItem: Label { text: parent.text; color: root.colText; font.pixelSize: 13; horizontalAlignment: Text.AlignHCenter }
                                background: Rectangle { radius: 8; color: parent.hovered ? root.colBorder : "transparent"; border.color: root.colBorder; border.width: 1 }
                                leftPadding: 16; rightPadding: 16; topPadding: 7; bottomPadding: 7
                            }
                        }
                    }
                }
            }
        }
    }
}
