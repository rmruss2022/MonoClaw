import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient } from '@aws-sdk/lib-dynamodb';

export const dynamoDBClient = new DynamoDBClient({
  region: process.env.AWS_REGION || 'us-east-1',
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID || '',
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY || '',
  },
});

export const docClient = DynamoDBDocumentClient.from(dynamoDBClient);

export const TABLES = {
  users: process.env.DYNAMODB_USERS_TABLE || 'shadow-ai-users',
  journalEntries: process.env.DYNAMODB_JOURNAL_ENTRIES_TABLE || 'shadow-ai-journal-entries',
  chatMessages: process.env.DYNAMODB_CHAT_MESSAGES_TABLE || 'shadow-ai-chat-messages',
  communityPosts: process.env.DYNAMODB_COMMUNITY_POSTS_TABLE || 'shadow-ai-community-posts',
  communityComments: process.env.DYNAMODB_COMMUNITY_COMMENTS_TABLE || 'shadow-ai-community-comments',
};
