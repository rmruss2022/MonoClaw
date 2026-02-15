# Rollback Guide (Pre-GitHub OpenClaw Transition)

**Created:** 2026-02-15

This document describes how to roll back changes made during the transition to building OpenClaw from the GitHub codebase.

## Transition Complete

- **OpenClaw source:** `~/openclaw-src` (cloned from GitHub)
- **Version:** 2026.2.15 (nested sub-agent orchestration enabled)
- **Linked via:** `npm link` (replaces global npm install)

To enable `openclaw update` to pull from your checkout, add to `~/.zshrc`:
```bash
export OPENCLAW_GIT_DIR=~/openclaw-src
```

## OpenClaw Config Backup

A backup of `openclaw.json` was created at:
```
~/.openclaw/openclaw.json.backup-pre-github-transition
```

To restore your config:
```bash
cp ~/.openclaw/openclaw.json.backup-pre-github-transition ~/.openclaw/openclaw.json
```

## OpenClaw Version Rollback

If you switch to the GitHub build and need to return to the npm version:

```bash
npm install -g openclaw@2026.2.14
```

## MonoClaw Workspace

To revert this commit:
```bash
cd ~/.openclaw/workspace
git log -1  # note the commit hash
git revert HEAD --no-edit  # or: git reset --hard HEAD~1
git push origin main
```

## OPENCLAW_GIT_DIR

If you set `OPENCLAW_GIT_DIR` for the GitHub checkout, unset it to use the default update behavior:
```bash
unset OPENCLAW_GIT_DIR
```
