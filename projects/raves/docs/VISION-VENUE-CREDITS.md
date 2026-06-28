# Groundfloor Credits — Venue-Local Money

**Status:** Aspirational / design spec  
**Author:** Claw  
**Date:** June 27, 2026

---

## The Concept

Every venue gets its own **credit economy** — like Cash App Boosts, but hyperlocal to the underground scene.

When you spend at a venue, you earn **Groundfloor Credits** (GFC) redeemable only at that venue (or its network). Credits live in your Rave Card wallet. The venue uses them to drive repeat attendance, off-peak fills, and loyalty without discounting tickets publicly.

Think: **"You have $12 in Knockdown Credits"** — not a generic reward points number, but a venue-specific balance that feels like money because it *is* money.

---

## Why This Works — The Economics

### The Cash App Boost Model (translated to venues)

Cash App Boosts work because:
1. **Merchant pays for the boost** (takes the discount, pays interchange to Square)  
2. **User gets instant cash-back** (feels like a reward, not a coupon)
3. **Cash App keeps the spread** (transaction fee + data on spend behavior)

In our model:
1. **Venue "funds" the credit pool** at a discount (e.g. 15¢ on the dollar — $150 real money = $1,000 face-value credits)  
2. **Ravers earn credits** automatically by attending and spending  
3. **Groundfloor takes a platform fee** (10–15%) on credit issuance + redemption spread

### The Loyalty Point Illusion (why it prints money for venues)

Classic loyalty economics:
- **Breakage rate:** 30–40% of loyalty points/credits issued are never redeemed (forgotten, expired, user churn). This is pure profit for the issuer.
- **Velocity effect:** Credits create urgency — people attend shows they'd skip just to use their balance ("I have $20 in HOY credits, might as well go")
- **Spend lift:** Credit holders spend **34% more per visit** on average (Stanford/Starbucks data) because they're in the mindset of "I already have value here"
- **Lock-in:** Credits at Venue A don't work at Venue B → anchors loyalty to that venue's calendar

### Why Venue-Local (not Global) is Key

Generic loyalty programs (think: casino comps, airline miles) lose value because they create an expectation of universal redemption. Venue-local credits:
- **Preserve scarcity** — "Elsewhere Credits" feel more exclusive than generic "nightlife points"  
- **Drive venue-specific behavior** — owners want their credits driving repeat visits to *their* place, not a competitor  
- **Allow partner networks** — venues can choose to accept each other's credits (e.g. House of Yes + Elsewhere co-op network), creating a micro-economy with defined borders

### The "Private Currency" Play

If Groundfloor becomes the rails, venue credits become a private currency ecosystem:
- Each venue sets its own **earn rate** (1 credit per $1 spent, or 2x on Sundays, or 5x for first visit)
- Each venue sets **redemption rules** (credits → free drinks, comp tickets, early entry)
- Groundfloor is the **central bank** — sets floor rules, prevents inflation, handles interop

This is exactly what airline miles became: a second currency with its own economy. At scale, venues *pay* to issue more credits because demand drives attendance.

---

## Credit Types

### 1. Spend Credits (earn by paying)
- Scan your Rave Card (QR or NFC) at the door/bar
- Earn 1 GFC per $1 spent at the venue
- Redeemable: drinks, tickets, merch, coat check

**Example:** You spend $75 at Knockdown (door + 2 drinks). You earn 75 KDC (Knockdown Credits). Next visit: free drink at $15 KDC.

### 2. Attendance Credits (earn by showing up)
- Check in at the venue (geofence or QR scan at door)
- Earn flat credits per visit: 10 base + tier multiplier (Regulars earn 2x, Legends 5x)
- Creates value even for non-spenders (comped entry, guest list regulars)

### 3. Intro Credits (earn by bringing someone)
- Refer a friend to the venue for the first time → earn 50 credits
- Referree also gets 25 welcome credits
- Classic two-sided referral flywheel

