# ORA-047: Design auth screens (sign-up, sign-in, forgot password)

**Priority:** Critical (P0)
**Type:** Design
**Estimated:** 4 hours
**Dependencies:** None
**Tags:** design, UI/UX, auth, onboarding

## 🎯 Objective

Design beautiful, calming authentication screens that match Calm/Headspace quality standards. Create a premium first impression for new users.

## 📋 Requirements

### Design Scope
Create mockups for 3 screens:
1. **Sign Up** - New user registration
2. **Sign In** - Returning user login
3. **Forgot Password** - Password recovery flow

### Brand Guidelines
**Reference brand assets:** `/Users/matthew/Desktop/Feb26/Ora 2/`

**Color Palette (from Ora 2 brand):**
- **Primary Blue:** `#4A90E2` (calm, trustworthy)
- **Cream Background:** `#FAF8F3` (warm, inviting)
- **Olive/Sage Accents:** `#8B9D7F` (natural, grounding)
- **Dark Text:** `#2C3E50` (readable, sophisticated)
- **Error Red:** `#E74C3C` (validation errors)

**Typography:**
- **Headers:** SF Pro Display, Bold, 28-32pt
- **Body:** SF Pro Text, Regular, 16-18pt
- **Buttons:** SF Pro Text, Semibold, 17pt

**Aesthetic:**
- Minimal, uncluttered layouts
- Generous whitespace
- Soft shadows (blur 20, opacity 10%)
- Rounded corners (16px buttons, 12px inputs)
- Calming, premium feel

## 🎨 Screen Specifications

### 1. Sign Up Screen

**Layout:**
```
┌─────────────────────────┐
│                         │
│    [Ora Logo]          │ ← Centered, 60pt height
│    Welcome to Ora      │ ← Header, Bold, 28pt
│    Start your journey  │ ← Subheader, Light, 16pt
│                         │
│  ┌──────────────────┐  │
│  │ Full Name        │  │ ← Input field
│  └──────────────────┘  │
│                         │
│  ┌──────────────────┐  │
│  │ Email            │  │
│  └──────────────────┘  │
│                         │
│  ┌──────────────────┐  │
│  │ Password         │  │
│  └──────────────────┘  │
│                         │
│  ┌──────────────────┐  │
│  │ Confirm Password │  │
│  └──────────────────┘  │
│                         │
│  ┌──────────────────┐  │
│  │   Create Account │  │ ← Primary button
│  └──────────────────┘  │
│                         │
│  Already have account? │ ← Link to Sign In
│       Sign In          │
│                         │
└─────────────────────────┘
```

