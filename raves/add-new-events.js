#!/usr/bin/env node

const { upsertEvent } = require('./lib/db');

// New events for week of Feb 23-Mar 1, 2026
const newEvents = [
  {
    id: "February-27-l3ni-dln9",
    name: "L3ni",
    venue: "DLN9",
    date: "2026-02-27",
    dayOfWeek: "Friday",
    genres: ["House", "Experimental"],
    description: "Local babe L3ni brings soulful, high‑energy Chicago + nyc-rooted house that meets the moment in any room. Marcus Logan brings deep, rhythmic house with touches of baile and jazz, while Seb Hall and Gaspar Muniz hold the Foyer with house, disco + electro blends.",
    topPick: false
  },
  {
    id: "February-28-toy-tonics-jam",
    name: "Toy Tonics Jam",
    venue: "Good Room",
    date: "2026-02-28",
    dayOfWeek: "Saturday",
    genres: ["House", "Disco"],
    description: "Berlin's Toy Tonics crew always brings the funk, soul, and joy back to house music, mixing it with disco, indie, and organic elements. Kapote—the label's founder and groove maestro—leads the night alongside Sam Ruffillo, and nyc's own beewack, all funky, excellent selectors. It's one of the most feel-good labels out there, so this will be a dancers heaven.",
    topPick: false
  },
  {
    id: "February-28-cassy-refuge",
    name: "Cassy",
    venue: "Refuge",
    date: "2026-02-28",
    dayOfWeek: "Saturday",
    genres: ["House", "Techno"],
    description: "Such a treat to have such a highly respected selector in NYC. Cassy's love for music is palpable—and her personal record collection is basically an electronic music encyclopedia, full of lost gems and B-sides. An early Panorama Bar resident, she can't be boxed into one sound because every set is shaped by the room in real time. Also special shoutout to Refuge resident Simon Heyliger, who radiates music from every cell in his body. 📵",
    topPick: false
  },
  {
    id: "February-28-richie-hawtin-stingray",
    name: "Richie Hawtin / DJ Stingray 313",
    venue: "Knockdown Center",
    date: "2026-02-28",
    dayOfWeek: "Saturday",
    genres: ["Techno", "Electro"],
    description: "Another stacked lineup of legends. Richie Hawtin was a defining force in '90s minimal techno, and to this day he's known for extremely precise mixing, long arcs, tons of layering and microscopic attention to detail. Detroit's DJ Stingray brings a different kind of pressure: fast, sci-fi electro with hard momentum that feels like being inside a machine. And Lindsey Herbert rounds it out with a new-school, high-intensity warehouse sound.",
    topPick: false
  },
  {
    id: "February-28-ksenyeah-manguito",
    name: "Ksenyeah x Manguito",
    venue: "Dead Letter No 9",
    date: "2026-02-28",
    dayOfWeek: "Saturday",
    genres: ["House", "Eclectic"],
    description: "We always love a night in the Cargo Room. It's such an intimate dancefloor, and the whole venue is full of cool, interactive little sidequest rooms. I'll be doing 3.5-hour b2b with Manguito, spinning up a high-energy, rhythmic blend of house and indie dance with plenty of lyrical moments. The front Foyer will also have music going if you want to switch the channel. Tickets are super affordable, and you can do a free RSVP if you get there before 10pm.",
    topPick: false
  },
  {
    id: "February-28-byron-aquarius-soul-summit",
    name: "Byron the Aquarius / Soul Summit / JADALAREIGN",
    venue: "Shh",
    date: "2026-02-28",
    dayOfWeek: "Saturday",
    genres: ["House", "Global"],
    description: "A pure celebration of Black dance music lineage, bringing together soulful house legends and the new school of Brooklyn selectors. Byron the Aquarius is a master of warm, jazzy grooves, Soul Summit always delivers a high-energy feel with classic vocal house and deep disco cuts, and JADALAREIGN adds a punchy feel. 12 hour marathon!",
    topPick: false
  },
  {
    id: "February-28-freddy-k-carry-nation",
    name: "Freddy K / The Carry Nation",
    venue: "Basement",
    date: "2026-02-28",
    dayOfWeek: "Saturday",
    genres: ["Techno", "House"],
    description: "A techno activist, DJ, and producer since the 90s, Freddy K is a marathon purist who builds relentless, high-precision journeys made for stamina and focus. Meanwhile Studio is going to be pure joy (+ a dancer's delight) with both The Carry Nation and Kim Ann Foxman sharing the floor. 📵",
    topPick: false
  },
  {
    id: "February-28-locklead-silo",
    name: "Locklead",
    venue: "Silo",
    date: "2026-02-28",
    dayOfWeek: "Saturday",
    genres: ["House", "Minimal"],
    description: "This Dutch producer (with releases on Slapfunk + Up the Stuss) has been bubbling up in Europe for his groove-led, minimal house that feels understated but confident. He keeps things stripped but bouncy—tight drums, slinky basslines, and active blends that pull you deeper.",
    topPick: false
  },
  {
    id: "February-28-resolute-fabric",
    name: "ReSolute x fabric London",
    venue: "H0l0",
    date: "2026-02-28",
    dayOfWeek: "Saturday",
    genres: ["House", "Techno"],
    description: "A marathon party collab with London's legendary Fabric, this one runs for 30+ hours with extended sets and open formats. Standouts include: Craig Richards and Move D (subtle, trippy house + techno), Francesco Del Garda and Gene On Earth (rolling minimal groove), and Ciel + Aline Umber live.",
    topPick: false
  },
  {
    id: "February-28-cinthie-public-records",
    name: "Cinthie All Night",
    venue: "Public Records",
    date: "2026-02-28",
    dayOfWeek: "Saturday",
    genres: ["House"],
    description: "A Berlin powerhouse and label boss (Beste Modus), Cinthie is a \"DJ's DJ\" respected for her deep knowledge of house history. Her sound is built on chunky basslines, raw 909 drums, and soulful piano stabs that feel warm and authentic. An all-night set in the Sound Room lets her dig deep in her massive collection.",
    topPick: false
  },
  {
    id: "February-28-facundo-mohrr",
    name: "Facundo Mohrr",
    venue: "House of Yes",
    date: "2026-02-28",
    dayOfWeek: "Saturday",
    genres: ["Melodic", "Progressive"],
    description: "He's part of the All Day I Dream universe, so this is going to be warm, melodic house with a progressive backbone that builds slowly and lets you breathe—rolling bass, soft synths, nothing rushed. He's a great pacer, layering in emotion without getting cheesy. Extended set!",
    topPick: false
  },
  {
    id: "March-1-tini-golden-record",
    name: "Golden Record: tINI",
    venue: "Shh",
    date: "2026-03-01",
    dayOfWeek: "Sunday",
    genres: ["House", "Minimal"],
    description: "tINI doesn't chase drops—she locks into a groove and slowly tightens it until the whole room is moving the same way. It's rolling, minimal-leaning house with a little sexiness to it. It's your flavor if you like dancing for hours without realizing time passed.",
    topPick: false
  },
  {
    id: "March-1-jackie-hollander",
    name: "Jackie Hollander",
    venue: "Superior Ingredients Roof",
    date: "2026-03-01",
    dayOfWeek: "Sunday",
    genres: ["House", "Industrial"],
    description: "One to watch! This SF-native has been carving out a space for herself with a style of tech house that feels way more sophisticated than the usual peak-time fluff. She leans into deep, chunky basslines and cool percussion, keeping the energy driving but soulful.",
    topPick: false
  },
  {
    id: "March-1-nonstop-nowadays",
    name: "Nonstop",
    venue: "Nowadays",
    date: "2026-03-01",
    dayOfWeek: "Sunday",
    genres: ["House", "Experimental"],
    description: "We personally like the arc starting from 12pm Sunday. Soulful, vocal house that lifts the room with Shaun J. Wright > Binh locking into rolling, minimal grooves that still feel good on your body > psychedelic, slow-burn selector magic to close with Vladimir Ivkovic.",
    topPick: false
  }
];

console.log(`Adding ${newEvents.length} new events...`);

let added = 0;
let errors = 0;

newEvents.forEach(event => {
  try {
    upsertEvent(event);
    added++;
    console.log(`✓ Added: ${event.name} @ ${event.venue} (${event.date})`);
  } catch (err) {
    console.error(`✗ Failed to add ${event.id}:`, err.message);
    errors++;
  }
});

console.log(`\n✓ Added ${added} events`);
if (errors > 0) {
  console.error(`✗ ${errors} errors`);
}
console.log('Done!');
