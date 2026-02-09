// OpenClaw Sessions Dashboard
// Displays all OpenClaw sessions with Docker integration

const API_URL = window.location.origin;
let autoRefreshInterval = null;
let currentView = 'tree';
let sessionsData = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  refreshData();
  setupAutoRefresh();
  setupFilters();
  addLog('Dashboard initialized', 'info');
});

// Setup auto-refresh
function setupAutoRefresh() {
  const checkbox = document.getElementById('auto-refresh');
  
  if (checkbox.checked) {
    startAutoRefresh();
  }

  checkbox.addEventListener('change', (e) => {
    if (e.target.checked) {
      startAutoRefresh();
    } else {
      stopAutoRefresh();
    }
  });
}

function startAutoRefresh() {
  if (autoRefreshInterval) return;
  autoRefreshInterval = setInterval(refreshData, 10000);
  addLog('Auto-refresh enabled (10s)', 'info');
}

function stopAutoRefresh() {
  if (autoRefreshInterval) {
    clearInterval(autoRefreshInterval);
    autoRefreshInterval = null;
    addLog('Auto-refresh disabled', 'info');
  }
}

// Setup filters
function setupFilters() {
  const filters = ['filter-docker', 'filter-local', 'filter-inactive'];
  filters.forEach(id => {
    document.getElementById(id).addEventListener('change', applyFilters);
  });
}

// Fetch and display sessions
async function refreshData() {
  try {
    const response = await fetch(`${API_URL}/api/sessions`);
    const data = await response.json();
    
    sessionsData = data;
    displaySessions(data);
    updateStats(data);
    
    addLog('Data refreshed successfully', 'success');
    
  } catch (error) {
    console.error('Failed to fetch sessions:', error);
    addLog(`Failed to fetch data: ${error.message}`, 'error');
  }
}

// Display sessions
function displaySessions(data) {
  if (currentView === 'tree') {
    displayTreeView(data.tree || []);
  } else {
    displayGridView(data.sessions || []);
  }
}

// Display tree view
function displayTreeView(tree) {
  const container = document.getElementById('tree-view');
  
  if (tree.length === 0) {
    container.innerHTML = '<div class="no-sessions">No sessions found</div>';
    return;
  }

  container.innerHTML = tree.map(node => renderSessionNode(node)).join('');
}

// Render session node recursively
function renderSessionNode(session, depth = 0) {
  const hasChildren = session.children && session.children.length > 0;
  const dockerBadge = session.isDocker ? '<span class="docker-badge">🐳 Docker</span>' : '';
  const statusClass = session.status || 'idle';
  const icon = getSessionIcon(session);
  
  let html = `
    <div class="session-node" style="margin-left: ${depth * 20}px" data-session-id="${session.id || session.label}">
      <div class="session-item ${session.isDocker ? 'docker' : ''} ${statusClass}" onclick="showSessionDetails('${session.id || session.label}')">
        ${hasChildren ? `<button class="expand-btn" onclick="event.stopPropagation(); toggleChildren(this)">▼</button>` : ''}
        
        <div class="session-header">
          <span class="session-icon">${icon}</span>
          <span class="session-label">${session.label || session.id}</span>
          ${dockerBadge}
          <span class="session-status ${statusClass}">${statusClass}</span>
        </div>

        <div class="session-info">
          ${session.model ? `
            <div class="info-item">
              <span class="info-label">Model</span>
              <span class="info-value">${formatModel(session.model)}</span>
            </div>
          ` : ''}
          
          ${session.parent ? `
            <div class="info-item">
              <span class="info-label">Parent</span>
              <span class="info-value">${session.parent}</span>
            </div>
          ` : ''}
          
          ${session.created ? `
            <div class="info-item">
              <span class="info-label">Runtime</span>
              <span class="info-value">${formatDuration(Date.now() - session.created)}</span>
            </div>
          ` : ''}
          
          ${session.tokenUsage ? `
            <div class="info-item">
              <span class="info-label">Tokens</span>
              <span class="info-value">${formatTokens(session.tokenUsage)}</span>
            </div>
          ` : ''}
        </div>

        ${session.isDocker && session.docker ? renderDockerDetails(session.docker) : ''}
      </div>

      ${hasChildren ? `
        <div class="session-children">
          ${session.children.map(child => renderSessionNode(child, depth + 1)).join('')}
        </div>
      ` : ''}
    </div>
  `;

  return html;
}

