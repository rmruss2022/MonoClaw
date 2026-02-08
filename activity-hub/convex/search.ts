import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

// Index content for search
export const indexContent = mutation({
  args: {
    source: v.string(),
    path: v.optional(v.string()),
    content: v.string(),
    type: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("searchIndex", {
      ...args,
      timestamp: Date.now(),
    });
  },
});

// Search across all indexed content
export const searchWorkspace = query({
  args: {
    query: v.string(),
    source: v.optional(v.string()),
    limit: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const limit = args.limit ?? 20;
    
    // Use Convex search
    let results = await ctx.db
      .query("searchIndex")
      .withSearchIndex("search_content", (q) => {
        let search = q.search("content", args.query);
        if (args.source) {
          search = search.eq("source", args.source);
        }
        return search;
      })
      .take(limit);
    
    return results.map(r => ({
      ...r,
      snippet: getSnippet(r.content, args.query),
    }));
  },
});

// Get snippet with highlighted query
function getSnippet(content: string, query: string, contextLength = 150): string {
  const lowerContent = content.toLowerCase();
  const lowerQuery = query.toLowerCase();
  const index = lowerContent.indexOf(lowerQuery);
  
  if (index === -1) {
    return content.slice(0, contextLength) + "...";
  }
  
  const start = Math.max(0, index - contextLength / 2);
  const end = Math.min(content.length, index + lowerQuery.length + contextLength / 2);
  
  let snippet = content.slice(start, end);
  if (start > 0) snippet = "..." + snippet;
  if (end < content.length) snippet = snippet + "...";
  
  return snippet;
}

// Rebuild search index from workspace files
export const rebuildSearchIndex = mutation({
  handler: async (ctx) => {
    // Clear existing index
    const existing = await ctx.db.query("searchIndex").collect();
    for (const item of existing) {
      await ctx.db.delete(item._id);
    }
    
    // Return count
    return { cleared: existing.length };
  },
});

// Get recent search index entries
export const getRecentIndexEntries = query({
  args: {
    limit: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const limit = args.limit ?? 20;
    return await ctx.db
      .query("searchIndex")
      .order("desc")
      .take(limit);
  },
});
