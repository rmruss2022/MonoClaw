# Lumen 🔆 — light up the world, one breath at a time

A gamified meditation app. Every session you complete drops a point of light on a
living world map, earns **Light** (XP), builds your streak, and moves you up the
weekly leagues (Ember → Spark → Glow → Flare → Beacon → Nova → Supernova).

- **Meditate**: pick a duration + soundscape (rain / forest / ocean / deep space /
  silence — all synthesized live in-browser, no audio files), breathe with the orb,
  earn Light with streak + time-of-day multipliers.
- **Map**: Leaflet + CARTO dark tiles, glowing pins for everyone who meditated
  today / all-time. Locations are fuzzed for privacy.
- **Leagues**: your weekly league + promotion zone, plus global leaderboards
  (today / week / all-time, by Light or minutes).
- **Journal**: shared daily reflection prompt, private entries, opt-in community feed.
- **Profile**: level, streak, stats, achievements, home location.

## Run
    ./start.sh            # http://127.0.0.1:18834
    ./tunnel.sh           # public Cloudflare quick tunnel -> data/public_url.txt

## Stack
Single-file stdlib Python (`http.server` + `sqlite3`), zero third-party deps.
PBKDF2 + HttpOnly cookie sessions. Data in `./data/lumen.db`. On first run it seeds
a synthetic global community (46 practitioners across 30 cities) so the map and
leagues feel alive on day one; your first real account joins them.
