#!/usr/bin/env node

const http = require('http');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

const PORT = 18795;
const HOME_DIR = process.env.HOME || '/Users/matthew';
const OPENCLAW_DIR = path.join(HOME_DIR, '.openclaw');
const LOG_PATH = path.join(OPENCLAW_DIR, 'logs/gateway.log');
const ERR_LOG_PATH = path.join(OPENCLAW_DIR, 'logs/gateway.err.log');
const SWARM_SESSIONS_PATH = path.join(OPENCLAW_DIR, 'agents/swarm/sessions/sessions.json');
const DELIVERY_QUEUE_PATH = path.join(OPENCLAW_DIR, 'delivery-queue');
const PRESSURE_LOOKBACK_MIN = 10;
const PRESSURE_TAIL_BYTES = 512 * 1024;

// Cache for openclaw status (expensive operation)
let statusCache = null;
let statusCacheTime = 0;
const STATUS_CACHE_TTL = 10000; // 10 seconds

function safeReadJson(filePath) {
    try {
        return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    } catch {
        return null;
    }
}

function readFileTail(filePath, maxBytes = PRESSURE_TAIL_BYTES) {
    try {
        const stats = fs.statSync(filePath);
        const size = stats.size;
        const start = Math.max(0, size - maxBytes);
        const length = size - start;
        const fd = fs.openSync(filePath, 'r');
        const buffer = Buffer.alloc(length);
        fs.readSync(fd, buffer, 0, length, start);
        fs.closeSync(fd);
        return buffer.toString('utf-8');
    } catch {
        return '';
    }
}

function parseTimestampFromLine(line) {
    // Logs are expected to start with an ISO timestamp.
    const token = line.trim().split(' ')[0] || '';
    const ts = Date.parse(token);
    return Number.isFinite(ts) ? ts : null;
}

function getRecentCount(lines, predicate, windowMs, nowMs) {
    return lines.filter(line => {
        const ts = parseTimestampFromLine(line);
        if (!ts) return false;
        if ((nowMs - ts) > windowMs) return false;
        return predicate(line);
    }).length;
}

function getRecentMax(lines, predicate, valueExtractor, windowMs, nowMs) {
    let maxValue = 0;
    for (const line of lines) {
        const ts = parseTimestampFromLine(line);
        if (!ts || (nowMs - ts) > windowMs) continue;
        if (!predicate(line)) continue;
        const value = valueExtractor(line);
        if (Number.isFinite(value) && value > maxValue) {
            maxValue = value;
        }
    }
    return maxValue;
}

function getLatestQueueAhead(lines, windowMs, nowMs) {
    let latestTs = -1;
    let latestAhead = null;
    const bounded = Number.isFinite(windowMs);
    for (const line of lines) {
        const ts = parseTimestampFromLine(line);
        if (!ts) continue;
        if (bounded && (nowMs - ts) > windowMs) continue;
        const m = line.match(/queueAhead=(\d+)/);
        if (!m) continue;
        if (ts > latestTs) {
            latestTs = ts;
            latestAhead = parseInt(m[1], 10) || 0;
        }
    }
    return { latestAhead, latestTimestamp: latestTs > 0 ? latestTs : null };
}

const HEARTBEAT_RE = /heartbeat: webhooks=(\d+)\/(\d+)\/(\d+) active=(\d+) waiting=(\d+) queued=(\d+)/;

function getLatestDiagnosticHeartbeat(lines, windowMs, nowMs) {
    let latestTs = -1;
    let result = null;
    for (const line of lines) {
        const ts = parseTimestampFromLine(line);
        if (!ts) continue;
        if (Number.isFinite(windowMs) && (nowMs - ts) > windowMs) continue;
        const m = line.match(HEARTBEAT_RE);
        if (!m) continue;
        if (ts > latestTs) {
            latestTs = ts;
            result = {
                active: parseInt(m[4], 10),
                waiting: parseInt(m[5], 10),
                queued: parseInt(m[6], 10),
                webhooks: { received: parseInt(m[1], 10), processed: parseInt(m[2], 10), errors: parseInt(m[3], 10) },
                ts: latestTs
            };
        }
    }
    return result;
}

function countDeliveryQueueFiles() {
    try {
        const entries = fs.readdirSync(DELIVERY_QUEUE_PATH);
        // Count only .json files (exclude 'failed' subdirectory and non-json)
        return entries.filter(e => e.endsWith('.json')).length;
    } catch {
        return 0;
    }
}

