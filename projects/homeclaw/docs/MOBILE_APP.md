# HomeClaw Mobile App

## Overview

The HomeClaw mobile app is the remote brain for your home — a native iOS and Android app that gives you full control, ambient awareness, and intelligent management of every device and mode from anywhere.

Built with React Native (Expo) so it's one codebase, two platforms, fast to ship.

---

## Core Philosophy

The app is NOT a dashboard of switches. Anyone can build that. HomeClaw's app is **context-aware and proactive** — it knows what's happening at home, what's on your calendar, and surfaces the right controls at the right time without you having to dig through menus.

---

## Key Screens

### 1. Home — The Ambient Dashboard
The home screen is a living snapshot of your home right now:
- **Current Mode** — big pill at top (Deep Work / Evening / Away / etc.) with one-tap to switch
- **Active devices** — only what's actually ON or relevant right now (not 47 switches)
- **Next event** — "Meeting in 22 min — lights will shift automatically"
- **Quick actions** — 4 personalized shortcuts that learn from your patterns
- **Energy pulse** — live home power draw, animated

### 2. Modes — One-Tap Home States
Horizontal scroll of all your modes as big cards:
- Tap to activate instantly
- Shows what it'll change ("Sets 6 devices, pauses music, shifts lights to 5000K")
- Favorite modes pinned to top
- Build custom modes with the Mode Editor

### 3. Rooms
Floor plan view or room grid — tap any room to see and control everything in it:
- Lights (brightness + color temp slider, color picker)
- Climate (thermostat control, per-room sensors)
- Devices (speakers, switches, plugs)
- Presence indicator (room occupied / empty)

### 4. Now Playing
Dedicated music control screen:
- Full playback controls
- Room selector for where music is playing
- Mood selector ("more energizing", "wind it down", "focus mode")
- Queue visibility + voice-add to queue

### 5. Calendar View
Your day at a glance with home context:
- Timeline of events
- Annotations showing what HomeClaw will do for each event ("Lights shift 5min before this")
- Edit home behavior per event directly from here

### 6. Tasks & Backlog
- Connected to your task app (Todoist, Things, Linear)
- Swipe to capture new task via voice
- Focus session launcher: pick a task, start a Pomodoro, home enters Deep Work mode
- Daily review: what got done, what's still open

### 7. Automations
Visual automation builder:
- Trigger → Condition → Action flow, but in plain English
- "When I arrive home after 6pm on a weekday and my next calendar event is more than 2 hours away → activate Evening mode"
- Test any automation before enabling
- View automation history (what ran, when, what it did)

### 8. Insights
Weekly intelligence report:
- Hours in each mode
- Energy usage vs last week
- Sleep schedule consistency
- Focus time achieved vs target
- "Your home ran 22% more efficiently than last week"

---

## Standout Mobile Features

### Geofencing (Local, No Cloud)
- Uses your phone's native location (iOS CoreLocation / Android Geofencing API)
- No location data sent to any server — processed on-device
- Arrival/departure triggers HomeClaw Hub via local API when you're on the same network, or via secure tunnel when remote
- Radius customizable: 0.5mi, 1mi, 5mi

### Complication / Widget
- iOS Live Activity: current mode + active room count + energy draw, on your lock screen
- iOS Widget: home status, quick mode switcher, now playing
- Android widget: same
- Apple Watch complication: mode name + one-tap mode switch

### Siri / Google Assistant Shortcuts
- "Hey Siri, goodnight" → triggers HomeClaw Sleep mode via shortcut
- Exposes all modes and common commands as shortcuts
- Works even when app is closed

### Remote Access
- When away from home network, connects via secure encrypted tunnel (WireGuard-based, self-hosted)
- No HomeClaw servers in the middle — direct to your Hub
- Optional: HomeClaw Cloud ($4.99/mo) for easier remote setup without self-hosting a VPN

### Notification Intelligence
- "Your package was delivered 8 minutes ago" (with camera snapshot if available)
- "CI/CD pipeline failed — lights in your office are red"
- "You've been in Deep Work for 90 minutes — take a break?"
- "Guests arriving in 30 min — switch to Guest mode?"
- Actionable notifications: tap to approve, dismiss, or run alternative

### PuckNode Management
- See all PuckNodes on a map of your home
- Check firmware version, signal strength, battery (if applicable)
- Update firmware OTA from the app
- Configure wake word sensitivity per room
- Enable/disable mic per PuckNode (e.g. disable bedroom PuckNode at night for privacy)

---

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Framework | React Native (Expo) | One codebase, fast iteration, good native feel |
| State | Zustand | Lightweight, works great with real-time updates |
| Real-time | WebSocket to HomeClaw Hub | Instant state updates, sub-100ms |
| Local discovery | mDNS (Bonjour) | Auto-finds Hub on local network |
| Remote access | WireGuard tunnel or HomeClaw Cloud relay | User's choice |
| Notifications | Expo Push + HomeClaw Hub → APNs/FCM | Hub sends, phone receives |
| Auth | Local Hub token (offline-capable) | No cloud auth dependency |
| Animations | Reanimated 3 + Skia | Smooth 60fps home state transitions |

---

## Development Roadmap

**v1.0 (Launch with hardware)**
- Home dashboard, Modes, Rooms, basic music control
- Geofencing
- Widget + complications
- iOS + Android

**v1.1**
- Calendar integration view
- Task capture + Pomodoro launcher
- Automation builder (basic)
- Apple Watch app

**v1.2**
- Insights + weekly report
- Energy dashboard
- Full automation builder with conditions
- Siri/Google shortcuts deep integration

**v2.0**
- AI chat interface: type or speak to your home from the app
- Household member profiles + per-person preferences
- Scene editor with visual room preview
- Integration marketplace browser
