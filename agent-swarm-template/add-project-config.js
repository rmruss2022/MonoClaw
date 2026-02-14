const Database = require('better-sqlite3');
const db = new Database('swarm.db');

// Ora AI project configuration
const oraAiConfig = {
  file_paths: {
    app_root: '/Users/matthew/Desktop/Feb26/ora-ai/',
    backend_root: '/Users/matthew/Desktop/Feb26/ora-ai-api/',
    brand_assets: '/Users/matthew/Desktop/Feb26/Ora 2/',
    home_screen_reference: '/Users/matthew/Desktop/Feb26/ora-ai/HomeScreen.png'
  },
  reference_materials: [
    {
      type: 'design',
      name: 'Home Screen Reference',
      path: '/Users/matthew/Desktop/Feb26/ora-ai/HomeScreen.png'
    },
    {
      type: 'brand',
      name: 'Ora 2 Brand Assets',
      path: '/Users/matthew/Desktop/Feb26/Ora 2/',
      contents: ['logo', 'brand_bible.pdf', 'fonts (Sentient, Switzer)', 'stock_photos']
    }
  ],
  tech_stack: {
    frontend: 'React Native / Expo',
    backend: 'Node.js + PostgreSQL',
    database_extensions: ['pgvector'],
    services: ['activities', 'ai-tools', 'ai', 'behavior-detection', 'community', 'inbox', 'meditation']
  },
  agent_requirements: {
    designer: ['Figma', 'iOS design patterns', 'DALL-E 3 image generation', 'brand guidelines'],
    ios_dev: ['React Native', 'Expo', 'TypeScript', 'animations', 'navigation'],
    backend_dev: ['Node.js', 'PostgreSQL', 'pgvector', 'Redis', 'WebSocket', 'LLM APIs'],
    qa: ['Jest', 'Detox', 'accessibility testing', 'performance profiling'],
    content: ['UX copy', 'meditation guidance', 'quiz questions']
  }
};

// Update Ora AI project with configuration
const stmt = db.prepare(`
  UPDATE projects 
  SET configuration_json = ? 
  WHERE id = 3
`);

stmt.run(JSON.stringify(oraAiConfig));

console.log('✅ Ora AI project configuration added');

// Verify
const project = db.prepare('SELECT id, name, configuration_json FROM projects WHERE id = 3').get();
console.log('📋 Project:', project.name);
console.log('🔧 Config:', JSON.parse(project.configuration_json).file_paths.app_root);

db.close();