async function getPressureSignals() {
    const nowMs = Date.now();
    const lookbackMs = PRESSURE_LOOKBACK_MIN * 60 * 1000;

    const sessionsJson = safeReadJson(SWARM_SESSIONS_PATH) || {};
    const swarmMain = sessionsJson['agent:swarm:main'] || {};
    const contextTokens = swarmMain.contextTokens || 0;
    const totalTokens = swarmMain.totalTokens || swarmMain.inputTokens || 0;
    const contextPct = contextTokens > 0 ? Math.round((totalTokens / contextTokens) * 100) : 0;
    const compactions = swarmMain.compactionCount || 0;
    const gatewayLines = readFileTail(LOG_PATH).split('\n').filter(Boolean);
    const errLines = readFileTail(ERR_LOG_PATH).split('\n').filter(Boolean);

    const orderingConflicts = getRecentCount(
        gatewayLines,
        line => line.toLowerCase().includes('message ordering conflict'),
        lookbackMs,
        nowMs
    );
    const noReplyEvents = getRecentCount(
        gatewayLines,
        line => line.includes('No reply from agent.'),
        lookbackMs,
        nowMs
    );
    const restarts = getRecentCount(
        gatewayLines,
        line => line.includes('[gateway] received SIGUSR1; restarting'),
        lookbackMs,
        nowMs
    );
    const serviceRestartDisconnects = getRecentCount(
        gatewayLines,
        line => line.includes('reason=service restart'),
        lookbackMs,
        nowMs
    );
    const swarmLaneWaitMaxMs = getRecentMax(
        errLines,
        line => line.includes('lane wait exceeded: lane=session:agent:swarm:main'),
        line => {
            const m = line.match(/waitedMs=(\d+)/);
            return m ? parseInt(m[1], 10) : 0;
        },
        lookbackMs,
        nowMs
    );
    const embeddedTimeouts = getRecentCount(
        errLines,
        line => line.includes('[agent/embedded] embedded run timeout') && line.includes('8dd498f8-43de-43f7-9c05-21de1775a34c'),
        lookbackMs,
        nowMs
    );
    const gatewayQueueMaxAhead = getRecentMax(
        errLines,
        line => line.includes('[diagnostic] lane wait exceeded:'),
        line => {
            const m = line.match(/queueAhead=(\d+)/);
            return m ? parseInt(m[1], 10) : 0;
        },
        lookbackMs,
        nowMs
    );
    const gatewayQueueLatest = getLatestQueueAhead(errLines, lookbackMs, nowMs);
    const gatewayQueueLatestAny = getLatestQueueAhead(errLines, Number.POSITIVE_INFINITY, nowMs);
    const inferredQueueFloor = (orderingConflicts > 0 || noReplyEvents > 0) ? 1 : 0;
    const effectiveLatestAhead = gatewayQueueLatest.latestAhead !== null
        ? gatewayQueueLatest.latestAhead
        : (inferredQueueFloor > 0 ? inferredQueueFloor : null);

    // Diagnostic heartbeat: real-time queue telemetry (every ~30s when diagnostics enabled)
    const heartbeat = getLatestDiagnosticHeartbeat(gatewayLines, lookbackMs, nowMs);
    const heartbeatAny = getLatestDiagnosticHeartbeat(gatewayLines, Number.POSITIVE_INFINITY, nowMs);
    const heartbeatAgeSec = heartbeat ? Math.max(0, Math.round((nowMs - heartbeat.ts) / 1000)) : null;
    const heartbeatFresh = heartbeatAgeSec !== null && heartbeatAgeSec < 90;

    // Outbound delivery queue: count pending files on disk
    const deliveryPending = countDeliveryQueueFiles();

    const gatewayQueue = {
        // Primary: diagnostic heartbeat (real-time session queue depth)
        sessionActive: heartbeat ? heartbeat.active : null,
        sessionWaiting: heartbeat ? heartbeat.waiting : null,
        sessionQueued: heartbeat ? heartbeat.queued : null,
        heartbeatAgeSec,
        heartbeatFresh,
        // Outbound delivery queue (filesystem)
        deliveryPending,
        // Legacy: lane-wait log parsing (reactive fallback)
        latestAhead: effectiveLatestAhead,
        maxAhead: gatewayQueueMaxAhead,
        telemetryFresh: gatewayQueueLatest.latestTimestamp !== null,
        telemetryAgeSec: gatewayQueueLatest.latestTimestamp ? Math.max(0, Math.round((nowMs - gatewayQueueLatest.latestTimestamp) / 1000)) : null,
        inferred: gatewayQueueLatest.latestTimestamp === null && inferredQueueFloor > 0,
        inferredReason: gatewayQueueLatest.latestTimestamp === null && inferredQueueFloor > 0
            ? (orderingConflicts > 0 ? 'message_ordering_conflict' : 'no_reply_events')
            : null,
        lastObservedAhead: gatewayQueueLatestAny.latestAhead,
        lastObservedAgeSec: gatewayQueueLatestAny.latestTimestamp ? Math.max(0, Math.round((nowMs - gatewayQueueLatestAny.latestTimestamp) / 1000)) : null,
        // Last-ever heartbeat (for "last seen" display when current window is empty)
        lastHeartbeat: heartbeatAny ? {
            active: heartbeatAny.active,
            waiting: heartbeatAny.waiting,
            queued: heartbeatAny.queued,
            ageSec: Math.max(0, Math.round((nowMs - heartbeatAny.ts) / 1000))
        } : null
    };

    const gatewayMemory = await (async () => {
        const thresholds = {
            goodMaxMb: 600,
            elevatedMaxMb: 1024,
            highMaxMb: 1800
        };
        try {
            // Find gateway process using ps (lsof not available on all systems)
            const { stdout: psStdout } = await execPromise('ps aux | grep "[o]penclaw-gateway" | awk \'{print $2}\'');
            const pid = parseInt((psStdout || '').trim().split('\n')[0] || '', 10);
            if (!Number.isFinite(pid)) {
                return { pid: null, memoryMb: null, band: 'UNKNOWN', score: 0, thresholds };
            }

            const { stdout: rssStdout } = await execPromise(`ps -o rss= -p ${pid}`);
            const rssKb = parseInt((rssStdout || '').trim().split(/\s+/)[0] || '', 10);
            if (!Number.isFinite(rssKb)) {
                return { pid, memoryMb: null, band: 'UNKNOWN', score: 0, thresholds };
            }

            const memoryMb = Math.round(rssKb / 1024);
            let band = 'GOOD';
            let score = 0;
            if (memoryMb >= thresholds.highMaxMb) {
                band = 'CRITICAL';
                score = 30;
            } else if (memoryMb >= thresholds.elevatedMaxMb) {
                band = 'HIGH';
                score = 18;
            } else if (memoryMb >= thresholds.goodMaxMb) {
                band = 'ELEVATED';
                score = 8;
            }

            return { pid, memoryMb, band, score, thresholds };
        } catch {
            return { pid: null, memoryMb: null, band: 'UNKNOWN', score: 0, thresholds };
        }
    })();

    // Lightweight risk scoring: 0-100
    let risk = 0;
    risk += Math.min(contextPct, 100) * 0.35;               // up to 35
    // Queue congestion: prefer heartbeat data, fall back to lane-wait logs
    const queueDepthForRisk = heartbeatFresh ? (heartbeat.queued || 0) : gatewayQueueMaxAhead;
    risk += Math.min(queueDepthForRisk * 8, 24);            // up to 24
    risk += Math.min(orderingConflicts * 10, 20);           // up to 20
    risk += Math.min(restarts * 25, 25);                    // up to 25
    risk += Math.min(serviceRestartDisconnects * 10, 10);   // up to 10
    risk += Math.min(noReplyEvents * 5, 10);                // up to 10
    risk += swarmLaneWaitMaxMs >= 60000 ? 12 : swarmLaneWaitMaxMs >= 30000 ? 6 : 0;
    risk += Math.min(embeddedTimeouts * 6, 12);             // up to 12
    risk += gatewayMemory.score || 0;
    risk = Math.min(100, Math.round(risk));

    let band = 'LOW';
    if (risk >= 75) band = 'CRITICAL';
    else if (risk >= 50) band = 'HIGH';
    else if (risk >= 25) band = 'MEDIUM';

    return {
        riskScore: risk,
        riskBand: band,
        lookbackMinutes: PRESSURE_LOOKBACK_MIN,
        context: {
            used: totalTokens,
            limit: contextTokens,
            pct: contextPct,
            compactions
        },
        gatewayQueue,
        events: {
            orderingConflicts,
            noReplyEvents,
            restarts,
            serviceRestartDisconnects,
            swarmLaneWaitMaxMs,
            embeddedTimeouts
        },
        gatewayMemory
    };
}

