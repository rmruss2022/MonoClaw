import Anthropic from '@anthropic-ai/sdk';

let anthropicClient: Anthropic | null = null;

export function getAnthropicClient(): Anthropic {
  if (!anthropicClient) {
    const apiKey = process.env.ANTHROPIC_API_KEY;
    if (!apiKey || apiKey === 'your_anthropic_api_key_here') {
      throw new Error('ANTHROPIC_API_KEY not configured');
    }
    anthropicClient = new Anthropic({ apiKey });
  }
  return anthropicClient;
}

export const ANTHROPIC_CONFIG = {
  get model() {
    return process.env.ANTHROPIC_MODEL || 'claude-sonnet-4-20250514';
  },
  get maxTokens() {
    return parseInt(process.env.ANTHROPIC_MAX_TOKENS || '1000');
  },
};
