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
    // Fetch current orchestrator instructions
    const docs = await httpRequest('GET', '/api/projects/3/context');
    const orchDoc = docs.documents.find(d => d.document_type === 'orchestrator');
    
    if (!orchDoc) {
      console.error('Orchestrator document not found');
      return;
    }
    
    // Add image generation section
    const imageGenSection = `

### Designer-Agent Image Generation 🎨

Designer agents have access to image generation capabilities:

**Tools Available:**
1. **OpenAI DALL-E 3** (via openai-image-gen skill)
   - High-quality, photorealistic images
   - Great for UI mockups, icons, illustrations
   - Access via: Use the openai-image-gen skill in ~/.nvm/versions/node/v22.22.0/lib/node_modules/openclaw/skills/openai-image-gen/

2. **Web Search for Stock Photos**
   - Find high-quality stock images
   - Unsplash, Pexels for free commercial use
   - Search via web_search tool

3. **Design with Figma/Sketch**
   - Create vector designs
   - Export assets (SVG, PNG)
   - Reference Ora 2 brand assets at /Users/matthew/Desktop/Feb26/Ora 2/

**Designer Agent Spawning Template with Image Generation:**

\`\`\`javascript
sessions_spawn({
  cleanup: "delete",
  agentId: "main",
  label: "Designer-Agent: Create Home Screen Mockup",
  model: "anthropic/claude-opus-4-6",
  thinking: "high",
  task: \`You are a Designer-Agent working on Ora AI (Project ID 3).

TASK: ORA-001 - Design Home Screen

CONTEXT:
- Reference: HomeScreen.png at /Users/matthew/Desktop/Feb26/ora-ai/HomeScreen.png
- Brand assets: /Users/matthew/Desktop/Feb26/Ora 2/
- Ora 2 brand bible PDF with color palette and fonts

YOUR CAPABILITIES:
1. **Image Generation**: You can generate images using DALL-E 3
   - Use for: UI mockups, icons, illustrations, background images
   - Read the openai-image-gen skill documentation
   - Generate batch images for different use cases
   
2. **Web Search**: Find stock photos and design inspiration
   - Search "wellness app UI design" for inspiration
   - Find high-quality stock photos for backgrounds
   
3. **Design Software**: Create vector designs
   - Reference brand guidelines (fonts, colors, spacing)
   - Export assets as PNG/SVG
   - Follow iOS design guidelines

REQUIREMENTS:
- 5 behavior cards with icons
- Clean header with app name
- Follow Ora 2 brand colors and fonts
- Modern iOS aesthetic

DELIVERABLES:
1. Figma/Sketch design link or exported mockup images
2. Icon assets (SVG or PNG @2x, @3x)
3. Design spec document (spacing, colors, fonts)
4. Any generated images saved to project assets folder

After completing:
- Update task state: PATCH http://localhost:3001/api/tasks/ORA-001
- Log completion: POST /api/activity with design links
\`,
  runTimeoutSeconds: 3600,
  cleanup: "keep"
});
\`\`\`

**Image Generation Workflow:**

1. **Planning**: Understand the design need (icon, mockup, illustration)
2. **Generation**: Use DALL-E 3 to generate initial concepts
3. **Iteration**: Refine prompts based on results
4. **Export**: Save high-res images to project assets
5. **Documentation**: Note which images were generated vs sourced

**Best Practices:**
- Generate multiple variants (2-3 options)
- Use consistent art style across project
- Follow brand colors in generation prompts
- Generate @2x and @3x for iOS (or upscale after)
- Save originals + exports

`;

    // Insert image generation section after "### Designer-Agent" and before "### iOS-Dev-Agent"
    const updatedContent = orchDoc.content.replace(
      /### iOS-Dev-Agent/,
      imageGenSection + '\n### iOS-Dev-Agent'
    );
    
    // Update the document
    await httpRequest('PUT', `/api/projects/3/context/${orchDoc.id}`, {
      title: orchDoc.title,
      content: updatedContent
    });
    
    console.log('✅ Orchestrator instructions updated with image generation capability');
    
  } catch (error) {
    console.error('❌ Error:', error.message);
  }
}

updateOrchestrator();