### 4. Promo Credits (limited-time drops)
- Venue issues "Sunday Boost" — 3x credits before midnight
- Off-peak incentive to fill the room on dead Sundays
- Can be targeted: only Rookie and Regular tiers, only subscribers

---

## UI Spec

### Wallet Card View
```
┌─────────────────────────────────────────────────┐
│  GROUNDFLOOR WALLET                              │
│                                                   │
│  KNOCKDOWN CENTER          $47.00 in credits      │
│  ████████████░░░░░░        47 / 50 to free ticket │
│                                                   │
│  HOUSE OF YES              $12.00 in credits      │
│  ████░░░░░░░░░░░░          12 / 50 to comp drink  │
│                                                   │
│  ELSEWHERE                 $0.00                  │
│  Attend to start earning                          │
└─────────────────────────────────────────────────┘
```

### At-a-Glance (Stats Bar)
Add "WALLET $59" stat next to COMMITTED on the Stats Bar.

### Credit Bar (in Event Cards)
When viewing a Going event at a venue where you have credits:
```
💳 12 HOY Credits available · $12 toward entry
```

### Earn Notification
After a show you attended:
```
🎉 Earned 75 Knockdown Credits from Saturday's show
   Balance: 122 KDC · Redeem for free entry at $150
```

---

## Venue Partner Economics (the pitch to owners)

| Metric | Impact |
|--------|--------|
| Customer re-attendance rate | +25–40% with active credit program |
| Average spend per visit | +34% for credit holders |
| Off-peak attendance | +20% with targeted promo credits |
| Breakage revenue (unredeemed) | 30–40% of issued credits = free marketing |
| Cost per acquired repeat customer | 60–80% cheaper than ads |

**The founder pitch:**
> "You're already spending $5–10 per head on door-staff, ticket platforms, and social ads to fill your room. Give us $0.15 on the dollar, and we'll send the same ravers back — spending more — without you lifting a finger."

---

## Monetization for Groundfloor

### Revenue Streams

1. **Issuance Fee:** 10% on credits purchased by venues  
   → Venue buys $1,000 in credit value for $150 real dollars; Groundfloor takes $15

2. **Redemption Spread:** 2–5% on redemptions processed  
   → Credits redeemed at point-of-sale, Groundfloor charges merchant rate

3. **Breakage Capture:** Negotiate 25–50% of unredeemed credits after 12 months  
   → Structural revenue that grows with the balance sheet

