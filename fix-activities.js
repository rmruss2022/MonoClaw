const fs = require('fs');

const filePath = '/Users/matthew/.openclaw/workspace/activity-hub/activities-store.json';
const content = fs.readFileSync(filePath, 'utf8');

// Try to parse and fix
try {
  // Remove trailing junk
  const lines = content.split('\n');
  let fixed = lines.slice(0, -3).join('\n') + '\n]';
  
  // Validate it parses
  JSON.parse(fixed);
  
  // Write back
  fs.writeFileSync(filePath, fixed);
  console.log('✓ Fixed activities-store.json');
} catch (error) {
  console.error('Failed to fix:', error.message);
  process.exit(1);
}
