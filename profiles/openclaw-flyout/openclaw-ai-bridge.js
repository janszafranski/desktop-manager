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
const { execFile, spawn } = require('child_process');

const HOST = '127.0.0.1';
const PORT = parseInt(process.env.OPENCLAW_BRIDGE_PORT || '8787', 10);
const DEFAULT_SESSION = process.env.OPENCLAW_BRIDGE_SESSION || 'agent:main:ai-flyout';
const AGENT_TIMEOUT = process.env.OPENCLAW_BRIDGE_TIMEOUT || '600';
const MODEL_ID = 'openclaw';
// How many times to retry a turn that failed for a transient reason (gateway
// restart / OOM kill / provider failover mid-turn). The gateway auto-clears the
// session after such a failure, so a fresh retry almost always succeeds.
const AGENT_RETRIES = parseInt(process.env.OPENCLAW_BRIDGE_RETRIES || '1', 10);
const RETRY_DELAY_MS = parseInt(process.env.OPENCLAW_BRIDGE_RETRY_DELAY_MS || '1500', 10);

// Errors worth retrying: the gateway was restarted/killed or the provider failed
// over mid-turn. Not user-visible content errors — those should surface as-is.
const TRANSIENT_RE = /FailoverError|Claude CLI failed|gateway (restart|shutdown|restarting)|UNAVAILABLE|ECONNREFUSED|ECONNRESET|socket hang up|EPIPE|active run/i;

const sleep = ms => new Promise(r => setTimeout(r, ms));

// Real token-by-token streaming via the supported ACP bridge (`openclaw acp`),
// unless disabled. Falls back to the one-shot execFile path automatically.
const STREAM_ENABLED = (process.env.OPENCLAW_BRIDGE_STREAM || '1') !== '0';
// Auto-approve tool permission requests during a turn to preserve parity with
// the one-shot `openclaw agent` path (the flyout session is already tool-capable
// and loopback-only). Set OPENCLAW_BRIDGE_ACP_APPROVE=0 to deny instead.
const ACP_AUTO_APPROVE = (process.env.OPENCLAW_BRIDGE_ACP_APPROVE || '1') !== '0';
const ACP_WORKSPACE =
  process.env.OPENCLAW_BRIDGE_CWD || `${process.env.HOME || '/root'}/.openclaw/workspace`;

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

// Run a turn, retrying once (by default) on transient failures — a gateway
// restart, OOM kill, or provider failover that interrupted the in-flight turn.
// The gateway clears the session after a failed reused turn, so the retry starts
// clean and normally succeeds; this keeps the flyout from surfacing blips.
async function runAgentResilient(message, sessionKey) {
  let lastErr;
  for (let attempt = 0; attempt <= AGENT_RETRIES; attempt++) {
    try {
      return await runAgent(message, sessionKey);
    } catch (e) {
      lastErr = e;
      const transient = TRANSIENT_RE.test(e && e.message ? e.message : '');
      if (!transient || attempt === AGENT_RETRIES) break;
      console.log(
        `[bridge] transient turn failure (attempt ${attempt + 1}/${AGENT_RETRIES + 1}), retrying in ${RETRY_DELAY_MS}ms: ${e.message.split('\n')[0]}`
      );
      await sleep(RETRY_DELAY_MS);
    }
  }
  throw lastErr;
}

