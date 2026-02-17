# Portfolio Website - Build Instructions for Claude

**Project:** Matthew Russell Personal Portfolio  
**Location:** `/Users/matthew/.openclaw/workspace/portfolio-site/`  
**Stack:** Next.js 14, TypeScript, Tailwind CSS, Framer Motion  
**Goal:** Elite 10X engineer portfolio showcasing OpenClaw plugins, Aura app, and professional experience

---

## 🎯 Your Mission

Build a **world-class personal portfolio website** that immediately communicates "elite engineer" through:
- Modern, striking visual design (dark theme with blue accents)
- Compelling copy that demonstrates impact
- Showcase of 4 major projects with proof/links
- Professional experience at top companies
- Fast, accessible, SEO-optimized

**Vibe:** Think Linear.app, Stripe.com, Vercel.com - clean, modern, minimal, technical elegance

---

## 📁 Project Structure

This is a Next.js 14 (App Router) project with:
- TypeScript for type safety
- Tailwind CSS for styling
- Framer Motion for animations
- React Hook Form + Zod for forms

```
portfolio-site/
├── src/
│   ├── app/
│   │   ├── page.tsx          # Homepage (main portfolio)
│   │   ├── layout.tsx        # Root layout
│   │   ├── globals.css       # Global styles + Tailwind
│   │   └── api/
│   │       └── contact/
│   │           └── route.ts  # Contact form API
│   └── components/
│       ├── Hero.tsx          # Hero section
│       ├── Projects.tsx      # Projects showcase
│       ├── Experience.tsx    # Work experience
│       ├── Skills.tsx        # Tech stack
│       ├── Contact.tsx       # Contact form
│       └── ui/               # Reusable components
├── public/
│   ├── images/               # Project screenshots, logos
│   └── resume.pdf            # (Will be added by Matthew)
├── CLAUDE.md                 # This file
├── DESIGN.md                 # Design specifications
├── CONTENT.md                # Copy and content
└── package.json
```

---

## 🎨 Design System (Use These Exactly)

### Colors
```css
/* Tailwind config - already set up in tailwind.config.ts */
--color-dark: #0A0E27;        /* Background */
--color-primary: #3B82F6;     /* Blue accent */
--color-accent: #10B981;      /* Green for CTAs */
--color-text: #F9FAFB;        /* Off-white text */
--color-text-muted: #9CA3AF;  /* Gray for descriptions */
--color-border: #1F2937;      /* Subtle borders */
```

### Typography
- **Font:** Inter (already imported via next/font/google)
- **Headings:** 700 weight, -0.02em tracking
- **Body:** 400 weight, -0.01em tracking, 1.6 line-height
- **Code:** Use `font-mono` (Fira Code)

### Spacing
- **Section padding:** py-20 (mobile), py-32 (desktop)
- **Max width:** max-w-7xl mx-auto
- **Card padding:** p-6 (mobile), p-8 (desktop)

---

## 📄 What to Build

### 1. Hero Section (`components/Hero.tsx`)

**Layout:**
- Full viewport height (min-h-screen)
- Centered content
- Dark gradient background
- Large headline + subheadline
- 2 CTA buttons

**Content:**
```tsx
Headline: "Matthew Russell"
Subheadline: "Building AI systems that multiply human capability"
Description: "Full-stack engineer specializing in AI-powered automation, developer tools, and scalable systems. Creator of OpenClaw plugins used by engineers worldwide."
CTA Primary: "View My Work" (smooth scroll to projects)
CTA Secondary: "Download Resume" (link to /resume.pdf)
```

**Design:**
- Background: dark gradient (from-slate-950 to-slate-900)
- Headline: text-5xl md:text-7xl font-bold
- Subheadline: text-2xl md:text-3xl text-blue-400
- Description: text-lg text-gray-400 max-w-2xl
- Buttons: rounded-lg with hover effects
- Add subtle Framer Motion fade-in animation

---

### 2. Projects Section (`components/Projects.tsx`)

**Layout:**
- Grid: 1 column mobile, 2 columns desktop (grid-cols-1 md:grid-cols-2)
- Gap between cards: gap-8
- 4 project cards total

**Projects to showcase:**

#### Project 1: ActivityClaw
```
Title: "ActivityClaw"
Subtitle: "Real-time Activity Tracking for OpenClaw"
Description: "Production-ready OpenClaw plugin with React dashboard, WebSocket updates, and REST API. Published to npm and ClawHub."
Tech: TypeScript, React, Node.js, WebSockets
Links:
  - npm: https://www.npmjs.com/package/@tigertroll14/activityclaw
  - GitHub: https://github.com/rmruss2022/ActivityClaw
  - ClawHub: https://clawhub.ai/skills/activityclaw-usage
Image: /images/activityclaw.png (placeholder for now)
```

