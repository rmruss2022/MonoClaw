const { execFile } = require('child_process');
const { promisify } = require('util');
const crypto = require('crypto');
const fs = require('fs');
const ContextStorage = require('./context-storage');

const execFileAsync = promisify(execFile);

const OPENCLAW_BIN = process.env.OPENCLAW_BIN || '/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw';
const MAX_STDERR = 4096;
const COMMAND_TIMEOUT_MS = Number(process.env.CONTEXT_COMMAND_TIMEOUT_MS || 30000);
const AGENT_RE = /^[a-zA-Z0-9_-]+$/;
const OPENCLAW_HOME = process.env.OPENCLAW_HOME || '/Users/matthew/.openclaw';

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

  async getContextInspection(agentId = 'main') {
    this.validateAgent(agentId);
    const cmd = await this.runOpenClaw(['ctxinspect', '--agent', agentId, '--last', '--detailed']);
    const output = cmd.stdout || '';
    
    // Parse the output
    const result = {
      agentId,
      totalTokens: 0,
      totalContextTokens: 0,
      summaryTokens: 0,
      categories: [],
      toolStats: [],
      toolOutputBreakdown: [],
      topPruningTargets: [],
      optimizationScore: 0,
      suggestions: [],
      messageCount: 0,
      transcriptSize: '',
      rawOutput: output
    };
    
    // Extract summary line (messages, tokens, transcript size)
    const summaryMatch = output.match(/\*\*Summary:\*\*\s+(\d+)\s+messages,\s+([\d,]+)\s+tokens.*?([\d.]+\s+[MKG]B)/);
    if (summaryMatch) {
      result.messageCount = parseInt(summaryMatch[1]);
      result.summaryTokens = parseInt(summaryMatch[2].replace(/,/g, ''));
      result.transcriptSize = summaryMatch[3];
    }

    // Extract full context total from detailed breakdown section
    const totalContextMatch = output.match(/\*\*Total Context:\*\*\s+([\d,]+)\s+tokens/);
    if (totalContextMatch) {
      result.totalContextTokens = parseInt(totalContextMatch[1].replace(/,/g, ''), 10);
    }

    // Backwards-compatible field expected by existing UI consumers
    result.totalTokens = result.totalContextTokens || result.summaryTokens;
    
    // Extract token breakdown
    const breakdownMatch = output.match(/\*\*Token Breakdown:\*\*([\s\S]*?)\n\n/);
    if (breakdownMatch) {
      const breakdownLines = breakdownMatch[1].split('\n').filter(l => l.includes('tokens'));
      breakdownLines.forEach(line => {
        const match = line.match(/- ([^:]+):\s+([\d,]+)\s+tokens/);
        if (match) {
          const name = match[1].trim();
          const tokens = parseInt(match[2].replace(/,/g, ''));
          result.categories.push({
            name,
            tokens,
            percent: result.summaryTokens > 0 ? (tokens / result.summaryTokens * 100) : 0
          });
        }
      });
    }
    
    // Extract tool usage
    const toolMatch = output.match(/\*\*Tool Usage:\*\*([\s\S]*?)\n\n/);
    if (toolMatch) {
      const toolLines = toolMatch[1].split('\n').filter(l => l.includes('calls'));
      toolLines.forEach(line => {
        const match = line.match(/- ([^:]+):\s+(\d+)\s+calls/);
        if (match) {
          result.toolStats.push({
            name: match[1].trim(),
            calls: parseInt(match[2])
          });
        }
      });
    }
    
    // Extract optimization score
    const scoreMatch = output.match(/Optimization Score:.*?(\d+)\/100/);
    if (scoreMatch) {
      result.optimizationScore = parseInt(scoreMatch[1]);
    }
    
    // Extract suggestions
    const suggestionsSection = output.match(/\*\*💡 Optimization Suggestions:\*\*([\s\S]*?)(?=\n\*\*Optimization Score|$)/);
    if (suggestionsSection) {
      const suggestionLines = suggestionsSection[1].split('\n').filter(l => l.trim().match(/^\d+\./));
      result.suggestions = suggestionLines.map(l => {
        // Remove emoji and number prefix, keep the suggestion text
        return l.replace(/^\d+\.\s*[🟡🟢🔴🟠]\s*/, '').trim();
      });
    }

    // Extract tool output breakdown from detailed section
    const toolOutputSection = output.match(/\*\*🧪 Tool Output Breakdown \(by tokens\):\*\*([\s\S]*?)(?=\n\n\*\*🎯 Best Pruning Targets|\n\*\*🎯 Best Pruning Targets|$)/);
    if (toolOutputSection) {
      const lines = toolOutputSection[1]
        .split('\n')
        .map((l) => l.trim())
        .filter((l) => l.startsWith('• '));
      for (const line of lines) {
        if (line.startsWith('• Action:')) {
          result.toolOutputAction = line.replace(/^•\s*Action:\s*/, '').trim();
          continue;
        }
        const m = line.match(/^•\s*([^:]+):\s*([\d,]+)\s+tokens\s+\(([\d,]+)\s+calls\s*-\s*(.+)\)$/);
        if (!m) continue;
        result.toolOutputBreakdown.push({
          label: m[1].trim(),
          tokens: parseInt(m[2].replace(/,/g, ''), 10),
          calls: parseInt(m[3].replace(/,/g, ''), 10),
          details: m[4].trim(),
        });
      }
    }

    // Extract top pruning targets from detailed section
    const pruningSection = output.match(/\*\*🎯 Best Pruning Targets \(by impact\):\*\*([\s\S]*?)$/);
    if (pruningSection) {
      const lines = pruningSection[1].split('\n').map((l) => l.trim());
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const header = line.match(/^(\S+)\s+#(\d+):\s+\*\*([^*]+)\*\*\s+-\s+([\d,]+)\s+tokens\s+\(([\d.]+)%\)$/u);
        if (!header) continue;
        let action = '';
        let topItems = '';
        for (let j = i + 1; j < Math.min(i + 5, lines.length); j++) {
          if (!action && lines[j].includes('Action:')) {
            action = lines[j].replace(/^Action:\s*/, '').trim();
          }
          if (!topItems && lines[j].startsWith('Top items:')) {
            topItems = lines[j].replace(/^Top items:\s*/, '').trim();
          }
          if (lines[j] === '') break;
        }
        result.topPruningTargets.push({
          icon: header[1],
          rank: parseInt(header[2], 10),
          name: header[3].trim(),
          tokens: parseInt(header[4].replace(/,/g, ''), 10),
          percent: Number(header[5]),
          action,
          topItems,
        });
      }
    }

    return {
      ok: true,
      requestId: cmd.requestId,
      durationMs: cmd.durationMs,
      data: {
        ...result,
        inspectedAt: Date.now(),
      },
    };
  }

  async getActiveAgents() {
    const cmd = await this.runOpenClaw(['agents', 'list', '--json']);
    let agentsPayload;
    try {
      agentsPayload = JSON.parse(cmd.stdout || '[]');
    } catch (error) {
      throw {
        requestId: cmd.requestId,
        durationMs: cmd.durationMs,
        mapped: makeError('INTERNAL_ERROR', 'Failed to parse agents list JSON output.', error.message),
      };
    }

    const now = Date.now();
    const activeWindowMs = 15 * 60 * 1000; // "running now" heuristic
    const configuredAgents = Array.isArray(agentsPayload) ? agentsPayload : [];
    const agents = [];

    for (const agent of configuredAgents) {
      const id = String(agent?.id || '');
      if (!id || !AGENT_RE.test(id)) continue;

      const sessionsPath = `${OPENCLAW_HOME}/agents/${id}/sessions/sessions.json`;
      let sessions = {};
      try {
        sessions = JSON.parse(fs.readFileSync(sessionsPath, 'utf-8'));
      } catch {
        sessions = {};
      }

      const values = Object.values(sessions || {});
      let newestUpdatedAt = 0;
      for (const s of values) {
        const updatedAt = Number(s?.updatedAt || 0);
        if (Number.isFinite(updatedAt) && updatedAt > newestUpdatedAt) newestUpdatedAt = updatedAt;
      }
      const ageMs = newestUpdatedAt > 0 ? Math.max(0, now - newestUpdatedAt) : null;
      const isRunning = ageMs !== null && ageMs <= activeWindowMs;

      agents.push({
        id,
        isDefault: !!agent?.isDefault,
        sessionCount: values.length,
        newestAgeMs: ageMs,
        activeSessionCount: isRunning ? 1 : 0,
        running: isRunning,
      });
    }

    const activeAgents = agents
      .filter((a) => a.running)
      .sort((a, b) => (a.newestAgeMs ?? Number.POSITIVE_INFINITY) - (b.newestAgeMs ?? Number.POSITIVE_INFINITY));

    return {
      ok: true,
      requestId: cmd.requestId,
      durationMs: cmd.durationMs,
      data: {
        generatedAt: now,
        activeWindowMinutes: activeWindowMs / 60000,
        agents: activeAgents,
      },
    };
  }
}

module.exports = ContextManagerService;
