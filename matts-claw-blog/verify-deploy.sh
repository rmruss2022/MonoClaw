#!/bin/bash
# Verify that the blog deployed successfully to Vercel

set -e

BLOG_URL="https://matts-claw.vercel.app"
TODAY=$(date '+%Y-%m-%d')

# Wait for Vercel to build (up to 2 minutes)
echo "⏳ Waiting for Vercel deployment..."
sleep 30

for i in {1..4}; do
  # Check if today's post exists on the live site
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BLOG_URL}/posts/${TODAY}" 2>&1)
  
  if [ "$STATUS" = "200" ]; then
    echo "✅ Blog post deployed successfully: ${BLOG_URL}/posts/${TODAY}"
    exit 0
  fi
  
  echo "⏳ Deployment not ready yet (attempt $i/4), waiting 30s..."
  sleep 30
done

echo "❌ Blog post deployment failed or timed out"
echo "Check Vercel dashboard: https://vercel.com/matthew/matts-claw-blog/deployments"
exit 1
