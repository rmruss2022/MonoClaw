import { postgresService } from './postgres.service';
import { activitiesService } from './activities.service';

// Tool definitions for Claude with proper typing
export const aiTools = [
  {
    name: 'get_user_summaries',
    description: `Get summaries about the user to understand their personality, goals, patterns, and preferences.
This provides context about who the user is and what they're working on.
Summary types: 'personality', 'goals', 'patterns', 'preferences'`,
    input_schema: {
      type: 'object' as const,
      properties: {
        summary_type: {
          type: 'string' as const,
          description:
            "Optional: Filter by summary type ('personality', 'goals', 'patterns', 'preferences')",
        },
      },
    },
  },
  {
    name: 'get_recent_journal_entries',
    description: `Get the user's recent journal entries to understand their recent thoughts, experiences, and emotional state.
Use this to provide personalized responses based on what they've been journaling about.`,
    input_schema: {
      type: 'object' as const,
      properties: {
        limit: {
          type: 'number' as const,
          description: 'Number of entries to retrieve (default: 5, max: 20)',
        },
      },
    },
  },
  {
    name: 'search_journal_entries',
    description: `Search through the user's journal entries for specific topics or keywords.
Use this to find relevant past entries when the user asks about their history or patterns.`,
    input_schema: {
      type: 'object' as const,
      properties: {
        query: {
          type: 'string' as const,
          description: 'Search query (keywords or phrases to find)',
        },
        limit: {
          type: 'number' as const,
          description: 'Maximum number of results (default: 10)',
        },
      },
      required: ['query'],
    },
  },
  {
    name: 'get_conversation_history',
    description: `Get recent conversation history to understand the context of the current discussion.
Use this sparingly as recent context is usually provided automatically.`,
    input_schema: {
      type: 'object' as const,
      properties: {
        limit: {
          type: 'number' as const,
          description: 'Number of messages to retrieve (default: 20)',
        },
      },
    },
  },
  {
    name: 'save_user_insight',
    description: `Save a new insight or summary about the user based on the conversation.
Use this to remember important details about the user's personality, goals, patterns, or preferences.`,
    input_schema: {
      type: 'object' as const,
      properties: {
        summary_type: {
          type: 'string' as const,
          enum: ['personality', 'goals', 'patterns', 'preferences'] as const,
          description: 'Type of summary to save',
        },
        summary_text: {
          type: 'string' as const,
          description: 'The insight or summary to save',
        },
        confidence: {
          type: 'number' as const,
          description: 'Confidence level (0.0-1.0)',
        },
      },
      required: ['summary_type', 'summary_text'],
    },
  },
  {
    name: 'get_available_activities',
    description: `Get ALL available activities, exercises, and practices the user can do.
This is your COMPLETE INDEX of everything available to the user. Use this whenever user asks:
- "What can I do?"
- "What exercises are available?"
- "Help me with [stress/anxiety/planning/etc]"
- Or shows signs of needing support

Categories returned:
- 'meditation': Guided audio practices (3-15 min) - breathwork, sleep, anxiety relief, loving-kindness
- 'conversation': Talk through challenges with AI (10-25 min) - emotion processing, boundaries, self-compassion, cognitive reframing
- 'planning': Set intentions and goals (15-20 min) - weekly planning, goal setting
- 'reflection': Process patterns (10-25 min) - weekly review, gratitude, values clarification, inner child work
- 'quick-practice': Fast exercises (5 min) - energy check-ins

Each activity includes: name, category, duration, description, whenToUse, and triggers.
Use this to recommend specific activities based on user's current state and needs.`,
    input_schema: {
      type: 'object' as const,
      properties: {
        category: {
          type: 'string' as const,
          enum: ['meditation', 'conversation', 'planning', 'reflection', 'quick-practice'] as const,
          description: 'Optional: Filter by category',
        },
      },
    },
  },
  {
    name: 'search_activities',
    description: `Search activities by keywords or emotional state (e.g., "stress", "sleep", "boundaries", "plan").
Use this when user describes how they're feeling or what they need help with.
Returns matching activities with suggestions.`,
    input_schema: {
      type: 'object' as const,
      properties: {
        query: {
          type: 'string' as const,
          description: 'Search query (emotional state, need, or topic)',
        },
      },
      required: ['query'],
    },
  },
];

