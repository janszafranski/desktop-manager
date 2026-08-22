#!/usr/bin/env node
/*
 * openclaw-ai-bridge — loopback data layer for the OpenClaw sidebar / end4 flyout.
 *
 * Endpoints (127.0.0.1):
 *   POST /v1/chat/completions  OpenAI-compatible; forwards to `openclaw agent`.
 *                              Body may include "session": "<key>" to target a
 *                              specific session (default OPENCLAW_BRIDGE_SESSION).
 *   GET  /sessions             List stored sessions (recent-chats), newest first.
 *   GET  /history?session=<k>  Return the normalized transcript for one session.
 *
 * Streaming note: `openclaw agent` is one-shot, so replies arrive as a burst of
 * SSE deltas after the turn completes (no token-by-token). Real streaming needs
 * an operator WS connection (device-auth), out of scope here.
 *
 * Loopback-only by design: anything local that can POST here can run agent turns.
 */
'use strict';

const http = require('http');
const fs = require('fs');
const { execFile } = require('child_process');

const HOST = '127.0.0.1';
const PORT = parseInt(process.env.OPENCLAW_BRIDGE_PORT || '8787', 10);
const DEFAULT_SESSION = process.env.OPENCLAW_BRIDGE_SESSION || 'agent:main:ai-flyout';
const AGENT_TIMEOUT = process.env.OPENCLAW_BRIDGE_TIMEOUT || '600';
const MODEL_ID = 'openclaw';

// ---- helpers ---------------------------------------------------------------

function lastUserMessage(messages) {
  if (!Array.isArray(messages)) return '';
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m && m.role === 'user') {
      if (typeof m.content === 'string') return m.content;
      if (Array.isArray(m.content)) {
        return m.content.map(p => (typeof p === 'string' ? p : p.text || '')).join('');
      }
    }
  }
  return '';
}

function runAgent(message, sessionKey) {
  return new Promise((resolve, reject) => {
    execFile(
      'openclaw',
      ['agent', '--json', '--session-key', sessionKey, '--timeout', AGENT_TIMEOUT, '--message', message],
      { maxBuffer: 64 * 1024 * 1024, timeout: (parseInt(AGENT_TIMEOUT, 10) + 30) * 1000 },
      (err, stdout, stderr) => {
        if (err && !stdout) return reject(new Error(stderr || err.message));
        try {
          const d = JSON.parse(stdout);
          const text =
            d?.result?.meta?.finalAssistantVisibleText ||
            (Array.isArray(d?.result?.payloads)
              ? d.result.payloads.map(p => p.text || '').join('')
              : '') ||
            d?.summary ||
            '(no reply)';
          resolve(text);
        } catch (e) {
          reject(new Error('Could not parse openclaw output: ' + e.message + '\n' + stdout));
        }
      }
    );
  });
}

// Read `openclaw sessions list --json` once; returns the raw sessions array.
function sessionIndex() {
  return new Promise(resolve => {
    execFile(
      'openclaw',
      ['sessions', 'list', '--json', '--limit', '50'],
      { maxBuffer: 16 * 1024 * 1024 },
      (err, stdout) => {
        if (err || !stdout) return resolve([]);
        try {
          const d = JSON.parse(stdout);
          resolve(Array.isArray(d.sessions) ? d.sessions : []);
        } catch (e) {
          resolve([]);
        }
      }
    );
  });
}

// Parse a session .jsonl transcript into [{role, content}] (user/assistant only).
function parseTranscript(sessionFile) {
  const out = [];
  let raw;
  try {
    raw = fs.readFileSync(sessionFile, 'utf8');
  } catch (e) {
    return out;
  }
  for (const line of raw.split('\n')) {
    const t = line.trim();
    if (!t) continue;
    let o;
    try {
      o = JSON.parse(t);
    } catch (e) {
      continue;
    }
    if (o.type !== 'message' || !o.message) continue;
    const m = o.message;
    if (m.role !== 'user' && m.role !== 'assistant') continue;
    let text = '';
    const c = m.content;
    if (typeof c === 'string') text = c;
    else if (Array.isArray(c)) text = c.map(p => (typeof p === 'string' ? p : (p && p.text) || '')).join('');
    text = text.trim();
    if (!text) continue;
    // skip silent-token rows
    if (text === 'NO_REPLY' || text === 'no_reply') continue;
    out.push({ role: m.role, content: text });
  }
  return out;
}

function titleFor(sessionFile) {
  const msgs = parseTranscript(sessionFile);
  const firstUser = msgs.find(m => m.role === 'user');
  if (firstUser) return firstUser.content.replace(/\s+/g, ' ').slice(0, 60);
  return null;
}

function sendJson(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
  res.end(body);
}

function sseChunk(res, content) {
  const payload = {
    id: 'chatcmpl-openclaw',
    object: 'chat.completion.chunk',
    model: MODEL_ID,
    choices: [{ index: 0, delta: { content }, finish_reason: null }],
  };
  res.write('data: ' + JSON.stringify(payload) + '\n\n');
}

// ---- server ----------------------------------------------------------------

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${HOST}:${PORT}`);
  const path = url.pathname;

  if (req.method === 'GET' && path.startsWith('/v1/models')) {
    return sendJson(res, 200, { object: 'list', data: [{ id: MODEL_ID, object: 'model', owned_by: 'openclaw' }] });
  }

  // --- recent-chats list ---
  if (req.method === 'GET' && path === '/sessions') {
    sessionIndex().then(sessions => {
      const list = sessions
        .map(s => ({
          key: s.key,
          updatedAt: s.updatedAt || 0,
          sessionId: s.sessionId,
          title: titleFor(s.sessionFile) || s.key,
        }))
        .sort((a, b) => b.updatedAt - a.updatedAt);
      sendJson(res, 200, { sessions: list });
    });
    return;
  }

  // --- transcript for one session ---
  if (req.method === 'GET' && path === '/history') {
    const key = url.searchParams.get('session') || DEFAULT_SESSION;
    sessionIndex().then(sessions => {
      const s = sessions.find(x => x.key === key);
      if (!s) return sendJson(res, 200, { session: key, messages: [] });
      sendJson(res, 200, { session: key, messages: parseTranscript(s.sessionFile) });
    });
    return;
  }

  // --- chat turn ---
  if (req.method === 'POST' && path.startsWith('/v1/chat/completions')) {
    let body = '';
    req.on('data', c => {
      body += c;
      if (body.length > 16 * 1024 * 1024) req.destroy();
    });
    req.on('end', async () => {
      let msg = '';
      let sessionKey = DEFAULT_SESSION;
      try {
        const parsed = JSON.parse(body);
        msg = lastUserMessage(parsed.messages);
        if (parsed.session && typeof parsed.session === 'string') sessionKey = parsed.session;
      } catch (_) {
        /* fall through */
      }
      if (!msg) return sendJson(res, 400, { error: { message: 'No user message' } });

      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
        'Access-Control-Allow-Origin': '*',
      });
      try {
        const reply = await runAgent(msg, sessionKey);
        const parts = reply.match(/\S+\s*/g) || [reply];
        for (const p of parts) sseChunk(res, p);
      } catch (e) {
        sseChunk(res, '**Bridge error**: ' + e.message);
      }
      res.write('data: [DONE]\n\n');
      res.end();
    });
    return;
  }

  sendJson(res, 404, { error: { message: 'Not found' } });
});

server.listen(PORT, HOST, () => {
  console.log(
    `openclaw-ai-bridge listening on http://${HOST}:${PORT} ` +
      `(chat -> default session ${DEFAULT_SESSION}; +/sessions +/history)`
  );
});