function getAvailableModels(config) {
    const models = [];
    
    // Anthropic models (check both env and auth profiles)
    const hasAnthropic = config.env?.ANTHROPIC_API_KEY || 
                        Object.keys(config.auth?.profiles || {}).some(k => k.startsWith('anthropic'));
    if (hasAnthropic) {
        models.push('anthropic/claude-sonnet-4-5');
        models.push('anthropic/claude-opus-4');
        models.push('anthropic/claude-3.5-sonnet');
    }
    
    // OpenAI models (check both env and auth profiles)
    const hasOpenAI = config.env?.OPENAI_API_KEY ||
                     Object.keys(config.auth?.profiles || {}).some(k => k.startsWith('openai'));
    if (hasOpenAI) {
        models.push('openai/gpt-4o');
        models.push('openai/gpt-4o-mini');
        models.push('openai/o1');
        models.push('openai/o1-mini');
    }
    
    // NVIDIA models - check custom configuration
    if (config.env?.NVIDIA_API_KEY && config.models?.providers?.nvidia) {
        // Add custom NVIDIA models from config
        const nvidiaModels = config.models.providers.nvidia.models || [];
        nvidiaModels.forEach(m => {
            models.push(`nvidia/${m.id}`);
        });
        
        // Add common NVIDIA models if none configured
        if (nvidiaModels.length === 0) {
            models.push('nvidia/llama-3.1-nemotron-70b');
            models.push('nvidia/qwen-qwq');
        }
    }
    
    // DeepSeek models
    if (config.env?.DEEPSEEK_API_KEY) {
        models.push('deepseek/deepseek-chat');
        models.push('deepseek/deepseek-reasoner');
    }
    
    return models;
}