// Render Docker details
function renderDockerDetails(docker) {
  return `
    <div class="docker-details">
      <div class="session-info">
        <div class="info-item">
          <span class="info-label">Container ID</span>
          <span class="info-value">${docker.id}</span>
        </div>
        <div class="info-item">
          <span class="info-label">State</span>
          <span class="info-value">${docker.state}</span>
        </div>
        ${docker.network ? `
          <div class="info-item">
            <span class="info-label">Network</span>
            <span class="info-value">${docker.network.join(', ')}</span>
          </div>
        ` : ''}
      </div>

      ${docker.cpu !== undefined || docker.memory !== undefined ? `
        <div class="resource-bars">
          ${docker.cpu !== undefined ? `
            <div class="resource">
              <div class="resource-label">
                <span>CPU</span>
                <span>${docker.cpu.toFixed(1)}%</span>
              </div>
              <div class="resource-bar">
                <div class="resource-fill" style="width: ${Math.min(docker.cpu, 100)}%"></div>
              </div>
            </div>
          ` : ''}

          ${docker.memory !== undefined ? `
            <div class="resource">
              <div class="resource-label">
                <span>Memory</span>
                <span>${docker.memory.toFixed(1)}%</span>
              </div>
              <div class="resource-bar">
                <div class="resource-fill" style="width: ${Math.min(docker.memory, 100)}%"></div>
              </div>
            </div>
          ` : ''}
        </div>
      ` : ''}
    </div>
  `;
}

// Display grid view
function displayGridView(sessions) {
  const container = document.getElementById('grid-view');
  
  if (sessions.length === 0) {
    container.innerHTML = '<div class="no-sessions">No sessions found</div>';
    return;
  }

  container.innerHTML = sessions.map(session => renderSessionCard(session)).join('');
}

// Render session card (for grid view)
function renderSessionCard(session) {
  const dockerBadge = session.isDocker ? '<span class="docker-badge">🐳 Docker</span>' : '';
  const statusClass = session.status || 'idle';
  const icon = getSessionIcon(session);
  
  return `
    <div class="session-item ${session.isDocker ? 'docker' : ''} ${statusClass}" onclick="showSessionDetails('${session.id || session.label}')">
      <div class="session-header">
        <span class="session-icon">${icon}</span>
        <span class="session-label">${session.label || session.id}</span>
        ${dockerBadge}
        <span class="session-status ${statusClass}">${statusClass}</span>
      </div>

      <div class="session-info">
        ${session.model ? `
          <div class="info-item">
            <span class="info-label">Model</span>
            <span class="info-value">${formatModel(session.model)}</span>
          </div>
        ` : ''}
        
        ${session.parent ? `
          <div class="info-item">
            <span class="info-label">Parent</span>
            <span class="info-value">${session.parent}</span>
          </div>
        ` : ''}
      </div>

      ${session.isDocker && session.docker ? renderDockerDetails(session.docker) : ''}
    </div>
  `;
}

// Get session icon based on type
function getSessionIcon(session) {
  if (session.isDocker) return '🐳';
  if (session.parent) return '🤖';
  return '👤';
}

// Format model name
function formatModel(model) {
  // Shorten long model names
  const parts = model.split('/');
  return parts[parts.length - 1];
}

// Format duration
function formatDuration(ms) {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) return `${days}d ${hours % 24}h`;
  if (hours > 0) return `${hours}h ${minutes % 60}m`;
  if (minutes > 0) return `${minutes}m`;
  return `${seconds}s`;
}

// Format tokens
function formatTokens(tokenUsage) {
  if (!tokenUsage) return 'N/A';
  const total = (tokenUsage.input || 0) + (tokenUsage.output || 0);
  return total.toLocaleString();
}

