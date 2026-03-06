import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

// Sync cron jobs from OpenClaw
export const syncCronJobs = mutation({
  args: {
    jobs: v.array(v.object({
      jobId: v.string(),
      name: v.optional(v.string()),
      schedule: v.object({
        kind: v.string(),
        expr: v.optional(v.string()),
        everyMs: v.optional(v.number()),
        atMs: v.optional(v.number()),
        tz: v.optional(v.string()),
      }),
      enabled: v.boolean(),
      lastRun: v.optional(v.number()),
      nextRun: v.optional(v.number()),
      status: v.string(),
    })),
  },
  handler: async (ctx, args) => {
    // Clear existing jobs
    const existingJobs = await ctx.db.query("cronJobs").collect();
    for (const job of existingJobs) {
      await ctx.db.delete(job._id);
    }
    
    // Insert new jobs
    for (const job of args.jobs) {
      await ctx.db.insert("cronJobs", job);
    }
    
    return { synced: args.jobs.length };
  },
});

// Get all cron jobs
export const getAllCronJobs = query({
  handler: async (ctx) => {
    return await ctx.db.query("cronJobs").collect();
  },
});

// Get jobs by status
export const getCronJobsByStatus = query({
  args: {
    status: v.string(),
  },
  handler: async (ctx, args) => {
    const jobs = await ctx.db.query("cronJobs").collect();
    return jobs.filter(j => j.status === args.status);
  },
});

// Update job status
export const updateJobStatus = mutation({
  args: {
    jobId: v.string(),
    status: v.string(),
    lastRun: v.optional(v.number()),
    nextRun: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const job = await ctx.db
      .query("cronJobs")
      .withIndex("by_jobId", (q) => q.eq("jobId", args.jobId))
      .first();
    
    if (!job) {
      throw new Error(`Job ${args.jobId} not found`);
    }
    
    await ctx.db.patch(job._id, {
      status: args.status,
      lastRun: args.lastRun,
      nextRun: args.nextRun,
    });
    
    return job._id;
  },
});
