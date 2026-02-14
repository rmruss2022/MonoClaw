# Agent Swarm - Project Setup Guide

This guide explains how to add new projects to the Agent Swarm system with proper configuration.

## Overview

The Agent Swarm system is designed to support **multiple projects simultaneously**. Each project has its own:

- File paths and directories
- Reference materials
- Technology stack
- Agent requirements
- Tasks and dependencies
- Context documents

## Adding a New Project

### Step 1: Create the Project

Use the API to create a new project:

```bash
curl -X POST http://localhost:3001/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Awesome Project",
    "description": "Brief description of what this project is",
    "reference": "Optional reference URL or path",
    "status": "not-started"
  }'
```

This returns a project with an `id` (e.g., `4`). Note this ID for the next steps.

### Step 2: Add Project Configuration

Create a configuration file (e.g., `my-project-config.json`):

```json
{
  "file_paths": {
    "app_root": "/path/to/your/app/",
    "backend_root": "/path/to/your/backend/",
    "assets": "/path/to/assets/",
    "reference_docs": "/path/to/docs/"
  },
  "reference_materials": [
    {
      "type": "design",
      "name": "Main Design Mockup",
      "path": "/path/to/design.fig"
    },
    {
      "type": "brand",
      "name": "Brand Guidelines",
      "path": "/path/to/brand-guide.pdf"
    }
  ],
  "tech_stack": {
    "frontend": "React / Vue / Angular / etc",
    "backend": "Node.js / Python / Ruby / etc",
    "database": "PostgreSQL / MongoDB / etc",
    "services": ["list", "of", "services"]
  },
  "agent_requirements": {
    "designer": ["Figma", "Adobe XD", "etc"],
    "frontend_dev": ["React", "TypeScript", "etc"],
    "backend_dev": ["Node.js", "databases", "etc"],
    "qa": ["Jest", "Cypress", "etc"],
    "content": ["copywriting", "etc"]
  }
}
```

Update the project with configuration:

```bash
# Using SQLite directly
sqlite3 swarm.db "UPDATE projects SET configuration_json = readfile('my-project-config.json') WHERE id = 4;"

# OR using a Node.js script
node -e "
const Database = require('better-sqlite3');
const fs = require('fs');
const db = new Database('swarm.db');
const config = JSON.parse(fs.readFileSync('my-project-config.json', 'utf8'));
db.prepare('UPDATE projects SET configuration_json = ? WHERE id = 4').run(JSON.stringify(config));
db.close();
"
```

### Step 3: Add Context Documents

Add planning documents, roadmaps, and orchestrator instructions:

```javascript
// roadmap.md
const roadmap = fs.readFileSync('roadmap.md', 'utf8');

await fetch('http://localhost:3001/api/projects/4/context', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    document_type: 'roadmap',
    title: 'Project Roadmap',
    content: roadmap,
    file_path: '/path/to/roadmap.md'
  })
});

// Repeat for other documents (plan, specs, etc)
```

### Step 4: Create Tasks

Use the PM-Agent to break down the project into tasks, or create them manually:

```bash
curl -X POST http://localhost:3001/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "id": "MYPROJ-001",
    "project_id": 4,
    "title": "Design home screen",
    "description": "Create mockup for home screen",
    "state": "todo",
    "priority": "critical",
    "estimated_hours": 4,
    "assigned_to": "Designer-Agent",
    "dependencies": [],
    "tags": ["design", "P0"]
  }'
```

### Step 5: Customize Orchestrator Instructions

The orchestrator instructions use **configuration placeholders** that work for any project:

- `{project.configuration.file_paths.app_root}`
- `{project.configuration.file_paths.backend_root}`
- `{project.configuration.file_paths.assets}`
- etc.

When the orchestrator spawns agents, it fetches the project configuration and replaces these placeholders with actual paths.

**No customization needed!** The orchestrator is already project-agnostic.

## Project Configuration Schema

### Required Fields

```json
{
  "file_paths": {
    "app_root": "string (required)",
    "backend_root": "string (optional)",
    // Add any custom paths your project needs
  }
}
```

### Optional Fields

