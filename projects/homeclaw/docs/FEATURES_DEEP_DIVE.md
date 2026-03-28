# HomeClaw — Features Deep Dive
## Every Integration Category, What It Does, and Why Developers Actually Want It

*Research-backed. Community-validated. Built for the person who knows what they want and is tired of products that don't deliver it.*

---

## 🎵 Music & Audio Intelligence

The single most-requested feature in every smart home community. Current solutions are embarrassingly bad — you either bark a keyword at Alexa or manually queue something. HomeClaw treats music as a first-class citizen of your environment.

### What We Build
- **Mood-aware playback** — LLM infers your energy level from time of day, calendar, weather, recent activity patterns. 9 PM on a Friday after a long week → downtempo. 7 AM Monday → energizing.
- **Room-aware audio mesh** — multiple PuckNodes understand which room you're in and fade/follow you as you move through the house. "Continue in the kitchen" is detected automatically, not triggered manually.
- **Context handoff** — your music follows your state. Starts a Pomodoro focus session → music automatically shifts to instrumental/lo-fi and volume drops 20%. Pomodoro ends → back to your preferred playlist.
- **"DJ Mode"** — tell HomeClaw the vibe for a gathering ("8 people coming over, dinner party, mix of jazz and indie") and it manages the queue all night, adjusting tempo and energy as the evening progresses.
- **Morning reveal** — wakes you with music that ramps from silence to your wake-up volume over 5 minutes, keyed to your actual alarm time from calendar.
- **Voice-controlled queuing** — "add this to my Friday night playlist," "skip anything by [artist]," "find something like this but more upbeat" — actual LLM reasoning, not keyword matching.

### Integrations
Spotify, Apple Music, YouTube Music, Tidal, Plex Media Server, Sonos, Chromecast Audio, AirPlay 2 devices, MQTT-based amplifiers, Snapcast (multi-room sync for audiophiles)

---

## 💡 Lighting & Circadian Intelligence

Lighting is the highest-ROI smart home upgrade and the most badly implemented. Most people set up three scenes and never touch it again. HomeClaw makes lighting genuinely dynamic.

### What We Build
- **Circadian rhythm engine** — automatically shifts color temperature from 6500K cool white in morning → warm 2700K by evening → 1800K red-tinted after 9 PM. Backed by sleep science (bright blue light suppresses melatonin). Runs automatically, no manual scene switching.
- **Adaptive brightness** — uses ambient light sensor on PuckNode to keep your environment at a consistent perceived brightness regardless of time of day or outdoor conditions. Your office stays at 400 lux all day.
- **Focus mode lighting** — when you enter a Pomodoro or Deep Work block, lights shift to your personal "focus profile" (most people prefer 4000-5000K, ~500 lux). Break time → warmer, dimmer.
- **"What's happening" awareness** — calendar says "video call at 2pm" → lights automatically shift to a flattering, bright, neutral tone 5 minutes before. Meeting ends → back to your working profile.
- **Occupancy with context** — lights don't just turn on when you enter a room. They turn on to the RIGHT scene based on what you're likely doing. Walking into the kitchen at 7am → bright cooking light. Same room at 10pm → dim, warm ambient.
- **Sleep ramp** — starting 30 minutes before your sleep time (pulled from calendar or a set schedule), lights in your home gradually dim and shift to deep amber. Your body knows it's time to sleep before your brain does.
- **Sunrise simulation** — room where you sleep slowly brightens from 0 to your wake brightness over 20 minutes, keyed to your alarm. Wakes you in a light sleep phase instead of jolting you awake.
- **Party/Entertain mode** — color cycling, scene syncing across multiple rooms, music-reactive lighting (PuckNode audio → beats → light pulse via Hue Entertainment API)

### Integrations
Philips Hue (full Entertainment API), LIFX, Govee, Nanoleaf, WiZ, Kasa, Zigbee generic (any Zigbee bulb), WLED (for LED strips), Shelly dimmers, Lutron Caséta

---

## 🌡️ Comfort & Climate Intelligence

Your thermostat is dumb. It runs on a schedule you set once in 2019 and never updated. HomeClaw makes comfort predictive, not reactive.

