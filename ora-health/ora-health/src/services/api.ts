/**
 * API Service for Ora Health
 * Connects to backend running on localhost:4000
 */

const API_BASE_URL = 'http://localhost:4000';

export interface Meditation {
  id: string;
  title: string;
  description: string;
  duration: number;
  category: 'breathwork' | 'sleep' | 'mindful' | 'guided';
  icon: string;
  audioUrl: string | null;
}

export interface Category {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  displayOrder: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  behavior?: string;
  timestamp: string;
}

export interface Post {
  id: string;
  userId: string;
  content: string;
  categoryId: string;
  isAnonymous: boolean;
  likes: number;
  comments: number;
  createdAt: string;
}

// Meditation API
export const meditationAPI = {
  async getAll(): Promise<Meditation[]> {
    const response = await fetch(`${API_BASE_URL}/meditations`);
    const data = await response.json();
    return data.meditations;
  },
  
  async getByCategory(category: string): Promise<Meditation[]> {
    const all = await this.getAll();
    return all.filter(m => m.category === category);
  },
};

// Community API
export const communityAPI = {
  async getCategories(): Promise<Category[]> {
    const response = await fetch(`${API_BASE_URL}/community/categories`);
    const data = await response.json();
    return data.categories;
  },
  
  async getPosts(categoryId?: string): Promise<Post[]> {
    const url = categoryId 
      ? `${API_BASE_URL}/community/posts?category=${categoryId}`
      : `${API_BASE_URL}/community/posts`;
    const response = await fetch(url);
    const data = await response.json();
    return data.posts || [];
  },
  
  async createPost(content: string, categoryId: string, isAnonymous: boolean = false): Promise<Post> {
    const response = await fetch(`${API_BASE_URL}/community/posts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, categoryId, isAnonymous }),
    });
    const data = await response.json();
    return data.post;
  },
};

// Chat API
export const chatAPI = {
  async sendMessage(message: string, history: ChatMessage[] = []): Promise<ChatMessage> {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        message,
        history: history.map(m => ({ role: m.role, content: m.content })),
      }),
    });
    const data = await response.json();
    return {
      role: 'assistant',
      content: data.response,
      behavior: data.behavior,
      timestamp: new Date().toISOString(),
    };
  },
};

// Journal API
export const journalAPI = {
  async createEntry(content: string, mood?: string, tags?: string[]): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/journal`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, mood, tags }),
    });
    return response.json();
  },
};

// Inbox API
export const inboxAPI = {
  async getMessages(): Promise<any[]> {
    const response = await fetch(`${API_BASE_URL}/inbox`);
    const data = await response.json();
    return data.messages || [];
  },
  
  async getUnreadCount(): Promise<number> {
    const response = await fetch(`${API_BASE_URL}/inbox/unread-count`);
    const data = await response.json();
    return data.count || 0;
  },
};