```json
{
  "reference_materials": [
    {
      "type": "design | brand | spec | docs",
      "name": "Display name",
      "path": "File path or URL",
      "contents": ["optional", "list", "of", "items"]
    }
  ],
  "tech_stack": {
    "frontend": "Framework name",
    "backend": "Framework name",
    "database": "Database name",
    "services": ["array", "of", "services"]
  },
  "agent_requirements": {
    "agent_type": ["skill1", "skill2", "tool1"]
  }
}
```

## Accessing Configuration

### In Dashboard

The dashboard automatically loads and displays project configuration. Hard refresh (Cmd+Shift+R) to see updates.

### In API

```bash
# Get full project with configuration
curl http://localhost:3001/api/projects/4 | jq '.project.configuration'

# Get specific path
curl http://localhost:3001/api/projects/4 | jq '.project.configuration.file_paths.app_root'
```

### In Orchestrator

```javascript
// Orchestrator automatically fetches configuration before spawning
const response = await fetch('http://localhost:3001/api/projects/4');
const projectData = await response.json();
const config = projectData.project.configuration;

// Use paths in agent spawning
const appRoot = config.file_paths.app_root;
const backendRoot = config.file_paths.backend_root;
```

## Multi-Project Workflow

### Switching Projects in Dashboard

Use the project dropdown in the header to switch between projects. The dashboard will:

1. Load the selected project's tasks
2. Fetch project configuration
3. Display context documents
4. Show active agents

### Running Multiple Projects Simultaneously

The orchestrator can manage multiple projects:

1. Monitor all projects in rotation
2. Spawn agents for ready tasks across projects
3. Track progress independently
4. Report per-project status

## Example: CLI Tool Project

```json
{
  "file_paths": {
    "app_root": "/Users/matthew/projects/my-cli-tool/",
    "docs": "/Users/matthew/projects/my-cli-tool/docs/"
  },
  "tech_stack": {
    "language": "Node.js",
    "cli_framework": "Commander.js",
    "testing": "Jest"
  },
  "agent_requirements": {
    "backend_dev": ["Node.js", "CLI tools", "npm publishing"],
    "qa": ["Jest", "integration testing"],
    "content": ["documentation", "README", "CLI help text"]
  }
}
```

## Example: Web App Project

```json
{
  "file_paths": {
    "app_root": "/Users/matthew/projects/my-web-app/client/",
    "backend_root": "/Users/matthew/projects/my-web-app/server/",
    "assets": "/Users/matthew/projects/my-web-app/assets/",
    "design_files": "/Users/matthew/projects/my-web-app/design/"
  },
  "reference_materials": [
    {
      "type": "design",
      "name": "Figma Mockups",
      "path": "https://figma.com/file/xyz"
    }
  ],
  "tech_stack": {
    "frontend": "React + Vite",
    "backend": "Express.js",
    "database": "PostgreSQL"
  },
  "agent_requirements": {
    "designer": ["Figma", "Web design", "responsive design"],
    "frontend_dev": ["React", "Vite", "TypeScript", "Tailwind"],
    "backend_dev": ["Node.js", "Express", "PostgreSQL", "REST API"],
    "qa": ["Cypress", "Jest", "Playwright"]
  }
}
```

## Tips

1. **Use absolute paths** for file_paths to avoid ambiguity
2. **Add trailing slashes** to directory paths for consistency
3. **Document custom paths** in reference_materials
4. **Keep tech_stack updated** as you add dependencies
5. **Update agent_requirements** if you need specialized skills

## Troubleshooting

### Configuration not showing in dashboard

- Hard refresh the dashboard (Cmd+Shift+R)
- Check API: `curl http://localhost:3001/api/projects/{id} | jq '.project.configuration'`
- Verify JSON is valid: `echo $CONFIG | jq .`

### Orchestrator using wrong paths

- Check that placeholders exist: `{project.configuration.file_paths.app_root}`
- Verify orchestrator instructions updated: `curl http://localhost:3001/api/projects/{id}/context`
- Ensure configuration was saved to database

### Agent spawning fails

- Check task dependencies are met
- Verify agent type matches assigned_to field
- Ensure project configuration has required paths

---

**Created:** 2026-02-13  
**Version:** 1.0  
**Location:** `/Users/matthew/.openclaw/workspace/agent-swarm-template/PROJECT_SETUP_GUIDE.md`
