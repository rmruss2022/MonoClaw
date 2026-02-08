#!/usr/bin/env node
/**
 * NYC Rave Parser
 * Extracts event data from Discord #rave-rex weekly posts
 */

const genreMap = {
  '🏠': 'House',
  '🖤': 'Techno',
  '🪩': 'Disco',
  '🎨': 'Experimental',
  '🌍': 'Global',
  '🪘': 'Percussion',
  '✨': 'Eclectic',
  '🔲': 'Minimal',
  '🧬': 'Acid',
  '🤖': 'Electro',
  '🛠️': 'Industrial',
  '🎹': 'Melodic',
  '⏩': 'Progressive'
};

function parseRaveMessage(text) {
  const events = [];
  const lines = text.split('\n');
  
  let currentDay = null;
  let currentEvent = null;
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    
    // Skip empty lines or headers
    if (!line || line.includes('Hey @everyone') || line.includes('Genre key')) continue;
    
    // Detect day headers
    const dayMatch = line.match(/(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(\w+)\s+(\d+)/);
    if (dayMatch) {
      currentDay = {
        dayOfWeek: dayMatch[1],
        month: dayMatch[2],
        date: parseInt(dayMatch[3])
      };
      continue;
    }
    
    // Detect event lines (start with emoji and have "@" for venue)
    const eventMatch = line.match(/^([🏠🖤🪩🎨🌍🪘✨🔲🧬🤖🛠️🎹⏩]+)\s*(.+?)\s+@\s+(.+?):/);
    if (eventMatch && currentDay) {
      // Save previous event if exists
      if (currentEvent) {
        events.push(currentEvent);
      }
      
      const genreEmojis = eventMatch[1];
      const genres = Array.from(genreEmojis).map(e => genreMap[e] || 'Other');
      
      currentEvent = {
        id: `${currentDay.month}-${currentDay.date}-${eventMatch[2].toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
        name: eventMatch[2].trim(),
        venue: eventMatch[3].trim(),
        date: `2026-${getMonthNumber(currentDay.month)}-${String(currentDay.date).padStart(2, '0')}`,
        dayOfWeek: currentDay.dayOfWeek,
        genres: genres,
        description: line.split(': ')[1] || '',
        topPick: line.includes('**') || isBolded(line)
      };
    } else if (currentEvent && line.length > 10) {
      // Continue description from previous line
      currentEvent.description += ' ' + line;
    }
  }
  
  // Add last event
  if (currentEvent) {
    events.push(currentEvent);
  }
  
  return events;
}

function getMonthNumber(month) {
  const months = {
    'January': '01', 'February': '02', 'March': '03', 'April': '04',
    'May': '05', 'June': '06', 'July': '07', 'August': '08',
    'September': '09', 'October': '10', 'November': '11', 'December': '12'
  };
  return months[month] || '01';
}

function isBolded(text) {
  // Check if text appears to be bolded (in markdown or Discord formatting)
  return text.includes('**') || text.match(/\*\*[^*]+\*\*/);
}

// Test with sample message
const sampleMessage = `Thursday, February 5
🏠Honeytrap Anniversary @ Signal: Honeytrap is Amelia Holt's taste-driven party—warm, curious, and built around smart selection...
🏠DVS1: House Set @ Green Room: A rare treat—this is DVS1 playing house...`;

if (require.main === module) {
  const fs = require('fs');
  const inputFile = process.argv[2];
  
  if (inputFile) {
    const text = fs.readFileSync(inputFile, 'utf8');
    const events = parseRaveMessage(text);
    console.log(JSON.stringify({ events, lastUpdated: new Date().toISOString() }, null, 2));
  } else {
    console.error('Usage: node parser.js <input-file>');
    process.exit(1);
  }
}

module.exports = { parseRaveMessage };