#### Project 2: ContextClaw
```
Title: "ContextClaw"
Subtitle: "Intelligent Session Management"
Description: "Advanced session management plugin with context analysis, cost tracking, and optimization strategies. Published to npm and ClawHub."
Tech: TypeScript, React, Tailwind CSS
Links:
  - npm: https://www.npmjs.com/package/@tigertroll14/contextclaw
  - GitHub: https://github.com/rmruss2022/ContextClaw
  - ClawHub: https://clawhub.ai/skills/contextclaw-usage
Image: /images/contextclaw.png
```

#### Project 3: Ora Health
```
Title: "Ora Health"
Subtitle: "AI-Powered Mental Wellness Companion"
Description: "iOS application featuring Agentic AI with Multi-Vector Broadcast Architecture. Delivers personalized meditations, affirmations, and mindset exercises powered by Eleven Labs."
Tech: Swift, iOS, LangChain, Eleven Labs, Vector DBs
Status: In Development (Mar 2025 - Present)
Links:
  - Status: In Development
Image: /images/ora-health.png
```

#### Project 4: Agent Swarm
```
Title: "Multi-Agent Orchestration"
Subtitle: "Discord-Integrated AI Agent Swarms"
Description: "Production-ready system with automatic Discord channels, Kanban automation, and inter-agent communication."
Tech: Node.js, SQLite, Discord API, Express
Links:
  - GitHub: [To be added]
Image: /images/agent-swarm.png
```

**Card Design:**
- Glass-morphism effect: `bg-slate-800/50 backdrop-blur-xl`
- Border: `border border-slate-700/50`
- Rounded: `rounded-xl`
- Padding: `p-6 md:p-8`
- Hover: lift effect (`hover:-translate-y-2 hover:border-blue-500/50`)
- Transition: `transition-all duration-300`

**Card Structure:**
```tsx
<div className="project-card">
  <div className="image-placeholder h-48 bg-slate-700 rounded-lg mb-4" />
  <h3 className="text-2xl font-bold mb-2">{title}</h3>
  <p className="text-blue-400 mb-4">{subtitle}</p>
  <p className="text-gray-400 mb-4">{description}</p>
  <div className="tech-badges flex flex-wrap gap-2 mb-4">
    {/* Tech badges */}
  </div>
  <div className="links flex gap-4">
    {/* External links */}
  </div>
</div>
```

---

### 3. Experience Section (`components/Experience.tsx`)

**Layout:**
- Timeline design (vertical line with dots)
- 3 company cards

**Content Structure:**
```tsx
Company 1: AgriVaR
- Role: Software Engineer
- Duration: June 2024 – Present
- Description: Big-data agricultural startup
- Achievements: 4 bullet points (see CONTENT.md)
- Tech: React, TypeScript, AWS

Company 2: BitWave
- Role: Software Engineer II
- Duration: June 2023 – June 2024
- Description: Digital asset platform
- Achievements: 4 bullet points (see CONTENT.md)
- Tech: Rust, CQRS, Distributed Systems

Company 3: Unilever | Liquid I.V.
- Role: Full Stack Software Engineer
- Duration: July 2021 – June 2023
- Description: Logistics and inventory management
- Achievements: 4 bullet points (see CONTENT.md)
- Tech: React, TypeScript, GraphQL, AWS
```

**All content is final** - use exact copy from CONTENT.md.

**Example:**
```tsx
<div className="experience-card">
  <div className="company-logo w-16 h-16 bg-slate-700 rounded-lg mb-4" />
  <h3 className="text-2xl font-bold">AgriVaR</h3>
  <p className="text-blue-400 mb-2">Software Engineer • June 2024 – Present</p>
  <p className="text-gray-400 mb-4">
    Big-data agricultural startup optimizing farm operations through advanced data analysis.
  </p>
  <ul className="space-y-2 text-gray-300">
    <li>• Re-architected legacy systems on AWS for speed and redundancy</li>
    <li>• Built high-performance React interfaces for multi-dimensional geospatial datasets</li>
    <li>• Designed commodity trading platform with streaming updates and alerting</li>
    <li>• Created drawing tools for geographical analysis, increasing harvests by 20+%</li>
  </ul>
  <div className="tech-badges mt-4">
    {/* React, TypeScript, AWS, Geospatial */}
  </div>
</div>
```

---

### 4. Skills Section (`components/Skills.tsx`)

**Layout:**
- Categories of skills
- Badge grid

**Categories:**
```tsx
Languages: TypeScript, Python, JavaScript, SQL, Bash
Frontend: React, Next.js, Tailwind CSS
Backend: Node.js, Express, Django
Databases: PostgreSQL, SQLite, Redis
DevOps: Git, Docker, Vercel, Railway
AI & Automation: OpenClaw, AI Agents, LLM Integration
```

**Badge Design:**
- Small pills: `px-4 py-2 rounded-full`
- Background: `bg-slate-800 border border-slate-700`
- Text: `text-sm text-gray-300`
- Hover: slight brightness increase

---

### 5. Contact Section (`components/Contact.tsx`)