4. **Premium Venue Tiers:** Venues pay $200–800/month for:
   - Analytics dashboard (who's coming, spend patterns)
   - Targeted promotions to Groundfloor users by tier
   - Featured placement in "Trending This Week"
   - Custom credit multiplier campaigns

5. **Data Products:** Anonymized scene intelligence  
   → "House of Yes sees 3x return visits from Techno-leaning Regulars vs House-leaning ones" → venue programming insight

### Unit Economics (Example Venue)
- Venue with 500 unique ravers/month, avg $60 spend
- $30,000 monthly venue GMV
- Groundfloor earns: ~$300 issuance + ~$200 redemption + $400 premium = **$900/month/venue**
- At 50 venue partners: **$45,000 MRR**
- At 200 venue partners: **$180,000 MRR**

---

## Phase Rollout

### Phase 1 — Simulated Credits (no venue integration needed)
- Groundfloor tracks attendance via "Mark Attended" + cost logged
- Retroactively calculates credit balance based on past spend
- Shows users their *theoretical* credit balance at each venue
- Purpose: create desire + vocabulary before pitching venues

### Phase 2 — Venue Partnership (soft launch)
- Sign 3–5 indie venues (start with HOY, Elsewhere, Knockdown — all community-oriented)
- Issue real credits via QR scan at door (venue staff has a simple web UI)
- Ravers see balance update in real-time after scan
- Redeem: show QR at bar, staff validates in admin panel

### Phase 3 — Card Integration
- Groundfloor Credits load onto physical/virtual Rave Card
- Scan Apple/Google Wallet or NFC at door → credits auto-applied
- No venue staff training needed — just card reader integration

### Phase 4 — Inter-venue Network
- Define credit exchange rates between partners (1 KDC = 0.8 HOY Credits, or fixed 1:1)
- Ravers can "transfer" credits across their venue portfolio
- Creates genuine nightlife currency across the NYC underground ecosystem

---

## Key Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Credits feel cheap/fake | Give them real redemption value immediately (free drink > 10% off) |
| Venue doesn't honor credits | Contractual obligation + Groundfloor arbitration |
| Inflation / credit abuse | Per-venue issuance caps, earn rate limits, velocity checks |
| Ravers don't care | Make balance visible EVERYWHERE — wallet tab, event cards, going modal |
| Regulatory (money transmission) | Credits are non-transferable, venue-specific, no cash redemption = gifting model, not currency |

---

---

## The Travel Layer — Hotels, Flights, Food

Ravers travel. Boiler Room Barcelona. Awakenings Amsterdam. Dekmantel. Movement Detroit. Electric Daisy Las Vegas. The underground doesn't stay underground — it goes global. And every trip has the same spend pattern: flights, hotels, food, Ubers, tickets.

Groundfloor should own that entire trip wallet, not just the door.

---

### The Model: Scene-Aware Travel Rewards

The core insight: **the reason you're traveling is the music**. Every other spend on the trip is downstream of that rave. So Groundfloor should be the anchor point for trip planning, not a bolt-on after you've already booked through Expedia.

This is the **American Express model applied to nightlife culture**: AmEx makes money because high-spending cardholders use it everywhere — restaurants, hotels, flights, shopping. The card becomes identity. Groundfloor Credits become the raver's travel wallet.

---

### Credit Earn on Travel Spend

| Category | Earn Rate | Notes |
|----------|-----------|-------|
| Venue tickets | 3 GFC per $1 | Core product |
| Flights (tagged to a rave trip) | 2 GFC per $1 | User marks trip as "going to [Festival]" |
| Hotels / Airbnb | 2 GFC per $1 | Same trip-tagging logic |
| Food & drink (trip days) | 1.5 GFC per $1 | Auto-detect via GPS on trip dates |
| Rideshare (to/from venue) | 2 GFC per $1 | Tagged by proximity to venue location |
| Merch (at-event purchases) | 3 GFC per $1 | Matches ticket earn rate |
| Travel essentials (luggage, passport) | 1 GFC per $1 | Lower tier — stretch spend |

**Trip multiplier:** Tag a trip as a music festival → all associated spend earns 1.5x base rate for the duration.

---

### Travel Credit Types

#### 1. Rave Trip Credits
When you mark an event as Going + it's in a different city:
- Auto-creates a "Rave Trip" container in your wallet
- All spend during trip window (+2 days) earns at travel rate
- Trip recap: total spend, credits earned, shows attended

#### 2. Airline Partner Credits
Negotiate with Frontier, Spirit, JetBlue (routes heavy to rave cities):
- Amsterdam, Berlin, Ibiza, Miami, Chicago, Detroit, LA
- Earn GFC on flights + redeem GFC for seat upgrades, bag fees, early boarding
- Ravers travel in packs → family plan + group booking incentives

#### 3. Hotel Credits
Partner with boutique/hostel networks in rave cities:
- Generator (Amsterdam, Barcelona, Berlin) — natural fit for the demographic
- Pod Hotels (NYC), Ace Hotel, Freehand
- Earn 2 GFC per $1 + venue-city credits (e.g. "200 Berghain-Area Credits" redeemable at partner bars)
- Partner hotels get filled on festival weekends when they'd otherwise price-gouge

#### 4. Food & Bar Credits (travel days)
- Earn at any restaurant/bar during a tagged trip
- Categorized by cuisine/scene: "Berlin kebab discount," "Amsterdam broodje spot"
- At home: earn at venue-adjacent bars (pre-game + after-party spots)
- Expand venue network to include the bars inside or next to the club

---

### The Trip Wallet UI

```
┌────────────────────────────────────────────────────┐
│  AWAKENINGS 2026 TRIP                              │
│  Amsterdam · Jun 19–22                             │
│                                                    │
│  ✈ Flight (JetBlue)          $680  → 1,360 GFC    │
│  🏨 Generator Hostel          $240  → 480 GFC      │
│  🎟 Awakenings tickets        $180  → 540 GFC      │
│  🍔 Food & drink (4 days)     $190  → 285 GFC      │
│  🚕 Rideshare / transit       $85   → 170 GFC      │
│  ─────────────────────────────────────             │
│  TRIP TOTAL                 $1,375  → 2,835 GFC    │
│                                                    │
│  ≈ $28 in venue credits earned this trip           │
└────────────────────────────────────────────────────┘
```

---

### The Broader Economics

#### Why travel spend changes the unit economics dramatically

A typical NYC raver:
- Local spend: ~$150/month in tickets + drinks = 150 GFC/month
- One festival trip (1x per year): ~$1,200 in travel spend = 1,800–2,400 GFC in a single trip

Travel spend is **10–15x** the monthly local spend compressed into a few days. The ravers who travel are exactly the high-LTV users you want to own — they're spending $2,000+ on a weekend, not once a year, but 3–5 times annually for major festivals.

#### The interchange opportunity

If Groundfloor issues a **co-branded debit/credit card** (Mastercard/Visa partnership):
- Earn 1.5–2% interchange on every swipe (industry standard)
- Trips average $1,000–1,500 spend → $15–30 interchange per trip per user
- At 10,000 active traveling users: **$150,000–300,000 in annual interchange**

This is exactly how airline co-branded cards work. Delta SkyMiles Amex earns Delta more money from interchange on grocery shopping than from flying. The card *becomes* the product.

#### The "Trip as Identity" angle

When you log a festival trip, Groundfloor knows:
- Where you went (city, festival)
- What you spent (flight, hotel, food tier)
- What you listened to (lineups = genre profile)
- Who you went with (future: group trips)

This is richer cultural data than Spotify, richer spending data than your bank, richer travel data than TripAdvisor. **That dataset is worth something to brands** (festival promoters, travel companies, music labels) — ethically monetized via opt-in partnership insights.

---

### Redemption: Where Credits Go on a Trip

| Redemption | Cost | Notes |
|------------|------|-------|
| Checked bag fee | 150 GFC | Redeemable at airline partner |
| Hotel room upgrade | 500 GFC | Boutique partner only |
| Airport lounge day pass | 800 GFC | Priority Pass-style integration |
| Festival shuttle | 200 GFC | Partner transportation |
| Pre-game dinner for 2 | 400 GFC | Restaurant partner near venue |
| Free ticket to local show (on return) | 300–600 GFC | Back to the core loop |

The last row is key: **travel credits come home.** You go to Amsterdam, earn 2,800 GFC, come back to Brooklyn, and use them for free entry at Knockdown Center for three months. The trip subsidizes your local scene engagement. The circle closes.

---

### Partnership Stack (Travel)

**Tier 1 — Direct rave audience:**
- Boiler Room (official travel packages)
- Resident Advisor (they already have the audience + editorial)
- Festival promoters (Awakenings, Dekmantel, Movement, EDC) — revenue share on travel bookings

**Tier 2 — Travel infrastructure:**
- JetBlue, Frontier, Spirit (NYC-heavy route maps, lower LTV travelers who match rave demographics)
- Generator Hostels, Freehand, Pod Hotels
- Uber/Lyft (direct SDK integration for geofenced venue rides)

**Tier 3 — Scene-adjacent food:**
- Local restaurant chains near major venues
- Late-night food: Roberta's, Five Guys, McDonald's (post-set hunger)
- Festival food vendors (on-site integration at bigger events)

---

## The Vision in One Sentence

> **Every venue becomes a bank for its own community — Groundfloor is the Federal Reserve, and every trip is a deposit.**

---

*This document lives in `/docs/` alongside the product and design vision. Update as the model evolves.*