// Tool execution handlers
export class AIToolsService {
  async executeTool(
    toolName: string,
    toolInput: any,
    userId: string
  ): Promise<any> {
    switch (toolName) {
      case 'get_user_summaries':
        return this.getUserSummaries(userId, toolInput.summary_type);

      case 'get_recent_journal_entries':
        return this.getRecentJournalEntries(
          userId,
          toolInput.limit || 5
        );

      case 'search_journal_entries':
        return this.searchJournalEntries(
          userId,
          toolInput.query,
          toolInput.limit || 10
        );

      case 'get_conversation_history':
        return this.getConversationHistory(userId, toolInput.limit || 20);

      case 'save_user_insight':
        return this.saveUserInsight(
          userId,
          toolInput.summary_type,
          toolInput.summary_text,
          toolInput.confidence || 0.7
        );

      case 'get_available_activities':
        return this.getAvailableActivities(toolInput.category);

      case 'search_activities':
        return this.searchActivities(toolInput.query);

      default:
        throw new Error(`Unknown tool: ${toolName}`);
    }
  }

  private async getUserSummaries(
    userId: string,
    summaryType?: string
  ): Promise<any> {
    const summaries = await postgresService.getUserSummaries(
      userId,
      summaryType
    );

    if (summaries.length === 0) {
      return {
        found: false,
        message: 'No summaries found for this user yet.',
      };
    }

    return {
      found: true,
      summaries: summaries.map((s) => ({
        type: s.summary_type,
        content: s.summary_text,
        confidence: s.confidence_score,
        last_updated: s.updated_at,
      })),
    };
  }

  private async getRecentJournalEntries(
    userId: string,
    limit: number
  ): Promise<any> {
    const entries = await postgresService.getJournalEntries(
      userId,
      Math.min(limit, 20)
    );

    if (entries.length === 0) {
      return {
        found: false,
        message: 'No journal entries found for this user yet.',
      };
    }

    return {
      found: true,
      entries: entries.map((e) => ({
        id: e.id,
        content: e.content,
        mood: e.mood,
        tags: e.tags,
        created_at: e.created_at,
        behavior_context: e.behavior_context,
      })),
    };
  }

  private async searchJournalEntries(
    userId: string,
    query: string,
    limit: number
  ): Promise<any> {
    const entries = await postgresService.searchJournalEntries(
      userId,
      query,
      Math.min(limit, 20)
    );

    if (entries.length === 0) {
      return {
        found: false,
        message: `No journal entries found matching "${query}".`,
      };
    }

    return {
      found: true,
      query: query,
      entries: entries.map((e) => ({
        id: e.id,
        content: e.content,
        mood: e.mood,
        created_at: e.created_at,
      })),
    };
  }

  private async getConversationHistory(
    userId: string,
    limit: number
  ): Promise<any> {
    const messages = await postgresService.getChatHistory(
      userId,
      Math.min(limit, 50)
    );

    return {
      found: true,
      messages: messages.map((m) => ({
        role: m.role,
        content: m.content,
        behavior_id: m.behavior_id,
        created_at: m.created_at,
      })),
    };
  }

  private async saveUserInsight(
    userId: string,
    summaryType: string,
    summaryText: string,
    confidence: number
  ): Promise<any> {
    // Check if summary already exists
    const existing = await postgresService.getUserSummaries(
      userId,
      summaryType
    );

    if (existing.length > 0) {
      // Update existing
      await postgresService.updateUserSummary(
        userId,
        summaryType,
        summaryText,
        confidence
      );
      return {
        success: true,
        action: 'updated',
        message: `Updated ${summaryType} summary`,
      };
    } else {
      // Create new
      await postgresService.createUserSummary({
        userId,
        summaryType,
        summaryText,
        confidenceScore: confidence,
      });
      return {
        success: true,
        action: 'created',
        message: `Created new ${summaryType} summary`,
      };
    }
  }

  private async getAvailableActivities(category?: string): Promise<any> {
    try {
      const result = await activitiesService.getAllActivities(category);
      return result;
    } catch (error: any) {
      return {
        found: false,
        error: error.message,
      };
    }
  }

  private async searchActivities(query: string): Promise<any> {
    try {
      const result = await activitiesService.searchActivities(query);
      return result;
    } catch (error: any) {
      return {
        found: false,
        error: error.message,
      };
    }
  }
}

export const aiToolsService = new AIToolsService();
