const { execFile } = require('child_process');
const { promisify } = require('util');
const crypto = require('crypto');
const ContextStorage = require('./context-storage');

const execFileAsync = promisify(execFile);

const OPENCLAW_BIN = process.env.OPENCLAW_BIN || '/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw';
const MAX_STDERR = 4096;
const COMMAND_TIMEOUT_MS = Number(process.env.CONTEXT_COMMAND_TIMEOUT_MS || 30000);
const AGENT_RE = /^[a-zA-Z0-9_-]+$/;

function trimStderr(stderr = '') {
  if (!stderr) return '';
  return stderr.length > MAX_STDERR ? stderr.slice(0, MAX_STDERR) : stderr;
}

function makeError(code, message, stderr) {
  return {
    code,
    message,
    stderr: trimStderr(stderr || ''),
  };
}

function mapCommandError(error) {
  const stderr = trimStderr(error?.stderr || error?.message || '');
  const msg = `${error?.message || ''}\n${stderr}`.toLowerCase();
  if (error?.killed || error?.signal === 'SIGTERM' || msg.includes('timed out') || msg.includes('timeout')) {
    return makeError('COMMAND_TIMEOUT', 'Command timed out.', stderr);
  }
  if (msg.includes('config invalid') || msg.includes('invalid config')) {
    return makeError('CONFIG_INVALID', 'OpenClaw configuration is invalid.', stderr);
  }
  if (msg.includes('unknown command') || msg.includes('not a valid command') || msg.includes('plugin') && msg.includes('not found')) {
    return makeError('PLUGIN_NOT_FOUND', 'ctx-manager plugin command is not available.', stderr);
  }
  if (msg.includes('not running') || msg.includes('rpc probe: failed')) {
    return makeError('GATEWAY_UNAVAILABLE', 'Gateway is not running or unreachable.', stderr);
  }
  return makeError('INTERNAL_ERROR', 'Unexpected command failure.', stderr);
}

function parseJsonOutput(stdout) {
  const first = stdout.indexOf('{');
  const last = stdout.lastIndexOf('}');
  if (first === -1 || last === -1 || last <= first) {
    throw new Error('No JSON object found in command output.');
  }
  return JSON.parse(stdout.slice(first, last + 1));
}

class ContextManagerService {
  constructor() {
    this.storage = new ContextStorage();
  }

  validateAgent(agentId) {
    if (!agentId || !AGENT_RE.test(agentId)) {
      throw makeError('VALIDATION_ERROR', 'Invalid agentId. Use letters, numbers, _ or - only.');
    }
  }

  validateOlderThanMinutes(value) {
    const n = Number(value);
    if (!Number.isInteger(n) || n < 1 || n > 10080) {
      throw makeError('VALIDATION_ERROR', 'olderThanMinutes must be an integer between 1 and 10080.');
    }
    return n;
  }

  async runOpenClaw(args) {
    const started = Date.now();
    const requestId = crypto.randomUUID();
    const safeArgs = args.map((a) => String(a));
    console.log(`[context] requestId=${requestId} cmd=${OPENCLAW_BIN} args=${safeArgs.join(' ')}`);
    try {
      const { stdout, stderr } = await execFileAsync(OPENCLAW_BIN, safeArgs, {
        timeout: COMMAND_TIMEOUT_MS,
        maxBuffer: 10 * 1024 * 1024,
      });
      const durationMs = Date.now() - started;
      console.log(`[context] requestId=${requestId} exit=0 durationMs=${durationMs}`);
      return { requestId, durationMs, stdout, stderr: trimStderr(stderr) };
    } catch (error) {
      const durationMs = Date.now() - started;
      console.error(`[context] requestId=${requestId} exit=1 durationMs=${durationMs} err=${error.message}`);
      throw { requestId, durationMs, raw: error, mapped: mapCommandError(error) };
    }
  }

  async getReport(agentId) {
    this.validateAgent(agentId);
    const cmd = await this.runOpenClaw(['ctxreport', '--agent', agentId, '--json']);
    let report;
    try {
      report = parseJsonOutput(cmd.stdout);
    } catch (error) {
      throw {
        requestId: cmd.requestId,
        durationMs: cmd.durationMs,
        mapped: makeError('INTERNAL_ERROR', 'Failed to parse ctxreport JSON output.', error.message),
      };
    }

    let storageWarning = null;
    try {
      this.storage.saveReport({
        id: crypto.randomUUID(),
        agentId,
        createdAt: Date.now(),
        totalSessions: report?.totals?.totalSessions,
        mainSessions: report?.totals?.mainSessions,
        subAgentSessions: report?.totals?.subAgentSessions,
        totalTranscriptMb: report?.totals?.totalTranscriptSizeMb,
        payloadJson: JSON.stringify(report),
      });
    } catch (error) {
      storageWarning = 'Report persisted failed.';
      console.error('[context] storage saveReport failed:', error.message);
    }

    return {
      ok: true,
      requestId: cmd.requestId,
      durationMs: cmd.durationMs,
      data: report,
      ...(storageWarning ? { storageWarning } : {}),
    };
  }

