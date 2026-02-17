/**
 * Discord Bot Utilities for Agent Swarm
 * Handles Discord server/channel management and agent communication
 */

const axios = require('axios');

class DiscordBot {
  constructor(botToken) {
    this.botToken = botToken;
    this.baseUrl = 'https://discord.com/api/v10';
    this.headers = {
      'Authorization': `Bot ${botToken}`,
      'Content-Type': 'application/json'
    };
  }

  /**
   * Create project channels in Discord server
   */
  async createProjectChannels(guildId, projectName, projectId) {
    try {
      console.log(`🎮 Creating Discord channels for project: ${projectName}`);

      // 1. Create category for the project
      const category = await this.createChannel(guildId, {
        name: `project-${projectName.toLowerCase().replace(/\s+/g, '-')}`,
        type: 4, // Category
        position: 1
      });

      const categoryId = category.id;

      // 2. Create project management channels
      const boardChannel = await this.createChannel(guildId, {
        name: 'project-board',
        type: 0, // Text channel
        parent_id: categoryId,
        topic: `Kanban board updates for ${projectName}`
      });

      const decisionsChannel = await this.createChannel(guildId, {
        name: 'decisions',
        type: 0,
        parent_id: categoryId,
        topic: 'Architectural and technical decisions'
      });

      const statusChannel = await this.createChannel(guildId, {
        name: 'status',
        type: 0,
        parent_id: categoryId,
        topic: 'Agent heartbeats and progress updates'
      });

      // 3. Create coordination channels
      const generalChannel = await this.createChannel(guildId, {
        name: 'general',
        type: 0,
        parent_id: categoryId,
        topic: 'General agent discussion and coordination'
      });

      const questionsChannel = await this.createChannel(guildId, {
        name: 'questions',
        type: 0,
        parent_id: categoryId,
        topic: 'Agent questions requiring answers'
      });

      const alertsChannel = await this.createChannel(guildId, {
        name: 'alerts',
        type: 0,
        parent_id: categoryId,
        topic: '🚨 Urgent issues and blockers'
      });

      // 4. Create specialty channels
      const backendChannel = await this.createChannel(guildId, {
        name: 'backend',
        type: 0,
        parent_id: categoryId,
        topic: 'Backend development discussion'
      });

      const frontendChannel = await this.createChannel(guildId, {
        name: 'frontend',
        type: 0,
        parent_id: categoryId,
        topic: 'Frontend development discussion'
      });

      const qaChannel = await this.createChannel(guildId, {
        name: 'qa',
        type: 0,
        parent_id: categoryId,
        topic: 'Quality assurance and testing'
      });

      // 5. Create webhooks for each channel
      const webhooks = {};
      const channels = {
        board: boardChannel.id,
        decisions: decisionsChannel.id,
        status: statusChannel.id,
        general: generalChannel.id,
        questions: questionsChannel.id,
        alerts: alertsChannel.id,
        backend: backendChannel.id,
        frontend: frontendChannel.id,
        qa: qaChannel.id
      };

      for (const [name, channelId] of Object.entries(channels)) {
        const webhook = await this.createWebhook(channelId, `${projectName} - ${name}`);
        webhooks[name] = webhook.url;
      }

      console.log(`✅ Created ${Object.keys(channels).length} channels for ${projectName}`);

      return {
        categoryId,
        channels,
        webhooks
      };

    } catch (error) {
      console.error('❌ Discord channel creation failed:', error.response?.data || error.message);
      throw error;
    }
  }

  /**
   * Create a Discord channel
   */
  async createChannel(guildId, channelData) {
    try {
      console.log(`🔧 Creating channel:`, JSON.stringify(channelData, null, 2));
      const response = await axios.post(
        `${this.baseUrl}/guilds/${guildId}/channels`,
        channelData,
        { headers: this.headers }
      );
      return response.data;
    } catch (error) {
      console.error(`❌ Channel creation failed:`, JSON.stringify(error.response?.data, null, 2));
      throw error;
    }
  }

  /**
   * Create a webhook for a channel
   */
  async createWebhook(channelId, name) {
    const response = await axios.post(
      `${this.baseUrl}/channels/${channelId}/webhooks`,
      { name },
      { headers: this.headers }
    );
    return response.data;
  }

