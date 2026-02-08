import {
  PutCommand,
  GetCommand,
  QueryCommand,
  UpdateCommand,
  DeleteCommand,
} from '@aws-sdk/lib-dynamodb';
import { docClient, TABLES } from '../config/aws';
import { mockStorage } from './mock-storage.service';

// Use mock storage if AWS credentials are not configured
const USE_MOCK = !process.env.AWS_ACCESS_KEY_ID || process.env.AWS_ACCESS_KEY_ID === 'your_aws_access_key_id';

export class DynamoDBService {
  // User operations
  async createUser(user: any): Promise<void> {
    if (USE_MOCK) return mockStorage.createUser(user);

    await docClient.send(
      new PutCommand({
        TableName: TABLES.users,
        Item: {
          ...user,
          createdAt: new Date().toISOString(),
        },
      })
    );
  }

  async getUser(userId: string): Promise<any> {
    if (USE_MOCK) return mockStorage.getUser(userId);

    const result = await docClient.send(
      new GetCommand({
        TableName: TABLES.users,
        Key: { id: userId },
      })
    );
    return result.Item;
  }

  async getUserByEmail(email: string): Promise<any> {
    if (USE_MOCK) return mockStorage.getUserByEmail(email);

    const result = await docClient.send(
      new QueryCommand({
        TableName: TABLES.users,
        IndexName: 'email-index', // You'll need to create this GSI
        KeyConditionExpression: 'email = :email',
        ExpressionAttributeValues: {
          ':email': email,
        },
      })
    );
    return result.Items?.[0];
  }

  async updateUser(userId: string, updates: any): Promise<void> {
    const updateExpressions: string[] = [];
    const expressionAttributeNames: Record<string, string> = {};
    const expressionAttributeValues: Record<string, any> = {};

    Object.entries(updates).forEach(([key, value], index) => {
      const attrName = `#attr${index}`;
      const attrValue = `:val${index}`;
      updateExpressions.push(`${attrName} = ${attrValue}`);
      expressionAttributeNames[attrName] = key;
      expressionAttributeValues[attrValue] = value;
    });

    await docClient.send(
      new UpdateCommand({
        TableName: TABLES.users,
        Key: { id: userId },
        UpdateExpression: `SET ${updateExpressions.join(', ')}, updatedAt = :updatedAt`,
        ExpressionAttributeNames: expressionAttributeNames,
        ExpressionAttributeValues: {
          ...expressionAttributeValues,
          ':updatedAt': new Date().toISOString(),
        },
      })
    );
  }

  // Journal Entry operations
  async createJournalEntry(entry: any): Promise<void> {
    await docClient.send(
      new PutCommand({
        TableName: TABLES.journalEntries,
        Item: {
          ...entry,
          createdAt: new Date().toISOString(),
        },
      })
    );
  }

  async getJournalEntries(userId: string, limit: number = 50): Promise<any[]> {
    const result = await docClient.send(
      new QueryCommand({
        TableName: TABLES.journalEntries,
        KeyConditionExpression: 'userId = :userId',
        ExpressionAttributeValues: {
          ':userId': userId,
        },
        ScanIndexForward: false,
        Limit: limit,
      })
    );
    return result.Items || [];
  }

  async getJournalEntry(userId: string, entryId: string): Promise<any> {
    const result = await docClient.send(
      new GetCommand({
        TableName: TABLES.journalEntries,
        Key: { userId, id: entryId },
      })
    );
    return result.Item;
  }

  async deleteJournalEntry(userId: string, entryId: string): Promise<void> {
    await docClient.send(
      new DeleteCommand({
        TableName: TABLES.journalEntries,
        Key: { userId, id: entryId },
      })
    );
  }

  // Chat Message operations
  async saveChatMessage(message: any): Promise<void> {
    if (USE_MOCK) return mockStorage.saveChatMessage(message);

    await docClient.send(
      new PutCommand({
        TableName: TABLES.chatMessages,
        Item: {
          ...message,
          timestamp: new Date().toISOString(),
        },
      })
    );
  }

  async getChatHistory(userId: string, limit: number = 50): Promise<any[]> {
    if (USE_MOCK) return mockStorage.getChatHistory(userId, limit);

    const result = await docClient.send(
      new QueryCommand({
        TableName: TABLES.chatMessages,
        KeyConditionExpression: 'userId = :userId',
        ExpressionAttributeValues: {
          ':userId': userId,
        },
        ScanIndexForward: false,
        Limit: limit,
      })
    );
    return result.Items || [];
  }

  // Community Post operations
  async createCommunityPost(post: any): Promise<void> {
    await docClient.send(
      new PutCommand({
        TableName: TABLES.communityPosts,
        Item: {
          ...post,
          createdAt: new Date().toISOString(),
        },
      })
    );
  }

  async getCommunityPosts(limit: number = 50): Promise<any[]> {
    const result = await docClient.send(
      new QueryCommand({
        TableName: TABLES.communityPosts,
        IndexName: 'createdAt-index',
        ScanIndexForward: false,
        Limit: limit,
      })
    );
    return result.Items || [];
  }

  async deleteCommunityPost(postId: string): Promise<void> {
    await docClient.send(
      new DeleteCommand({
        TableName: TABLES.communityPosts,
        Key: { id: postId },
      })
    );
  }
}

export const dbService = new DynamoDBService();