async function isGmailEnabled() {
    try {
        const { stdout } = await Promise.race([
            execPromise('/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw cron list --json'),
            new Promise((_, reject) => setTimeout(() => reject(new Error('cron list timeout')), 3000))
        ]);
        const cronData = JSON.parse(stdout);
        const gmailJob = cronData.jobs?.find(j => j.id === '3956a4f1-f07b-4ce6-869d-5d69664debb2');
        return gmailJob?.enabled || false;
    } catch (error) {
        console.error('Failed to check Gmail status:', error.message);
        return false;
    }
}

async function toggleGmail(enabled) {
    try {
        const enableFlag = enabled ? 'true' : 'false';
        await execPromise(`/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw cron update 3956a4f1-f07b-4ce6-869d-5d69664debb2 --patch '{"enabled":${enableFlag}}'`);
        return { success: true, enabled };
    } catch (error) {
        console.error('Failed to toggle Gmail:', error.message);
        return { success: false, error: error.message };
    }
}

async function getSystemData() {
    try {
        // Read config
        const configPath = path.join(process.env.HOME, '.openclaw/openclaw.json');
        const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
        
        // Check actual service health (port-based, more reliable than LaunchAgent)
        // Run all port checks in parallel for speed
        const [voiceServerOnline, jobDashboard, ravesDashboard, tokenTracker, 
               missionControl, activityHub, moltbookDash, agentSwarmDash, 
               visionController, skillBuilderDash, dockerDash, monoclawDash, cannonService, contextManager] = await Promise.all([
            checkPort(18790),
            checkPort(18791),
            checkPort(18793),
            checkPort(18794),
            checkPort(18795),
            checkPort(18796),
            checkPort(18797),
            checkPort(18798),
            checkPort(18799),
            checkPort(18803),
            checkPort(9092),
            checkPort(18802),
            checkPort(18801),
            checkPort(18800)
        ]);
        const voiceHealth = voiceServerOnline ? 'healthy' : 'down';
        
        // Get cron jobs (sync) and parse status (async)
        const cronJobs = getCronJobs();
        const statusData = await parseOpenClawStatus();
        const pressure = await getPressureSignals();
        
        return {
            gateway: {
                port: config.gateway.port,
                mode: config.gateway.mode,
                bind: config.gateway.bind
            },
            system: {
                os: `macOS ${process.platform}`,
                node: process.version
            },
            model: {
                primary: config.agents.defaults.model?.primary || 'Not set',
                contextWindow: statusData.contextWindow || '195k',
                provider: (config.agents.defaults.model?.primary || '').split('/')[0] || 'anthropic',
                available: getAvailableModels(config)
            },
            session: {
                active: statusData.sessions || 1,
                tokensUsed: statusData.tokensUsed || '93k',
                tokensTotal: statusData.tokensTotal || '1000k',
                usagePercent: statusData.usagePercent || 9,
                lastActivity: statusData.lastActivity || '1m ago'
            },
            heartbeat: config.agents.defaults.heartbeat?.every || '30m',
            workspace: config.agents.defaults.workspace,
            channels: [
                {
                    name: 'Telegram',
                    state: config.channels.telegram ? 'OK' : 'OFF',
                    detail: config.channels.telegram ? `Bot configured, ${statusData.telegramAccounts || 1} account(s) paired` : 'Not configured'
                },
                {
                    name: 'Discord',
                    state: config.channels.discord?.enabled ? 'OK' : 'OFF',
                    detail: config.channels.discord?.enabled ? `Bot connected, ${config.channels.discord.groupPolicy || 'allowlist'} policy` : 'Disabled'
                },
                {
                    name: 'iMessage',
                    state: config.channels.imessage?.enabled ? 'WARN' : 'OFF',
                    detail: config.channels.imessage?.enabled ? 'Enabled (imsg CLI configured)' : 'Disabled'
                }
            ],
            services: [
                {
                    name: 'Gateway',
                    running: true,
                    detail: `Port ${config.gateway.port}, LaunchAgent`
                },
                {
                    name: 'Voice Server',
                    running: voiceServerOnline,
                    health: voiceHealth,
                    detail: voiceServerOnline ? `Port 18790, ${voiceHealth}` : 'Stopped'
                },
                {
                    name: 'Job Dashboard',
                    running: jobDashboard,
                    detail: jobDashboard ? `Port 18791` : 'Stopped'
                },
                {
                    name: 'NYC Raves Dashboard',
                    running: ravesDashboard,
                    detail: ravesDashboard ? `Port 18793` : 'Stopped'
                },
                {
                    name: 'Token Tracker',
                    running: tokenTracker,
                    detail: tokenTracker ? `Port 18794` : 'Stopped'
                },
                {
                    name: 'Mission Control',
                    running: missionControl,
                    detail: missionControl ? `Port 18795 (this dashboard)` : 'Stopped'
                },
                {
                    name: 'Activity Hub',
                    running: activityHub,
                    detail: activityHub ? `Port 18796` : 'Stopped'
                },
                {
                    name: 'Moltbook Dashboard',
                    running: moltbookDash,
                    detail: moltbookDash ? `Port 18797` : 'Stopped'
                },
                {
                    name: 'MonoClaw Dashboard',
                    running: monoclawDash,
                    detail: monoclawDash ? `Port 18798` : 'Stopped'
                },
                {
                    name: 'Vision Controller',
                    running: visionController,
                    detail: visionController ? `Port 18799` : 'Stopped'
                },
                {
                    name: 'Skill Builder Dashboard',
                    running: skillBuilderDash,
                    detail: skillBuilderDash ? `Port 18803` : 'Stopped'
                },
                {
                    name: 'Docker Agent Dashboard',
                    running: dockerDash,
                    detail: dockerDash ? `Port 9092` : 'Stopped'
                },
                {
                    name: 'Agent Swarm Dashboard',
                    running: agentSwarmDash,
                    detail: agentSwarmDash ? `Port 18798` : 'Stopped'
                },
                {
                    name: 'Cannon Celebration',
                    running: cannonService,
                    detail: cannonService ? `Port 18801` : 'Stopped'
                },
                {
                    name: 'Context Manager',
                    running: contextManager,
                    detail: contextManager ? `Port 18800` : 'Stopped'
                },
                {
                    name: 'Gmail Inbox Check',
                    running: await isGmailEnabled(),
                    detail: (await isGmailEnabled()) ? 'Every 10 minutes' : 'Disabled',
                    controllable: true,
                    cronJobId: '3956a4f1-f07b-4ce6-869d-5d69664debb2'
                }
            ],
            apiKeys: [
                config.env?.ANTHROPIC_API_KEY ? 'Anthropic' : null,
                config.env?.OPENAI_API_KEY ? 'OpenAI' : null,
                config.env?.NVIDIA_API_KEY ? 'NVIDIA' : null,
                config.tools?.web?.search?.apiKey ? 'Brave Search' : null
            ].filter(Boolean),
            projects: [
                {
                    name: 'Job Search Tracker',
                    description: '11 companies tracked, 3 excited about',
                    url: 'http://127.0.0.1:18791',
                    icon: '💼'
                },
                {
                    name: 'NYC Raves',
                    description: '24 events this week, genre filtering',
                    url: 'http://127.0.0.1:18793',
                    icon: '🎧'
                },
                {
                    name: 'Token Usage Tracker',
                    description: 'Real-time token monitoring with charts',
                    url: 'http://127.0.0.1:18794',
                    icon: '🪙'
                },
                {
                    name: 'Mission Control',
                    description: 'System status and command hub',
                    url: 'http://127.0.0.1:18795',
                    icon: '🎛️'
                },
                {
                    name: 'Activity Hub',
                    description: 'Track all agent activity and sessions',
                    url: 'http://127.0.0.1:18796',
                    icon: '📊'
                },
                {
                    name: 'Agent Swarm Dashboard',
                    description: '4 active projects, agent orchestration',
                    url: 'http://127.0.0.1:18798',
                    icon: '🤖'
                },
                {
                    name: 'MonoClaw Dashboard',
                    description: '19 active projects, quick launch buttons',
                    url: 'http://127.0.0.1:18802',
                    icon: '🦞'
                },
                {
                    name: 'Vision Controller',
                    description: 'Real-time hand gesture recognition with WebSocket',
                    url: 'http://127.0.0.1:18799',
                    icon: '👋'
                },
                {
                    name: 'Skill Builder',
                    description: 'Auto-discover services, generate documentation',
                    url: 'http://127.0.0.1:18803',
                    icon: '🔧'
                },
                {
                    name: 'Cannon Celebration',
                    description: 'Fire celebratory cannon with confetti and sound',
                    url: 'http://127.0.0.1:18801',
                    icon: '🎉'
                },
                {
                    name: 'Context Manager',
                    description: 'Session bloat reports and safe prune controls',
                    url: 'http://127.0.0.1:18800',
                    icon: '📝'
                },
                {
                    name: 'Docker Agent System',
                    description: 'Container-based agent runtime with WebSocket API',
                    url: 'http://127.0.0.1:9092',
                    icon: '🐳'
                }
            ],
            cron: cronJobs,
            pressure,
            warnings: [
                'State dir readable by others (chmod 700 recommended)',
                'Reverse proxy headers not trusted (gateway.trustedProxies empty)'
            ]
        };
    } catch (error) {
        console.error('Error gathering system data:', error);
        return { error: error.message };
    }
}

