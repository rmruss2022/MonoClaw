# Activity Tracker V3: Gateway Hook Integration
## Comprehensive Implementation Plan

**Goal:** Eliminate file polling entirely by hooking directly into OpenClaw's tool execution pipeline.

---

## Architecture Overview

### Current (v2/v3 - File Polling)
```
Tool Call → Transcript File → Poll (5s) → Read File → Parse → POST → Activity Hub
   ↓           ↓                ↓            ↓         ↓       ↓
  0ms        ~50ms            5000ms       ~100ms    ~50ms   ~20ms    = ~5220ms latency
```

### Proposed (v3 - Hook Integration)
```
Tool Call → Hook Handler → POST → Activity Hub
   ↓            ↓            ↓         ↓
  0ms         ~1ms         ~20ms    ~1ms              = ~22ms latency (250x faster!)
```

---

## Implementation Strategy

### Phase 1: Create OpenClaw Plugin (with tool_result_persist hook)

OpenClaw has two hook systems:
1. **Event hooks** (command:new, gateway:startup) - for lifecycle events
2. **Plugin hooks** (tool_result_persist) - for intercepting tool results

**Why Plugin:** The `tool_result_persist` hook lets us intercept tool calls BEFORE they're written to transcript, giving us real-time access to tool execution.

#### 1.1 Plugin Structure
```
~/.openclaw/plugins/activity-tracker/
├── package.json           # Plugin metadata
├── index.ts              # Plugin entry point
├── hooks/
│   └── activity-capture/
│       ├── HOOK.md       # Hook documentation
│       └── handler.ts    # Tool result interceptor
└── lib/
    └── activity-poster.ts # POST logic to Activity Hub
```

#### 1.2 package.json
```json
{
  "name": "@openclaw/activity-tracker",
  "version": "1.0.0",
  "description": "Real-time activity tracking via tool_result_persist hook",
  "main": "index.ts",
  "openclaw": {
    "plugin": {
      "id": "activity-tracker",
      "name": "Activity Tracker",
      "emoji": "📊",
      "hooks": ["./hooks/activity-capture"]
    }
  }
}
```

#### 1.3 hooks/activity-capture/HOOK.md
```markdown
---
name: activity-capture
description: "Capture tool calls in real-time and post to Activity Hub"
metadata:
  openclaw:
    emoji: "📊"
    events: ["tool_result_persist"]
    always: true
---

# Activity Capture Hook

Intercepts all tool calls before they're written to transcript and posts them to Activity Hub.

## Supported Tools
- write (file creation)
- edit (file modification)
- read (file access)
- exec (command execution)

## Configuration
Set `ACTIVITY_HUB_URL` environment variable (defaults to http://localhost:18796/api/activity/log)
```

#### 1.4 hooks/activity-capture/handler.ts
```typescript
import type { ToolResultPersistHook } from "../../../src/plugins/types.js";
import { postActivity } from "../../lib/activity-poster.js";

const handler: ToolResultPersistHook = (result, context) => {
  // Extract tool call details
  const { toolName, args, sessionId } = context;
  
  // Filter to tracked tools only
  if (!["write", "edit", "read", "exec"].includes(toolName)) {
    return; // Pass through unmodified
  }

  // Get agent label from session
  const agentLabel = context.session?.label || null;

  // Build activity payload
  const activity = buildActivity(toolName, args, sessionId, agentLabel);

  // Post asynchronously (non-blocking)
  void postActivity(activity);

  // Return undefined to keep result as-is
  return undefined;
};

function buildActivity(tool: string, args: any, sessionId: string, agentLabel?: string | null) {
  let action = '';
  let type = 'system';
  let category = 'system';
  let color = '#feca57';
  let icon = '🔧';
  let metadata: any = {
    tool,
    sessionId,
    agentLabel,
  };

  switch (tool) {
    case 'write':
      const writePath = args.path || args.file_path || 'file';
      action = agentLabel 
        ? `${agentLabel} created ${basename(writePath)}`
        : `Created ${basename(writePath)}`;
      type = 'file-create';
      category = 'file-create';
      color = '#00ff88';
      icon = '📝';
      metadata.path = writePath;
      metadata.filename = basename(writePath);
      break;

    case 'edit':
      const editPath = args.path || args.file_path || 'file';
      action = agentLabel
        ? `${agentLabel} modified ${basename(editPath)}`
        : `Modified ${basename(editPath)}`;
      type = 'file-edit';
      category = 'file-edit';
      color = '#00d9ff';
      icon = '✏️';
      metadata.path = editPath;
      metadata.filename = basename(editPath);
      break;

    case 'read':
      const readPath = args.path || args.file_path || 'file';
      action = agentLabel
        ? `${agentLabel} read ${basename(readPath)}`
        : `Read ${basename(readPath)}`;
      type = 'file-read';
      category = 'file-read';
      color = '#888';
      icon = '👁️';
      metadata.path = readPath;
      metadata.filename = basename(readPath);
      break;

    case 'exec':
      const cmd = args.command || '';
      const truncated = cmd.length > 60 ? cmd.substring(0, 60) + '...' : cmd;
      action = agentLabel
        ? `${agentLabel} executed: ${truncated}`
        : `Executed: ${truncated}`;
      type = 'command';
      category = 'command';
      color = '#9b59b6';
      icon = '⚡';
      metadata.command = cmd;
      break;
  }

  return {
    action,
    type,
    agentName: agentLabel || sessionId.substring(0, 8),
    agentId: sessionId.substring(0, 8),
    category,
    color,
    icon,
    metadata,
  };
}

function basename(path: string): string {
  return path.split('/').pop() || path;
}

export default handler;
```

