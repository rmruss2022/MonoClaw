#!/bin/bash
# Scaffold ContextClaw OpenClaw Plugin

set -e

REPO_NAME="ContextClaw"
REPO_DIR="$HOME/.openclaw/workspace/$REPO_NAME"

echo "🦞 Scaffolding ContextClaw Plugin..."
echo ""

# Create directory structure
mkdir -p "$REPO_DIR"/{src/{cli,analyzers},dashboard/public,dist}

cd "$REPO_DIR"

# Initialize package.json
cat > package.json << 'EOF'
{
  "name": "@rmruss2022/contextclaw",
  "version": "1.0.0",
  "description": "Session and context management for OpenClaw agents",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "bin": {
    "contextclaw": "./dist/cli/index.js"
  },
  "files": [
    "dist",
    "dashboard"
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
    "context",
    "sessions",
    "pruning",
    "analysis"
  ],
  "author": "Matthew Russell",
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "https://github.com/rmruss2022/ContextClaw"
  },
  "dependencies": {
    "express": "^4.18.2",
    "chalk": "^5.3.0",
    "inquirer": "^9.2.12",
    "cli-table3": "^0.6.3"
  },
  "devDependencies": {
    "@types/node": "^20.10.0",
    "@types/express": "^4.17.21",
    "@types/inquirer": "^9.0.3",
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
EOF

# README
cat > README.md << 'EOF'
# ContextClaw

Session and context management for OpenClaw agents.

## Installation

```bash
npm install -g @rmruss2022/contextclaw
openclaw plugins install @rmruss2022/contextclaw
```

## Setup

```bash
openclaw contextclaw setup
```

## Usage

Analyze and manage OpenClaw sessions and context usage.

```bash
openclaw contextclaw analyze      # Analyze all sessions
openclaw contextclaw prune        # Clean up old sessions
openclaw contextclaw dashboard    # Open dashboard
```

## Features

- 📊 Session analysis and statistics
- 🧹 Intelligent session pruning
- 📈 Context usage visualization
- 🔍 Token tracking per session
- 🗑️ Safe cleanup with backups

## License

MIT
EOF

# Main plugin entry point
cat > src/index.ts << 'EOF'
/**
 * ContextClaw - OpenClaw Plugin
 * Session and context management
 */

export default function ContextClawPlugin(context: any) {
  console.log('ContextClaw plugin loaded');
  
  return {
    name: 'contextclaw',
    version: '1.0.0',
    
    commands: {
      'setup': async () => {
        console.log('ContextClaw setup wizard...');
      },
      
      'analyze': async () => {
        console.log('Analyzing sessions...');
      },
      
      'prune': async () => {
        console.log('Pruning old sessions...');
      },
      
      'dashboard': async () => {
        console.log('Opening dashboard...');
      }
    }
  };
}
EOF

echo "✅ Scaffold complete!"
echo ""
echo "Next steps:"
echo "  cd $REPO_DIR"
echo "  npm install"
echo "  npm run build"
echo ""
echo "📂 Structure created at: $REPO_DIR"
