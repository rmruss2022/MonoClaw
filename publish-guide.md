# Complete Publishing Guide

## Step 1: npm Login

```bash
npm login
```

Follow the prompts to authenticate with npm.

## Step 2: Publish ActivityClaw to npm

```bash
cd ~/.openclaw/workspace/ActivityClaw
npm publish --access public
```

Expected output:
```
+ @rmruss2022/activityclaw@1.0.0
```

## Step 3: Publish ContextClaw to npm

```bash
cd ~/.openclaw/workspace/ContextClaw
npm publish --access public
```

Expected output:
```
+ @rmruss2022/contextclaw@1.0.0
```

## Step 4: Install ClawHub CLI (if not installed)

```bash
npm install -g clawhub
```

## Step 5: Login to ClawHub

```bash
clawhub login
```

This will open a browser for authentication.

## Step 6: Publish ActivityClaw Skill to ClawHub

```bash
cd ~/.openclaw/workspace
clawhub publish skills/activityclaw-usage \
  --slug activityclaw-usage \
  --name "ActivityClaw Plugin Usage" \
  --version 1.0.0 \
  --changelog "Initial release: Skill for using ActivityClaw plugin" \
  --tags latest,plugin,monitoring,activity
```

## Step 7: Publish ContextClaw Skill to ClawHub

```bash
clawhub publish skills/contextclaw-usage \
  --slug contextclaw-usage \
  --name "ContextClaw Plugin Usage" \
  --version 1.0.0 \
  --changelog "Initial release: Skill for using ContextClaw plugin" \
  --tags latest,plugin,context,session,management
```

## Step 8: Verify Publications

Check npm:
- https://www.npmjs.com/package/@rmruss2022/activityclaw
- https://www.npmjs.com/package/@rmruss2022/contextclaw

Check ClawHub:
- https://clawhub.ai/skills/activityclaw-usage
- https://clawhub.ai/skills/contextclaw-usage

## Step 9: Post to Discord

Copy from `discord-announcements.md` and post to:
- #plugins channel (or #showcase)

## Step 10: Test Installation

Test the full install flow:

```bash
# Test ActivityClaw
npm install -g @rmruss2022/activityclaw
openclaw plugins install @rmruss2022/activityclaw
openclaw activityclaw status
openclaw activityclaw dashboard

# Test ContextClaw
npm install -g @rmruss2022/contextclaw
openclaw plugins install @rmruss2022/contextclaw
openclaw contextclaw analyze
openclaw contextclaw dashboard

# Test skills
clawhub install activityclaw-usage
clawhub install contextclaw-usage
```

## Troubleshooting

### npm publish fails with 403

You need to verify your email with npm:
```bash
npm profile get
```

Check if email is verified. If not, verify it on npmjs.com.

### ClawHub publish fails

Make sure you're logged in:
```bash
clawhub whoami
```

If not logged in:
```bash
clawhub login
```

### Plugin install fails

Make sure OpenClaw is up to date:
```bash
openclaw --version
openclaw gateway restart
```

## After Publishing

1. Add screenshots to both GitHub repos
2. Update README files with npm badges
3. Star both repos
4. Share on Twitter/X with #OpenClaw hashtag
5. Consider writing blog posts about the plugins