#### 1.5 lib/activity-poster.ts
```typescript
const ACTIVITY_HUB_URL = process.env.ACTIVITY_HUB_URL || 'http://localhost:18796/api/activity/log';
const POST_TIMEOUT = 3000; // 3 seconds

// Simple queue to batch requests
const activityQueue: any[] = [];
let flushTimer: NodeJS.Timeout | null = null;

export async function postActivity(activity: any) {
  activityQueue.push(activity);

  // Debounce: flush after 500ms of inactivity
  if (flushTimer) clearTimeout(flushTimer);
  
  flushTimer = setTimeout(() => {
    flushQueue();
  }, 500);
}

async function flushQueue() {
  if (activityQueue.length === 0) return;

  const batch = activityQueue.splice(0, activityQueue.length);

  for (const activity of batch) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), POST_TIMEOUT);

      const response = await fetch(ACTIVITY_HUB_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(activity),
        signal: controller.signal,
      });

      clearTimeout(timeout);

      if (!response.ok) {
        console.error(`[activity-tracker] Failed to post: ${response.statusText}`);
      }
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        console.error('[activity-tracker] Request timeout');
      } else {
        console.error('[activity-tracker] Post error:', error);
      }
    }
  }
}
```

#### 1.6 index.ts (Plugin Entry)
```typescript
import type { Plugin } from "../../src/plugins/types.js";

const plugin: Plugin = {
  id: "activity-tracker",
  name: "Activity Tracker",
  description: "Real-time activity tracking via tool execution hooks",
  version: "1.0.0",

  async onLoad(api) {
    console.log("[activity-tracker] Plugin loaded");
    
    // Register hooks from ./hooks directory
    await api.registerPluginHooksFromDir("./hooks");
  },

  async onUnload() {
    console.log("[activity-tracker] Plugin unloaded");
  }
};

export default plugin;
```

---

### Phase 2: Install & Enable Plugin

#### 2.1 Install Plugin
```bash
# Install to managed plugins directory
openclaw plugins install ~/.openclaw/workspace/activity-hub/activity-tracker-plugin

# Or link for development
openclaw plugins install -l ~/.openclaw/workspace/activity-hub/activity-tracker-plugin
```

#### 2.2 Enable Plugin
```bash
openclaw plugins enable activity-tracker
```

#### 2.3 Verify Installation
```bash
# List plugins
openclaw plugins list
# Should show: 📊 activity-tracker ✓

# Check hooks
openclaw hooks list
# Should show: plugin:activity-tracker hooks
```

#### 2.4 Restart Gateway
```bash
# macOS menubar app: Click "Restart Gateway"
# Or via CLI:
openclaw gateway restart
```

---

### Phase 3: Deprecate Old Polling Tracker

#### 3.1 Stop Old Tracker
```bash
ps aux | grep activity-tracker-v3.js | grep -v grep | awk '{print $2}' | xargs kill -9
```

#### 3.2 Archive Old Implementation
```bash
mkdir -p ~/.openclaw/workspace/activity-hub/archive
mv activity-tracker-v2.js archive/
mv activity-tracker-v3.js archive/
```

#### 3.3 Update Documentation
- Add note to TRACKER_FIX.md about plugin-based v3
- Update README to reference plugin approach

---

### Phase 4: Testing & Validation

#### 4.1 Unit Tests
```typescript
// Test hook handler
import { test, expect } from "vitest";
import handler from "./hooks/activity-capture/handler.js";

test("captures write tool call", async () => {
  const result = { output: "Success" };
  const context = {
    toolName: "write",
    args: { path: "/tmp/test.txt", content: "Hello" },
    sessionId: "abc123",
    session: { label: "TestAgent" }
  };

  const modified = await handler(result, context);
  
  expect(modified).toBeUndefined(); // Should pass through
  // Assert POST was called (mock fetch)
});
```

