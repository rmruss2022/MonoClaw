import { postgresService } from './src/services/postgres.service';
import { query } from './src/config/database';

async function testPostgres() {
  console.log('Testing Postgres connection and operations...\n');

  try {
    // Test 1: Basic query
    console.log('1. Testing basic database connection...');
    const result = await query('SELECT NOW() as current_time');
    console.log('✓ Connected to Postgres:', result.rows[0].current_time);

    // Test 2: Check if test user exists
    console.log('\n2. Checking for test user...');
    const user = await postgresService.getUserById('test-user-123');
    if (user) {
      console.log('✓ Test user found:', user.email);
    } else {
      console.log('✗ Test user not found');
    }

    // Test 3: Create a user summary
    console.log('\n3. Creating user summary...');
    await postgresService.createUserSummary({
      userId: 'test-user-123',
      summaryType: 'goals',
      summaryText:
        'User wants to improve their mental health and establish a consistent journaling practice.',
      confidenceScore: 0.8,
    });
    console.log('✓ User summary created');

    // Test 4: Get user summaries
    console.log('\n4. Retrieving user summaries...');
    const summaries = await postgresService.getUserSummaries('test-user-123');
    console.log(`✓ Found ${summaries.length} summaries`);
    summaries.forEach((s) => {
      console.log(`  - ${s.summary_type}: ${s.summary_text.substring(0, 50)}...`);
    });

    // Test 5: Create journal entry
    console.log('\n5. Creating journal entry...');
    const entryId = await postgresService.createJournalEntry({
      userId: 'test-user-123',
      content:
        'Today was a good day. I spent time reflecting on my goals and felt motivated to make progress.',
      mood: 'positive',
      tags: ['reflection', 'goals'],
      behaviorContext: 'journal-prompt',
    });
    console.log('✓ Journal entry created:', entryId);

    // Test 6: Get journal entries
    console.log('\n6. Retrieving journal entries...');
    const entries = await postgresService.getJournalEntries('test-user-123', 5);
    console.log(`✓ Found ${entries.length} journal entries`);

    // Test 7: Save chat message
    console.log('\n7. Saving chat message...');
    await postgresService.saveChatMessage({
      userId: 'test-user-123',
      role: 'user',
      content: 'I want to talk about my goals',
      behaviorId: 'free-form-chat',
    });
    console.log('✓ Chat message saved');

    // Test 8: Get chat history
    console.log('\n8. Retrieving chat history...');
    const history = await postgresService.getChatHistory('test-user-123', 10);
    console.log(`✓ Found ${history.length} messages`);

    console.log('\n✅ All tests passed!');
    process.exit(0);
  } catch (error) {
    console.error('\n❌ Test failed:', error);
    process.exit(1);
  }
}

testPostgres();
