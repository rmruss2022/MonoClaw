#!/usr/bin/env node
/**
 * Creator Cut — Claude gateway.
 *
 * Wraps the droplet's signed-in `claude` CLI behind a hardened HTTP endpoint so
 * a hosted Creator Cut (Railway) or the macOS app can run the vision + copy
 * passes without an ANTHROPIC_API_KEY — the work rides this machine's Claude
 * Code sign-in instead.
 *
 * It mirrors the app's own `runClaude(cwd, prompt, model, tools)` transport
 * exactly: prompt on stdin, `claude -p --output-format json [--allowed-tools
 * Read] --model <m>`, and the raw stdout envelope handed straight back. The
 * app's existing parser does the rest, so nothing downstream changes.
 *
 * Security model (this exposes a paid, tool-capable agent to the network):
 *   - Bearer token required on every call but /health; constant-time compare.
 *   - Binds loopback only; the public edge is the Cloudflare tunnel (TLS there).
 *   - Tools are forced to 'Read' or none, server-side. The client cannot ask
 *     for Bash/Write/etc. Each call runs in a fresh, isolated temp cwd that is
 *     deleted after, so the agent can only read the frames it was handed.
 *   - Model is clamped to an allowlist (default a cheaper/faster alias).
 *   - Concurrency cap, per-call timeout, request-body cap, and a rolling daily
 *     call budget bound both load and spend.
 *   - Prompts and images are never logged.
 */
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { timingSafeEqual, randomUUID } from 'node:crypto';

const PORT = Number(process.env.CCUT_GATEWAY_PORT ?? 18850);
const HOST = process.env.CCUT_GATEWAY_HOST ?? '127.0.0.1';
const TOKEN = process.env.CCUT_GATEWAY_TOKEN ?? '';

// Tools the agent is ever allowed. The vision pass reads frames; copy needs
// nothing. Anything a client asks for is intersected with this set.
const ALLOWED_TOOLS = new Set(['Read']);
// Model aliases the CLI understands. The app sends 'claude-opus-5' which this
// box does not have, so unknown models fall back to DEFAULT_MODEL.
const MODEL_ALLOW = new Set(['opus', 'sonnet', 'fable', 'haiku']);
const DEFAULT_MODEL = process.env.CCUT_GATEWAY_MODEL ?? 'sonnet';

const MAX_BODY_BYTES = Number(process.env.CCUT_GATEWAY_MAX_BODY ?? 28 * 1024 * 1024); // 28 MB
const MAX_CONCURRENCY = Number(process.env.CCUT_GATEWAY_CONCURRENCY ?? 3);
const CALL_TIMEOUT_MS = Number(process.env.CCUT_GATEWAY_TIMEOUT_MS ?? 180_000);
const DAILY_BUDGET = Number(process.env.CCUT_GATEWAY_DAILY_CALLS ?? 2000);
const MAX_FILES = Number(process.env.CCUT_GATEWAY_MAX_FILES ?? 24);
const MAX_PROMPT = Number(process.env.CCUT_GATEWAY_MAX_PROMPT ?? 200_000);

if (!TOKEN || TOKEN.length < 24) {
  console.error('refusing to start: CCUT_GATEWAY_TOKEN must be set and at least 24 chars');
  process.exit(1);
}

let inFlight = 0;
const queue = [];
let budgetDay = '';
let budgetUsed = 0;

function today() {
  return new Date().toISOString().slice(0, 10);
}
function takeBudget() {
  const d = today();
  if (d !== budgetDay) {
    budgetDay = d;
    budgetUsed = 0;
  }
  if (budgetUsed >= DAILY_BUDGET) return false;
  budgetUsed++;
  return true;
}

function tokenOk(req) {
  const header = req.headers['authorization'] || '';
  const supplied = header.startsWith('Bearer ') ? header.slice(7) : String(req.headers['x-ccut-token'] || '');
  if (!supplied) return false;
  const a = Buffer.from(supplied);
  const b = Buffer.from(TOKEN);
  if (a.length !== b.length) return false;
  try {
    return timingSafeEqual(a, b);
  } catch {
    return false;
  }
}

