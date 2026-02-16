#!/bin/bash
# Scaffold ActivityClaw OpenClaw Plugin

set -e

REPO_NAME="ActivityClaw"
REPO_DIR="$HOME/.openclaw/workspace/$REPO_NAME"

echo "🦞 Scaffolding ActivityClaw Plugin..."
echo ""

# Create directory structure
mkdir -p "$REPO_DIR"/{src/{cli,hooks},dashboard/{public,server},skills,dist}

cd "$REPO_DIR"

# Initialize package.json
cat > package.json << 'EOF'
{
  "name": "@rmruss2022/activityclaw",
  "version": "1.0.0",
  "description": "Real-time activity tracking and visualization for OpenClaw agents",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "bin": {
    "activityclaw": "./dist/cli/index.js"
  },
  "files": [
    "dist",
    "dashboard",
    "skills"
  ],
  "scripts": {
    "build": "tsc",
    "dev": "tsc --watch",
    "prepublishOnly": "npm run build"
  },
  "openclaw": {
    "extensions": [
      "./dist/index.js"
    ]
  },
  "keywords": [
    "openclaw",
    "activity",
    "monitoring",
    "dashboard"
  ],
  "author": "Matthew Russell",
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "https://github.com/rmruss2022/ActivityClaw"
  },
  "dependencies": {
    "express": "^4.18.2",
    "better-sqlite3": "^9.3.0",
    "chalk": "^5.3.0",
    "inquirer": "^9.2.12"
  },
  "devDependencies": {
    "@types/node": "^20.10.0",
    "@types/express": "^4.17.21",
    "typescript": "^5.3.3"
  }
}
EOF

# TypeScript config
cat > tsconfig.json << 'EOF'
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "lib": ["ES2020"],
    "outDir": "./dist",
    "rootDir": "./src",
    "declaration": true,
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
EOF

# Git setup
cat > .gitignore << 'EOF'
node_modules/
dist/
*.log
.DS_Store
*.db
*.db-shm
*.db-wal
EOF

# README
cat > README.md << 'EOF'
# ActivityClaw

Real-time activity tracking and visualization for OpenClaw agents.

## Installation

```bash
npm install -g @rmruss2022/activityclaw
openclaw plugins install @rmruss2022/activityclaw
```

## Setup

```bash
openclaw activityclaw setup
```

## Usage

Once installed, ActivityClaw automatically tracks all agent activities in real-time.

Open the dashboard:
```bash
openclaw activityclaw dashboard
```

Or visit: http://localhost:18796

## Features

- 📊 Real-time activity monitoring
- 🤖 Multi-agent support (main + sub-agents)
- 🎨 Beautiful visual dashboard
- 🔍 Search and filter activities
- 📈 Activity statistics and trends
- 🔒 Local-only (privacy-first)

## Commands

```bash
openclaw activityclaw setup      # Interactive setup wizard
openclaw activityclaw start      # Start tracker + dashboard
openclaw activityclaw stop       # Stop services
openclaw activityclaw status     # Show status
openclaw activityclaw dashboard  # Open dashboard
openclaw activityclaw logs       # View logs
```

## License

MIT
EOF

# Main plugin entry point
cat > src/index.ts << 'EOF'
/**
 * ActivityClaw - OpenClaw Plugin
 * Real-time activity tracking and visualization
 */

// TODO: Import types from @openclaw/types when available
// For now, use any for rapid prototyping

export default function ActivityClawPlugin(context: any) {
  console.log('ActivityClaw plugin loaded');
  
  return {
    name: 'activityclaw',
    version: '1.0.0',
    
    // Register hooks for real-time tracking
    hooks: {
      'tool_result_persist': async (event: any) => {
        // TODO: Implement activity tracking hook
        console.log('Tool called:', event.toolName);
      }
    },
    
    // Register CLI commands
    commands: {
      'setup': async () => {
        console.log('ActivityClaw setup wizard...');
        // TODO: Implement setup wizard
      },
      
      'start': async () => {
        console.log('Starting ActivityClaw...');
        // TODO: Start tracker + dashboard server
      },
      
      'stop': async () => {
        console.log('Stopping ActivityClaw...');
        // TODO: Stop services
      },
      
      'status': async () => {
        console.log('ActivityClaw status...');
        // TODO: Show status
      },
      
      'dashboard': async () => {
        console.log('Opening dashboard...');
        // TODO: Open browser
      }
    }
  };
}
EOF

# Placeholder files
touch src/cli/setup.ts
touch src/cli/status.ts
touch src/hooks/activity.ts
touch src/server.ts

echo "✅ Scaffold complete!"
echo ""
echo "Next steps:"
echo "  cd $REPO_DIR"
echo "  npm install"
echo "  npm run build"
echo "  openclaw plugins install -l ."
echo ""
echo "📂 Structure created at: $REPO_DIR"