async function checkPort(port) {
    try {
        const response = await fetch(`http://localhost:${port}`, { signal: AbortSignal.timeout(300) });
        return true;
    } catch {
        return false;
    }
}

async function checkLaunchAgent(name) {
    try {
        const { stdout } = await execPromise(`launchctl list | grep ${name}`);
        const parts = stdout.trim().split(/\s+/);
        return {
            running: true,
            pid: parseInt(parts[0])
        };
    } catch {
        return { running: false, pid: null };
    }
}

async function checkVoiceServerHealth() {
    try {
        // Use the health check we already have in /api/health-check
        const response = await fetch('http://127.0.0.1:18790/health', { signal: AbortSignal.timeout(2000) });
        if (!response.ok) return 'down';
        const data = await response.json();
        return data.ok ? 'healthy' : 'down';
    } catch (err) {
        console.error('Voice server health check failed:', err.message);
        return 'down';
    }
}

function getCronJobs() {
    // Direct cron job list (gateway API not exposed in local mode)
    return [
        {
            name: 'Morning News Briefing',
            schedule: '0 8 * * *',
            nextRun: 'Daily at 8:00 AM EST',
            enabled: true
        },
        {
            name: 'Daily Security Audit',
            schedule: '0 9 * * *',
            nextRun: 'Daily at 9:00 AM EST',
            enabled: true
        },
        {
            name: 'Hourly Token Data Collection',
            schedule: '0 * * * *',
            nextRun: 'Top of every hour',
            enabled: true
        },
        {
            name: 'Centralized Health Check',
            schedule: 'Every 5 min',
            nextRun: 'Continuous (all services)',
            enabled: true
        },
        {
            name: 'Daily Moltbook Post',
            schedule: '30 23 * * *',
            nextRun: 'Daily at 11:30 PM EST',
            enabled: true
        },
        {
            name: 'Daily Blog Post',
            schedule: '59 23 * * *',
            nextRun: 'Daily at 11:59 PM EST',
            enabled: true
        }
    ];
}