  async runPrune({ agentId, olderThanMinutes, apply }) {
    this.validateAgent(agentId);
    const minutes = this.validateOlderThanMinutes(olderThanMinutes);
    const args = ['ctxprune', '--agent', agentId, '--older-than-minutes', String(minutes), '--json'];
    if (apply) args.push('--apply');
    const cmd = await this.runOpenClaw(args);
    let result;
    try {
      result = parseJsonOutput(cmd.stdout);
    } catch (error) {
      throw {
        requestId: cmd.requestId,
        durationMs: cmd.durationMs,
        mapped: makeError('INTERNAL_ERROR', 'Failed to parse ctxprune JSON output.', error.message),
      };
    }

    let storageWarning = null;
    try {
      this.storage.savePruneRun({
        id: crypto.randomUUID(),
        agentId,
        createdAt: Date.now(),
        olderThanMinutes: minutes,
        apply: !!apply,
        prunedCount: result?.prunedCount,
        renamedCount: result?.renamedCount,
        missingTranscriptCount: result?.missingTranscriptCount,
        totalSizeMb: result?.totalSizeMb,
        backupFile: result?.backupFile || null,
        resultJson: JSON.stringify(result),
      });
    } catch (error) {
      storageWarning = 'Prune run persisted failed.';
      console.error('[context] storage savePruneRun failed:', error.message);
    }

    let reportAfter = null;
    if (apply) {
      try {
        const post = await this.getReport(agentId);
        reportAfter = post.data;
      } catch (error) {
        reportAfter = null;
      }
    }

    return {
      ok: true,
      requestId: cmd.requestId,
      durationMs: cmd.durationMs,
      data: {
        ...result,
        ...(reportAfter ? { reportAfter } : {}),
      },
      ...(storageWarning ? { storageWarning } : {}),
    };
  }

  async getGatewayStatus() {
    const cmd = await this.runOpenClaw(['gateway', 'status']);
    const statusText = cmd.stdout || cmd.stderr || '';
    return {
      ok: true,
      requestId: cmd.requestId,
      durationMs: cmd.durationMs,
      data: {
        ok: statusText.toLowerCase().includes('rpc probe: ok'),
        statusText,
        timestamp: Date.now(),
      },
    };
  }

  async getDiagnostics() {
    const started = Date.now();
    const requestId = crypto.randomUUID();
    const run = async (args) => {
      try {
        const { stdout, stderr } = await execFileAsync(OPENCLAW_BIN, args, {
          timeout: COMMAND_TIMEOUT_MS,
          maxBuffer: 10 * 1024 * 1024,
        });
        return { ok: true, stdout, stderr: trimStderr(stderr) };
      } catch (error) {
        return { ok: false, stdout: error?.stdout || '', stderr: trimStderr(error?.stderr || error?.message || '') };
      }
    };
    const [pluginsList, pluginsDoctor, doctor] = await Promise.all([
      run(['plugins', 'list']),
      run(['plugins', 'doctor']),
      run(['doctor']),
    ]);
    return {
      ok: true,
      requestId,
      durationMs: Date.now() - started,
      data: {
        timestamp: Date.now(),
        pluginsList,
        pluginsDoctor,
        doctor,
      },
    };
  }

  getTrends(agentId, range) {
    this.validateAgent(agentId);
    const rangeMap = { '7d': 7, '30d': 30 };
    const rangeDays = rangeMap[range] || 7;
    const trends = this.storage.getTrends(agentId, rangeDays);
    return {
      ok: true,
      requestId: crypto.randomUUID(),
      durationMs: 0,
      data: trends,
    };
  }

  compactStorage() {
    const stats = this.storage.compactNow();
    return {
      ok: true,
      requestId: crypto.randomUUID(),
      durationMs: 0,
      data: {
        timestamp: Date.now(),
        ...stats,
      },
    };
  }
}

module.exports = ContextManagerService;
