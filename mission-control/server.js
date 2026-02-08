#!/usr/bin/env node

const http = require('http');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

const PORT = 18795;

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
        const voiceServerOnline = await checkPort(18790);
        const voiceHealth = voiceServerOnline ? 'healthy' : 'down';
        
        const jobDashboard = await checkPort(18791);
        const ravesDashboard = await checkPort(18793);
        const tokenTracker = await checkPort(18794);
        const missionControl = await checkPort(18795);
        const activityHub = await checkPort(18796);
        const moltbookDash = await checkPort(18797);
        
        // Get cron jobs
        const cronJobs = await getCronJobs();
        
        // Parse openclaw status output
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
        const response = await fetch(`http://localhost:${port}`, { signal: AbortSignal.timeout(2000) });
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

async function getCronJobs() {
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
    try {
        const { stdout } = await execPromise('/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw status');
        
        // Parse session tokens
        const tokenMatch = stdout.match(/(\d+k)\/(\d+k)\s+\((\d+)%\)/);
        const sessionsMatch = stdout.match(/Sessions.*?(\d+)\s+active/s);
        const telegramMatch = stdout.match(/accounts\s+(\d+)\/(\d+)/);
        
        return {
            tokensUsed: tokenMatch ? tokenMatch[1] : '93k',
            tokensTotal: tokenMatch ? tokenMatch[2] : '1000k',
            usagePercent: tokenMatch ? parseInt(tokenMatch[3]) : 9,
            sessions: sessionsMatch ? parseInt(sessionsMatch[1]) : 1,
            telegramAccounts: telegramMatch ? parseInt(telegramMatch[1]) : 1,
            lastActivity: '1m ago',
            contextWindow: '195k'
        };
    } catch {
        return {
            tokensUsed: '93k',
            tokensTotal: '1000k',
            usagePercent: 9,
            sessions: 1,
            telegramAccounts: 1,
            lastActivity: '1m ago',
            contextWindow: '195k'
        };
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
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: true, sessions }));
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