async function parseOpenClawStatus() {
    // Check cache first
    const now = Date.now();
    if (statusCache && (now - statusCacheTime) < STATUS_CACHE_TTL) {
        return statusCache;
    }
    
    try {
        // Add timeout to openclaw status command (max 2 seconds)
        const { stdout } = await Promise.race([
            execPromise('/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw status'),
            new Promise((_, reject) => setTimeout(() => reject(new Error('openclaw status timeout')), 2000))
        ]);
        
        // Parse session tokens
        const tokenMatch = stdout.match(/(\d+k)\/(\d+k)\s+\((\d+)%\)/);
        const sessionsMatch = stdout.match(/Sessions.*?(\d+)\s+active/s);
        const telegramMatch = stdout.match(/accounts\s+(\d+)\/(\d+)/);
        
        const result = {
            tokensUsed: tokenMatch ? tokenMatch[1] : '93k',
            tokensTotal: tokenMatch ? tokenMatch[2] : '1000k',
            usagePercent: tokenMatch ? parseInt(tokenMatch[3]) : 9,
            sessions: sessionsMatch ? parseInt(sessionsMatch[1]) : 1,
            telegramAccounts: telegramMatch ? parseInt(telegramMatch[1]) : 1,
            lastActivity: '1m ago',
            contextWindow: '195k'
        };
        
        // Cache the result
        statusCache = result;
        statusCacheTime = Date.now();
        return result;
    } catch (error) {
        console.error('Failed to parse openclaw status:', error.message);
        // Return cached data if available, otherwise defaults
        if (statusCache) return statusCache;
        
        const fallback = {
            tokensUsed: '93k',
            tokensTotal: '1000k',
            usagePercent: 9,
            sessions: 1,
            telegramAccounts: 1,
            lastActivity: '1m ago',
            contextWindow: '195k'
        };
        
        // Cache the fallback so we don't keep timing out
        statusCache = fallback;
        statusCacheTime = Date.now();
        
        return fallback;
    }
}