### What We Build
- **Presence-predictive preconditioning** — knows from calendar when you're arriving home. Starts heating/cooling 30-45 minutes early so you walk into the perfect temperature. Never pre-heats an empty house.
- **Room-by-room thermal logic** — if you're working in your office all day, only condition that room. Bedroom at night. Living room only when you're actually in it. Reduces HVAC runtime by 15-25%.
- **Sleep temperature protocol** — science shows 65-68°F is optimal for sleep. HomeClaw drops the bedroom to your target temperature 30 minutes before your sleep ramp begins, automatically.
- **Weather-responsive** — knows it's a hot day before it gets hot. Pre-cools the house in the morning when electricity is cheap, before the afternoon peak.
- **Open window detection** — uses air pressure/temperature delta from sensors to detect if a window is open. Pauses HVAC automatically so you're not cooling the street.
- **Guest mode** — "I have people coming over" → bumps setpoint slightly, adjusts for higher body heat load in the living room.
- **Utility rate awareness** — integrates with your electricity provider's time-of-use pricing (where available). Pre-cools before peak pricing window. Runs smart plugs and high-draw appliances off-peak.
- **Air quality integration** — CO2 sensor data triggers ventilation. High CO2 in your home office (common in poorly-ventilated rooms) → opens smart window actuator or activates ERV/HRV if installed. CO2 > 1000ppm kills productivity — HomeClaw protects it.

### Integrations
Nest (3rd gen+ with API), Ecobee with sensors, Honeywell T6 Pro, Sensibo (for mini-split/AC units), Mitsubishi MELCloud, Daikin, Fujitsu, Bosch BMP280 (air sensor), Airthings (air quality), Zigbee door/window sensors, Shelly (for window actuators)

---

## 📅 Calendar & Life Context

This is where HomeClaw leaps ahead of every existing solution. Your calendar is the ground truth of your life. Your home should know what's on it.

### What We Build
- **Day briefing** — every morning, HomeClaw gives you a verbal briefing: today's schedule, first meeting in X minutes, weather, any travel time warnings, top-priority tasks from your backlog. All from your actual calendar and task apps.
- **Meeting prep automation** — 5 minutes before every calendar event: lights shift to video-call profile, music pauses, PuckNode LED turns amber ("do not disturb"), smart lock sets to "no visitors," display (if present) shows meeting details.
- **Post-meeting decompression** — meeting ends → lights warm back up, music resumes, HomeClaw says "Your next event is at 3pm, you have 47 minutes free."
- **Travel time intelligence** — integrates with Google Maps/Apple Maps. Calendar event has a location → HomeClaw calculates current drive time and reminds you 10 minutes before you need to leave, not just at event time.
- **Buffer blocking** — knows when you've back-to-back meetings and adjusts your environment differently than when you have open blocks. Deep work blocks = focus mode. Gap between meetings = rest lighting.
- **Weekend mode** — detects it's Saturday, no work calendar events → home enters Weekend Profile. Later wake time assumed, relaxed lighting schedule, music is different, thermostat schedule shifts.
- **Holiday/vacation awareness** — if your calendar shows "Vacation - 7 days" → house enters Away Mode. Thermostat to setback, security to active monitoring, lights on random schedule to simulate occupancy.

### Integrations
Google Calendar (OAuth, local sync), Apple Calendar (local CalDAV), Outlook/Exchange, Fantastical, Notion Calendar, Calendly (incoming meetings), Google Maps API (travel time), Apple Maps

---

## ✅ Tasks, Todos & Backlog Management

The killer feature nobody has built. Your task manager and your home should be connected.

