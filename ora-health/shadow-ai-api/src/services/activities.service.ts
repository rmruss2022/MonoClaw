import { MeditationService } from './meditation.service';
import { BEHAVIORS } from '../config/behaviors';

const meditationService = new MeditationService();

export interface Activity {
  id: string;
  name: string;
  category: 'meditation' | 'conversation' | 'planning' | 'reflection' | 'quick-practice';
  duration: string; // "5-10 min" or "Conversational" or "15-20 min"
  description: string;
  whenToUse: string;
  icon?: string;
  priority?: number;
  triggers?: string[]; // Keywords that might indicate this activity is helpful
}

export class ActivitiesService {
  /**
   * Get all available activities the user can do
   */
  async getAllActivities(category?: string): Promise<{
    found: boolean;
    activities: Activity[];
    categories: Record<string, string>;
  }> {
    const activities: Activity[] = [];

    // 1. Add guided meditations
    try {
      const meditations = await meditationService.getAllMeditations();
      meditations.forEach((m) => {
        activities.push({
          id: `meditation-${m.id}`,
          name: m.title,
          category: 'meditation',
          duration: `${m.duration} min`,
          description: m.description,
          whenToUse: this.getMeditationWhenToUse(m.category),
          icon: m.icon,
        });
      });
    } catch (error) {
      console.error('Error loading meditations:', error);
    }

    // 2. Add conversational exercises from behaviors
    const conversationalActivities: Activity[] = [
      {
        id: 'difficult-emotion-processing',
        name: 'Difficult Emotion Processing',
        category: 'conversation',
        duration: 'Conversational',
        description: 'Process and validate difficult emotions with trauma-informed support',
        whenToUse: 'When feeling overwhelmed, anxious, distressed, or experiencing intense emotions',
        triggers: ['stressed', 'anxious', 'overwhelmed', 'struggling', 'distressed'],
        priority: 10,
      },
      {
        id: 'self-compassion-exercise',
        name: 'Self-Compassion Practice',
        category: 'conversation',
        duration: '10-15 min',
        description: 'Soften harsh self-criticism with Dr. Kristin Neff\'s self-compassion framework',
        whenToUse: 'When being hard on yourself, feeling like a failure, or engaging in negative self-talk',
        triggers: ['failure', 'worthless', 'hate myself', 'not good enough'],
        priority: 9,
      },
      {
        id: 'inner-child-work',
        name: 'Inner Child Healing',
        category: 'reflection',
        duration: '15-25 min',
        description: 'Gentle exploration and reparenting of wounded inner child',
        whenToUse: 'When processing childhood wounds, feeling triggered by old patterns, or wanting deep healing',
        triggers: ['childhood', 'parents', 'always felt', 'since I was young'],
        priority: 9,
      },
      {
        id: 'boundary-setting',
        name: 'Boundary Work',
        category: 'conversation',
        duration: '15-20 min',
        description: 'Identify needs and practice setting healthy boundaries with specific scripts',
        whenToUse: 'When feeling taken advantage of, having trouble saying no, or needing to protect your energy',
        triggers: ['say no', 'people-pleasing', 'taken advantage', 'boundaries'],
        priority: 8,
      },
      {
        id: 'cognitive-reframing',
        name: 'Cognitive Reframing',
        category: 'conversation',
        duration: '10-15 min',
        description: 'Challenge distorted thinking patterns through Socratic questioning',
        whenToUse: 'When stuck in negative thought loops, catastrophizing, or thinking in extremes',
        triggers: ['always', 'never', 'worst case', 'catastrophe', 'should'],
        priority: 8,
      },
    ];

    // 3. Add planning & reflection activities
    const planningActivities: Activity[] = [
      {
        id: 'weekly-planning',
        name: 'Weekly Planning',
        category: 'planning',
        duration: '15-20 min',
        description: 'Set 3-5 energizing intentions for the week with energy management',
        whenToUse: 'Start of week, feeling scattered, or wanting to focus your energy',
        triggers: ['plan week', 'upcoming week', 'this week', 'what should i focus on'],
        priority: 7,
      },
      {
        id: 'weekly-review',
        name: 'Weekly Review',
        category: 'reflection',
        duration: '15-20 min',
        description: 'Reflect on patterns, celebrate wins, and learn from your week',
        whenToUse: 'End of week, wanting to understand patterns, or celebrate progress',
        triggers: ['reflect', 'this week was', 'looking back', 'review'],
        priority: 7,
      },
      {
        id: 'goal-setting',
        name: 'Goal Setting & Tracking',
        category: 'planning',
        duration: '15-20 min',
        description: 'Set SMART goals with concrete action steps and obstacle planning',
        whenToUse: 'When wanting to achieve something specific or make a change',
        triggers: ['goal', 'want to achieve', 'working toward', 'make progress'],
        priority: 6,
      },
      {
        id: 'gratitude-practice',
        name: 'Gratitude Practice',
        category: 'reflection',
        duration: '10-15 min',
        description: 'Deep, specific gratitude exploration (quality over quantity)',
        whenToUse: 'When wanting perspective, feeling down, or cultivating positivity',
        triggers: ['grateful', 'thankful', 'appreciate', 'good things'],
        priority: 6,
      },
      {
        id: 'values-clarification',
        name: 'Values Clarification',
        category: 'reflection',
        duration: '15-20 min',
        description: 'Explore and clarify your core values and how they show up in life',
        whenToUse: 'When feeling disconnected, making decisions, or seeking direction',
        triggers: ['values', 'what matters', 'important to me', 'purpose'],
        priority: 6,
      },
    ];

    // 4. Add quick practices
    const quickPractices: Activity[] = [
      {
        id: 'energy-checkin',
        name: 'Energy & Mood Check-in',
        category: 'quick-practice',
        duration: '5 min',
        description: 'Quick assessment of physical and emotional state with practical next step',
        whenToUse: 'Anytime - quick grounding and assessment',
        triggers: ['how am i', 'tired', 'energy', 'mood'],
        priority: 5,
      },
    ];

    // Combine all activities
    activities.push(...conversationalActivities);
    activities.push(...planningActivities);
    activities.push(...quickPractices);

    // Filter by category if specified
    let filteredActivities = activities;
    if (category) {
      filteredActivities = activities.filter((a) => a.category === category);
    }

    // Sort by priority (if available) and then by name
    filteredActivities.sort((a, b) => {
      if (a.priority && b.priority) {
        return b.priority - a.priority;
      }
      return a.name.localeCompare(b.name);
    });

    return {
      found: filteredActivities.length > 0,
      activities: filteredActivities,
      categories: {
        meditation: 'Guided audio practices (3-15 min)',
        conversation: 'Talk through challenges with AI support (10-25 min)',
        planning: 'Set intentions and goals (15-20 min)',
        reflection: 'Process and understand patterns (10-25 min)',
        'quick-practice': 'Fast check-ins and exercises (5 min)',
      },
    };
  }