async function setModel(model) {
    try {
        const configPath = path.join(process.env.HOME, '.openclaw/openclaw.json');
        const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
        
        // Update the model
        config.agents.defaults.model = config.agents.defaults.model || {};
        config.agents.defaults.model.primary = model;
        
        // Write back
        fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
        
        // Restart gateway to apply
        await execPromise('/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw gateway restart');
        
        return { success: true };
    } catch (error) {
        return { success: false, error: error.message };
    }
}

async function getCodeStats() {
    try {
        const workspacePath = path.join(process.env.HOME, '.openclaw/workspace');
        
        // Get today's date boundaries
        const now = new Date();
        const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString();
        
        // Get week start (7 days ago, simpler and more intuitive)
        const weekStart = new Date(now);
        weekStart.setDate(now.getDate() - 7);
        weekStart.setHours(0, 0, 0, 0);
        const weekStartISO = weekStart.toISOString();
        
        // Get month start
        const monthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
        
        // Git command to get stats with --numstat (shows insertions/deletions per file)
        const getStats = async (since) => {
            try {
                const { stdout } = await execPromise(
                    `cd "${workspacePath}" && git log --since="${since}" --numstat --pretty=format:"" --no-merges`,
                    { maxBuffer: 10 * 1024 * 1024 }
                );
                
                let insertions = 0;
                let deletions = 0;
                
                // Exclude patterns for non-code files
                const excludePatterns = [
                    /package-lock\.json$/,
                    /node_modules\//,
                    /\.db$/,
                    /yarn\.lock$/,
                    /pnpm-lock\.yaml$/,
                    /\.min\.js$/,
                    /\.min\.css$/,
                    /\.map$/,
                    /\.png$/,
                    /\.jpg$/,
                    /\.jpeg$/,
                    /\.gif$/,
                    /\.svg$/,
                    /\.ico$/,
                    /\.woff/,
                    /\.ttf$/,
                    /\.eot$/,
                    /dist\//,
                    /build\//,
                    /\.next\//,
                    /coverage\//
                ];
                
                // Parse numstat output (format: insertions\tdeletions\tfilename)
                const lines = stdout.split('\n').filter(line => line.trim());
                for (const line of lines) {
                    const parts = line.split('\t');
                    if (parts.length >= 3) {
                        const filename = parts[2];
                        
                        // Skip if matches exclude patterns
                        if (excludePatterns.some(pattern => pattern.test(filename))) {
                            continue;
                        }
                        
                        // Skip binary files (show as -)
                        if (parts[0] === '-' || parts[1] === '-') {
                            continue;
                        }
                        
                        const ins = parseInt(parts[0]) || 0;
                        const dels = parseInt(parts[1]) || 0;
                        insertions += ins;
                        deletions += dels;
                    }
                }
                
                return { insertions, deletions, net: insertions - deletions };
            } catch (error) {
                console.error('Git stats error:', error.message);
                return { insertions: 0, deletions: 0, net: 0 };
            }
        };
        
        const [today, thisWeek, thisMonth] = await Promise.all([
            getStats(todayStart),
            getStats(weekStartISO),
            getStats(monthStart)
        ]);
        
        return {
            today,
            week: thisWeek,
            month: thisMonth
        };
    } catch (error) {
        console.error('Failed to get code stats:', error.message);
        return {
            today: { insertions: 0, deletions: 0, net: 0 },
            week: { insertions: 0, deletions: 0, net: 0 },
            month: { insertions: 0, deletions: 0, net: 0 }
        };
    }
}

function readRequestBody(req) {
    return new Promise((resolve, reject) => {
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', () => resolve(body));
        req.on('error', reject);
    });
}

