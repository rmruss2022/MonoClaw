#!/bin/bash
# Deploy blog to Vercel
# Commits new posts and pushes to trigger Vercel build

set -e

cd /Users/matthew/.openclaw/workspace/matts-claw-blog

# Check if there are changes
if [ -z "$(git status --porcelain)" ]; then
    echo "No changes to deploy"
    exit 0
fi

# Commit and push
git add public/posts/
git commit -m "Add blog post $(date '+%Y-%m-%d')"
git push origin main

echo "✅ Blog deployed! Vercel will rebuild automatically."
