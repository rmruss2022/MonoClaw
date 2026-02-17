# Design Brief - 10X Engineer Portfolio

## Design Philosophy
**"Elite engineering meets modern minimalism"**

The design should communicate:
- **Technical mastery** - Not a junior developer
- **Systems thinking** - Big picture, automation, architecture
- **Innovation** - Building cutting-edge tools (AI agents, plugins)
- **Attention to detail** - Every pixel matters

---

## Visual References (Inspiration)

### Style Direction
Think of these references:
- **Linear.app** - Clean, modern, precise
- **Stripe.com** - Professional, technical, beautiful
- **Vercel.com** - Developer-focused, fast, elegant
- **GitHub profile** - Technical but approachable
- **Apple product pages** - High-end, polished

### What to AVOID
- ❌ Overly busy/cluttered layouts
- ❌ Generic Bootstrap templates
- ❌ Flashy animations without purpose
- ❌ Stock photos of people coding
- ❌ "Web 2.0" gradients and glossy buttons
- ❌ Comic Sans or playful fonts (this is serious)

---

## Color Palette

### Primary Colors
```
Dark Background: #0A0E27 (deep navy/black)
Primary Accent: #3B82F6 (modern blue)
Success/Highlight: #10B981 (green for CTAs/achievements)
```

### Secondary Colors
```
Text Primary: #F9FAFB (off-white, high contrast)
Text Secondary: #9CA3AF (muted gray for descriptions)
Borders/Dividers: #1F2937 (subtle separation)
Code Blocks: #1E293B (slightly lighter than bg)
```

### Accent Colors (Sparingly)
```
Warning/Emphasis: #F59E0B (amber for important CTAs)
Links: #60A5FA (lighter blue, accessible)
Error/Alert: #EF4444 (red, if needed)
```

### Gradients (Subtle)
```css
/* Hero background gradient */
background: linear-gradient(135deg, #0A0E27 0%, #1E293B 100%);

/* Accent gradient for highlights */
background: linear-gradient(90deg, #3B82F6 0%, #8B5CF6 100%);

/* Glow effects */
box-shadow: 0 0 60px rgba(59, 130, 246, 0.15);
```

---

## Typography

### Font Families

**Headings:**
```css
font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
font-weight: 700; /* Bold */
letter-spacing: -0.02em; /* Tight */
```

**Body Text:**
```css
font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
font-weight: 400; /* Regular */
letter-spacing: -0.01em;
line-height: 1.6; /* Readable */
```

**Code/Monospace:**
```css
font-family: 'Fira Code', 'SF Mono', 'Monaco', 'Courier New', monospace;
font-weight: 400;
```

### Type Scale
```
H1: 48px (mobile: 32px) - Hero headline
H2: 36px (mobile: 28px) - Section titles
H3: 24px (mobile: 20px) - Subsections
Body: 16px (mobile: 16px) - Main text
Small: 14px - Captions, metadata
```

---

## Layout & Spacing

### Grid System
- **Max width:** 1280px (centered)
- **Padding:** 80px horizontal (desktop), 24px (mobile)
- **Vertical spacing:** 120px between sections (desktop), 80px (mobile)

### Card Components
```css
background: rgba(31, 41, 55, 0.5);
border: 1px solid rgba(255, 255, 255, 0.1);
border-radius: 12px;
padding: 32px;
backdrop-filter: blur(10px);
```

### Hover States
```css
/* Cards */
transform: translateY(-4px);
box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
border-color: rgba(59, 130, 246, 0.4);
transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

/* Buttons */
background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%);
box-shadow: 0 8px 24px rgba(59, 130, 246, 0.3);
```

---

## Components

### Hero Section
```
Layout: Full viewport height (100vh)
Background: Dark gradient with subtle animated particles/dots
Content: Centered, large headline, subheadline, CTA
Animation: Fade in on load, subtle parallax on scroll
```

### Project Cards
```
Layout: Grid (3 columns desktop, 1 column mobile)
Style: Glass-morphism effect (semi-transparent, blurred)
Hover: Lift + glow + border highlight
Content: Icon/logo, title, description, tech tags, links
```

### Tech Stack Badges
```
Style: Small pills/tags
Colors: Subtle background (#1F2937), border, white text
Icons: Use Devicons or Simple Icons
Layout: Flex wrap, compact spacing
```

### Timeline (Experience)
```
Style: Vertical line with dots for each position
Cards: Offset left/right alternating (desktop)
Content: Company logo, role, duration, achievements (bullet points)
```

