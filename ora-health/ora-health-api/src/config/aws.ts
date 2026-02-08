import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient } from '@aws-sdk/lib-dynamodb';

const client = new DynamoDBClient({
  region: process.env.AWS_REGION || 'us-east-1',
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID!,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY!,
  },
});

export const dynamoDb = DynamoDBDocumentClient.from(client);

// Table names
export const TABLES = {
  USERS: 'ora-health-users',
  HEALTH_METRICS: 'ora-health-metrics',
  MEDICATIONS: 'ora-health-medications',
  APPOINTMENTS: 'ora-health-appointments',
  AI_CONVERSATIONS: 'ora-health-conversations',
} as const;