// Stream a turn through the ACP bridge, invoking onDelta(text) for each
// agent_message_chunk as it arrives. Resolves with the number of characters
// streamed. Rejects on spawn/protocol failure (caller falls back to one-shot).
// `onDelta` is only ever called with visible assistant content — thinking
// (agent_thought_chunk) and tool events are intentionally not forwarded.
function runAgentStreaming(message, sessionKey, onDelta) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (fn, arg) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      try { child.stdin.end(); } catch (_) {}
      try { child.kill(); } catch (_) {}
      fn(arg);
    };

    const child = spawn('openclaw', ['acp', '--session', sessionKey], {
      stdio: ['pipe', 'pipe', 'ignore'],
    });
    child.on('error', e => finish(reject, new Error('acp spawn failed: ' + e.message)));

    const timer = setTimeout(
      () => finish(reject, new Error('acp turn timeout')),
      (parseInt(AGENT_TIMEOUT, 10) + 30) * 1000
    );

    let streamed = 0;
    let nextId = 1;
    const pending = new Map();
    const send = obj => {
      try { child.stdin.write(JSON.stringify(obj) + '\n'); } catch (_) {}
    };
    const rpc = (method, params) =>
      new Promise((res, rej) => {
        const id = nextId++;
        pending.set(id, { res, rej });
        send({ jsonrpc: '2.0', id, method, params });
      });

    let buf = '';
    child.stdout.on('data', d => {
      buf += d.toString();
      let nl;
      while ((nl = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (!line) continue;
        let o;
        try { o = JSON.parse(line); } catch (_) { continue; }
        // response to one of our requests
        if (o.id != null && pending.has(o.id)) {
          const p = pending.get(o.id);
          pending.delete(o.id);
          if (o.error) p.rej(new Error(JSON.stringify(o.error)));
          else p.res(o.result);
          continue;
        }
        // streaming notification
        if (o.method === 'session/update' && o.params && o.params.update) {
          const u = o.params.update;
          if (u.sessionUpdate === 'agent_message_chunk' && u.content && typeof u.content.text === 'string') {
            streamed += u.content.text.length;
            try { onDelta(u.content.text); } catch (_) {}
          }
          continue;
        }
        // server -> client request (e.g. permission prompt): keep the turn moving
        if (o.method && o.id != null) {
          if (o.method === 'session/request_permission') {
            const opts = (o.params && o.params.options) || [];
            let pick = null;
            if (ACP_AUTO_APPROVE) {
              pick =
                opts.find(x => /allow.*once|allow$|allow_once/i.test(x.optionId || '')) ||
                opts.find(x => (x.kind || '').includes('allow')) ||
                opts[0];
            }
            if (pick) send({ jsonrpc: '2.0', id: o.id, result: { outcome: { outcome: 'selected', optionId: pick.optionId } } });
            else send({ jsonrpc: '2.0', id: o.id, result: { outcome: { outcome: 'cancelled' } } });
          } else {
            // unknown client method: reply "not supported" so the bridge doesn't stall
            send({ jsonrpc: '2.0', id: o.id, error: { code: -32601, message: 'not supported' } });
          }
          continue;
        }
      }
    });

    child.on('exit', () => {
      // if the process dies before we resolve, surface as an error to trigger fallback
      finish(streamed > 0 ? resolve : reject, streamed > 0 ? streamed : new Error('acp exited before reply'));
    });

    (async () => {
      try {
        await rpc('initialize', {
          protocolVersion: 1,
          clientCapabilities: { fs: { readTextFile: false, writeTextFile: false } },
        });
        const sess = await rpc('session/new', { cwd: ACP_WORKSPACE, mcpServers: [] });
        await rpc('session/prompt', {
          sessionId: sess.sessionId,
          prompt: [{ type: 'text', text: message }],
        });
        finish(resolve, streamed);
      } catch (e) {
        finish(streamed > 0 ? resolve : reject, streamed > 0 ? streamed : e);
      }
    })();
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
      let streamedAny = false;
      try {
        if (STREAM_ENABLED) {
          // Real token-by-token streaming via ACP.
          const n = await runAgentStreaming(msg, sessionKey, delta => {
            streamedAny = true;
            sseChunk(res, delta);
          });
          if (!n) throw new Error('acp produced no output'); // fall back to one-shot
        } else {
          throw new Error('streaming disabled'); // jump straight to one-shot
        }
      } catch (streamErr) {
        if (streamedAny) {
          // Partial stream then failure mid-turn — can't safely restart without
          // duplicating text. End the turn; the reply so far is already delivered.
          const transient = TRANSIENT_RE.test(streamErr && streamErr.message ? streamErr.message : '');
          if (transient) sseChunk(res, '\n\n_(connection interrupted — reply may be incomplete)_');
        } else {
          // Nothing streamed yet: fall back to the proven one-shot path (with retry).
          try {
            const reply = await runAgentResilient(msg, sessionKey);
            const parts = reply.match(/\S+\s*/g) || [reply];
            for (const p of parts) sseChunk(res, p);
          } catch (e) {
            const transient = TRANSIENT_RE.test(e && e.message ? e.message : '');
            const note = transient
              ? '**Bridge**: the gateway was busy or restarting and the turn was interrupted — try again in a moment.'
              : '**Bridge error**: ' + e.message;
            sseChunk(res, note);
          }
        }
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
