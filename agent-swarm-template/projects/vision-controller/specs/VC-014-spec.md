# VC-014: System Tray Integration
**Agent Type:** frontend-dev
**Dependencies:** VC-007

Add macOS system tray icon using Electron Tray API.

## Deliverables
- Update /Users/matthew/Desktop/vision-controller/frontend/main.js
- Create Tray with context menu: Toggle Detection, Last Gesture display, Settings, Quit
- Show detection status (active/paused) in tray icon tooltip
- Use nativeImage for tray icon (create simple icon or use emoji)
- Tray click toggles the main window visibility

## When Complete
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='VC-014';"
