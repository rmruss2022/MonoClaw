#!/usr/bin/env node

/**
 * MonoClaw Dashboard Server
 * Visual dashboard for all projects in the MonoClaw monorepo
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const { promisify } = require('util');

const execAsync = promisify(exec);

const PORT = 18798;
const MONOCLAW_PATH = path.join(process.env.HOME, '.openclaw/workspace/MonoClaw');

// Project metadata mapping
const PROJECT_INFO = {
    'activity-hub': {
        name: 'Activity Hub',
        description: 'Real-time activity tracking, cron calendar, and workspace search',
        icon: '🦞',
        language: 'JavaScript',
        type: 'dashboard',
        url: 'http://localhost:18791'
    },
    'matts-claw-blog': {
        name: "Matt's Claw Blog",
        description: 'Daily dev blog chronicling Claw\'s adventures',
        icon: '📝',
        language: 'JavaScript',
        type: 'blog',
        url: 'https://matts-claw-blog.vercel.app'
    },
    'mission-control': {
        name: 'Mission Control',
        description: 'Central hub for managing OpenClaw operations',
        icon: '🎮',
        language: 'JavaScript',
        type: 'dashboard'
    },
    'moltbook-dashboard': {
        name: 'Moltbook Dashboard',
        description: 'View Matt\'s Claw\'s post history on Moltbook',
        icon: '🦞',
        language: 'JavaScript',
        type: 'dashboard',
        url: 'http://localhost:18797'
    },
    'ora-health': {
        name: 'Ora Health',
        description: 'Health and wellness tracking application',
        icon: '🏥',
        language: 'JavaScript',
        type: 'app'
    },
    'raves': {
        name: 'NYC Raves Tracker',
        description: 'Track weekly rave recommendations from Discord',
        icon: '🎵',
        language: 'JavaScript',
        type: 'dashboard'
    },
    'jobs': {
        name: 'Jobs Dashboard',
        description: 'Job application tracking and workflow management',
        icon: '💼',
        language: 'HTML/JS',
        type: 'dashboard'
    },
    'tokens': {
        name: 'Token Tracker',
        description: 'Track API token usage and costs',
        icon: '🎫',
        language: 'JavaScript',
        type: 'dashboard'
    },
    'skills': {
        name: 'Skills',
        description: 'OpenClaw skill modules (calendar, voice, etc.)',
        icon: '🛠️',
        language: 'Various',
        type: 'utilities'
    },
    'memory': {
        name: 'Memory',
        description: 'Daily memory logs and agent context',
        icon: '🧠',
        language: 'Markdown',
        type: 'documentation'
    }
};

async function getProjectStats(projectPath) {
    try {
        // Get last modified time
        const stats = fs.statSync(projectPath);
        const lastModified = stats.mtime;

        // Count files
        let fileCount = 0;
        try {
            const { stdout } = await execAsync(`find "${projectPath}" -type f | wc -l`);
            fileCount = parseInt(stdout.trim());
        } catch (e) {
            fileCount = 0;
        }

        // Get git info if available
        let gitInfo = null;
        try {
            const { stdout: branch } = await execAsync(`cd "${projectPath}" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo ""`);
            const { stdout: commits } = await execAsync(`cd "${projectPath}" && git rev-list --count HEAD 2>/dev/null || echo "0"`);
            if (branch.trim()) {
                gitInfo = {
                    branch: branch.trim(),
                    commits: parseInt(commits.trim())
                };
            }
        } catch (e) {
            // No git info
        }

        return {
            lastModified: lastModified.toISOString(),
            fileCount,
            gitInfo
        };
    } catch (error) {
        return {
            lastModified: null,
            fileCount: 0,
            gitInfo: null
        };
    }
}

async function scanMonorepo() {
    const projects = [];
    
    try {
        const entries = fs.readdirSync(MONOCLAW_PATH, { withFileTypes: true });
        
        for (const entry of entries) {
            if (!entry.isDirectory()) continue;
            
            // Skip hidden and special directories
            if (entry.name.startsWith('.') || entry.name === 'node_modules') continue;
            
            const projectPath = path.join(MONOCLAW_PATH, entry.name);
            const info = PROJECT_INFO[entry.name] || {
                name: entry.name,
                description: 'Project in MonoClaw monorepo',
                icon: '📁',
                language: 'Unknown',
                type: 'project'
            };
            
            const stats = await getProjectStats(projectPath);
            
            projects.push({
                id: entry.name,
                path: projectPath,
                ...info,
                ...stats
            });
        }
        
        // Sort by last modified (most recent first)
        projects.sort((a, b) => {
            if (!a.lastModified) return 1;
            if (!b.lastModified) return -1;
            return new Date(b.lastModified) - new Date(a.lastModified);
        });
        
    } catch (error) {
        console.error('Error scanning monorepo:', error);
    }
    
    return projects;
}

async function getDashboardData() {
    const projects = await scanMonorepo();
    
    return {
        monoClawPath: MONOCLAW_PATH,
        totalProjects: projects.length,
        projects,
        lastScanned: new Date().toISOString()
    };
}

const server = http.createServer(async (req, res) => {
    // CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET');
    
    if (req.url === '/data') {
        const data = await getDashboardData();
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(data));
    } else if (req.url.startsWith('/open')) {
        // Handle open actions (VS Code, Terminal, Finder, Git, GitHub)
        const url = new URL(req.url, `http://localhost:${PORT}`);
        const project = url.searchParams.get('project');
        const action = url.searchParams.get('action');
        
        if (project && action) {
            const projectPath = path.join(MONOCLAW_PATH, project);
            
            try {
                if (action === 'cursor') {
                    exec(`open -a "Cursor" "${projectPath}"`);
                } else if (action === 'terminal') {
                    exec(`open -a Terminal "${projectPath}"`);
                } else if (action === 'finder') {
                    exec(`open "${projectPath}"`);
                } else if (action === 'git') {
                    // Open the Git directory in Finder
                    exec(`open "${MONOCLAW_PATH}/.git"`);
                } else if (action === 'github') {
                    // Open GitHub repo in browser
                    exec(`open "https://github.com/rmruss2022/MonoClaw"`);
                }
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ success: true }));
            } catch (error) {
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ success: false, error: error.message }));
            }
        } else {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: false, error: 'Missing parameters' }));
        }
    } else if (req.url === '/' || req.url === '/index.html') {
        const html = fs.readFileSync(path.join(__dirname, 'dashboard.html'), 'utf-8');
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(html);
    } else {
        res.writeHead(404);
        res.end('Not found');
    }
});

server.listen(PORT, '127.0.0.1', () => {
    console.log(`🦞 MonoClaw Dashboard running at http://127.0.0.1:${PORT}`);
    console.log(`   Monitoring: ${MONOCLAW_PATH}`);
});
