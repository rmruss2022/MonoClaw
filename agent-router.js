// Agent Router for Telegram Group Chat
// Detects agent mentions and routes messages to the correct agent

const AGENT_MAP = {
  'sage': 'career-coach',
  'atlas': 'tech-lead',
  'claw': 'main'
};

function parseAgentMention(text) {
  const match = text.match(/^(@?(?:sage|atlas|claw))[\s:,]+(.*)/i);
  if (!match) return null;
  
  const agentName = match[1].replace('@', '').toLowerCase();
  const message = match[2].trim();
  
  return {
    agentId: AGENT_MAP[agentName],
    agentName,
    message
  };
}

module.exports = { parseAgentMention, AGENT_MAP };
