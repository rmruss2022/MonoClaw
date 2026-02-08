#!/usr/bin/env node

/**
 * Moltbook Dashboard Server
 * View Matt's Claw's post history on Moltbook
 */

const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');

const PORT = 18797;
const MOLTBOOK_API_KEY = 'moltbook_sk_INf7-5a5KWpzlt3pxbMOQL6PG81-gULG';
const MOLTBOOK_API = 'https://www.moltbook.com/api/v1';
const MY_POST_IDS_FILE = path.join(__dirname, 'my-posts.json');

async function fetchMoltbookData(endpoint) {
    return new Promise((resolve, reject) => {
        const url = `${MOLTBOOK_API}${endpoint}`;
        const options = {
            headers: {
                'Authorization': `Bearer ${MOLTBOOK_API_KEY}`,
                'Accept': 'application/json'
            }
        };

        https.get(url, options, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    resolve(JSON.parse(data));
                } catch (e) {
                    resolve({ success: false, error: 'Failed to parse response' });
                }
            });
        }).on('error', (err) => {
            resolve({ success: false, error: err.message });
        });
    });
}

async function getDashboardData() {
    try {
        // Get profile info
        const profile = await fetchMoltbookData('/agents/me');
        
        // Read our post IDs from file
        let postIds = [];
        if (fs.existsSync(MY_POST_IDS_FILE)) {
            postIds = JSON.parse(fs.readFileSync(MY_POST_IDS_FILE, 'utf-8'));
        }
        
        // Fetch each post by ID
        const posts = [];
        for (const postId of postIds) {
            const postData = await fetchMoltbookData(`/posts/${postId}`);
            if (postData.success && postData.post) {
                posts.push(postData.post);
            }
        }
        
        // Sort by created_at desc
        posts.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        
        return {
            profile: profile.agent || profile,
            posts,
            profileUrl: 'https://moltbook.com/u/MattsClaw',
            lastFetched: new Date().toISOString()
        };
    } catch (error) {
        console.error('Error fetching Moltbook data:', error);
        return {
            profile: null,
            posts: [],
            error: error.message
        };
    }
}

const server = http.createServer(async (req, res) => {
    // CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET');
    
    if (req.url === '/data') {
        const data = await getDashboardData();
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(data));
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
    console.log(`🦞 Moltbook Dashboard running at http://127.0.0.1:${PORT}`);
});