**Elements:**
- **Logo:** Use Ora 2 brand logo, centered at top (80pt margin from top)
- **Header:** "Welcome to Ora" in bold, dark blue
- **Subheader:** "Start your journey to wellness" in light gray
- **Input Fields:**
  - Height: 56pt
  - Background: White with 1pt border (#E0E0E0)
  - Border radius: 12px
  - Padding: 16pt
  - Placeholder text: Gray (#A0A0A0)
  - Focus state: Blue border (#4A90E2)
  - Error state: Red border + red helper text below
- **Password Field:** Show/hide eye icon on right
- **Create Account Button:**
  - Full width, 56pt height
  - Background: Gradient (blue to lighter blue)
  - Text: White, bold
  - Shadow: 0 4px 12px rgba(74, 144, 226, 0.3)
  - Press state: Slightly darker, scale 0.98
- **Sign In Link:** Gray text with blue underline on tap

**Validation States:**
- Empty field error: "This field is required"
- Email format error: "Please enter a valid email"
- Password mismatch: "Passwords don't match"
- Weak password: "Password must be at least 8 characters"

### 2. Sign In Screen

**Layout:**
```
┌─────────────────────────┐
│                         │
│    [Ora Logo]          │
│    Welcome Back        │
│    Continue your       │
│    wellness practice   │
│                         │
│  ┌──────────────────┐  │
│  │ Email            │  │
│  └──────────────────┘  │
│                         │
│  ┌──────────────────┐  │
│  │ Password         │  │
│  └──────────────────┘  │
│                         │
│      Forgot Password?  │ ← Link (right-aligned)
│                         │
│  ┌──────────────────┐  │
│  │    Sign In       │  │ ← Primary button
│  └──────────────────┘  │
│                         │
│  Don't have account?   │
│       Sign Up          │
│                         │
└─────────────────────────┘
```

**Differences from Sign Up:**
- Fewer fields (email + password only)
- "Forgot Password?" link aligned right, above button
- Simpler header: "Welcome Back"
- Warmer subheader referencing continuity

### 3. Forgot Password Screen

**Layout:**
```
┌─────────────────────────┐
│                         │
│    [←]                 │ ← Back button (top-left)
│                         │
│    Forgot Password?    │
│    We'll send you      │
│    a reset link        │
│                         │
│  ┌──────────────────┐  │
│  │ Email            │  │
│  └──────────────────┘  │
│                         │
│  ┌──────────────────┐  │
│  │   Send Reset     │  │
│  │      Link        │  │
│  └──────────────────┘  │
│                         │
│   Remember password?   │
│     Back to Sign In    │
│                         │
└─────────────────────────┘
```

**Elements:**
- **Back Button:** Chevron left icon, top-left (44pt tap target)
- **Single Input:** Email address only
- **Send Button:** Same style as other primary buttons
- **Confirmation State:** After tap, show success message:
  ```
  ✓ Email Sent!
  Check your inbox for reset instructions.
  ```

## 🎨 Additional Design Details

### Loading States
- **Button Loading:** Replace text with spinner, button stays same size
- **Spinner Style:** Small circular, blue (#4A90E2)

### Keyboard Behavior
- Auto-focus first input field on screen load
- "Next" button advances to next field
- "Done" on last field submits form
- Inputs scroll to stay visible above keyboard

### Accessibility
- All inputs have labels (can be hidden visually but present for screen readers)
- Color contrast ratio ≥ 4.5:1 for all text
- Touch targets ≥ 44pt × 44pt
- Support Dynamic Type (scale fonts with system settings)

### Animation / Transitions
- Screen transitions: Slide from right (300ms ease-out)
- Input focus: Border color fade (150ms)
- Button press: Scale + opacity (100ms)
- Error shake: Horizontal shake animation (200ms)

## 📁 Deliverables

Create mockups in preferred format (Figma, Sketch, or detailed descriptions):

1. **Desktop Mockups:**
   - `auth-signup.png` - Sign Up screen
   - `auth-signin.png` - Sign In screen  
   - `auth-forgot-password.png` - Forgot Password screen

2. **Mobile Mockups** (iPhone 15 Pro, 393×852pt):
   - All 3 screens at actual size
   - Include both light mode versions

3. **State Variations:**
   - Empty state
   - Focused state (one input focused)
   - Error state (validation errors shown)
   - Loading state (button with spinner)
   - Success state (password reset confirmation)

4. **Design Specs Document:**
   - `AUTH_DESIGN_SPECS.md` with:
     - Color codes
     - Font sizes and weights
     - Spacing measurements
     - Component dimensions
     - Animation timings

5. **Asset Export:**
   - Ora logo (1x, 2x, 3x)
   - Any custom icons needed

## ✅ Acceptance Criteria

- [ ] All 3 screens designed with consistent style
- [ ] Matches Ora 2 brand colors and aesthetic
- [ ] Layouts work on iPhone SE (smallest) to iPhone 15 Pro Max
- [ ] All interaction states documented (focus, error, loading, success)
- [ ] Accessibility considerations documented
- [ ] Design feels premium and calming (comparable to Calm/Headspace)
- [ ] Specs are clear enough for iOS developer to implement
- [ ] All assets exported and organized

## 🚀 Next Steps After Completion

This unblocks:
- ORA-048: Implement auth screens in React Native
- ORA-049: Wire auth screens to backend API
- ORA-050: Add social auth options (Google, Apple)

## 🎯 Agent Type Required

**Designer Agent** with:
- UI/UX design experience
- Mobile app design expertise
- Understanding of iOS Human Interface Guidelines
- Attention to detail and polish
