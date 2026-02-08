// In-memory storage for development/testing without AWS
export class MockStorageService {
  private users: Map<string, any> = new Map();
  private journalEntries: Map<string, any[]> = new Map();
  private chatMessages: Map<string, any[]> = new Map();
  private usersByEmail: Map<string, any> = new Map();

  async createUser(user: any): Promise<void> {
    this.users.set(user.id, {
      ...user,
      createdAt: new Date().toISOString(),
    });
    this.usersByEmail.set(user.email, user);
  }

  async getUser(userId: string): Promise<any> {
    return this.users.get(userId);
  }

  async getUserByEmail(email: string): Promise<any> {
    return this.usersByEmail.get(email);
  }

  async updateUser(userId: string, updates: any): Promise<void> {
    const user = this.users.get(userId);
    if (user) {
      const updated = { ...user, ...updates, updatedAt: new Date().toISOString() };
      this.users.set(userId, updated);
      this.usersByEmail.set(user.email, updated);
    }
  }

  async createJournalEntry(entry: any): Promise<void> {
    const entries = this.journalEntries.get(entry.userId) || [];
    entries.push({ ...entry, createdAt: new Date().toISOString() });
    this.journalEntries.set(entry.userId, entries);
  }

  async getJournalEntries(userId: string, limit: number = 50): Promise<any[]> {
    const entries = this.journalEntries.get(userId) || [];
    return entries.slice(-limit).reverse();
  }

  async getJournalEntry(userId: string, entryId: string): Promise<any> {
    const entries = this.journalEntries.get(userId) || [];
    return entries.find((e) => e.id === entryId);
  }

  async deleteJournalEntry(userId: string, entryId: string): Promise<void> {
    const entries = this.journalEntries.get(userId) || [];
    const filtered = entries.filter((e) => e.id !== entryId);
    this.journalEntries.set(userId, filtered);
  }

  async saveChatMessage(message: any): Promise<void> {
    const messages = this.chatMessages.get(message.userId) || [];
    messages.push({ ...message, timestamp: new Date().toISOString() });
    this.chatMessages.set(message.userId, messages);
  }

  async getChatHistory(userId: string, limit: number = 50): Promise<any[]> {
    const messages = this.chatMessages.get(userId) || [];
    return messages.slice(-limit);
  }
}

export const mockStorage = new MockStorageService();
