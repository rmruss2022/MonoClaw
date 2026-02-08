import dotenv from 'dotenv';
dotenv.config();

import { postgresService } from './src/services/postgres.service';

async function setupTestData() {
  console.log('Setting up test data for browser testing...\n');

  const testUserId = 'test-user-123';

  try {
    // Create journal entries
    console.log('Creating journal entries...');

    await postgresService.createJournalEntry({
      userId: testUserId,
      content: 'Today I felt really motivated to work on my personal goals. I spent an hour journaling and planning my week ahead. It felt good to get my thoughts organized.',
      mood: 'motivated',
      tags: ['goals', 'planning', 'motivation'],
      behaviorContext: 'journal-prompt',
    });

    await postgresService.createJournalEntry({
      userId: testUserId,
      content: 'I have been struggling with work-life balance lately. The deadlines at work are overwhelming and I feel like I never have time for myself.',
      mood: 'stressed',
      tags: ['work', 'stress', 'balance'],
      behaviorContext: 'free-form-chat',
    });

    await postgresService.createJournalEntry({
      userId: testUserId,
      content: 'Went for a long walk today and practiced mindfulness. I noticed my breathing, the sounds around me, and just tried to be present. It was really calming.',
      mood: 'peaceful',
      tags: ['mindfulness', 'self-care', 'meditation'],
      behaviorContext: 'guided-exercise',
    });

    await postgresService.createJournalEntry({
      userId: testUserId,
      content: 'I want to establish a consistent morning routine. Wake up at 6am, journal for 15 minutes, exercise for 30 minutes, and have a healthy breakfast.',
      mood: 'determined',
      tags: ['goals', 'routine', 'habits'],
      behaviorContext: 'weekly-planning',
    });

    console.log('✓ Created 4 journal entries');

    // Create user summaries
    console.log('\nCreating user summaries...');

    await postgresService.createUserSummary({
      userId: testUserId,
      summaryType: 'goals',
      summaryText: 'User wants to improve work-life balance, establish a consistent morning routine with journaling and exercise, and develop better stress management habits.',
      confidenceScore: 0.85,
    });

    await postgresService.createUserSummary({
      userId: testUserId,
      summaryType: 'patterns',
      summaryText: 'User tends to journal when feeling stressed or motivated. Shows strong interest in mindfulness and self-care practices. Often seeks structure and planning when feeling overwhelmed.',
      confidenceScore: 0.75,
    });

    await postgresService.createUserSummary({
      userId: testUserId,
      summaryType: 'preferences',
      summaryText: 'Prefers guided exercises and structured activities. Responds well to practical, actionable advice. Values organization and planning.',
      confidenceScore: 0.70,
    });

    console.log('✓ Created 3 user summaries');

    console.log('\n✅ Test data setup complete!');
    console.log('\nYou can now test the chat at http://localhost:8081');
    console.log('\nTry asking:');
    console.log('  - "What have I been journaling about?"');
    console.log('  - "Tell me about my goals"');
    console.log('  - "Have I written about stress?"');
    console.log('  - "What patterns do you notice in my entries?"');

    process.exit(0);
  } catch (error) {
    console.error('❌ Setup failed:', error);
    process.exit(1);
  }
}

setupTestData();
