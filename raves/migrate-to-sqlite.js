#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { upsertEvent } = require('./lib/db');

// Read events.json
const eventsPath = path.join(__dirname, 'events.json');
const data = JSON.parse(fs.readFileSync(eventsPath, 'utf8'));

console.log(`Migrating ${data.events.length} events to SQLite...`);

let imported = 0;
let errors = 0;

data.events.forEach(event => {
  try {
    upsertEvent(event);
    imported++;
  } catch (err) {
    console.error(`Failed to import event ${event.id}:`, err.message);
    errors++;
  }
});

console.log(`✓ Imported ${imported} events`);
if (errors > 0) {
  console.error(`✗ ${errors} errors`);
}
console.log('Migration complete!');
