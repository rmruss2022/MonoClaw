/**
 * Enhanced Agent Swarm Server with Discord Integration
 * Automatically creates Discord channels when projects are created
 */

require('dotenv').config(); // Load .env file

const express = require('express');
const Database = require('better-sqlite3');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const DiscordBot = require('./discord-bot');

const app = express();
const PORT = process.env.PORT || 18798;

// Discord configuration (from environment)
const DISCORD_BOT_TOKEN = process.env.DISCORD_BOT_TOKEN;
const DISCORD_GUILD_ID = process.env.DISCORD_GUILD_ID;

let discordBot = null;
if (DISCORD_BOT_TOKEN && DISCORD_GUILD_ID) {
  discordBot = new DiscordBot(DISCORD_BOT_TOKEN);
  console.log('✅ Discord bot initialized');
} else {
  console.warn('⚠️  Discord not configured - set DISCORD_BOT_TOKEN and DISCORD_GUILD_ID');
}

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static(__dirname));
app.use(express.static(path.join(__dirname, 'dashboard', 'dist')));

// Initialize SQLite Database
const db = new Database('swarm.db');
db.pragma('journal_mode = WAL');

// Create tables (enhanced with Discord metadata)
function initializeDatabase() {
  console.log('🔧 Initializing database schema...');
  
  // Projects table (with Discord metadata)
  db.exec(`
    CREATE TABLE IF NOT EXISTS projects (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      description TEXT,
      reference TEXT,
      status TEXT DEFAULT 'not-started',
      created_at TEXT NOT NULL,
      target_completion TEXT,
      configuration_json TEXT,
      discord_category_id TEXT,
      discord_channels_json TEXT,
      discord_webhooks_json TEXT
    )
  `);

  // Tasks table
  db.exec(`
    CREATE TABLE IF NOT EXISTS tasks (
      id TEXT PRIMARY KEY,
      project_id INTEGER NOT NULL,
      title TEXT NOT NULL,
      description TEXT,
      state TEXT DEFAULT 'todo',
      priority TEXT DEFAULT 'medium',
      estimated_hours REAL DEFAULT 0,
      actual_hours REAL DEFAULT 0,
      assigned_to TEXT,
      agent_session_key TEXT,
      started_at TEXT,
      completed_at TEXT,
      spec_file TEXT,
      dependencies_json TEXT,
      tags_json TEXT,
      code_files_json TEXT,
      discord_thread_id TEXT,
      FOREIGN KEY (project_id) REFERENCES projects(id)
    )
  `);

  // Agents table
  db.exec(`
    CREATE TABLE IF NOT EXISTS agents (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      project_id INTEGER NOT NULL,
      agent_id TEXT NOT NULL,
      session_key TEXT,
      task_id TEXT,
      spawned_at TEXT NOT NULL,
      completed_at TEXT,
      status TEXT DEFAULT 'running',
      result TEXT,
      discord_thread_id TEXT,
      FOREIGN KEY (project_id) REFERENCES projects(id),
      FOREIGN KEY (task_id) REFERENCES tasks(id)
    )
  `);

  // Activity log table
  db.exec(`
    CREATE TABLE IF NOT EXISTS activity_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      project_id INTEGER NOT NULL,
      timestamp TEXT NOT NULL,
      agent TEXT NOT NULL,
      task_id TEXT,
      message TEXT NOT NULL,
      type TEXT DEFAULT 'info',
      FOREIGN KEY (project_id) REFERENCES projects(id)
    )
  `);

  console.log('✅ Database schema initialized');
}

initializeDatabase();

// Helper functions
function calculateStats(projectId) {
  const tasks = db.prepare('SELECT * FROM tasks WHERE project_id = ?').all(projectId);
  
  const stats = {
    total_tasks: tasks.length,
    completed: tasks.filter(t => t.state === 'done').length,
    in_progress: tasks.filter(t => t.state === 'in-progress').length,
    todo: tasks.filter(t => t.state === 'todo').length,
    ready: tasks.filter(t => t.state === 'ready').length,
    qa: tasks.filter(t => t.state === 'qa').length,
    blocked: tasks.filter(t => t.state === 'blocked').length,
    estimated_hours_remaining: tasks
      .filter(t => t.state !== 'done')
      .reduce((sum, t) => sum + (t.estimated_hours || 0), 0)
  };
  
  stats.progress = stats.total_tasks > 0 
    ? Math.round((stats.completed / stats.total_tasks) * 100)
    : 0;
  
  return stats;
}

function formatTask(task) {
  if (!task) return null;
  
  return {
    ...task,
    dependencies: task.dependencies_json ? JSON.parse(task.dependencies_json) : [],
    tags: task.tags_json ? JSON.parse(task.tags_json) : [],
    code_files: task.code_files_json ? JSON.parse(task.code_files_json) : []
  };
}

// API Endpoints