### CTA Buttons
```css
/* Primary CTA */
background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%);
padding: 14px 32px;
border-radius: 8px;
font-weight: 600;
box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25);

/* Secondary CTA */
background: transparent;
border: 2px solid #3B82F6;
padding: 12px 28px;
```

---

## Animations & Interactions

### Principles
- **Purposeful:** Every animation should have a reason
- **Fast:** < 300ms for most transitions
- **Smooth:** Use cubic-bezier easing
- **Accessible:** Respect `prefers-reduced-motion`

### Key Animations
```css
/* Fade in on scroll */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Subtle pulse for CTAs */
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4); }
  50% { box-shadow: 0 0 0 8px rgba(59, 130, 246, 0); }
}

/* Background particles (subtle) */
/* Use canvas or CSS for floating dots/lines */
```

### Scroll Effects
- Parallax on hero section (subtle)
- Fade in sections as they enter viewport
- Progress indicator at top (optional)
- Smooth scroll behavior

---

## Imagery & Media

### Screenshots
- High-resolution (2x Retina)
- Consistent shadow/border treatment
- Add subtle browser chrome mockup for web apps
- Use WebP format with fallback

### Icons
- **Style:** Outlined or duotone (not filled)
- **Library:** Heroicons, Lucide, or custom SVG
- **Color:** Match accent colors
- **Size:** 24px default, scale for headings

### Code Snippets
- Syntax highlighting (Prism.js or Shiki)
- Dark theme to match site
- Copy button on hover
- Subtle glow effect around block

### Logos
- OpenClaw logo (if available)
- Company logos (Liquid IV, Barwaves, Aqara)
- npm logo for packages
- GitHub octocat for repos

---

## Mobile Design

### Key Considerations
- **Touch targets:** Minimum 44x44px
- **Readable text:** 16px minimum
- **Simplified nav:** Hamburger menu
- **Stacked layout:** Single column for all content
- **Hero height:** 70vh (not 100vh)
- **Reduced animations:** Simpler on mobile

### Mobile-First Approach
Start with mobile design, enhance for desktop (not the reverse)

---

## Technical Implementation

### Recommended Stack
```
Framework: Next.js (React)
Styling: Tailwind CSS
Animations: Framer Motion
Icons: Heroicons or Lucide
Fonts: Google Fonts (Inter)
Hosting: Vercel
```

### Performance Optimizations
- Image optimization (next/image)
- Code splitting
- Lazy load below-the-fold content
- Preload critical assets
- Minimal third-party scripts

---

## Example Structure

```
┌─────────────────────────────────────┐
│   HERO - Full viewport              │
│   "Matthew Russell"                 │
│   "Building AI-powered systems"     │
│   [View Work] [Contact]             │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│   FEATURED PROJECTS                 │
│   ┌──────┐ ┌──────┐ ┌──────┐       │
│   │ Claw │ │ Claw │ │ Aura │       │
│   │Plugin│ │Plugin│ │ App  │       │
│   └──────┘ └──────┘ └──────┘       │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│   EXPERIENCE                        │
│   ○───[Liquid IV]                   │
│       [Barwaves]───○                │
│   ○───[Aqara]                       │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│   SKILLS & TECH                     │
│   [TS] [React] [Python] [AI]...    │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│   CONTACT                           │
│   Let's build something.            │
│   [Email] [GitHub] [Resume PDF]     │
└─────────────────────────────────────┘
```

---

## Design Deliverables

1. **Wireframes** (low-fidelity mockups)
2. **High-fidelity designs** (Figma/mockups)
3. **Component library** (reusable UI elements)
4. **Responsive breakpoints** (mobile, tablet, desktop views)
5. **Animation specs** (timing, easing, triggers)
6. **Asset exports** (logos, icons, images)

---

## Success Metrics

✅ **Visual impact:** Looks expensive/professional  
✅ **Brand consistency:** Cohesive color/typography  
✅ **Hierarchy:** Clear visual flow  
✅ **Accessibility:** Passes contrast checks  
✅ **Performance:** Smooth 60fps animations  
✅ **Responsive:** Looks great on all devices  

---

## References

**Great Portfolio Examples:**
- https://brittanychiang.com (Brittany Chiang - excellent layout)
- https://jacekjeznach.com (Jacek Jeznach - clean, modern)
- https://www.adhamdannaway.com (Adham Dannaway - visual storytelling)
- https://bruno-simon.com (Bruno Simon - creative but professional)

**Design Systems to Study:**
- https://vercel.com/design
- https://stripe.com/docs/design
- https://linear.app/design
