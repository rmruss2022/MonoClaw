const http = require('http');

function httpRequest(method, path, data) {
  return new Promise((resolve, reject) => {
    const body = data ? JSON.stringify(data) : '';
    
    const options = {
      hostname: 'localhost',
      port: 3001,
      path,
      method,
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body)
      }
    };
    
    const req = http.request(options, (res) => {
      let responseData = '';
      
      res.on('data', (chunk) => {
        responseData += chunk;
      });
      
      res.on('end', () => {
        try {
          resolve(JSON.parse(responseData));
        } catch (e) {
          reject(new Error('Invalid JSON response'));
        }
      });
    });
    
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

async function updateOrchestrator() {
  try {
    // Fetch orchestrator instructions
    const docs = await httpRequest('GET', '/api/projects/3/context');
    const orchDoc = docs.documents.find(d => d.document_type === 'orchestrator');
    
    if (!orchDoc) {
      console.error('Orchestrator document not found');
      return;
    }
    
    // Replace all hardcoded Ora AI paths with dynamic references
    let updatedContent = orchDoc.content;
    
    // Replace specific file paths with generic placeholders
    updatedContent = updatedContent.replace(
      /\/Users\/matthew\/Desktop\/Feb26\/ora-ai\//g,
      '{project.configuration.file_paths.app_root}'
    );
    
    updatedContent = updatedContent.replace(
      /\/Users\/matthew\/Desktop\/Feb26\/ora-ai-api\//g,
      '{project.configuration.file_paths.backend_root}'
    );
    
    updatedContent = updatedContent.replace(
      /\/Users\/matthew\/Desktop\/Feb26\/Ora 2\//g,
      '{project.configuration.file_paths.brand_assets}'
    );
    
    updatedContent = updatedContent.replace(
      /\/Users\/matthew\/Desktop\/Feb26\/ora-ai\/HomeScreen\.png/g,
      '{project.configuration.file_paths.home_screen_reference}'
    );
    
    // Add section about project configuration at the top
    const configSection = `## Project Configuration System

**CRITICAL: All file paths are project-specific!**

Before spawning any agent, fetch the project configuration:

\`\`\`javascript
const projectData = await fetch('http://localhost:3001/api/projects/{projectId}');
const config = projectData.project.configuration;
\`\`\`

**Configuration Structure:**
\`\`\`json
{
  "file_paths": {
    "app_root": "/path/to/app/",
    "backend_root": "/path/to/backend/",
    "brand_assets": "/path/to/assets/",
    "home_screen_reference": "/path/to/reference.png"
  },
  "reference_materials": [...],
  "tech_stack": {...},
  "agent_requirements": {...}
}
\`\`\`

**Using Configuration in Agent Spawning:**

When spawning agents, always replace placeholders with actual paths from configuration:
- \`{project.configuration.file_paths.app_root}\` → actual app root path
- \`{project.configuration.file_paths.backend_root}\` → actual backend path
- \`{project.configuration.file_paths.brand_assets}\` → actual brand assets path
- \`{project.configuration.file_paths.home_screen_reference}\` → actual reference image path

**Example Spawning Code:**

\`\`\`javascript
// Fetch project data first
const response = await fetch('http://localhost:3001/api/projects/3');
const projectData = await response.json();
const config = projectData.project.configuration;

// Replace placeholders in task prompt
let taskPrompt = \`
CONTEXT:
- Project root: {project.configuration.file_paths.app_root}
- Backend root: {project.configuration.file_paths.backend_root}
- Reference design: {project.configuration.file_paths.home_screen_reference}
- Brand assets: {project.configuration.file_paths.brand_assets}
\`;

// Replace with actual paths
taskPrompt = taskPrompt
  .replace('{project.configuration.file_paths.app_root}', config.file_paths.app_root)
  .replace('{project.configuration.file_paths.backend_root}', config.file_paths.backend_root)
  .replace('{project.configuration.file_paths.home_screen_reference}', config.file_paths.home_screen_reference)
  .replace('{project.configuration.file_paths.brand_assets}', config.file_paths.brand_assets);

// Now spawn with real paths
sessions_spawn({
  agentId: "main",
  label: "iOS-Dev-Agent: Task XYZ",
  task: taskPrompt,
  ...
});
\`\`\`

**Multi-Project Support:**

This system allows different projects to have completely different:
- File structures
- Technology stacks
- Agent requirements
- Reference materials

Always fetch configuration before spawning agents to ensure correct paths!

---

`;
    
    // Insert at the beginning after the title
    updatedContent = updatedContent.replace(
      /## Your Role/,
      configSection + '\n## Your Role'
    );
    
    // Update the document
    await httpRequest('PUT', `/api/projects/3/context/${orchDoc.id}`, {
      title: orchDoc.title,
      content: updatedContent
    });
    
    console.log('✅ Orchestrator instructions updated to support multiple projects');
    console.log('📝 All hardcoded paths replaced with configuration placeholders');
    console.log('🔧 Added project configuration section at the top');
    
  } catch (error) {
    console.error('❌ Error:', error.message);
  }
}

updateOrchestrator();