### What We Build
- **Morning task briefing** — "Good morning. You have 3 priority tasks due today: finish the auth-agent PR, send invoice to client, and call your accountant." Pulled from your actual task app.
- **Voice task capture** — walking to the kitchen, think of something → "Hey HomeClaw, remind me to review the PR before standup" → it appears in your task app. No unlocking a phone, no friction.
- **Ambient backlog pressure** — HomeClaw knows when you're in a focus block with nothing scheduled. Proactively surfaces your backlog: "You have an open 2-hour window. Your highest priority task is [X]. Want me to start a focus session?"
- **Done → celebration** — mark a task done → HomeClaw can do a brief ambient celebration (lights flash, plays a quick sound, celebratory message). Dopamine on completion, not just on creation.
- **Standup prep** — detects your daily standup on calendar. 5 minutes before, pulls what you completed yesterday and what's in progress → reads you a draft standup. You show up prepared.
- **Grocery/supply intelligence** — "Add paper towels to my shopping list" → goes directly into your preferred list app. "What's on my list?" → reads it back. Works with Alexa Shopping List, Todoist, Things 3, or a HomeClaw-native list.
- **Project context switching** — "I'm working on HomeClaw now" → HomeClaw loads your HomeClaw focus profile (specific music, lighting, pulls relevant tasks to surface, sets DND).

### Integrations
Things 3 (via URL scheme + AppleScript), Todoist (REST API), Linear (GraphQL API), GitHub Issues, Notion databases, Obsidian (local vault), Apple Reminders, Jira, Trello, OmniFocus

---

## 🧘 Health, Sleep & Wellbeing

The most underserved category in smart home. Your home should actively support your health, not just not interfere with it.

### What We Build
- **Sleep tracking integration** — connects to your wearable (Oura Ring, Whoop, Apple Watch) to know your actual sleep/wake times and sleep quality. Adjusts tomorrow's environment based on last night's data. Poor sleep → gentler morning wake, more coffee prompts, earlier wind-down tonight.
- **Movement reminders** — knows when you've been sitting for too long (PuckNode audio detects you're still there, no movement sounds). After 90 minutes → "Hey, you've been at your desk for a while. Take a 5-minute walk."
- **Hydration prompts** — optional, but genuinely useful for WFH developers who forget to drink water. Timed reminders that also learn — if you always ignore 2pm, it stops trying at 2pm.
- **Eye strain protection** — after 2 hours of screen time (inferred from presence + computer activity via optional Mac/Linux agent), shifts lights to reduce glare, reminds you to do the 20-20-20 exercise.
- **Stress detection (optional)** — if you have an HRV-capable wearable, HomeClaw can detect elevated stress and proactively offer: lower the temperature slightly, dim lights, offer to play calming music, surface a break.
- **Deep work tracking** — logs your actual focus sessions (Pomodoro blocks, calendar deep work time) and shows you a weekly focus score. "You hit 4.2 hours of deep work today — best this week."
- **Workout integration** — Garmin/Apple Health detects you started a workout → HomeClaw sets house to Workout Mode: energizing playlist, cooler temperature, no interruptions.

### Integrations
Oura Ring API, Whoop API, Apple HealthKit (via local bridge), Garmin Connect, Fitbit, Eight Sleep (mattress temperature), Withings (sleep tracker), Mac focus mode detection (via local agent), Windows Focus Assist

---

## 🏠 Presence & Security Intelligence

True presence detection — not just "is someone home" but "who is where doing what."

### What We Build
- **Room-level presence** — PuckNode mic arrays do passive audio presence detection (breathing, movement sounds, keyboard typing — not recording, just detecting presence probability). No need for motion sensors in every room.
- **Person identification** — optional voice ID lets HomeClaw know it's YOU vs. a roommate vs. a guest. Different profiles load automatically.
- **Guest mode** — "I have someone staying this week" → guest network isolated from HomeClaw control, common areas stay managed, private areas excluded.
- **Delivery intelligence** — doorbell rings + no one home → HomeClaw sends you a push notification with camera snapshot and can instruct smart lock to authorize a delivery (if you set it up).
- **Arrival sequence** — phone Bluetooth or geofence detects you're 5 minutes away → home preheats, lights come on, music starts, coffee maker kicks on. Walk in to a ready home.
- **Away mode automation** — last person leaves → lights off, thermostat to setback, security arms, robot vacuum starts, HomeClaw sends confirmation: "All clear. House secured at 9:14 AM."
- **Panic word** — you can set a word or phrase that, if spoken, silently alerts a contact and starts recording audio/video. For domestic safety situations.

