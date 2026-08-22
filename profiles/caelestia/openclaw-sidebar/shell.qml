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
    property bool busy: false
    property int  elapsed: 0              // seconds the current turn has been running
    readonly property string base: "http://127.0.0.1:8787"
    property string currentSession: "agent:main:ai-flyout"   // active chat
    property bool   sessionsOpen: false                       // recent-chats drawer open

    Timer {
        interval: 1000; repeat: true; running: root.busy
        onTriggered: root.elapsed += 1
    }

    // --- palette (Caelestia-ish: AMOLED black + catppuccin accents) ---
    readonly property color colBg:      "#c2101018"   // more transparent so Hyprland blur frosts it more
    readonly property color colHeader:  "#cc1a1a26"
    readonly property color colUserBub: "#cb1e1e2e"
    readonly property color colAsstBub: "#00000000"
    readonly property color colAccent:  "#cba6f7"     // mauve
    readonly property color colText:    "#cdd6f4"
    readonly property color colSubtle:  "#9399b2"
    readonly property color colBorder:  "#2a2a3c"
    readonly property color colInputBg: "#b316161f"

    ListModel { id: chatModel }
    ListModel { id: sessionsModel }

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
        function show(): void   { root.shown = true }
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
    }

    function newChat() {
        root.currentSession = "agent:main:flyout-" + Date.now();
        chatModel.clear();
        root.sessionsOpen = false;
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
        var idx = chatModel.count - 1;

        var xhr = new XMLHttpRequest();
        xhr.open("POST", root.base + "/v1/chat/completions");
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.timeout = 620000;   // bridge agent turns can run up to ~600s
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== XMLHttpRequest.DONE) return;
            root.busy = false;
            var out = "";
            if (xhr.status === 200) {
                var lines = xhr.responseText.split("\n");
                for (var i = 0; i < lines.length; i++) {
                    var ln = lines[i];
                    if (ln.indexOf("data: ") !== 0) continue;
                    var data = ln.substring(6);
                    if (data === "[DONE]") continue;
                    try {
                        var j = JSON.parse(data);
                        var d = j.choices && j.choices[0] ? j.choices[0].delta : null;
                        if (d && d.content) out += d.content;
                    } catch (e) { /* ignore keep-alive/partial lines */ }
                }
            } else if (xhr.status === 0) {
                out = "**Can't reach the bridge.** Is `openclaw-ai-bridge.service` running?";
            } else {
                out = "**Error " + xhr.status + "**\n\n" + xhr.responseText;
            }
            chatModel.set(idx, { "role": "assistant", "content": out.length ? out : "(no reply)" });
            root.loadSessions();   // refresh recent-chats (new session / title / order)
            root.pumpQueue();      // send the next queued message, if any
        };
        xhr.send(JSON.stringify({
            "model": "openclaw",
            "session": root.currentSession,
            "messages": [{ "role": "user", "content": t }],
            "stream": true
        }));
    }

    PanelWindow {
        id: win
        visible: root.shown
        color: "transparent"
        implicitWidth: root.panelWidth

        anchors { left: true; top: true; bottom: true }
        exclusiveZone: root.pinned ? root.panelWidth : 0

        WlrLayershell.namespace: "openclaw-sidebar"
        WlrLayershell.layer: WlrLayer.Top
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand

        Rectangle {
            anchors.fill: parent
            color: root.colBg
            border.color: root.colBorder
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 0
                spacing: 0

                // ---------- header ----------
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 48
                    color: root.colHeader
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
            }
        }
    }
}
