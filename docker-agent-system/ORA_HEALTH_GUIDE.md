# Ora Health in Docker Agent

## Setup Complete ✅

The Ora Health React Native app is now running in the Docker agent `simple-test`.

**Project Location:** `/workspace/ora-health` (inside container)
**Dependencies:** 1,482 packages installed
**Build Time:** 18 seconds

## Quick Commands

### From Host

```bash
cd ~/.openclaw/workspace/docker-agent-system/cli

# Run any npm command
./docker-agent exec simple-test "cd /workspace/ora-health && npm <command>"

# Interactive shell
./docker-agent shell simple-test
# Then: cd /workspace/ora-health
```

### Available Scripts

```bash
# Start Expo dev server
npm start

# Start for specific platform
npm run android
npm run ios  
npm run web

# Run tests
npm test
npm run test:coverage
npm run test:watch
```

## Working on the App

### 1. View Source Files

```bash
./docker-agent exec simple-test "cd /workspace/ora-health && ls -R src/"
```

### 2. Edit Code

Option A: Copy files out, edit, copy back
```bash
# Copy out
docker cp openclaw-agent-simple-test:/workspace/ora-health/src ./local-src

# Edit locally...

# Copy back
docker cp ./local-src openclaw-agent-simple-test:/workspace/ora-health/src
```

Option B: Use shell + vim/nano (installed in container)
```bash
./docker-agent shell simple-test
cd /workspace/ora-health/src
# Edit files
```

### 3. Run Development Server

```bash
# Start Expo
./docker-agent exec simple-test "cd /workspace/ora-health && npm start"

# Or web version (easier for Docker)
./docker-agent exec simple-test "cd /workspace/ora-health && npm run web"
```

### 4. Run Tests

```bash
# All tests
./docker-agent exec simple-test "cd /workspace/ora-health && npm test"

# With coverage
./docker-agent exec simple-test "cd /workspace/ora-health && npm run test:coverage"

# Watch mode
./docker-agent exec simple-test "cd /workspace/ora-health && npm run test:watch"
```

### 5. Build for Production

```bash
# Expo build
./docker-agent exec simple-test "cd /workspace/ora-health && npx expo export"
```

## Project Structure

```
ora-health/
├── App.tsx                 # Root component
├── src/
│   ├── components/         # Reusable UI components
│   ├── screens/            # App screens
│   ├── navigation/         # Navigation setup
│   ├── services/           # API/backend services
│   ├── theme/              # Theme configuration
│   └── types/              # TypeScript types
├── package.json
└── tsconfig.json
```

## Current Status

- ✅ Dependencies installed (1,482 packages)
- ✅ TypeScript configured
- ✅ React Native + Expo setup
- ✅ Navigation configured
- ✅ API services ready
- ⚠️ 17 vulnerabilities (2 low, 1 moderate, 14 high) - run `npm audit fix`

## Next Steps

### Recommended First Tasks

1. **Audit Security Issues**
   ```bash
   ./docker-agent exec simple-test "cd /workspace/ora-health && npm audit fix"
   ```

2. **Run Tests to Verify Setup**
   ```bash
   ./docker-agent exec simple-test "cd /workspace/ora-health && npm test"
   ```

3. **Start Development Server**
   ```bash
   ./docker-agent exec simple-test "cd /workspace/ora-health && npm run web"
   ```

4. **Review Documentation**
   ```bash
   ./docker-agent exec simple-test "cd /workspace/ora-health && cat README.md"
   ./docker-agent exec simple-test "cd /workspace/ora-health && cat CLAUDE.md"
   ```

## Continuous Development Workflow

### Using a Sub-Agent for Development

For active development on Ora Health, you could:

1. **Spawn a dedicated sub-agent**
   ```bash
   # From workspace
   openclaw sessions:spawn "Work on Ora Health app in Docker agent simple-test. Make improvements, fix bugs, and test changes."
   ```

2. **Or use feature branch workflow**
   ```bash
   cd /workspace/ora-health
   git checkout -b feature/new-feature
   # Make changes
   npm test
   git commit -m "feat: Add new feature"
   ```

## Tips

- **Persistent Storage:** `/workspace` is a Docker volume - changes persist across restarts
- **Fast Rebuilds:** Dependencies cached in `node_modules` (already installed)
- **TypeScript:** Configured and ready - type checking on save
- **Hot Reload:** Expo provides fast refresh during development
- **Testing:** Jest configured with coverage reporting

## Troubleshooting

### Permission Issues
```bash
# Fix ownership (run from host)
docker exec -u root openclaw-agent-simple-test chown -R node:node /workspace/ora-health
```

### Clear Node Modules
```bash
./docker-agent exec simple-test "cd /workspace/ora-health && rm -rf node_modules && npm install --legacy-peer-deps"
```

### View Logs
```bash
./docker-agent logs simple-test --follow
```

## Resource Usage

Container stats:
```bash
docker stats openclaw-agent-simple-test --no-stream
```

Current usage:
- Node modules: ~826 directories
- Disk: ~1MB source + ~800MB dependencies
- Memory: ~50-100MB (idle), more during build

---

**Agent:** simple-test  
**Profile:** base (Node.js 18)  
**Status:** Ready for development ✅  
**Last Updated:** Feb 9, 2026 12:47 PM EST
