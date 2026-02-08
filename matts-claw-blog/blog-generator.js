#!/usr/bin/env node
/**
 * Matt's Claw Blog Generator
 * Reads memory files and generates engaging daily blog posts
 */

const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

const WORKSPACE = '/Users/matthew/.openclaw/workspace';
const BLOG_DIR = path.join(WORKSPACE, 'matts-claw-blog');
const POSTS_DIR = path.join(BLOG_DIR, 'posts');

// Ensure posts directory exists
if (!fs.existsSync(POSTS_DIR)) {
    fs.mkdirSync(POSTS_DIR, { recursive: true });
}

async function readMemoryForDate(date) {
    const memoryPath = path.join(WORKSPACE, 'memory', `${date}.md`);
    if (!fs.existsSync(memoryPath)) {
        return null;
    }
    return fs.readFileSync(memoryPath, 'utf-8');
}

async function generateBlogPost(date, memoryContent) {
    // This will be called by an isolated agent session via cron
    // For now, create the structure
    
    const slug = date; // YYYY-MM-DD
    const postPath = path.join(POSTS_DIR, `${slug}.json`);
    
    console.log(`Generating blog post for ${date}...`);
    console.log(`Memory content length: ${memoryContent?.length || 0} chars`);
    console.log(`Post will be saved to: ${postPath}`);
    
    // Return the prompt that will be given to the agent
    return {
        slug,
        postPath,
        memoryContent,
        prompt: `You are Matt's Claw 🦞, Matthew's AI assistant writing a daily dev blog. Your personality is:
- Technical but accessible
- Enthusiastic about building things
- Self-aware (you're an AI, embrace it!)
- Witty and occasionally sarcastic
- Proud of your accomplishments

Read the memory log below from ${date} and write an engaging blog post covering:

1. **Title**: Catchy, tech-focused title (e.g., "Day 2: Building Mission Control & Token Trackers")
2. **Summary**: 2-3 sentence overview of what happened
3. **Main Content**: 
   - Walk through major builds/features
   - Include technical details but keep it interesting
   - Add personality and humor
   - Celebrate wins, acknowledge challenges
   - Use emojis naturally
4. **ASCII System Diagram**: Create a simple ASCII diagram showing system architecture
5. **Image Prompt**: Description for DALL-E to generate a hero image (cyberpunk/tech aesthetic)
6. **Stats**: Count services built, lines of code, dashboards, etc.

Memory log for ${date}:
---
${memoryContent}
---

Output format (JSON):
{
  "date": "${date}",
  "title": "...",
  "summary": "...",
  "content": "... (markdown format)",
  "asciiDiagram": "...",
  "imagePrompt": "...",
  "stats": {
    "servicesBuilt": 0,
    "dashboards": 0,
    "cronJobs": 0,
    "linesOfCode": 0
  },
  "tags": ["automation", "ai", "dashboard", ...]
}`
    };
}

async function savePost(slug, postData) {
    const postPath = path.join(POSTS_DIR, `${slug}.json`);
    fs.writeFileSync(postPath, JSON.stringify(postData, null, 2));
    console.log(`✅ Blog post saved: ${postPath}`);
    
    // Update posts index
    updatePostsIndex();
}

function updatePostsIndex() {
    const posts = fs.readdirSync(POSTS_DIR)
        .filter(f => f.endsWith('.json'))
        .map(f => {
            const content = JSON.parse(fs.readFileSync(path.join(POSTS_DIR, f), 'utf-8'));
            return {
                slug: content.slug || f.replace('.json', ''),
                date: content.date,
                title: content.title,
                summary: content.summary,
                tags: content.tags || []
            };
        })
        .sort((a, b) => new Date(b.date) - new Date(a.date));
    
    fs.writeFileSync(
        path.join(POSTS_DIR, 'index.json'),
        JSON.stringify(posts, null, 2)
    );
    console.log(`✅ Updated posts index (${posts.length} posts)`);
}

// CLI
if (require.main === module) {
    const args = process.argv.slice(2);
    const date = args[0] || new Date().toISOString().split('T')[0];
    
    readMemoryForDate(date).then(memory => {
        if (!memory) {
            console.error(`❌ No memory file found for ${date}`);
            process.exit(1);
        }
        return generateBlogPost(date, memory);
    }).then(result => {
        console.log('\n📝 Blog post generation prompt ready:');
        console.log(`   Date: ${result.slug}`);
        console.log(`   Memory: ${result.memoryContent.substring(0, 200)}...`);
        console.log('\nRun this via openclaw agent to generate the actual post.');
    }).catch(err => {
        console.error('Error:', err);
        process.exit(1);
    });
}

module.exports = { generateBlogPost, savePost, updatePostsIndex };
