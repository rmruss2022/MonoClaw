/**
 * Service Analysis Module
 * Analyzes discovered services to extract API details and usage patterns
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

/**
 * Read and parse package.json
 */
async function analyzePackageJson(servicePath) {
  const pkgPath = path.join(servicePath, 'package.json');
  try {
    const content = fs.readFileSync(pkgPath, 'utf8');
    const pkg = JSON.parse(content);
    return {
      name: pkg.name,
      version: pkg.version,
      description: pkg.description,
      main: pkg.main,
      scripts: pkg.scripts,
      dependencies: Object.keys(pkg.dependencies || {}),
      devDependencies: Object.keys(pkg.devDependencies || {}),
      port: pkg.port || extractPortFromContent(content)
    };
  } catch (e) {
    return null;
  }
}

/**
 * Extract port from file content
 */
function extractPortFromContent(content) {
  const portMatch = content.match(/(\d{4,5})/);
  return portMatch ? parseInt(portMatch[1]) : null;
}

/**
 * Analyze server.js to extract endpoints
 */
async function analyzeServerJs(servicePath) {
  const serverFiles = ['server.js', 'index.js', 'app.js', 'main.js'];
  let endpoints = [];
  let port = null;
  
  for (const file of serverFiles) {
    const filePath = path.join(servicePath, file);
    try {
      const content = fs.readFileSync(filePath, 'utf8');
      
      // Extract Express/Fastify routes
      const routeMatches = content.matchAll(/\.(get|post|put|delete|patch)\s*\(\s*['"]([^'"]+)['"]/g);
      for (const match of routeMatches) {
        endpoints.push({
          method: match[1].toUpperCase(),
          path: match[2]
        });
      }
      
      // Extract port
      const portMatch = content.match(/port\s*[=:]\s*(\d{4,5})|listen\s*\(\s*(\d{4,5})/);
      if (portMatch && !port) {
        port = parseInt(portMatch[1] || portMatch[2]);
      }
      
      // Check for Next.js
      if (content.includes('next dev')) {
        return { framework: 'nextjs', devCommand: 'npm run dev', port: port || 3000 };
      }
      
    } catch (e) {
      // File doesn't exist
    }
  }
  
  return { endpoints, port };
}

/**
 * Analyze README for API documentation
 */
async function analyzeReadme(servicePath) {
  const readmeFiles = ['README.md', 'README', 'readme.md', 'Readme.md'];
  
  for (const file of readmeFiles) {
    const filePath = path.join(servicePath, file);
    try {
      const content = fs.readFileSync(filePath, 'utf8');
      
      // Extract API endpoints from markdown
      const apiSection = content.match(/## API[\s\S]*?(?=##|\Z)/i);
      const endpointMatches = content.matchAll(/```(?:bash|shell|curl)[\s\S]*?curl[^`]*```/g);
      const curlExamples = [];
      
      for (const match of endpointMatches) {
        curlExamples.push(match[0].replace(/```[a-z]*\n?|```/g, '').trim());
      }
      
      // Extract description
      const descMatch = content.match(/^#\s+(.+)\n\n([\s\S]+?)(?=\n##|\Z)/);
      
      return {
        description: descMatch ? descMatch[1] : '',
        overview: descMatch ? descMatch[2].trim() : '',
        hasApiDocs: !!apiSection,
        curlExamples: curlExamples.slice(0, 5),
        content: content.substring(0, 5000) // Limit content size
      };
    } catch (e) {
      // File doesn't exist
    }
  }
  
  return null;
}

/**
 * Analyze SKILL.md if it exists
 */
async function analyzeSkillFile(servicePath) {
  const skillPath = path.join(servicePath, 'SKILL.md');
  try {
    const content = fs.readFileSync(skillPath, 'utf8');
    return {
      exists: true,
      content: content,
      lastModified: fs.statSync(skillPath).mtime
    };
  } catch (e) {
    return { exists: false };
  }
}

/**
 * Detect service capabilities
 */
async function detectCapabilities(service) {
  const capabilities = [];
  
  if (service.port) {
    // Test common endpoints
    const tests = [
      { path: '/health', capability: 'health-check' },
      { path: '/status', capability: 'status-report' },
      { path: '/api', capability: 'api-endpoint' },
      { path: '/', capability: 'web-interface' }
    ];
    
    for (const test of tests) {
      try {
        execSync(`curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:${service.port}${test.path}`, {
          timeout: 1000,
          stdio: ['pipe', 'pipe', 'ignore']
        });
        capabilities.push(test.capability);
      } catch (e) {
        // Not available
      }
    }
  }
  
  return capabilities;
}

/**
 * Analyze a service and extract all metadata
 */
async function analyzeService(service) {
  console.log(`  Analyzing ${service.name}...`);
  
  const analysis = {
    name: service.name,
    port: service.port,
    type: service.type,
    category: service.category,
    status: service.status,
    discoveredVia: service.discoveredVia
  };

  // Analyze package.json if available
  if (service.metadata?.hasPackageJson) {
    const pkg = await analyzePackageJson(service.path || service.metadata?.path);
    if (pkg) {
      analysis.packageJson = pkg;
      analysis.port = analysis.port || pkg.port;
    }
  }

  // Analyze server code
  if (service.path) {
    const serverInfo = await analyzeServerJs(service.path);
    if (serverInfo) {
      analysis.serverInfo = serverInfo;
      analysis.port = analysis.port || serverInfo.port;
    }
  }

  // Analyze README
  if (service.path || service.metadata?.hasReadme) {
    const readme = await analyzeReadme(service.path || path.join('/Users/matthew/.openclaw/workspace/skills', service.name));
    if (readme) {
      analysis.readme = readme;
      analysis.description = readme.description || readme.overview?.split('\n')[0];
    }
  }

  // Check existing skill
  const skillPath = path.join('/Users/matthew/.openclaw/workspace/skills', service.name);
  const skill = await analyzeSkillFile(skillPath);
  analysis.existingSkill = skill;

  // Detect capabilities
  if (service.port) {
    analysis.capabilities = await detectCapabilities(service);
  }

  return analysis;
}

/**
 * Get dependency tree for a service
 */
async function getDependencies(servicePath) {
  const deps = [];
  
  try {
    const pkgPath = path.join(servicePath, 'package.json');
    const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
    
    const allDeps = { ...pkg.dependencies, ...pkg.devDependencies };
    
    for (const [name, version] of Object.entries(allDeps)) {
      deps.push({ name, version });
    }
  } catch (e) {
    // No package.json
  }
  
  return deps;
}

module.exports = {
  analyzeService,
  analyzePackageJson,
  analyzeServerJs,
  analyzeReadme,
  analyzeSkillFile,
  detectCapabilities,
  getDependencies
};