  /**
   * Search activities by keywords or emotional state
   */
  async searchActivities(query: string): Promise<{
    found: boolean;
    query: string;
    matches: Activity[];
    suggestions: string[];
  }> {
    const allActivities = await this.getAllActivities();
    const queryLower = query.toLowerCase();

    // Search in name, description, whenToUse, and triggers
    const matches = allActivities.activities.filter((activity) => {
      const searchText = [
        activity.name,
        activity.description,
        activity.whenToUse,
        ...(activity.triggers || []),
      ]
        .join(' ')
        .toLowerCase();

      return searchText.includes(queryLower);
    });

    // Generate suggestions based on common queries
    const suggestions = this.generateSuggestions(queryLower);

    return {
      found: matches.length > 0,
      query,
      matches,
      suggestions,
    };
  }

  private getMeditationWhenToUse(category: string): string {
    const whenToUseMap: Record<string, string> = {
      breathwork: 'When needing to center, ground, or reset your state',
      sleep: 'Before bed or when having trouble sleeping',
      'loving-kindness': 'When being hard on yourself or wanting to cultivate compassion',
      anxiety: 'When feeling anxious, overwhelmed, or stressed',
    };
    return whenToUseMap[category] || 'For general mindfulness and presence';
  }

  private generateSuggestions(query: string): string[] {
    const suggestionMap: Record<string, string[]> = {
      stress: ['Anxiety Relief meditation', 'Difficult Emotion Processing', 'Quick Reset meditation'],
      anxious: ['Anxiety Relief meditation', 'Cognitive Reframing', 'Breath Awareness meditation'],
      sleep: ['Body Scan for Sleep meditation', 'Evening Wind Down meditation'],
      tired: ['Energy Check-in', 'Quick Reset meditation', 'Morning Presence meditation'],
      plan: ['Weekly Planning', 'Goal Setting & Tracking'],
      reflect: ['Weekly Review', 'Gratitude Practice', 'Values Clarification'],
      boundaries: ['Boundary Work', 'Self-Compassion Practice'],
      'self-critical': ['Self-Compassion Practice', 'Cognitive Reframing'],
    };

    for (const [key, suggestions] of Object.entries(suggestionMap)) {
      if (query.includes(key)) {
        return suggestions;
      }
    }

    return ['Try: "stress", "plan", "reflect", "boundaries", or "sleep"'];
  }
}

export const activitiesService = new ActivitiesService();
