import { BEHAVIORS, Behavior } from '../config/behaviors';
import { postgresService } from './postgres.service';

interface BehaviorDetectionResult {
  behavior: Behavior;
  confidence: number;
  matchedTriggers: string[];
}

export class BehaviorDetectionService {
  /**
   * Detect the most appropriate behavior for the given message
   * Returns the highest priority behavior that matches, or free-form-chat as fallback
   */
  async detectBehavior(
    message: string,
    userId: string,
    conversationHistory?: any[]
  ): Promise<BehaviorDetectionResult> {
    const lowercaseMessage = message.toLowerCase();
    const detectionResults: BehaviorDetectionResult[] = [];

    // Check each behavior for matches
    for (const behavior of BEHAVIORS) {
      const result = this.checkBehaviorMatch(
        behavior,
        lowercaseMessage,
        conversationHistory
      );

      if (result.confidence > 0) {
        detectionResults.push(result);
      }
    }

    // Sort by priority (higher first), then by confidence
    detectionResults.sort((a, b) => {
      if (a.behavior.priority !== b.behavior.priority) {
        return b.behavior.priority - a.behavior.priority;
      }
      return b.confidence - a.confidence;
    });

    // Return highest priority match, or free-form-chat as fallback
    const selectedBehavior =
      detectionResults.length > 0
        ? detectionResults[0]
        : {
            behavior: BEHAVIORS.find((b) => b.id === 'free-form-chat')!,
            confidence: 1.0,
            matchedTriggers: ['default'],
          };

    // Log behavior transition
    await this.logBehaviorTransition(userId, selectedBehavior, message);

    return selectedBehavior;
  }

  /**
   * Check if a behavior matches the given message
   */
  private checkBehaviorMatch(
    behavior: Behavior,
    lowercaseMessage: string,
    conversationHistory?: any[]
  ): BehaviorDetectionResult {
    const matchedTriggers: string[] = [];
    let confidence = 0;

    // Check keywords
    for (const keyword of behavior.triggers.keywords) {
      if (lowercaseMessage.includes(keyword.toLowerCase())) {
        matchedTriggers.push(`keyword:${keyword}`);
        confidence += 1;
      }
    }

    // Check regex patterns
    if (behavior.triggers.patterns) {
      for (const pattern of behavior.triggers.patterns) {
        if (pattern.test(lowercaseMessage)) {
          matchedTriggers.push(`pattern:${pattern.source}`);
          confidence += 2; // Patterns are more specific, higher weight
        }
      }
    }

    // Check context hints (day of week, time context)
    if (behavior.triggers.contextHints) {
      const currentDay = new Date()
        .toLocaleDateString('en-US', { weekday: 'long' })
        .toLowerCase();

      for (const hint of behavior.triggers.contextHints) {
        if (
          lowercaseMessage.includes(hint.toLowerCase()) ||
          currentDay === hint.toLowerCase()
        ) {
          matchedTriggers.push(`context:${hint}`);
          confidence += 0.5;
        }
      }
    }

    // Normalize confidence (0-1 scale, capped at 1)
    const normalizedConfidence = Math.min(confidence / 5, 1);

    return {
      behavior,
      confidence: normalizedConfidence,
      matchedTriggers,
    };
  }

  /**
   * Log behavior transition to database for analytics and learning
   */
  private async logBehaviorTransition(
    userId: string,
    detection: BehaviorDetectionResult,
    userMessage: string
  ): Promise<void> {
    try {
      await postgresService.recordBehaviorTransition({
        userId,
        fromBehavior: undefined, // We'll track this in a more sophisticated way later
        toBehavior: detection.behavior.id,
        triggerReason: 'keyword_detection',
        confidenceScore: detection.confidence,
        context: {
          matchedTriggers: detection.matchedTriggers,
          messageExcerpt: userMessage.substring(0, 100),
          behaviorName: detection.behavior.name,
          timestamp: new Date().toISOString(),
        },
      });
    } catch (error) {
      console.error('Failed to log behavior transition:', error);
      // Don't throw - logging failure shouldn't break the conversation
    }
  }

  /**
   * Get the current active behavior for a user based on recent transitions
   * This will be useful when we add behavior persistence/decay
   */
  async getCurrentBehavior(userId: string): Promise<Behavior> {
    try {
      const recentTransitions = await postgresService.getBehaviorTransitions(
        userId,
        1
      );

      if (recentTransitions.length > 0) {
        const lastBehaviorId = recentTransitions[0].to_behavior;
        const behavior = BEHAVIORS.find((b) => b.id === lastBehaviorId);
        if (behavior) {
          return behavior;
        }
      }
    } catch (error) {
      console.error('Failed to get current behavior:', error);
    }

    // Fallback to free-form-chat
    return BEHAVIORS.find((b) => b.id === 'free-form-chat')!;
  }

  /**
   * Get all available behaviors
   */
  getAllBehaviors(): Behavior[] {
    return BEHAVIORS;
  }

  /**
   * Get a specific behavior by ID
   */
  getBehaviorById(behaviorId: string): Behavior | undefined {
    return BEHAVIORS.find((b) => b.id === behaviorId);
  }
}

export const behaviorDetectionService = new BehaviorDetectionService();
