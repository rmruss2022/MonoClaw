import { NextRequest, NextResponse } from 'next/server';
import { readFile, readdir } from 'fs/promises';
import { join } from 'path';

const WORKSPACE_PATH = '/Users/matthew/.openclaw/workspace';
const MEMORY_PATH = join(WORKSPACE_PATH, 'memory');

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const query = searchParams.get('q');
    
    if (!query || query.length < 2) {
      return NextResponse.json({
        success: false,
        error: 'Query must be at least 2 characters',
      }, { status: 400 });
    }

    const results: any[] = [];

    // Search MEMORY.md
    try {
      const memoryContent = await readFile(join(WORKSPACE_PATH, 'MEMORY.md'), 'utf-8');
      if (memoryContent.toLowerCase().includes(query.toLowerCase())) {
        results.push({
          source: 'memory',
          path: 'MEMORY.md',
          type: 'Long-term Memory',
          snippet: getSnippet(memoryContent, query),
          timestamp: Date.now(),
        });
      }
    } catch (e) {
      // MEMORY.md doesn't exist or can't be read
    }

    // Search daily memory files
    try {
      const memoryFiles = await readdir(MEMORY_PATH);
      const mdFiles = memoryFiles.filter(f => f.endsWith('.md'));
      
      for (const file of mdFiles.slice(0, 10)) { // Last 10 days
        try {
          const content = await readFile(join(MEMORY_PATH, file), 'utf-8');
          if (content.toLowerCase().includes(query.toLowerCase())) {
            results.push({
              source: 'memory',
              path: `memory/${file}`,
              type: 'Daily Memory',
              snippet: getSnippet(content, query),
              timestamp: Date.now(),
            });
          }
        } catch (e) {
          // Skip files that can't be read
        }
      }
    } catch (e) {
      // Memory directory doesn't exist
    }

    // Search workspace docs
    const workspaceDocs = [
      'AGENTS.md',
      'SOUL.md',
      'USER.md',
      'TOOLS.md',
      'IDENTITY.md',
      'HEARTBEAT.md',
    ];

    for (const doc of workspaceDocs) {
      try {
        const content = await readFile(join(WORKSPACE_PATH, doc), 'utf-8');
        if (content.toLowerCase().includes(query.toLowerCase())) {
          results.push({
            source: 'doc',
            path: doc,
            type: 'Workspace Document',
            snippet: getSnippet(content, query),
            timestamp: Date.now(),
          });
        }
      } catch (e) {
        // Document doesn't exist
      }
    }

    return NextResponse.json({
      success: true,
      query,
      results,
      count: results.length,
    });
  } catch (error) {
    console.error('[Search Error]', error);
    return NextResponse.json({
      success: false,
      error: 'Search failed',
    }, { status: 500 });
  }
}

function getSnippet(content: string, query: string, contextLength = 150): string {
  const lowerContent = content.toLowerCase();
  const lowerQuery = query.toLowerCase();
  const index = lowerContent.indexOf(lowerQuery);
  
  if (index === -1) {
    return content.slice(0, contextLength) + '...';
  }
  
  const start = Math.max(0, index - contextLength / 2);
  const end = Math.min(content.length, index + query.length + contextLength / 2);
  
  let snippet = content.slice(start, end);
  if (start > 0) snippet = '...' + snippet;
  if (end < content.length) snippet = snippet + '...';
  
  return snippet;
}
