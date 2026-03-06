import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  activities: defineTable({
    timestamp: v.number(),
    time: v.string(), // Human-readable time (HH:MM)
    action: v.string(),
    type: v.string(), // file, command, build, system, cron, message
    metadata: v.optional(v.object({
      path: v.optional(v.string()),
      command: v.optional(v.string()),
      status: v.optional(v.string()),
      details: v.optional(v.string()),
    })),
  }).index("by_timestamp", ["timestamp"]),

  cronJobs: defineTable({
    jobId: v.string(),
    name: v.optional(v.string()),
    schedule: v.object({
      kind: v.string(), // "at", "every", "cron"
      expr: v.optional(v.string()),
      everyMs: v.optional(v.number()),
      atMs: v.optional(v.number()),
      tz: v.optional(v.string()),
    }),
    enabled: v.boolean(),
    lastRun: v.optional(v.number()),
    nextRun: v.optional(v.number()),
    status: v.string(), // "scheduled", "active", "failed"
  }).index("by_jobId", ["jobId"]),

  searchIndex: defineTable({
    source: v.string(), // "memory", "activity", "cron", "doc"
    path: v.optional(v.string()),
    content: v.string(),
    timestamp: v.number(),
    type: v.string(),
  })
    .index("by_source", ["source"])
    .index("by_timestamp", ["timestamp"])
    .searchIndex("search_content", {
      searchField: "content",
      filterFields: ["source", "type"],
    }),
});
