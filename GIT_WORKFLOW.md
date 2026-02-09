# Git Workflow for OpenClaw Workspace

## Branch Strategy

### Main Branches
- `main` - Production-ready code, always stable
- `develop` - Integration branch for features

### Feature Branches
- `feature/<name>` - New features or systems
- `fix/<name>` - Bug fixes
- `docs/<name>` - Documentation updates
- `refactor/<name>` - Code refactoring

## Workflow

### 1. Start New Work
```bash
# Make sure main is up to date
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/descriptive-name
```

### 2. Make Changes
```bash
# Work on your changes
# Commit frequently with clear messages
git add <files>
git commit -m "Clear, descriptive commit message"
```

### 3. Keep Branch Updated
```bash
# Regularly rebase on main to stay current
git fetch origin
git rebase origin/main

# Or merge if you prefer
git merge origin/main
```

### 4. Finish Feature
```bash
# Ensure branch is clean and rebased
git rebase -i origin/main  # Interactive rebase to clean up commits

# Push feature branch
git push origin feature/descriptive-name

# Merge to main (fast-forward if possible)
git checkout main
git merge --ff-only feature/descriptive-name
# OR
git merge --no-ff feature/descriptive-name  # Keep branch history

# Push main
git push origin main

# Delete feature branch
git branch -d feature/descriptive-name
git push origin --delete feature/descriptive-name
```

## Commit Message Format

```
<type>: <subject>

<body (optional)>

<footer (optional)>
```

### Types
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `refactor:` Code refactoring
- `test:` Adding tests
- `chore:` Maintenance tasks

### Examples
```
feat: Add Docker agent system with 5 profiles

- Built complete CLI with 12 commands
- Implemented hub integration
- Added builder, tester, deployer, researcher, docker-host profiles
- Tested with Express API build

Closes #123
```

## Rebase vs Merge

### Use Rebase When
- Updating your feature branch with latest main
- Cleaning up commit history before merging
- Working alone on a branch

```bash
git rebase origin/main
git rebase -i HEAD~5  # Interactive rebase last 5 commits
```

### Use Merge When
- Integrating feature branch into main (for history preservation)
- Multiple people working on same branch
- Want to preserve exact commit timeline

```bash
git merge --no-ff feature/my-feature  # Preserve branch history
git merge --ff-only feature/my-feature  # Fast-forward only
```

## Interactive Rebase

Clean up commits before merging:

```bash
git rebase -i HEAD~3

# In editor:
# pick abc123 First commit
# squash def456 Fix typo
# squash ghi789 Another small fix
# Result: One clean commit
```

## Rules
1. **Never force push to main** - `git push --force` only on feature branches
2. **Keep commits atomic** - One logical change per commit
3. **Write clear commit messages** - Future you will thank you
4. **Rebase before merging** - Keep history clean
5. **Delete merged branches** - Keep repo tidy

## Emergency Fixes

For urgent hotfixes:

```bash
git checkout main
git checkout -b hotfix/critical-bug
# Fix the bug
git commit -m "hotfix: Fix critical production bug"
git checkout main
git merge --ff-only hotfix/critical-bug
git push origin main
git branch -d hotfix/critical-bug
```

## Current Practice (Updated Feb 9, 2026)

Going forward, all work will:
1. Start on a feature branch
2. Be committed with clear messages
3. Be rebased on main before merging
4. Be merged to main only when ready
5. Have branches deleted after merge

Last direct-to-main commit: 581678b (Feb 9, 2026)
