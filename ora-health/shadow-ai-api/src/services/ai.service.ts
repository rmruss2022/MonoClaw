import { getAnthropicClient, ANTHROPIC_CONFIG } from '../config/anthropic';
import { postgresService } from './postgres.service';
import { aiTools, aiToolsService } from './ai-tools.service';
import { behaviorDetectionService } from './behavior-detection.service';

export class AIService {
  private shouldUseMock(): boolean {
    return (
      !process.env.ANTHROPIC_API_KEY ||
      process.env.ANTHROPIC_API_KEY === 'your_anthropic_api_key_here'
    );
  }

  async sendMessage(
    userId: string,
    message: string,
    behaviorId: string // This parameter is now ignored - we detect dynamically
  ): Promise<{
    content: string;
    role: string;
    toolsUsed?: string[];
    activeBehavior?: string;
  }> {
    // Use mock responses if Anthropic key not configured
    if (this.shouldUseMock()) {
      console.log('Using mock AI responses');
      return this.getMockResponse(message, behaviorId);
    }

    console.log('Using real Claude API with dynamic behaviors');

    try {
      // Get chat history from Postgres
      const history = await postgresService.getChatHistory(userId, 10);

      // Detect appropriate behavior based on user message and context
      const behaviorDetection = await behaviorDetectionService.detectBehavior(
        message,
        userId,
        history
      );

      const activeBehavior = behaviorDetection.behavior;
      console.log(`🎯 Activated behavior: ${activeBehavior.name}`);
      console.log(
        `   Confidence: ${behaviorDetection.confidence.toFixed(2)}, Triggers: ${behaviorDetection.matchedTriggers.join(', ')}`
      );

      // Build messages array for Claude
      const messages: any[] = [
        ...history.map((msg) => ({
          role: msg.role === 'assistant' ? 'assistant' : 'user',
          content: msg.content,
        })),
        {
          role: 'user',
          content: message,
        },
      ];

      // Call Claude API with tools and dynamic behavior system prompt
      let completion = await getAnthropicClient().messages.create({
        model: ANTHROPIC_CONFIG.model,
        max_tokens: ANTHROPIC_CONFIG.maxTokens,
        system: activeBehavior.instructions.systemPrompt,
        messages,
        tools: aiTools,
      });

      const toolsUsed: string[] = [];

      // Handle tool use responses (Claude may use multiple tools)
      while (completion.stop_reason === 'tool_use') {
        // Find all tool use blocks in the response
        const toolUses = completion.content.filter(
          (block: any) => block.type === 'tool_use'
        );

        // Execute all tools
        const toolResults = await Promise.all(
          toolUses.map(async (toolUse: any) => {
            console.log(`Executing tool: ${toolUse.name}`, toolUse.input);
            toolsUsed.push(toolUse.name);

            try {
              const result = await aiToolsService.executeTool(
                toolUse.name,
                toolUse.input,
                userId
              );

              return {
                type: 'tool_result',
                tool_use_id: toolUse.id,
                content: JSON.stringify(result),
              };
            } catch (error: any) {
              return {
                type: 'tool_result',
                tool_use_id: toolUse.id,
                content: JSON.stringify({ error: error.message }),
                is_error: true,
              };
            }
          })
        );

        // Continue conversation with tool results
        messages.push({
          role: 'assistant',
          content: completion.content,
        });

        messages.push({
          role: 'user',
          content: toolResults,
        });

        // Get next response from Claude with tool results
        completion = await getAnthropicClient().messages.create({
          model: ANTHROPIC_CONFIG.model,
          max_tokens: ANTHROPIC_CONFIG.maxTokens,
          system: this.getBehaviorPrompt(behaviorId),
          messages,
          tools: aiTools,
        });
      }

      // Extract final text response
      const textBlocks = completion.content.filter(
        (block: any) => block.type === 'text'
      );
      const assistantMessage =
        textBlocks.length > 0 && 'text' in textBlocks[0] ? textBlocks[0].text : '';

      // Save both messages to Postgres
      await postgresService.saveChatMessage({
        userId,
        role: 'user',
        content: message,
        behaviorId: activeBehavior.id,
      });

      await postgresService.saveChatMessage({
        userId,
        role: 'assistant',
        content: assistantMessage,
        behaviorId: activeBehavior.id,
        metadata: {
          tokens:
            completion.usage.input_tokens + completion.usage.output_tokens,
          model: completion.model,
          toolsUsed: toolsUsed.length > 0 ? toolsUsed : undefined,
          behaviorName: activeBehavior.name,
          behaviorConfidence: behaviorDetection.confidence,
          matchedTriggers: behaviorDetection.matchedTriggers,
        },
      });

      return {
        content: assistantMessage,
        role: 'assistant',
        toolsUsed: toolsUsed.length > 0 ? toolsUsed : undefined,
        activeBehavior: activeBehavior.name,
      };
    } catch (error) {
      console.error('AI Service Error:', error);
      throw new Error('Failed to process message');
    }
  }

  private getMockResponse(
    message: string,
    behaviorId: string
  ): { content: string; role: string } {
    const responses: Record<string, string[]> = {
      'free-form-chat': [
        'I hear you. Tell me more about that. What thoughts or feelings are coming up for you?',
        "That's interesting. How does that make you feel?",
        'I appreciate you sharing that with me. What would you like to explore further?',
        "Thank you for opening up. What's been on your mind lately?",
      ],
      'journal-prompt': [
        "Let's start journaling. What was the most significant moment of your day?",
        'What are you grateful for right now?',
        "Describe how you're feeling in this moment.",
      ],
    };

    const behaviorResponses =
      responses[behaviorId] || responses['free-form-chat'];
    const randomResponse =
      behaviorResponses[Math.floor(Math.random() * behaviorResponses.length)];

    return {
      content: randomResponse,
      role: 'assistant',
    };
  }

  private getBehaviorPrompt(behaviorId: string): string {
    const prompts: Record<string, string> = {
      'journal-prompt': `You are a supportive journaling companion. Help users reflect on their thoughts and feelings through thoughtful questions and gentle guidance. Encourage deeper exploration of their experiences.

You have access to tools to get context about the user and their journal history. Use these tools when relevant to provide personalized support.`,

      'free-form-chat': `You are a compassionate listener and mental wellness companion. Provide a safe space for users to express themselves. Listen actively, validate emotions, and offer gentle insights when appropriate.

You have access to tools to understand the user better. Use them when helpful to provide more personalized support.`,

      'progress-analysis': `You are an insightful analyst helping users understand their personal growth journey. Review their journal entries and provide meaningful observations about patterns, progress, and areas for continued focus.

Use the available tools to access the user's journal history and summaries to provide detailed insights.`,

      'weekly-planning': `You are a thoughtful planning assistant. Help users set intentions for their week, break down goals into manageable steps, and plan for self-care activities.

You can access the user's goals and preferences to help create personalized plans.`,

      'guided-exercise': `You are a skilled guide for personal growth exercises. Lead users through structured activities like gratitude practice, cognitive reframing, or values clarification with clear instructions and supportive feedback.

You can access user context to make exercises more relevant to their situation.`,
    };

    return prompts[behaviorId] || prompts['free-form-chat'];
  }
}

export const aiService = new AIService();
