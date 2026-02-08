import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

// Log a new activity
export const logActivity = mutation({
  args: {
    timestamp: v.number(),
    time: v.string(),
    action: v.string(),
    type: v.string(),
    metadata: v.optional(v.object({
      path: v.optional(v.string()),
      command: v.optional(v.string()),
      status: v.optional(v.string()),
      details: v.optional(v.string()),
    })),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("activities", args);
  },
});

// Get recent activities (default 50)
export const getRecentActivities = query({
  args: {
    limit: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const limit = args.limit ?? 50;
    return await ctx.db
      .query("activities")
      .order("desc")
      .take(limit);
  },
});

// Get activities by type
export const getActivitiesByType = query({
  args: {
    type: v.string(),
    limit: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const limit = args.limit ?? 50;
    const activities = await ctx.db
      .query("activities")
      .order("desc")
      .collect();
    
    return activities
      .filter(a => a.type === args.type)
      .slice(0, limit);
  },
});

// Get activities in date range
export const getActivitiesInRange = query({
  args: {
    startMs: v.number(),
    endMs: v.number(),
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("activities")
      .withIndex("by_timestamp", (q) =>
        q.gte("timestamp", args.startMs).lte("timestamp", args.endMs)
      )
      .order("desc")
      .collect();
  },
});

// Clear old activities (keep last N days)
export const cleanupOldActivities = mutation({
  args: {
    daysToKeep: v.number(),
  },
  handler: async (ctx, args) => {
    const cutoffMs = Date.now() - (args.daysToKeep * 24 * 60 * 60 * 1000);
    const oldActivities = await ctx.db
      .query("activities")
      .withIndex("by_timestamp", (q) => q.lt("timestamp", cutoffMs))
      .collect();
    
    for (const activity of oldActivities) {
      await ctx.db.delete(activity._id);
    }
    
    return { deleted: oldActivities.length };
  },
});