#### 4.2 Integration Tests
```bash
# Trigger tool calls in real session
openclaw chat "Create a file called test.txt with content 'Hello World'"

# Check Activity Hub dashboard
open http://localhost:18796/

# Verify activity appears within 1 second
```

#### 4.3 Performance Validation
```bash
# Measure latency
time openclaw chat "Run a command: echo 'test'"

# Monitor CPU/memory
top -pid $(pgrep -f openclaw)

# Expected: <0.1% CPU increase, <5MB memory
```

---

### Phase 5: Production Optimization

#### 5.1 Add Rate Limiting
```typescript
// In activity-poster.ts
const rateLimiter = new Map<string, number>();

function shouldThrottle(activityKey: string): boolean {
  const lastPost = rateLimiter.get(activityKey);
  const now = Date.now();
  
  if (lastPost && (now - lastPost) < 1000) {
    return true; // Skip if same activity posted within 1 second
  }
  
  rateLimiter.set(activityKey, now);
  return false;
}
```

#### 5.2 Add Circuit Breaker
```typescript
// If Activity Hub is down, stop posting for 5 minutes
let circuitOpen = false;
let circuitResetTimer: NodeJS.Timeout | null = null;

async function postWithCircuitBreaker(url: string, body: any) {
  if (circuitOpen) {
    console.log('[activity-tracker] Circuit open, skipping post');
    return;
  }

  try {
    const response = await fetch(url, { method: 'POST', body });
    if (response.ok) {
      return; // Success
    }
    throw new Error(`HTTP ${response.status}`);
  } catch (error) {
    console.error('[activity-tracker] Opening circuit for 5 minutes');
    circuitOpen = true;
    
    if (circuitResetTimer) clearTimeout(circuitResetTimer);
    circuitResetTimer = setTimeout(() => {
      console.log('[activity-tracker] Circuit reset');
      circuitOpen = false;
    }, 300000); // 5 minutes
    
    throw error;
  }
}
```

#### 5.3 Add Health Check
```typescript
// Periodic health check to Activity Hub
setInterval(async () => {
  try {
    const response = await fetch('http://localhost:18796/api/health', {
      method: 'GET',
      signal: AbortSignal.timeout(1000)
    });
    
    if (response.ok) {
      console.log('[activity-tracker] Health check OK');
    }
  } catch (error) {
    console.error('[activity-tracker] Activity Hub unreachable');
  }
}, 60000); // Every minute
```

---

## Benefits of Hook-Based Approach

### Performance
- **250x faster**: ~22ms vs ~5220ms latency
- **Zero polling overhead**: No file scanning, no CPU waste
- **Instant feedback**: Activities appear immediately
- **Scalable**: Handles any volume of tool calls

### Reliability
- **No missed activities**: Captures every tool call
- **No file reading errors**: Direct hook integration
- **No race conditions**: Synchronous hook execution
- **Persistent across restarts**: Plugin auto-loads

### Maintainability
- **Cleaner architecture**: Standard OpenClaw plugin
- **Better error handling**: Circuit breaker, rate limiting
- **Easy debugging**: Gateway logs show hook execution
- **Future-proof**: Uses official plugin API

---

## Rollback Plan

If hook-based approach fails:

1. **Keep v3 polling tracker as backup**
   ```bash
   mv archive/activity-tracker-v3.js ./
   node activity-tracker-v3.js
   ```

2. **Disable plugin**
   ```bash
   openclaw plugins disable activity-tracker
   openclaw gateway restart
   ```

3. **Document issues** in TRACKER_FIX.md

---

## Success Metrics

After deployment, verify:

- ✅ Activities appear in <1 second
- ✅ CPU usage <0.1% (vs 2% with polling)
- ✅ Zero timeout errors in logs
- ✅ 100% tool call capture rate
- ✅ Activity Hub database growing correctly
- ✅ Gateway logs show hook registration

---

## Timeline

- **Phase 1** (Plugin Creation): 30 minutes
- **Phase 2** (Installation): 5 minutes
- **Phase 3** (Deprecation): 5 minutes
- **Phase 4** (Testing): 15 minutes
- **Phase 5** (Optimization): 15 minutes

**Total: ~70 minutes**

---

## Next Steps

1. Create plugin directory structure
2. Implement handler.ts with tool_result_persist hook
3. Create activity-poster.ts with batching logic
4. Write package.json and index.ts
5. Install plugin via openclaw plugins install
6. Enable and test
7. Monitor and optimize

**Ready to build?** Let's start with Phase 1 and create the plugin structure.