### Integrations
Life360, OwnTracks (self-hosted location), Apple Find My, Unifi Protect, Frigate NVR (local AI camera detection — face/person/car), Ring, Arlo, Eufy, August/Schlage/Yale locks, Z-Wave door sensors

---

## 🔋 Energy & Home Economics

Smart homes should save you money. Most don't because they're not actually smart about energy.

### What We Build
- **Real-time energy dashboard** — shows you live power draw by circuit (with a smart energy monitor like Emporia Vue or Sense). "Your HVAC is running 40% more than last week — here's why."
- **Phantom load elimination** — smart plugs detect devices in standby drawing significant power. HomeClaw alerts you and offers to auto-cut power on a schedule (your TV consumes 50W in standby).
- **EV charging optimization** — if you have an EV, HomeClaw schedules charging for off-peak hours automatically, based on your utility rate plan and when you next need the car (from calendar).
- **Solar + battery integration** — if you have solar, HomeClaw shifts high-draw appliances to run when you're generating surplus. Runs dishwasher, laundry, EV charging during solar peak.
- **Grocery/consumables tracking** — smart scale under your coffee beans, laundry detergent, etc. When low → adds to shopping list automatically. Never run out of coffee again.
- **Utility rate integration** — pulls real-time grid pricing (where available: PG&E, ConEd, etc.). Pre-cools, pre-heats, runs high-draw appliances during cheap windows. Estimates your monthly savings.

### Integrations
Emporia Vue, Sense Home Energy Monitor, Tesla Powerwall, Enphase (solar), SolarEdge, Tesla/ChargePoint/Wallbox EV chargers, smart plugs with power monitoring (TP-Link, Shelly), utility APIs (Green Button Data standard)

---

## 🎮 Developer-Specific Power Features

The stuff only HomeClaw offers. This is the reason developers choose us over anything else.

### What We Build
- **GitHub/Linear/Jira webhooks** — PR merged → lights flash green. CI/CD pipeline fails → lights flash red. Deploy succeeds → brief celebration sequence. Your build status is ambient in your environment.
- **Terminal-native control** — `homeclaw lights office --brightness 80 --kelvin 4000` from any terminal. Full CLI. Scriptable with any shell script or cron job.
- **Webhook receiver** — any external service can trigger HomeClaw via a simple authenticated POST. IFTTT-free automation with any web service.
- **Node-RED integration** — for power users, HomeClaw exposes a Node-RED compatible node library. Visual automation flows without limits.
- **On-call detection** — PagerDuty/OpsGenie integration. You go on-call → HomeClaw switches to On-Call Mode (keeps your office lit longer, maintains a quieter house if family is present, enables a specific DND mode on PuckNodes except your office).
- **Meeting status API** — HomeClaw exposes an endpoint that your Elgato Stream Deck, home-built Raspberry Pi indicator, or any script can query: "Am I in a meeting right now?" → returns true/false + meeting name.
- **Automation scripting in JS/Python** — write automations in real code, not YAML or drag-and-drop. Deployed to HomeClaw Hub, version-controlled in your repo.
- **Time-series data logging** — every sensor reading, every state change, logged to InfluxDB (bundled) and queryable in Grafana. Your home generates data — own it and analyze it.

### Integrations
GitHub (webhooks + API), GitLab, Linear, Jira, PagerDuty, OpsGenie, Datadog (receive alerts), Grafana + InfluxDB (bundled), Node-RED, Elgato Stream Deck (plugin), Home automation CLI, full REST + WebSocket API

---

## 🍳 Kitchen & Daily Life Intelligence

The mundane stuff that actually matters every day.

