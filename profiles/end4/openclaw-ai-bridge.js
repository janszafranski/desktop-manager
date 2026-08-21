#!/usr/bin/env node
/*
 * openclaw-ai-bridge — exposes an OpenAI-compatible /v1/chat/completions endpoint
 * on 127.0.0.1 that forwards to the OpenClaw agent, so the end4 (illogical-impulse)
 * left-edge AI flyout talks to the actual OpenClaw agent (memory + persona), not a
 * raw model.
 *
 * Loopback-only by design: anything that can POST here can run agent turns.
 */
'use strict';

const http = require('http');
const { execFile } = require('child_process');

const HOST = '127.0.0.1';
const PORT = parseInt(process.env.OPENCLAW_BRIDGE_PORT || '8787', 10);
const SESSION_KEY = process.env.OPENCLAW_BRIDGE_SESSION || 'agent:main:ai-flyout';
const AGENT_TIMEOUT = process.env.OPENCLAW_BRIDGE_TIMEOUT || '300';
const MODEL_ID = 'openclaw';

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

function runAgent(message) {
  return new Promise((resolve, reject) => {
    execFile(
      'openclaw',
      ['agent', '--json', '--session-key', SESSION_KEY, '--timeout', AGENT_TIMEOUT, '--message', message],
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

function sseChunk(res, content) {
  const payload = {
    id: 'chatcmpl-openclaw',
    object: 'chat.completion.chunk',
    model: MODEL_ID,
    choices: [{ index: 0, delta: { content }, finish_reason: null }],
  };
  res.write('data: ' + JSON.stringify(payload) + '\n\n');
}

const server = http.createServer((req, res) => {
  if (req.method === 'GET' && req.url.startsWith('/v1/models')) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ object: 'list', data: [{ id: MODEL_ID, object: 'model', owned_by: 'openclaw' }] }));
    return;
  }
  if (req.method !== 'POST' || !req.url.startsWith('/v1/chat/completions')) {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: { message: 'Not found' } }));
    return;
  }

  let body = '';
  req.on('data', c => { body += c; if (body.length > 16 * 1024 * 1024) req.destroy(); });
  req.on('end', async () => {
    let msg = '';
    try {
      msg = lastUserMessage(JSON.parse(body).messages);
    } catch (_) { /* fall through */ }

    if (!msg) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: { message: 'No user message' } }));
      return;
    }

    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive',
    });

    try {
      const reply = await runAgent(msg);
      // Stream word-by-word for a typing feel; the flyout concatenates deltas.
      const parts = reply.match(/\S+\s*/g) || [reply];
      for (const p of parts) sseChunk(res, p);
    } catch (e) {
      sseChunk(res, '**Bridge error**: ' + e.message);
    }
    res.write('data: [DONE]\n\n');
    res.end();
  });
});

server.listen(PORT, HOST, () => {
  console.log(`openclaw-ai-bridge listening on http://${HOST}:${PORT}/v1/chat/completions -> session ${SESSION_KEY}`);
});