  /**
   * Send a message to a channel via webhook
   */
  async sendWebhookMessage(webhookUrl, content, options = {}) {
    try {
      const payload = {
        content,
        username: options.username || 'Agent',
        avatar_url: options.avatarUrl,
        embeds: options.embeds
      };

      await axios.post(webhookUrl, payload);
    } catch (error) {
      console.error('❌ Failed to send Discord message:', error.response?.data || error.message);
    }
  }

  /**
   * Read messages from a channel
   */
  async getMessages(channelId, limit = 50) {
    try {
      const response = await axios.get(
        `${this.baseUrl}/channels/${channelId}/messages?limit=${limit}`,
        { headers: this.headers }
      );
      return response.data;
    } catch (error) {
      console.error('❌ Failed to read Discord messages:', error.message);
      return [];
    }
  }

  /**
   * Create a thread in a channel
   */
  async createThread(channelId, name, message = null) {
    try {
      const payload = {
        name,
        type: 11, // Public thread
        auto_archive_duration: 1440 // 24 hours
      };

      if (message) {
        payload.message = { content: message };
      }

      const response = await axios.post(
        `${this.baseUrl}/channels/${channelId}/threads`,
        payload,
        { headers: this.headers }
      );

      return response.data;
    } catch (error) {
      console.error('❌ Failed to create thread:', error.message);
      throw error;
    }
  }

  /**
   * Add a reaction to a message
   */
  async addReaction(channelId, messageId, emoji) {
    try {
      await axios.put(
        `${this.baseUrl}/channels/${channelId}/messages/${messageId}/reactions/${encodeURIComponent(emoji)}/@me`,
        {},
        { headers: this.headers }
      );
    } catch (error) {
      console.error('❌ Failed to add reaction:', error.message);
    }
  }

  /**
   * Delete channels for a project
   */
  async deleteProjectChannels(categoryId, channelIds) {
    try {
      // Delete all channels in category
      for (const channelId of channelIds) {
        await axios.delete(
          `${this.baseUrl}/channels/${channelId}`,
          { headers: this.headers }
        );
      }

      // Delete category
      await axios.delete(
        `${this.baseUrl}/channels/${categoryId}`,
        { headers: this.headers }
      );

      console.log(`✅ Deleted project channels`);
    } catch (error) {
      console.error('❌ Failed to delete channels:', error.message);
    }
  }

  /**
   * Post a Kanban board status embed
   */
  async postKanbanUpdate(webhookUrl, kanbanData, projectName) {
    const embed = {
      title: '📋 Kanban Board Update',
      color: 0x0099ff,
      fields: [
        {
          name: '📝 Todo',
          value: `${kanbanData.todo || 0} tasks`,
          inline: true
        },
        {
          name: '🔧 In Progress',
          value: `${kanbanData.inProgress || 0} tasks`,
          inline: true
        },
        {
          name: '✅ Done',
          value: `${kanbanData.done || 0} tasks`,
          inline: true
        }
      ],
      footer: {
        text: `Project: ${projectName} | ${new Date().toLocaleString()}`
      }
    };

    if (kanbanData.recentlyCompleted && kanbanData.recentlyCompleted.length > 0) {
      embed.fields.push({
        name: 'Recently Completed',
        value: kanbanData.recentlyCompleted.map(t => `• ${t}`).join('\n'),
        inline: false
      });
    }

    if (kanbanData.currentlyActive && kanbanData.currentlyActive.length > 0) {
      embed.fields.push({
        name: 'Currently Active',
        value: kanbanData.currentlyActive.map(t => `• ${t}`).join('\n'),
        inline: false
      });
    }

    await this.sendWebhookMessage(webhookUrl, null, {
      username: 'Orchestrator',
      embeds: [embed]
    });
  }

  /**
   * Post agent completion report
   */
  async postCompletionReport(webhookUrl, taskData, agentName) {
    const embed = {
      title: `✅ Task Complete: ${taskData.title}`,
      color: 0x00ff00,
      fields: [
        { name: 'Agent', value: agentName, inline: true },
        { name: 'Duration', value: taskData.duration || 'Unknown', inline: true },
        { name: 'Files Created', value: taskData.files?.join('\n') || 'None', inline: false }
      ],
      footer: {
        text: 'Ready for review'
      },
      timestamp: new Date().toISOString()
    };

    if (taskData.summary) {
      embed.description = taskData.summary;
    }

    await this.sendWebhookMessage(webhookUrl, null, {
      username: agentName,
      embeds: [embed]
    });
  }
}

module.exports = DiscordBot;