### What We Build
- **Morning coffee automation** — HomeClaw knows your wake time from calendar/alarm. If you have a smart coffee maker or smart plug + timer coffee maker, coffee is ready when you walk in. Not when you wake up. When you WALK IN.
- **Cooking assistant** — "Start a 25-minute timer for pasta" (basic), but also: "I'm making chicken at 425 degrees — remind me to flip it in 20 minutes and alert me at 165 internal temp" (with a meat thermometer integration).
- **Grocery list from voice** — mid-cooking, realize you're low on olive oil → "Hey HomeClaw, add olive oil to my shopping list" → instant, hands-free, goes straight to your list app.
- **Meal plan integration** — if you use Mealime, Plan to Eat, or even a Notion meal planner → HomeClaw knows what you're making this week and can add all ingredients to your shopping list at once.
- **Package tracking** — HomeClaw monitors your email (optional, local processing) for shipping notifications and tells you "Your package from Amazon is out for delivery today."
- **Appliance reminders** — washer finished 20 minutes ago and you haven't moved clothes to dryer → gentle reminder. Dishwasher done → "Dishes are clean."

### Integrations
Hamilton Beach Smart Coffee Maker, Fellow Stagg EKG, iKettle, Instant Pot Smart, GE Smart Appliances, Miele (some models), Oven with probe (Weber Connect, Meater), Any smart plug + dumb appliance, Todoist/Things 3 for lists, USPS/UPS/FedEx tracking APIs

---

## The Integrations Nobody Else Has

**Obsidian vault** — if you use Obsidian for notes, HomeClaw can read your daily notes and surface relevant context. Working on a specific project? HomeClaw sees your Obsidian project page and loads the relevant task context.

**Readwise** — your highlights from books and articles, surfaced as ambient prompts. Every morning, one highlight from your reading history in your briefing.

**Duolingo streak** — if you're learning a language, HomeClaw knows your streak status and reminds you before midnight if you haven't practiced.

**Strava/Garmin** — completed a run → HomeClaw congratulates you, adjusts thermostat for recovery (slightly cooler), suggests a recovery playlist.

**Waze/Google Maps real-time** — if there's a traffic incident on your usual commute route → HomeClaw alerts you 15 minutes earlier than you'd normally leave.

**Air quality (IQAir/PurpleAir)** — outdoor air quality drops (wildfire smoke) → closes smart windows, activates air purifier, notifies you.

**Hacker News digest** — top 5 stories this morning, read aloud during your coffee time. Optional. Genuinely useful for the target market.

**GitHub trending** — weekly briefing on what's trending in your primary language.

---

## The Modes System — How It All Comes Together

Every feature above connects through HomeClaw's Mode system. Modes are named states that configure your entire environment at once, automatically.

| Mode | When It Activates | What It Does |
|------|------------------|--------------|
| **Morning** | Wake time from calendar | Sunrise simulation, circadian lighting begins, morning briefing, coffee starts |
| **Deep Work** | Calendar block or voice trigger | Focus lighting (5000K), lo-fi music, DND on PuckNode LED, surfaces top backlog tasks |
| **Meeting** | 5 min before calendar event | Video lighting, music pauses, DND, thermostat stable |
| **Break** | Pomodoro break or between meetings | Warmer lighting, music up, movement reminder, hydration prompt |
| **Evening** | Sunset or configurable time | Circadian shift begins, lighting warms, music shifts |
| **Wind Down** | 60 min before sleep | Lights ramp to red/amber, volume decreases, thermostat drops, task recap |
| **Sleep** | Bedtime | All lights off, thermostat to sleep temp, security armed |
| **Weekend** | Saturday-Sunday, no work events | Relaxed schedule, later everything, different music profiles |
| **Away** | Last person leaves | Thermostat setback, security on, lights off, robot vacuum starts |
| **Guest** | Manual or calendar "guests" event | Common areas managed, guest network, private spaces excluded |
| **Workout** | Wearable detects exercise | Energizing music, cool temperature, hydration reminder after |
| **On-Call** | PagerDuty integration | Extended work lighting, family DND in other rooms, alert-ready mode |
| **Movie Night** | Voice trigger | Lights dim to 5%, bias lighting on, music off, thermostat stable, DND |
| **Party** | Voice trigger | Color scenes, music managed for group, thermostat adjusted for occupancy |
| **Emergency** | Smoke/CO detector or panic word | All lights full white, emergency contacts alerted, doors unlocked |

---

*This is the version of smart home that should have existed five years ago. HomeClaw is building it now.*
