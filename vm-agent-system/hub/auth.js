const crypto = require('crypto');

class AuthManager {
  constructor() {
    this.tokens = new Map(); // token -> { agentId, createdAt, expiresAt }
  }

  /**
   * Generate a new authentication token
   * @param {string} agentId - Agent identifier
   * @param {number} ttl - Time to live in milliseconds (default: 365 days)
   * @returns {string} Authentication token
   */
  generateToken(agentId, ttl = 365 * 24 * 60 * 60 * 1000) {
    const token = crypto.randomBytes(32).toString('hex');
    const now = Date.now();
    
    this.tokens.set(token, {
      agentId,
      createdAt: now,
      expiresAt: now + ttl
    });

    return token;
  }

  /**
   * Validate a token
   * @param {string} token - Token to validate
   * @returns {object|null} Token data or null if invalid
   */
  validateToken(token) {
    const tokenData = this.tokens.get(token);
    
    if (!tokenData) {
      return null;
    }

    // Check expiration
    if (Date.now() > tokenData.expiresAt) {
      this.tokens.delete(token);
      return null;
    }

    return tokenData;
  }

  /**
   * Revoke a token
   * @param {string} token - Token to revoke
   * @returns {boolean} True if revoked, false if not found
   */
  revokeToken(token) {
    return this.tokens.delete(token);
  }

  /**
   * Revoke all tokens for an agent
   * @param {string} agentId - Agent identifier
   * @returns {number} Number of tokens revoked
   */
  revokeAgentTokens(agentId) {
    let count = 0;
    for (const [token, data] of this.tokens.entries()) {
      if (data.agentId === agentId) {
        this.tokens.delete(token);
        count++;
      }
    }
    return count;
  }

  /**
   * Get all tokens for an agent
   * @param {string} agentId - Agent identifier
   * @returns {Array} Array of token strings
   */
  getAgentTokens(agentId) {
    const tokens = [];
    for (const [token, data] of this.tokens.entries()) {
      if (data.agentId === agentId) {
        tokens.push(token);
      }
    }
    return tokens;
  }

  /**
   * Clean up expired tokens
   * @returns {number} Number of tokens cleaned up
   */
  cleanupExpired() {
    const now = Date.now();
    let count = 0;
    
    for (const [token, data] of this.tokens.entries()) {
      if (now > data.expiresAt) {
        this.tokens.delete(token);
        count++;
      }
    }
    
    return count;
  }
}

module.exports = AuthManager;
