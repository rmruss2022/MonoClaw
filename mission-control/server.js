#!/usr/bin/env node

const http = require('http');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

const PORT = 18795;

// Cache for openclaw status (expensive operation)
let statusCache = null;
let statusCacheTime = 0;
const STATUS_CACHE_TTL = 10000; // 10 seconds

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

async function getSystemData() {
    try {
        // Read config
        const configPath = path.join(process.env.HOME, '.openclaw/openclaw.json');
        const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
        
        // Check actual service health (port-based, more reliable than LaunchAgent)
        // Run all port checks in parallel for speed
        const [voiceServerOnline, jobDashboard, ravesDashboard, tokenTracker, 
               missionControl, activityHub, moltbookDash, monoclawDash, 
               skillBuilderDash, dockerDash] = await Promise.all([
            checkPort(18790),
            checkPort(18791),
            checkPort(18793),
            checkPort(18794),
            checkPort(18795),
            checkPort(18796),
            checkPort(18797),
            checkPort(18798),
            checkPort(18799),
            checkPort(9092)
        ]);
        const voiceHealth = voiceServerOnline ? 'healthy' : 'down';
        
        // Get cron jobs (sync) and parse status (async)
        const cronJobs = getCronJobs();
        const statusData = await parseOpenClawStatus();
        
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
                    name: 'Skill Builder Dashboard',
                    running: skillBuilderDash,
                    detail: skillBuilderDash ? `Port 18799` : 'Stopped'
                },
                {
                    name: 'Docker Agent Dashboard',
                    running: dockerDash,
                    detail: dockerDash ? `Port 9092` : 'Stopped'
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
                    url: 'http://127.0.0.1:18791'
                },
                {
                    name: 'NYC Raves',
                    description: '24 events this week, genre filtering',
                    url: 'http://127.0.0.1:18793'
                },
                {
                    name: 'Token Usage Tracker',
                    description: 'Real-time token monitoring with charts',
                    url: 'http://127.0.0.1:18794'
                },
                {
                    name: 'Mission Control',
                    description: 'System status and command hub',
                    url: 'http://127.0.0.1:18795'
                },
                {
                    name: 'Activity Hub',
                    description: 'Track all agent activity and sessions',
                    url: 'http://127.0.0.1:18796'
                },
                {
                    name: 'MonoClaw Dashboard',
                    description: '19 active projects, quick launch buttons',
                    url: 'http://127.0.0.1:18798'
                },
                {
                    name: 'Skill Builder',
                    description: 'Auto-discover services, generate documentation',
                    url: 'http://127.0.0.1:18799'
                },
                {
                    name: 'Docker Agent System',
                    description: 'Container-based agent runtime with WebSocket API',
                    url: 'http://127.0.0.1:9092'
                }
            ],
            cron: cronJobs,
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
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', async () => {
            try {
                const { model } = JSON.parse(body);
                const result = await setModel(model);
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify(result));
            } catch (error) {
                res.writeHead(400, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ success: false, error: error.message }));
            }
        });
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