// GET /api/projects - List all projects
app.get('/api/projects', (req, res) => {
  try {
    const projects = db.prepare('SELECT * FROM projects ORDER BY created_at DESC').all();
    
    // Parse Discord metadata for each project
    projects.forEach(p => {
      if (p.discord_channels_json) {
        p.discord_channels = JSON.parse(p.discord_channels_json);
      }
      if (p.discord_webhooks_json) {
        p.discord_webhooks = JSON.parse(p.discord_webhooks_json);
      }
    });
    
    res.json({ projects });
  } catch (error) {
    console.error('Error listing projects:', error);
    res.status(500).json({ error: error.message });
  }
});

// GET /api/projects/:id - Get full project data
app.get('/api/projects/:id', (req, res) => {
  try {
    const projectId = parseInt(req.params.id);
    
    // Get project
    const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }
    
    // Parse Discord metadata
    if (project.discord_channels_json) {
      project.discord_channels = JSON.parse(project.discord_channels_json);
    }
    if (project.discord_webhooks_json) {
      project.discord_webhooks = JSON.parse(project.discord_webhooks_json);
    }
    
    // Get all tasks
    const tasks = db.prepare('SELECT * FROM tasks WHERE project_id = ?')
      .all(projectId)
      .map(formatTask);
    
    // Get active agents
    const activeAgents = db.prepare(`
      SELECT * FROM agents 
      WHERE project_id = ? AND status = 'running'
      ORDER BY spawned_at DESC
    `).all(projectId);
    
    // Get recent activity
    const activityLog = db.prepare(`
      SELECT * FROM activity_log
      WHERE project_id = ?
      ORDER BY timestamp DESC
      LIMIT 50
    `).all(projectId);
    
    // Calculate stats
    const stats = calculateStats(projectId);
    
    res.json({
      project,
      stats,
      tasks,
      agents: { active: activeAgents },
      activity_log: activityLog
    });
  } catch (error) {
    console.error('Error fetching project:', error);
    res.status(500).json({ error: error.message });
  }
});

// POST /api/projects - Create new project (with Discord integration)
app.post('/api/projects', async (req, res) => {
  try {
    const { name, description, reference, status, target_completion, createDiscordChannels } = req.body;
    
    // Create project in database first
    const stmt = db.prepare(`
      INSERT INTO projects (name, description, reference, status, created_at, target_completion)
      VALUES (?, ?, ?, ?, ?, ?)
    `);
    
    const result = stmt.run(
      name,
      description || '',
      reference || '',
      status || 'not-started',
      new Date().toISOString(),
      target_completion || null
    );
    
    const projectId = result.lastInsertRowid;
    
    // Create Discord channels if requested and configured
    let discordData = null;
    if (createDiscordChannels !== false && discordBot && DISCORD_GUILD_ID) {
      try {
        console.log(`🎮 Creating Discord channels for project ${projectId}: ${name}`);
        discordData = await discordBot.createProjectChannels(DISCORD_GUILD_ID, name, projectId);
        
        // Update project with Discord metadata
        db.prepare(`
          UPDATE projects 
          SET discord_category_id = ?,
              discord_channels_json = ?,
              discord_webhooks_json = ?
          WHERE id = ?
        `).run(
          discordData.categoryId,
          JSON.stringify(discordData.channels),
          JSON.stringify(discordData.webhooks),
          projectId
        );
        
        // Post initial message to project board
        await discordBot.sendWebhookMessage(
          discordData.webhooks.board,
          `🚀 **Project Created: ${name}**\n\n${description || 'No description'}`,
          { username: 'Orchestrator' }
        );
        
        console.log(`✅ Discord channels created for project ${projectId}`);
      } catch (error) {
        console.error('⚠️  Discord channel creation failed:', error.message);
        // Continue anyway - project still created
      }
    }
    
    // Log activity
    db.prepare(`
      INSERT INTO activity_log (project_id, timestamp, agent_id, message, event_type)
      VALUES (?, ?, ?, ?, ?)
    `).run(
      projectId,
      new Date().toISOString(),
      'system',
      `Project created: ${name}`,
      'info'
    );
    
    // Fetch created project
    const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(projectId);
    if (project.discord_channels_json) {
      project.discord_channels = JSON.parse(project.discord_channels_json);
    }
    if (project.discord_webhooks_json) {
      project.discord_webhooks = JSON.parse(project.discord_webhooks_json);
    }
    
    res.json({ 
      success: true, 
      project,
      discordCreated: !!discordData
    });
  } catch (error) {
    console.error('Error creating project:', error);
    res.status(500).json({ error: error.message });
  }
});

