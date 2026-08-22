//@ pragma UseQApplication
// OpenClaw sidebar — a standalone, pinnable left-docked chat panel that talks to
// the OpenClaw agent via the local bridge (127.0.0.1:8787, OpenAI-compatible SSE).
// Shell-agnostic: runs as its own Quickshell instance (`qs -c openclaw-sidebar`),
// so it survives Caelestia/end4 package updates. Toggle over IPC:
//   qs -c openclaw-sidebar ipc call sidebar toggle
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
    readonly property string endpoint: "http://127.0.0.1:8787/v1/chat/completions"

    // --- palette (Caelestia-ish: AMOLED black + catppuccin accents) ---
    readonly property color colBg:      "#e6101018"   // semi-transparent so Hyprland blur frosts it
    readonly property color colHeader:  "#f21a1a26"
    readonly property color colUserBub: "#cb1e1e2e"
    readonly property color colAsstBub: "#00000000"
    readonly property color colAccent:  "#cba6f7"     // mauve
    readonly property color colText:    "#cdd6f4"
    readonly property color colSubtle:  "#9399b2"
    readonly property color colBorder:  "#2a2a3c"
    readonly property color colInputBg: "#cc16161f"

    ListModel { id: chatModel }

    IpcHandler {
        target: "sidebar"
        function toggle(): void { root.shown = !root.shown }
        function show(): void   { root.shown = true }
        function hide(): void   { root.shown = false }
        function pin(): void    { root.pinned = !root.pinned }
        function widen(): void  { root.panelWidth = (root.panelWidth >= 620 ? 460 : 620) }
        function clear(): void  { chatModel.clear() }
    }

    // Queue of user messages waiting to be sent. Input is never blocked; if a turn
    // is already in flight, new messages queue and fire sequentially as it frees up
    // (the agent session is sequential, so we must not send concurrently).
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
        chatModel.append({ "role": "assistant", "content": "…" });
        var idx = chatModel.count - 1;

        var xhr = new XMLHttpRequest();
        xhr.open("POST", root.endpoint);
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
            root.pumpQueue();   // send the next queued message, if any
        };
        xhr.send(JSON.stringify({
            "model": "openclaw",
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
                        anchors.leftMargin: 14
                        anchors.rightMargin: 8
                        spacing: 8
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
                            text: "thinking…" + (root.pending.length > 0 ? " · " + root.pending.length + " queued" : "")
                            color: root.colSubtle
                            font.pixelSize: 12
                        }
                        // widen
                        ToolButton {
                            text: "⇔"
                            onClicked: root.panelWidth = (root.panelWidth >= 620 ? 460 : 620)
                            ToolTip.text: "Toggle width"; ToolTip.visible: hovered
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
                        // clear
                        ToolButton {
                            text: "🗑"
                            onClicked: chatModel.clear()
                            ToolTip.text: "Clear conversation"; ToolTip.visible: hovered
                            contentItem: Label { text: parent.text; color: root.colSubtle; font.pixelSize: 14; horizontalAlignment: Text.AlignHCenter }
                            background: Rectangle { color: parent.hovered ? root.colBorder : "transparent"; radius: 6 }
                        }
                    }
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: root.colBorder }

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