// Update stats
function updateStats(data) {
  const stats = data.stats || {};
  const sessions = data.sessions || [];
  
  document.getElementById('total-sessions').textContent = stats.total || sessions.length || 0;
  document.getElementById('active-sessions').textContent = stats.active || 0;
  document.getElementById('docker-agents').textContent = stats.docker || 0;
  
  const subagents = sessions.filter(s => s.parent).length;
  document.getElementById('subagents').textContent = subagents;
}

// Switch view
function switchView(view) {
  currentView = view;
  
  document.querySelectorAll('.btn-view').forEach(btn => {
    btn.classList.remove('active');
  });
  document.querySelector(`[data-view="${view}"]`).classList.add('active');
  
  document.getElementById('tree-view').style.display = view === 'tree' ? 'block' : 'none';
  document.getElementById('grid-view').style.display = view === 'grid' ? 'grid' : 'none';
  
  if (sessionsData) {
    displaySessions(sessionsData);
  }
  
  addLog(`Switched to ${view} view`, 'info');
}

// Toggle children visibility
function toggleChildren(btn) {
  const node = btn.closest('.session-node');
  const children = node.querySelector('.session-children');
  
  if (children) {
    if (children.style.display === 'none') {
      children.style.display = 'block';
      btn.textContent = '▼';
    } else {
      children.style.display = 'none';
      btn.textContent = '▶';
    }
  }
}

// Show session details in modal
function showSessionDetails(sessionId) {
  if (!sessionsData) return;
  
  const session = sessionsData.sessions.find(s => 
    (s.id === sessionId) || (s.label === sessionId)
  );
  
  if (!session) {
    addLog(`Session ${sessionId} not found`, 'error');
    return;
  }

  const modalBody = document.getElementById('modal-body');
  modalBody.innerHTML = `
    <h2>${session.label || session.id}</h2>
    <pre>${JSON.stringify(session, null, 2)}</pre>
  `;
  
  document.getElementById('modal').style.display = 'flex';
}

// Close modal
function closeModal() {
  document.getElementById('modal').style.display = 'none';
}

// Apply filters
function applyFilters() {
  const showDocker = document.getElementById('filter-docker').checked;
  const showLocal = document.getElementById('filter-local').checked;
  const showInactive = document.getElementById('filter-inactive').checked;

  if (!sessionsData) return;

  const filtered = sessionsData.sessions.filter(session => {
    if (session.isDocker && !showDocker) return false;
    if (!session.isDocker && !showLocal) return false;
    if (session.status !== 'active' && !showInactive) return false;
    return true;
  });

  const filteredData = {
    ...sessionsData,
    sessions: filtered,
    tree: buildTree(filtered)
  };

  displaySessions(filteredData);
  addLog(`Applied filters: ${filtered.length} sessions shown`, 'info');
}

// Build tree from filtered sessions
function buildTree(sessions) {
  const sessionMap = new Map();
  const roots = [];

  sessions.forEach(s => sessionMap.set(s.id || s.label, { ...s, children: [] }));

  sessions.forEach(session => {
    const node = sessionMap.get(session.id || session.label);
    if (!session.parent) {
      roots.push(node);
    } else {
      const parent = sessionMap.get(session.parent);
      if (parent) {
        parent.children.push(node);
      } else {
        roots.push(node);
      }
    }
  });

  return roots;
}

// Add log entry
function addLog(message, level = 'info') {
  const logs = document.getElementById('logs');
  const entry = document.createElement('div');
  entry.className = `log-entry ${level}`;
  
  const time = document.createElement('span');
  time.className = 'log-time';
  time.textContent = new Date().toLocaleTimeString();
  
  const msg = document.createElement('span');
  msg.className = 'log-message';
  msg.textContent = message;
  
  entry.appendChild(time);
  entry.appendChild(msg);
  logs.insertBefore(entry, logs.firstChild);

  // Limit to 50 log entries
  while (logs.children.length > 50) {
    logs.removeChild(logs.lastChild);
  }
}

// Close modal on background click
document.addEventListener('click', (e) => {
  const modal = document.getElementById('modal');
  if (e.target === modal) {
    closeModal();
  }
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeModal();
  }
  if (e.key === 'r' && e.ctrlKey) {
    e.preventDefault();
    refreshData();
  }
});
