# Deployment Guide - Portfolio Website

## 🚀 Quick Deploy to Vercel (Recommended)

### Prerequisites
- GitHub account
- Vercel account (free tier is perfect)

### Steps

1. **Push to GitHub** (if not already done):
   ```bash
   cd /Users/matthew/.openclaw/workspace/portfolio-site
   git init
   git add .
   git commit -m "Initial portfolio site"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git push -u origin main
   ```

2. **Deploy via Vercel**:
   - Go to [vercel.com](https://vercel.com)
   - Click "Import Project"
   - Connect your GitHub repository
   - Vercel will auto-detect Next.js
   - Click "Deploy"
   - Done! Your site will be live at `your-project.vercel.app`

3. **Add Custom Domain** (Optional):
   - Go to your Vercel project settings
   - Navigate to "Domains"
   - Add your custom domain (e.g., `matthewrussell.com`)
   - Follow DNS configuration instructions

---

## 📦 Build & Deploy Options

### Option 1: Vercel (Recommended)
- **Pros**: Zero config, automatic deployments, free SSL, CDN
- **Cons**: None for this use case
- **Best for**: Quick, professional deployment

### Option 2: Netlify
```bash
npm run build
# Upload .next folder to Netlify
```
- Similar to Vercel, also great option

### Option 3: Railway
```bash
# Install Railway CLI
npm install -g railway
railway login
railway init
railway up
```

### Option 4: Self-Host (VPS)
```bash
# Build production
npm run build

# Start production server
npm run start
# or use PM2 for process management
pm2 start npm --name "portfolio" -- start
```

---

## 🔧 Pre-Deployment Checklist

### 1. Add Resume PDF
```bash
# Place your resume at:
# /public/resume.pdf
```

### 2. Add Project Images (Optional)
```bash
# Add project screenshots to:
mkdir -p public/images
# Place images:
# - activityclaw.png
# - contextclaw.png
# - ora-health.png
# - agent-swarm.png
```

### 3. Update Contact Form API (Optional)
The form is ready but needs a backend. Options:

#### A) Resend Email Service (Recommended)
```bash
npm install resend
```

Create `/src/app/api/contact/route.ts`:
```typescript
import { Resend } from 'resend';
import { NextResponse } from 'next/server';

const resend = new Resend(process.env.RESEND_API_KEY);

export async function POST(request: Request) {
  const { name, email, message } = await request.json();

  try {
    await resend.emails.send({
      from: 'onboarding@resend.dev',
      to: 'mattrussellc@gmail.com',
      subject: `Portfolio Contact: ${name}`,
      text: `From: ${name} (${email})\n\n${message}`,
    });

    return NextResponse.json({ success: true });
  } catch (error) {
    return NextResponse.json({ error: 'Failed to send' }, { status: 500 });
  }
}
```

Add to `.env.local`:
```
RESEND_API_KEY=your_api_key_here
```

#### B) FormSpree (No Backend Needed)
Update form action:
```tsx
<form action="https://formspree.io/f/YOUR_FORM_ID" method="POST">
```

#### C) Web3Forms (No Backend Needed)
Similar to FormSpree, just update the form endpoint.

### 4. Environment Variables
If using contact form API, add to Vercel:
- Go to Project Settings → Environment Variables
- Add `RESEND_API_KEY` (or other API keys)

### 5. Analytics (Optional)
Add Vercel Analytics:
```bash
npm install @vercel/analytics
```

In `layout.tsx`:
```tsx
import { Analytics } from '@vercel/analytics/react';

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        {children}
        <Analytics />
      </body>
    </html>
  );
}
```

---

## 🔍 SEO Optimization

### Already Implemented ✅
- Meta tags (title, description, keywords)
- Open Graph tags
- Twitter Card tags
- Semantic HTML
- Fast loading
- Mobile responsive

### Additional Steps (Optional)
1. **Submit to Google Search Console**
   - Verify your domain
   - Submit sitemap

2. **Add sitemap.xml**
   Create `/public/sitemap.xml`:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
     <url>
       <loc>https://yoursite.com/</loc>
       <lastmod>2026-02-17</lastmod>
       <priority>1.0</priority>
     </url>
   </urlset>
   ```

3. **Add robots.txt**
   Create `/public/robots.txt`:
   ```
   User-agent: *
   Allow: /
   Sitemap: https://yoursite.com/sitemap.xml
   ```

---

## 📊 Performance Optimization

### Already Optimized ✅
- CSS-only animations (no JS overhead)
- Optimized font loading (Geist with swap)
- Framer Motion tree-shaking
- Minimal JavaScript bundle
- Proper image loading (when added)

### If Adding Images
Use Next.js Image component:
```tsx
import Image from 'next/image';

<Image
  src="/images/project.png"
  alt="Project screenshot"
  width={1200}
  height={630}
  priority
/>
```

---

## 🐛 Troubleshooting

### Build Errors
```bash
# Clear cache and rebuild
rm -rf .next
npm run build
```

### Development Issues
```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### Deployment Issues on Vercel
1. Check build logs in Vercel dashboard
2. Ensure `package.json` has correct scripts
3. Verify Node version (should use latest LTS)

---

## 🎯 Post-Deployment

### 1. Test Everything
- [ ] Navigation works on all pages
- [ ] All external links work (npm, GitHub, LinkedIn, etc.)
- [ ] Resume PDF downloads
- [ ] Contact form submits (if implemented)
- [ ] Mobile responsive
- [ ] Performance is fast (Lighthouse score 90+)

### 2. Share Your Portfolio
Update these profiles with your new portfolio URL:
- GitHub README
- LinkedIn profile
- Twitter/X bio
- Resume/CV
- Email signature

### 3. Monitor Performance
- Vercel Analytics (if installed)
- Google Search Console
- Google Analytics (if needed)

---

## 🔒 Security

### Already Secure ✅
- No exposed API keys (use environment variables)
- HTTPS via Vercel (automatic)
- CSP headers (handled by Next.js)
- XSS protection (React escaping)

### Best Practices
- Never commit `.env.local` to Git
- Use environment variables for secrets
- Keep dependencies updated: `npm audit fix`

---

## 📈 Maintenance

### Regular Updates
```bash
# Update dependencies monthly
npm update
npm run build  # Test after updating
```

### Content Updates
To update content, edit:
- `src/components/Projects.tsx` - Add/edit projects
- `src/components/Experience.tsx` - Add work experience
- `src/components/Skills.tsx` - Update tech stack

Deploy updates:
```bash
git add .
git commit -m "Update content"
git push
# Vercel auto-deploys
```

---

## 🎉 You're Ready!

Your portfolio is production-ready. Just:
1. Add resume PDF (optional)
2. Add project images (optional)
3. Push to GitHub
4. Deploy to Vercel
5. Share with the world!

**Questions?** Check Next.js docs or Vercel docs for more details.

Good luck! 🚀
