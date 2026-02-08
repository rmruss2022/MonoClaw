import dotenv from 'dotenv';
dotenv.config();

import { aiService } from './src/services/ai.service';
import { postgresService } from './src/services/postgres.service';

async function testAITools() {
  console.log('Testing AI Tools Integration...\n');

  const testUserId = 'test-user-123';

  try {
    // Setup: Create some test data
    console.log('Setting up test data...');

    // Create a journal entry
    await postgresService.createJournalEntry({
      userId: testUserId,
      content:
        'I have been feeling stressed about work lately. The deadlines are piling up and I feel overwhelmed.',
      mood: 'anxious',
      tags: ['work', 'stress'],
      behaviorContext: 'journal-prompt',
    });

    // Create another journal entry
    await postgresService.createJournalEntry({
      userId: testUserId,
      content:
        'Today I took a break and went for a walk. It really helped clear my mind.',
      mood: 'calm',
      tags: ['self-care', 'mindfulness'],
      behaviorContext: 'journal-prompt',
    });

    console.log('✓ Test data created\n');

    // Test 1: Ask Claude about recent journal entries
    console.log('Test 1: Asking Claude about recent journal entries...');
    console.log('User message: "What have I been journaling about recently?"\n');

    const response1 = await aiService.sendMessage(
      testUserId,
      'What have I been journaling about recently?',
      'progress-analysis'
    );

    console.log('Claude response:', response1.content);
    if (response1.toolsUsed) {
      console.log('Tools used:', response1.toolsUsed.join(', '));
    }
    console.log();

    // Test 2: Ask Claude to search for specific topics
    console.log('\nTest 2: Asking Claude to search journal entries...');
    console.log('User message: "Have I written anything about stress?"\n');

    const response2 = await aiService.sendMessage(
      testUserId,
      'Have I written anything about stress?',
      'progress-analysis'
    );

    console.log('Claude response:', response2.content);
    if (response2.toolsUsed) {
      console.log('Tools used:', response2.toolsUsed.join(', '));
    }

    console.log('\n✅ AI Tools integration test complete!');
    process.exit(0);
  } catch (error) {
    console.error('\n❌ Test failed:', error);
    process.exit(1);
  }
}

testAITools();