const server = http.createServer(async (req, res) => {
    // Enable CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    
    if (req.method === 'OPTIONS') {
        res.writeHead(200);
        res.end();
        return;
    }
    
    if (req.url.startsWith('/data')) {
        const data = await getSystemData();
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(data));
    } else if (req.url === '/set-model' && req.method === 'POST') {
        const body = await readRequestBody(req);
        try {
            const { model } = JSON.parse(body);
            const result = await setModel(model);
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify(result));
        } catch (error) {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: false, error: error.message }));
        }
    } else if (req.url === '/api/open-finder' && req.method === 'POST') {
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', async () => {
            try {
                const { path: dirPath } = JSON.parse(body);
                await execPromise(`open "${dirPath}"`);
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ success: true }));
            } catch (error) {
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ success: false, error: error.message }));
            }
        });
    } else if (req.url === '/api/open-terminal' && req.method === 'POST') {
        try {
            // Open Terminal with openclaw status
            await execPromise(`osascript -e 'tell application "Terminal" to do script "openclaw status"'`);
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: true }));
        } catch (error) {
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: false, error: error.message }));
        }
    } else if (req.url === '/api/openclaw-status' && req.method === 'GET') {
        try {
            const { stdout } = await execPromise('/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw status');
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: true, output: stdout }));
        } catch (error) {
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: false, error: error.message, output: error.stdout || '' }));
        }
    } else if (req.url === '/api/open-vscode' && req.method === 'POST') {
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', async () => {
            try {
                const { path: filePath } = JSON.parse(body);
                await execPromise(`code "${filePath}"`);
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ success: true }));
            } catch (error) {
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ success: false, error: error.message }));
            }
        });
    } else if (req.url === '/api/health-check' && req.method === 'GET') {
        // Check health of all services
        const services = {
            'gateway': 18789,
            'voice-server': 18790,
            'job-tracker': 18791,
            'raves': 18793,
            'token-tracker': 18794,
            'mission-control': 18795
        };
        
        const health = {};
        for (const [name, port] of Object.entries(services)) {
            try {
                const response = await fetch(`http://localhost:${port}`, { signal: AbortSignal.timeout(2000) });
                health[name] = { online: true, port };
            } catch {
                health[name] = { online: false, port };
            }
        }
        
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(health));
    } else if (req.url === '/api/sessions' && req.method === 'GET') {
        try {
            const { stdout } = await execPromise('/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw sessions list --json');
            const sessions = JSON.parse(stdout);
            
            // Enrich sessions with labels from sessions.json (openclaw CLI doesn't return them)
            try {
                const sessionsJsonPath = path.join(process.env.HOME, '.openclaw/agents/main/sessions/sessions.json');
                const sessionsData = JSON.parse(fs.readFileSync(sessionsJsonPath, 'utf-8'));
                
                // Map labels by session key
                const labelMap = {};
                for (const [key, session] of Object.entries(sessionsData)) {
                    if (session.label) {
                        labelMap[key] = session.label;
                    }
                }
                
                // Apply labels to sessions list
                if (sessions.sessions) {
                    sessions.sessions = sessions.sessions.map(s => ({
                        ...s,
                        label: labelMap[s.key] || s.label
                    }));
                }
            } catch (labelError) {
                console.error('Failed to load session labels:', labelError.message);
            }
            
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: true, sessions }));
        } catch (error) {
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: false, error: error.message }));
        }
    } else if (req.url.startsWith('/api/sessions/history') && req.method === 'GET') {
        try {
            const url = new URL(req.url, `http://${req.headers.host}`);
            const sessionKey = url.searchParams.get('sessionKey');
            
            if (!sessionKey) {
                res.writeHead(400, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ success: false, error: 'sessionKey required' }));
                return;
            }
            
            const { stdout } = await execPromise(`/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw sessions history "${sessionKey}" --json --limit 50`);
            const data = JSON.parse(stdout);
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: true, history: data.messages || [] }));
        } catch (error) {
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: false, error: error.message }));
        }
    } else if (req.url === '/api/code-stats' && req.method === 'GET') {
        try {
            const stats = await getCodeStats();
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: true, stats }));
        } catch (error) {
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: false, error: error.message }));
        }
    } else if (req.url === '/api/toggle-gmail' && req.method === 'POST') {
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', async () => {
            try {
                const { enabled } = JSON.parse(body);
                const result = await toggleGmail(enabled);
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify(result));
            } catch (error) {
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ success: false, error: error.message }));
            }
        });
    } else if (req.url === '/hub' || req.url === '/hub.html') {
        const html = fs.readFileSync(path.join(__dirname, 'hub.html'), 'utf-8');
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(html);
    } else if (req.url === '/' || req.url === '/index.html') {
        const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf-8');
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(html);
    } else {
        res.writeHead(404);
        res.end('Not found');
    }
});

server.listen(PORT, '127.0.0.1', () => {
    console.log(`🦞 Mission Control running at http://127.0.0.1:${PORT}`);
});