// POST /api/tasks - Create task (with Discord thread)
app.post('/api/tasks', async (req, res) => {
  try {
    const {
      id,
      project_id,
      title,
      description,
      state,
      priority,
      estimated_hours,
      dependencies,
      tags
    } = req.body;
    
    const taskId = id || `task-${Date.now()}`;
    
    // Insert task
    const stmt = db.prepare(`
      INSERT INTO tasks (
        id, project_id, title, description, state, priority,
        estimated_hours, dependencies_json, tags_json
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    
    stmt.run(
      taskId,
      project_id,
      title,
      description || '',
      state || 'todo',
      priority || 'medium',
      estimated_hours || 0,
      JSON.stringify(dependencies || []),
      JSON.stringify(tags || [])
    );
    
    // Create Discord thread if channels exist
    const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(project_id);
    if (project && project.discord_channels_json && discordBot) {
      try {
        const channels = JSON.parse(project.discord_channels_json);
        const thread = await discordBot.createThread(
          channels.general,
          `task-${taskId}-${title.toLowerCase().replace(/\s+/g, '-').substring(0, 30)}`,
          `📋 **New Task:** ${title}\n\n${description || 'No description'}`
        );
        
        // Update task with thread ID
        db.prepare('UPDATE tasks SET discord_thread_id = ? WHERE id = ?').run(
          thread.id,
          taskId
        );
        
        console.log(`✅ Created Discord thread for task ${taskId}`);
      } catch (error) {
        console.error('⚠️  Discord thread creation failed:', error.message);
      }
    }
    
    // Log activity
    db.prepare(`
      INSERT INTO activity_log (project_id, timestamp, agent_id, task_id, message, event_type)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(
      project_id,
      new Date().toISOString(),
      'system',
      taskId,
      `Task created: ${title}`,
      'info'
    );
    
    const task = formatTask(db.prepare('SELECT * FROM tasks WHERE id = ?').get(taskId));
    res.json({ success: true, task });
  } catch (error) {
    console.error('Error creating task:', error);
    res.status(500).json({ error: error.message });
  }
});

// POST /api/tasks/:id/update-state - Update task state (with Discord notification)
app.post('/api/tasks/:id/update-state', async (req, res) => {
  try {
    const { state } = req.body;
    const taskId = req.params.id;
    
    const task = db.prepare('SELECT * FROM tasks WHERE id = ?').get(taskId);
    if (!task) {
      return res.status(404).json({ error: 'Task not found' });
    }
    
    // Update state
    db.prepare('UPDATE tasks SET state = ? WHERE id = ?').run(state, taskId);
    
    // Post to Discord if channels exist
    const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(task.project_id);
    if (project && project.discord_webhooks_json && discordBot) {
      try {
        const webhooks = JSON.parse(project.discord_webhooks_json);
        
        let emoji = '📝';
        if (state === 'in-progress') emoji = '🔧';
        if (state === 'ready') emoji = '✅';
        if (state === 'done') emoji = '🎉';
        if (state === 'blocked') emoji = '🚨';
        
        await discordBot.sendWebhookMessage(
          webhooks.status,
          `${emoji} **Task ${state.toUpperCase()}:** ${task.title}`,
          { username: 'Orchestrator' }
        );
      } catch (error) {
        console.error('⚠️  Discord notification failed:', error.message);
      }
    }
    
    // Log activity
    db.prepare(`
      INSERT INTO activity_log (project_id, timestamp, agent_id, task_id, message, event_type)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(
      task.project_id,
      new Date().toISOString(),
      'orchestrator',
      taskId,
      `Task moved to ${state}`,
      'info'
    );
    
    res.json({ success: true });
  } catch (error) {
    console.error('Error updating task state:', error);
    res.status(500).json({ error: error.message });
  }
});

// POST /api/discord/message - Send Discord message (for agents)
app.post('/api/discord/message', async (req, res) => {
  try {
    if (!discordBot) {
      return res.status(503).json({ error: 'Discord not configured' });
    }
    
    const { project_id, channel_type, content, username, embeds } = req.body;
    
    const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(project_id);
    if (!project || !project.discord_webhooks_json) {
      return res.status(404).json({ error: 'Project not found or Discord not configured' });
    }
    
    const webhooks = JSON.parse(project.discord_webhooks_json);
    const webhookUrl = webhooks[channel_type];
    
    if (!webhookUrl) {
      return res.status(400).json({ error: 'Invalid channel type' });
    }
    
    await discordBot.sendWebhookMessage(webhookUrl, content, {
      username: username || 'Agent',
      embeds
    });
    
    res.json({ success: true });
  } catch (error) {
    console.error('Error sending Discord message:', error);
    res.status(500).json({ error: error.message });
  }
});

// GET /api/discord/messages/:channel_id - Read Discord messages
app.get('/api/discord/messages/:channel_id', async (req, res) => {
  try {
    if (!discordBot) {
      return res.status(503).json({ error: 'Discord not configured' });
    }
    
    const messages = await discordBot.getMessages(req.params.channel_id, req.query.limit || 50);
    res.json({ messages });
  } catch (error) {
    console.error('Error reading Discord messages:', error);
    res.status(500).json({ error: error.message });
  }
});

// Health check
app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok',
    discord: !!discordBot,
    timestamp: new Date().toISOString()
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`✅ Agent Swarm Server running on http://localhost:${PORT}`);
  console.log(`   Discord: ${discordBot ? 'Enabled' : 'Disabled'}`);
});
