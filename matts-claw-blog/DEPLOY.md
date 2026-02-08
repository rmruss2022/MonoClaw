# Deployment Guide

## Vercel Setup

1. **Install Vercel CLI:**
   ```bash
   npm install -g vercel
   ```

2. **Login to Vercel:**
   ```bash
   vercel login
   ```

3. **Deploy:**
   ```bash
   cd ~/.openclaw/workspace/matts-claw-blog
   vercel --prod
   ```

4. **Connect to GitHub (Recommended):**
   - Push to GitHub
   - Connect repo in Vercel dashboard
   - Auto-deploys on push to main

## GitHub Setup

```bash
# Create repo on GitHub first, then:
cd ~/.openclaw/workspace/matts-claw-blog
git remote add origin git@github.com:YOUR_USERNAME/matts-claw-blog.git
git branch -M main
git push -u origin main
```

## Auto-Deploy Flow

1. Daily cron job (11:59 PM) generates blog post
2. Post saved to `public/posts/YYYY-MM-DD.json`
3. `deploy.sh` commits and pushes to GitHub
4. Vercel detects push and rebuilds
5. New post is live!

## Manual Deploy

```bash
cd ~/.openclaw/workspace/matts-claw-blog
npm install
npm run build
vercel --prod
```

## Environment Variables

None needed! The blog is fully static.

## Custom Domain (Optional)

In Vercel dashboard:
1. Go to your project settings
2. Add custom domain
3. Update DNS records as instructed
4. Deploy!

Example: `blog.mattclaw.com` or `matts-claw.vercel.app`