**Layout:**
- 2 columns: Contact info (left) + Form (right)
- Mobile: stack vertically

**Contact Info:**
```tsx
Email: mattrussellc@gmail.com
GitHub: https://github.com/rmruss2022
Telegram: @corecadet99
Resume: Download PDF button
```

**Contact Form:** (Implement later)
```tsx
Fields:
- Name (text input)
- Email (email input)
- Message (textarea)
- Submit button

Validation: React Hook Form + Zod
API: POST to /api/contact (implement basic version)
```

---

## 🎬 Animations (Framer Motion)

Use these patterns:

**Fade in on scroll:**
```tsx
<motion.div
  initial={{ opacity: 0, y: 20 }}
  whileInView={{ opacity: 1, y: 0 }}
  viewport={{ once: true }}
  transition={{ duration: 0.6 }}
>
  {content}
</motion.div>
```

**Stagger children:**
```tsx
<motion.div
  variants={{
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.1 }
    }
  }}
  initial="hidden"
  whileInView="show"
  viewport={{ once: true }}
>
  {items.map(item => (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: 20 },
        show: { opacity: 1, y: 0 }
      }}
    >
      {item}
    </motion.div>
  ))}
</motion.div>
```

---

## 🎨 Tailwind Configuration

Add to `tailwind.config.ts`:

```ts
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: "#0A0E27",
        primary: "#3B82F6",
        accent: "#10B981",
      },
      fontFamily: {
        sans: ['var(--font-inter)'],
      },
    },
  },
  plugins: [],
};
export default config;
```

---

## 🚀 Development Steps

### Phase 1: Foundation (Start Here)
1. ✅ Project created (Next.js + dependencies installed)
2. Update `tailwind.config.ts` with custom colors
3. Set up Inter font in `app/layout.tsx`
4. Create basic component files (empty shells)
5. Update `app/page.tsx` to import all components

### Phase 2: Build Components
6. Build Hero section (complete)
7. Build Projects section (cards with placeholder images)
8. Build Experience section (placeholder content)
9. Build Skills section (badge grid)
10. Build Contact section (info + simple form)

### Phase 3: Polish
11. Add Framer Motion animations
12. Implement hover effects
13. Add responsive breakpoints
14. Test on mobile/desktop

### Phase 4: Content (Once Matthew Provides)
15. Replace experience placeholders with real data
16. Add project screenshots to `/public/images/`
17. Add resume PDF to `/public/resume.pdf`
18. Update meta tags for SEO

---

## 📊 Performance Targets

- Lighthouse Performance: 95+
- First Contentful Paint: < 1s
- Largest Contentful Paint: < 2.5s
- Bundle size: < 100KB (gzipped)

**How to achieve:**
- Use Next.js Image component for all images
- Lazy load components below fold
- Minimize JavaScript (tree-shake unused code)
- Optimize Tailwind (purge unused classes)

---

## 🔍 SEO Setup

In `app/layout.tsx`, add metadata:

```tsx
export const metadata = {
  title: 'Matthew Russell - Full-Stack Engineer | AI Automation',
  description: 'Full-stack engineer specializing in AI automation, developer tools, and scalable systems. Creator of OpenClaw plugins.',
  openGraph: {
    title: 'Matthew Russell - Full-Stack Engineer',
    description: 'Building AI-powered systems and automation tools',
    type: 'website',
  },
}
```

---

## ⚡ Quick Start Commands

```bash
# Development server
npm run dev
# → http://localhost:3000

# Production build (test)
npm run build
npm run start

# Lint
npm run lint
```

---

## 📝 Notes

**Placeholders:**
- Use gray boxes for images until Matthew provides screenshots
- Use generic text for work experience until resume provided
- Links work but may go to placeholder pages

**To be added later:**
- Contact form API implementation (Resend)
- Actual project screenshots
- Real resume data
- Domain setup

**Priority:** Build a beautiful, functional site with placeholder content first. Content can be swapped in easily later.

---

## 🎯 Success Criteria

When done, the site should:
- ✅ Look modern and professional (dark theme, clean design)
- ✅ Work on mobile and desktop
- ✅ Have smooth animations (but not overdone)
- ✅ Showcase 4 projects with working external links
- ✅ Have clear CTAs (View Work, Contact, Download Resume)
- ✅ Load fast (< 2s)
- ✅ Be ready for content swap (easy to update copy)

---

## 🤝 Collaboration Notes

**For Matthew:**
- Review design in browser
- Provide resume for experience section
- Provide project screenshots for /public/images/
- Test on your devices
- Feedback welcome at any stage

**For Claude:**
- Build incrementally, test as you go
- Use Tailwind classes, avoid custom CSS
- Keep components simple and readable
- Comment complex logic
- Follow Next.js best practices

---

**Ready to build!** Start with Phase 1, then move through Phase 2 systematically. The foundation is set up - now bring it to life with clean code and beautiful design. 🚀