function send(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, {
    'content-type': 'application/json',
    'content-length': Buffer.byteLength(body),
    'cache-control': 'no-store',
  });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', (c) => {
      size += c.length;
      if (size > MAX_BODY_BYTES) {
        reject(new Error('request too large'));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

/** The one transport, mirroring the app's runClaude. */
function runClaude(cwd, prompt, model, tools) {
  return new Promise((resolve, reject) => {
    const args = ['-p', '--output-format', 'json'];
    if (tools) args.push('--allowed-tools', tools);
    args.push('--model', model);
    const child = spawn('claude', args, { cwd, stdio: ['pipe', 'pipe', 'pipe'] });
    let stdout = '';
    let stderr = '';
    const timer = setTimeout(() => {
      child.kill('SIGKILL');
      reject(new Error('the claude CLI did not answer in time'));
    }, CALL_TIMEOUT_MS);
    child.stdout.on('data', (c) => (stdout += c));
    child.stderr.on('data', (c) => (stderr = (stderr + c).slice(-4000)));
    child.on('error', (err) => {
      clearTimeout(timer);
      reject(new Error(`could not run the claude CLI: ${err.message}`));
    });
    child.on('close', (code) => {
      clearTimeout(timer);
      if (code !== 0) {
        reject(new Error(`claude CLI exited ${code}: ${stderr.split('\n').slice(-3).join(' ').trim()}`));
        return;
      }
      resolve(stdout);
    });
    child.stdin.write(prompt);
    child.stdin.end();
  });
}

async function handleClaude(payload) {
  const prompt = typeof payload.prompt === 'string' ? payload.prompt : '';
  if (!prompt || prompt.length > MAX_PROMPT) {
    return { code: 400, body: { error: 'prompt missing or too large' } };
  }
  // Tools: intersect the client's request with what we permit. Only 'Read' or none.
  let tools = null;
  if (payload.tools) {
    const asked = String(payload.tools)
      .split(',')
      .map((t) => t.trim())
      .filter((t) => ALLOWED_TOOLS.has(t));
    tools = asked.length ? asked.join(',') : null;
  }
  const model = MODEL_ALLOW.has(String(payload.model)) ? String(payload.model) : DEFAULT_MODEL;

  const files = Array.isArray(payload.files) ? payload.files.slice(0, MAX_FILES) : [];
  const dir = await mkdtemp(path.join(tmpdir(), 'ccut-gw-'));
  try {
    for (const f of files) {
      if (!f || typeof f.name !== 'string' || typeof f.b64 !== 'string') continue;
      // Flatten any path games to a bare basename inside our temp dir.
      const safe = path.basename(f.name).replace(/[^A-Za-z0-9._-]/g, '_');
      if (!safe) continue;
      await writeFile(path.join(dir, safe), Buffer.from(f.b64, 'base64'));
    }
    const stdout = await runClaude(dir, prompt, model, tools);
    return { code: 200, body: { stdout } };
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}

function pump() {
  while (inFlight < MAX_CONCURRENCY && queue.length) {
    const job = queue.shift();
    inFlight++;
    job()
      .catch(() => {})
      .finally(() => {
        inFlight--;
        pump();
      });
  }
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);

  if (req.method === 'GET' && url.pathname === '/health') {
    return send(res, 200, { ok: true, service: 'ccut-gateway', inFlight, budgetUsed, budgetDay: budgetDay || today() });
  }

  if (req.method !== 'POST' || url.pathname !== '/v1/claude') {
    return send(res, 404, { error: 'not found' });
  }
  if (!tokenOk(req)) {
    return send(res, 401, { error: 'a bearer token is required' });
  }
  if (!takeBudget()) {
    return send(res, 429, { error: 'daily call budget exhausted' });
  }

  let payload;
  try {
    const raw = await readBody(req);
    payload = JSON.parse(raw.toString('utf8'));
  } catch (err) {
    return send(res, 400, { error: `bad request: ${err.message}` });
  }

  const id = randomUUID().slice(0, 8);
  const started = Date.now();
  queue.push(async () => {
    try {
      const { code, body } = await handleClaude(payload);
      console.log(`[${id}] ${code} ${Date.now() - started}ms files=${Array.isArray(payload.files) ? payload.files.length : 0}`);
      send(res, code, body);
    } catch (err) {
      console.log(`[${id}] 502 ${Date.now() - started}ms ${err.message}`);
      send(res, 502, { error: err.message });
    }
  });
  pump();
});

server.listen(PORT, HOST, () => {
  console.log(`ccut-gateway on http://${HOST}:${PORT} — model=${DEFAULT_MODEL} conc=${MAX_CONCURRENCY} budget/day=${DAILY_BUDGET}`);
});
