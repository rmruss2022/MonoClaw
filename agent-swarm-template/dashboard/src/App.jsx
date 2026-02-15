import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [data, setData] = useState(null);
  const [initialLoad, setInitialLoad] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [projectId, setProjectId] = useState(3); // Default to Ora AI
  const [projects, setProjects] = useState([]);
  const [selectedTask, setSelectedTask] = useState(null);
  const [orchestratorStatus, setOrchestratorStatus] = useState(null);
  const [viewingFile, setViewingFile] = useState(null);

  // Load available projects
  const loadProjects = async () => {
    try {
      const response = await fetch('/api/projects');
      const data = await response.json();
      setProjects(data.projects.map(p => ({ id: p.id, name: p.name, isDemo: false })));
    } catch (err) {
      console.error('Error loading projects:', err);
    }
  };

  // Load data from API
  const loadData = async () => {
    try {
      setError(null);
      const apiUrl = `/api/projects/${projectId}`;
      const response = await fetch(apiUrl);
      if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
      }
      const jsonData = await response.json();
      
      // Also fetch agents for this project
      const agentsResponse = await fetch(`/api/agents?project_id=${projectId}`);
      const agentsData = await agentsResponse.json();
      
      // Merge agents into the data object
      jsonData.agents = {
        active: agentsData.agents.filter(a => a.status === 'running'),
        completed: agentsData.agents.filter(a => a.status === 'completed'),
        all: agentsData.agents
      };
      
      // Fetch per-project orchestrator status
      try {
        const orchResponse = await fetch(`/api/projects/${projectId}/orchestrator`);
        if (orchResponse.ok) {
          const orchData = await orchResponse.json();
          setOrchestratorStatus(orchData);
        }
      } catch (orchErr) {
        console.error('Error loading orchestrator status:', orchErr);
        // Set default stopped status on error
        setOrchestratorStatus({ status: 'stopped', isRunning: false });
      }
      
      setData(jsonData);
      setLastUpdate(new Date());
      if (initialLoad) setInitialLoad(false);
    } catch (err) {
      console.error('Error loading data:', err);
      setError(err.message);
      if (initialLoad) setInitialLoad(false);
    }
  };

  // Load projects on mount
  useEffect(() => {
    loadProjects();
  }, []);

  // Auto-refresh every 10 seconds when projectId changes
  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [projectId]);

  if (initialLoad && !data) return <LoadingScreen />;
  if (error && !data) return <ErrorScreen error={error} retry={loadData} />;
  if (!data) return <LoadingScreen />;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 p-6">
      <div className="mb-8">
        <h1 className="text-5xl font-black bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
          Agent Swarm
        </h1>
        <p className="text-slate-600 mt-2 text-lg font-medium">
          🤖 Distributed workforce of specialized agents
        </p>
      </div>
      <Header 
        project={data.project} 
        lastUpdate={lastUpdate} 
        refresh={loadData}
        projects={projects}
        projectId={projectId}
        setProjectId={setProjectId}
      />
      <Stats stats={data.stats} />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
        <div className="lg:col-span-2 space-y-6">
          <ProjectPipeline project={data.project} onViewFile={setViewingFile} />
          <KanbanBoard tasks={data.tasks} onTaskClick={setSelectedTask} />
          <ProjectContext project={data.project} />
        </div>
        <div className="space-y-6">
          <OrchestratorStatus status={orchestratorStatus} />
          <ActiveAgents agents={data.agents.active} />
          <ActivityLog log={data.activity_log} />
        </div>
      </div>
      {selectedTask && (
        <TaskModal task={selectedTask} onClose={() => setSelectedTask(null)} />
      )}
      {viewingFile && (
        <FileViewerModal filePath={viewingFile} onClose={() => setViewingFile(null)} />
      )}
    </div>
  );
}

// Header Component
function Header({ project, lastUpdate, refresh, projects, projectId, setProjectId }) {
  const statusColors = {
    'not-started': 'bg-gray-100 text-gray-800',
    'in-progress': 'bg-blue-100 text-blue-800',
    'paused': 'bg-yellow-100 text-yellow-800',
    'completed': 'bg-green-100 text-green-800',
    'blocked': 'bg-red-100 text-red-800'
  };

  return (
    <div className="bg-white rounded-xl shadow-lg border border-slate-200 p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <select 
            value={projectId}
            onChange={(e) => setProjectId(Number(e.target.value))}
            className="px-4 py-2 border-2 border-blue-200 rounded-lg bg-white text-sm font-semibold text-slate-700 hover:border-blue-400 hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all">
            {projects.map(p => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          {projects.find(p => p.id === projectId)?.isDemo && (
            <span className="px-3 py-1 bg-yellow-100 text-yellow-700 text-xs font-semibold rounded-full">
              Demo Data
            </span>
          )}
        </div>
        <div className="text-right">
          <span className={`px-4 py-1.5 rounded-full text-sm font-semibold ${statusColors[project.status]}`}>
            {project.status}
          </span>
          <div className="text-sm text-slate-500 mt-2 font-medium">
            Last update: {lastUpdate.toLocaleTimeString()}
          </div>
          <button 
            onClick={refresh}
            className="mt-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg hover:from-blue-700 hover:to-indigo-700 text-sm font-semibold shadow-md hover:shadow-lg transition-all">
            🔄 Refresh
          </button>
        </div>
      </div>
      <div>
        <h1 className="text-3xl font-bold text-slate-900">{project.name}</h1>
        <p className="text-slate-600 mt-1">{project.description}</p>
        {project.reference && (
          <a href={project.reference} target="_blank" rel="noreferrer"
             className="text-blue-600 hover:text-blue-800 hover:underline text-sm mt-2 inline-block font-medium">
            Reference: {project.reference}
          </a>
        )}
      </div>
    </div>
  );
}

// Stats Component
function Stats({ stats }) {
  const total = stats.total_tasks || 1;
  const completed = stats.completed || 0;
  const progress = Math.round((completed / total) * 100);

  return (
    <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
      <StatCard label="Total Tasks" value={stats.total_tasks} color="blue" />
      <StatCard label="In Progress" value={stats.in_progress} color="yellow" />
      <StatCard label="Ready" value={stats.ready} color="purple" />
      <StatCard label="In QA" value={stats.qa} color="orange" />
      <StatCard label="Completed" value={stats.completed} color="green" />
      
      <div className="md:col-span-5 bg-white rounded-lg shadow-sm p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">Project Progress</span>
          <span className="text-sm font-bold text-gray-900">{progress}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3">
          <div 
            className="bg-green-600 h-3 rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
        {stats.estimated_hours_remaining > 0 && (
          <div className="text-sm text-gray-600 mt-2">
            ~{stats.estimated_hours_remaining}h remaining
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, color }) {
  const colors = {
    blue: 'bg-blue-50 text-blue-700',
    yellow: 'bg-yellow-50 text-yellow-700',
    purple: 'bg-purple-50 text-purple-700',
    orange: 'bg-orange-50 text-orange-700',
    green: 'bg-green-50 text-green-700'
  };

  return (
    <div className={`${colors[color]} rounded-lg p-4 shadow-sm`}>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-sm font-medium mt-1">{label}</div>
    </div>
  );
}

// Kanban Board Component
function KanbanBoard({ tasks, onTaskClick }) {
  const columns = [
    { id: 'todo', title: 'To Do', color: 'gray' },
    { id: 'in-progress', title: 'In Progress', color: 'blue' },
    { id: 'ready', title: 'Ready', color: 'purple' },
    { id: 'qa', title: 'QA', color: 'orange' },
    { id: 'done', title: 'Complete', color: 'green' }
  ];

  const getTasksByState = (state) => {
    return tasks.filter(task => task.state === state);
  };

  return (
    <div className="bg-white rounded-xl shadow-lg border border-slate-200 p-6">
      <h2 className="text-2xl font-bold text-slate-900 mb-4">📋 Kanban Board</h2>
      <div className="grid grid-cols-5 gap-4">
        {columns.map(column => (
          <KanbanColumn 
            key={column.id}
            column={column}
            tasks={getTasksByState(column.id)}
            onTaskClick={onTaskClick}
          />
        ))}
      </div>
    </div>
  );
}

function KanbanColumn({ column, tasks, onTaskClick }) {
  const colorMap = {
    gray: 'border-gray-300 bg-gray-50',
    blue: 'border-blue-300 bg-blue-50',
    purple: 'border-purple-300 bg-purple-50',
    orange: 'border-orange-300 bg-orange-50',
    green: 'border-green-300 bg-green-50'
  };

  return (
    <div className={`kanban-column border-2 rounded-lg p-3 ${colorMap[column.color]}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-sm text-gray-700">{column.title}</h3>
        <span className="text-xs bg-white px-2 py-1 rounded-full font-medium">
          {tasks.length}
        </span>
      </div>
      <div className="space-y-2">
        {tasks.length === 0 ? (
          <div className="text-xs text-gray-400 text-center py-4">No tasks</div>
        ) : (
          tasks.map(task => <TaskCard key={task.id} task={task} onClick={() => onTaskClick(task)} />)
        )}
      </div>
    </div>
  );
}

function TaskCard({ task, onClick }) {
  const priorityColors = {
    low: 'bg-gray-100 text-gray-700',
    medium: 'bg-blue-100 text-blue-700',
    high: 'bg-orange-100 text-orange-700',
    critical: 'bg-red-100 text-red-700'
  };

  return (
    <div 
      className="task-card bg-white border border-gray-200 rounded-md p-3 cursor-pointer hover:shadow-md transition-shadow"
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-2">
        <h4 className="text-sm font-medium text-gray-900 leading-tight">{task.title}</h4>
        {task.priority && (
          <span className={`text-xs px-2 py-0.5 rounded ${priorityColors[task.priority]}`}>
            {task.priority}
          </span>
        )}
      </div>
      {task.description && (
        <p className="text-xs text-gray-600 mb-2 line-clamp-2">{task.description}</p>
      )}
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>{task.estimated_hours}h</span>
        {task.assigned_to && (
          <span className="font-medium text-blue-600">{task.assigned_to}</span>
        )}
      </div>
      {task.tags && task.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {task.tags.map(tag => (
            <span key={tag} className="text-xs bg-gray-100 px-2 py-0.5 rounded">
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// Project Pipeline Component - Shows orchestrator configuration
function ProjectPipeline({ project, onViewFile }) {
  if (!project || !project.configuration) {
    return null;
  }

  const config = project.configuration;
  
  const handlePathClick = (path) => {
    if (onViewFile) {
      onViewFile(path);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-lg border border-slate-200 p-6">
      <h2 className="text-2xl font-bold text-slate-900 mb-4">🤖 Orchestrator Pipeline</h2>
      
      {/* Tech Stack */}
      {config.tech_stack && (
        <div className="mb-6">
          <h3 className="text-lg font-bold text-slate-800 mb-3 flex items-center gap-2">
            <span>⚙️</span> Tech Stack
          </h3>
          <div className="grid grid-cols-2 gap-4">
            {config.tech_stack.frontend && (
              <div className="bg-blue-50 rounded-lg p-3">
                <div className="text-xs font-semibold text-blue-600 mb-1">Frontend</div>
                <div className="text-sm text-slate-800">{config.tech_stack.frontend}</div>
              </div>
            )}
            {config.tech_stack.backend && (
              <div className="bg-green-50 rounded-lg p-3">
                <div className="text-xs font-semibold text-green-600 mb-1">Backend</div>
                <div className="text-sm text-slate-800">{config.tech_stack.backend}</div>
              </div>
            )}
          </div>
          {config.tech_stack.services && config.tech_stack.services.length > 0 && (
            <div className="mt-3 bg-purple-50 rounded-lg p-3">
              <div className="text-xs font-semibold text-purple-600 mb-2">Services</div>
              <div className="flex flex-wrap gap-2">
                {config.tech_stack.services.map((service, idx) => (
                  <span key={idx} className="text-xs bg-white px-2 py-1 rounded border border-purple-200 text-slate-700">
                    {service}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Agent Requirements */}
      {config.agent_requirements && (
        <div className="mb-6">
          <h3 className="text-lg font-bold text-slate-800 mb-3 flex items-center gap-2">
            <span>👥</span> Agent Specializations
          </h3>
          <div className="space-y-3">
            {Object.entries(config.agent_requirements).map(([agentType, skills]) => {
              const agentColors = {
                'designer': 'bg-pink-50 border-pink-200 text-pink-700',
                'ios_dev': 'bg-blue-50 border-blue-200 text-blue-700',
                'backend_dev': 'bg-green-50 border-green-200 text-green-700',
                'qa': 'bg-orange-50 border-orange-200 text-orange-700',
                'content': 'bg-purple-50 border-purple-200 text-purple-700'
              };
              
              const agentIcons = {
                'designer': '🎨',
                'ios_dev': '📱',
                'backend_dev': '⚙️',
                'qa': '✅',
                'content': '✍️'
              };

              const colorClass = agentColors[agentType] || 'bg-gray-50 border-gray-200 text-gray-700';
              const icon = agentIcons[agentType] || '🤖';
              const displayName = agentType.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());

              return (
                <div key={agentType} className={`border-2 rounded-lg p-3 ${colorClass}`}>
                  <div className="font-bold text-sm mb-2 flex items-center gap-2">
                    <span>{icon}</span>
                    <span>{displayName}</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {skills.map((skill, idx) => (
                      <span key={idx} className="text-xs bg-white/80 px-2 py-1 rounded border border-current/20">
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* File Paths */}
      {config.file_paths && (
        <div>
          <h3 className="text-lg font-bold text-slate-800 mb-3 flex items-center gap-2">
            <span>📁</span> Project Paths
          </h3>
          <div className="space-y-2 bg-slate-50 rounded-lg p-4">
            {Object.entries(config.file_paths).map(([key, path]) => {
              const displayKey = key.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
              return (
                <div key={key} className="flex items-start gap-3">
                  <span className="text-xs font-semibold text-slate-600 min-w-[120px]">{displayKey}:</span>
                  <button
                    onClick={() => handlePathClick(path)}
                    className="text-xs font-mono text-blue-600 hover:text-blue-800 hover:underline text-left break-all cursor-pointer"
                  >
                    {path}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Orchestrator Documentation */}
      {config.orchestrator_docs && config.orchestrator_docs.length > 0 && (
        <div className="mt-6">
          <h3 className="text-lg font-bold text-slate-800 mb-3 flex items-center gap-2">
            <span>📋</span> Orchestrator Documentation
          </h3>
          <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
            <div className="space-y-2">
              {config.orchestrator_docs.map((doc, idx) => {
                const fullPath = config.orchestrator_docs_path ? `${config.orchestrator_docs_path}/${doc}` : doc;
                return (
                  <button
                    key={idx}
                    onClick={() => handlePathClick(fullPath)}
                    className="w-full text-left flex items-center gap-3 p-3 bg-white hover:bg-indigo-100 rounded border border-indigo-200 hover:border-indigo-400 transition-all"
                  >
                    <span className="text-2xl">📄</span>
                    <div className="flex-1">
                      <div className="font-semibold text-indigo-900">{doc}</div>
                      <div className="text-xs text-indigo-600 font-mono">{fullPath}</div>
                    </div>
                    <span className="text-indigo-400">→</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Reference Materials */}
      {config.reference_materials && config.reference_materials.length > 0 && (
        <div className="mt-6">
          <h3 className="text-lg font-bold text-slate-800 mb-3 flex items-center gap-2">
            <span>📚</span> Reference Materials
          </h3>
          <div className="space-y-2">
            {config.reference_materials.map((ref, idx) => (
              <div key={idx} className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="font-semibold text-sm text-slate-800">{ref.name}</div>
                    <button
                      onClick={() => handlePathClick(ref.path)}
                      className="text-xs text-blue-600 hover:text-blue-800 hover:underline font-mono mt-1 text-left cursor-pointer"
                    >
                      {ref.path}
                    </button>
                    {ref.contents && ref.contents.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {ref.contents.map((item, i) => (
                          <span key={i} className="text-xs bg-white px-2 py-0.5 rounded border border-yellow-300">
                            {item}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <span className="text-xs font-semibold text-yellow-700 bg-yellow-100 px-2 py-1 rounded">
                    {ref.type}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Orchestrator Status Component
function OrchestratorStatus({ status }) {
  if (!status) {
    return (
      <div className="bg-white rounded-xl shadow-lg border border-slate-200 p-6">
        <h2 className="text-2xl font-bold text-slate-900 mb-4">⚙️ Orchestrator</h2>
        <div className="text-center text-slate-400 py-4">Loading status...</div>
      </div>
    );
  }

  const statusColors = {
    'healthy': 'bg-green-100 text-green-800 border-green-200',
    'stale': 'bg-yellow-100 text-yellow-800 border-yellow-200',
    'stopped': 'bg-red-100 text-red-800 border-red-200'
  };

  const statusIcons = {
    'healthy': '✅',
    'stale': '⚠️',
    'stopped': '🛑'
  };

  const formatTimeSince = (ms) => {
    if (!ms) return 'Never';
    const minutes = Math.floor(ms / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (days > 0) return `${days}d ${hours % 24}h ago`;
    if (hours > 0) return `${hours}h ${minutes % 60}m ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'Just now';
  };

  const lastCheckTime = status.lastCheck ? new Date(status.lastCheck).toLocaleTimeString() : 'Never';
  const timeSince = formatTimeSince(status.timeSinceLastCheck);

  return (
    <div className="bg-white rounded-xl shadow-lg border border-slate-200 p-6">
      <h2 className="text-2xl font-bold text-slate-900 mb-4">⚙️ Orchestrator</h2>
      
      <div className={`border-2 rounded-lg p-4 mb-4 ${statusColors[status.status]}`}>
        <div className="flex items-center justify-between mb-2">
          <span className="text-lg font-bold">
            {statusIcons[status.status]} {status.status.toUpperCase()}
          </span>
          <span className="text-xs font-mono">
            {status.isRunning ? 'Running' : 'Stopped'}
          </span>
        </div>
        
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-600">Last Poll:</span>
            <span className="font-medium">{lastCheckTime}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Poll Age:</span>
            <span className="font-medium">{timeSince}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Active Agents:</span>
            <span className="font-bold text-blue-600">{status.activeAgents?.length || 0}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Completed:</span>
            <span className="font-medium">{status.completedSinceRestart || 0}</span>
          </div>
          {status.tokenUsage > 0 && (
            <div className="flex justify-between">
              <span className="text-gray-600">Token Usage:</span>
              <span className="font-medium">{status.tokenUsage.toLocaleString()}</span>
            </div>
          )}
        </div>
      </div>

      {!status.isRunning && (
        <div className="text-sm text-gray-600 bg-gray-50 rounded p-3">
          <strong>Start orchestrator:</strong>
          <code className="block mt-1 text-xs font-mono bg-white p-2 rounded">
            cd agent-swarm-template && node orchestrator.js
          </code>
        </div>
      )}
    </div>
  );
}

// Active Agents Component
function ActiveAgents({ agents }) {
  return (
    <div className="bg-white rounded-xl shadow-lg border border-slate-200 p-6">
      <h2 className="text-2xl font-bold text-slate-900 mb-4">🤖 Active Agents</h2>
      {agents.length === 0 ? (
        <div className="text-center text-slate-400 py-8">No active agents</div>
      ) : (
        <div className="space-y-3">
          {agents.map((agent, idx) => (
            <AgentCard key={idx} agent={agent} />
          ))}
        </div>
      )}
    </div>
  );
}

function AgentCard({ agent }) {
  const runtime = agent.spawned_at 
    ? Math.floor((Date.now() - new Date(agent.spawned_at).getTime()) / 60000)
    : 0;

  const getModelDisplay = (model) => {
    if (!model) return null;
    
    const modelNames = {
      'orchestrator': 'Orchestrator',
      'shell-script': 'Shell Script',
      'claude-sonnet-4-5': 'Claude Sonnet 4.5',
      'claude-opus-4-6': 'Claude Opus 4.6',
      'kimi-k2.5': 'Kimi K2.5',
      'moonshotai/kimi-k2.5': 'Kimi K2.5',
      'anthropic/claude-sonnet-4-5': 'Claude Sonnet 4.5',
      'anthropic/claude-opus-4-6': 'Claude Opus 4.6'
    };

    return modelNames[model] || model.replace('moonshotai/', '').replace('anthropic/', '');
  };

  return (
    <div className="border border-gray-200 rounded-lg p-3 bg-gray-50">
      <div className="flex items-center justify-between mb-2">
        <span className="font-medium text-sm text-gray-900">{agent.agent_id}</span>
        <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full">
          {agent.status}
        </span>
      </div>
      <div className="text-xs text-gray-600 mb-1">
        Task: <span className="font-medium">{agent.task_id}</span>
      </div>
      {agent.model && (
        <div className="text-xs text-gray-500 mb-1">
          Model: <span className="font-medium">{getModelDisplay(agent.model)}</span>
        </div>
      )}
      <div className="text-xs text-gray-500">
        Runtime: {runtime}m
      </div>
      {agent.session_key && (
        <div className="text-xs text-gray-400 mt-1 font-mono truncate">
          {agent.session_key}
        </div>
      )}
    </div>
  );
}

// Activity Log Component
function ActivityLog({ log }) {
  const recentLog = log.slice(-10).reverse();

  return (
    <div className="bg-white rounded-xl shadow-lg border border-slate-200 p-6">
      <h2 className="text-2xl font-bold text-slate-900 mb-4">📝 Activity Log</h2>
      {recentLog.length === 0 ? (
        <div className="text-center text-slate-400 py-8">No activity yet</div>
      ) : (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {recentLog.map((entry, idx) => (
            <ActivityEntry key={idx} entry={entry} />
          ))}
        </div>
      )}
    </div>
  );
}

function ActivityEntry({ entry }) {
  const typeIcons = {
    spawn: '🚀',
    completion: '✅',
    error: '❌',
    update: '📝',
    info: 'ℹ️'
  };

  const time = new Date(entry.timestamp).toLocaleTimeString();

  return (
    <div className="border-l-4 border-blue-500 pl-3 py-2 text-sm">
      <div className="flex items-start justify-between">
        <span className="text-xs text-gray-500">{time}</span>
        <span>{typeIcons[entry.type] || '•'}</span>
      </div>
      <div className="text-gray-700 mt-1">
        <span className="font-medium text-blue-600">{entry.agent}</span>
        {entry.task_id && <span className="text-gray-500"> → {entry.task_id}</span>}
      </div>
      <div className="text-gray-600">{entry.message}</div>
    </div>
  );
}

// Project Context Component
function ProjectContext({ project }) {
  return (
    <div className="bg-white rounded-xl shadow-lg border border-slate-200 p-6">
      <h2 className="text-2xl font-bold text-slate-900 mb-4">📄 Project Context</h2>
      <div className="space-y-4">
        {project.reference && (
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Reference</h3>
            <a 
              href={project.reference} 
              target="_blank" 
              rel="noreferrer"
              className="text-blue-600 hover:text-blue-800 hover:underline text-sm break-all"
            >
              {project.reference}
            </a>
          </div>
        )}
        {project.description && (
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Description</h3>
            <p className="text-gray-600 text-sm whitespace-pre-wrap">{project.description}</p>
          </div>
        )}
        {project.tech_stack && project.tech_stack.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Tech Stack</h3>
            <div className="flex flex-wrap gap-2">
              {project.tech_stack.map(tech => (
                <span key={tech} className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
                  {tech}
                </span>
              ))}
            </div>
          </div>
        )}
        {project.repo_url && (
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Repository</h3>
            <a 
              href={project.repo_url} 
              target="_blank" 
              rel="noreferrer"
              className="text-blue-600 hover:text-blue-800 hover:underline text-sm font-mono"
            >
              {project.repo_url}
            </a>
          </div>
        )}
      </div>
    </div>
  );
}

// Loading & Error Screens
function LoadingScreen() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
        <p className="mt-4 text-gray-600">Loading dashboard...</p>
      </div>
    </div>
  );
}

function ErrorScreen({ error, retry }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center max-w-md">
        <div className="text-6xl mb-4">❌</div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Error Loading Dashboard</h2>
        <p className="text-gray-600 mb-4">{error}</p>
        <button 
          onClick={retry}
          className="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700">
          Retry
        </button>
        <p className="text-sm text-gray-500 mt-4">
          Make sure the API server is running: <code className="bg-gray-100 px-2 py-1 rounded">node server.js</code>
        </p>
      </div>
    </div>
  );
}

// Task Detail Modal
function TaskModal({ task, onClose }) {
  const priorityColors = {
    low: 'bg-gray-100 text-gray-700',
    medium: 'bg-blue-100 text-blue-700',
    high: 'bg-orange-100 text-orange-700',
    critical: 'bg-red-100 text-red-700'
  };

  const stateColors = {
    'todo': 'bg-gray-100 text-gray-700',
    'in-progress': 'bg-blue-100 text-blue-700',
    'ready': 'bg-purple-100 text-purple-700',
    'qa': 'bg-orange-100 text-orange-700',
    'done': 'bg-green-100 text-green-700'
  };

  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div 
        className="bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 p-6 flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-sm font-mono text-gray-500">{task.id}</span>
              {task.priority && (
                <span className={`text-xs px-2 py-1 rounded font-medium ${priorityColors[task.priority]}`}>
                  {task.priority}
                </span>
              )}
              {task.state && (
                <span className={`text-xs px-2 py-1 rounded font-medium ${stateColors[task.state]}`}>
                  {task.state}
                </span>
              )}
            </div>
            <h2 className="text-2xl font-bold text-gray-900">{task.title}</h2>
          </div>
          <button 
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none ml-4"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Description */}
          {task.description && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Description</h3>
              <p className="text-gray-600 whitespace-pre-wrap">{task.description}</p>
            </div>
          )}

          {/* Metadata */}
          <div className="grid grid-cols-2 gap-4">
            {task.estimated_hours && (
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-1">Estimated Hours</h3>
                <p className="text-gray-900">{task.estimated_hours}h</p>
              </div>
            )}
            {task.actual_hours > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-1">Actual Hours</h3>
                <p className="text-gray-900">{task.actual_hours}h</p>
              </div>
            )}
            {task.assigned_to && (
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-1">Assigned To</h3>
                <p className="text-blue-600 font-medium">{task.assigned_to}</p>
              </div>
            )}
            {task.completed_at && (
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-1">Completed</h3>
                <p className="text-gray-900">{new Date(task.completed_at).toLocaleString()}</p>
              </div>
            )}
          </div>

          {/* Dependencies */}
          {task.dependencies && task.dependencies.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Dependencies</h3>
              <div className="flex flex-wrap gap-2">
                {task.dependencies.map(dep => (
                  <span key={dep} className="text-sm bg-yellow-100 text-yellow-700 px-3 py-1 rounded font-mono">
                    {dep}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Tags */}
          {task.tags && task.tags.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Tags</h3>
              <div className="flex flex-wrap gap-2">
                {task.tags.map(tag => (
                  <span key={tag} className="text-sm bg-gray-100 text-gray-700 px-3 py-1 rounded">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Code Files */}
          {task.code_files && task.code_files.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Code Files</h3>
              <div className="bg-gray-50 rounded-lg p-4 space-y-1">
                {task.code_files.map((file, idx) => (
                  <div key={idx} className="text-sm font-mono text-gray-600">
                    📄 {file}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// File Viewer Modal
function FileViewerModal({ filePath: initialPath, onClose }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [fileData, setFileData] = useState(null);
  const [currentPath, setCurrentPath] = useState(initialPath);

  const loadFile = async (path) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`/api/files/read?path=${encodeURIComponent(path)}`);
      if (!response.ok) {
        throw new Error(`Failed to load file: ${response.statusText}`);
      }
      
      const data = await response.json();
      setFileData(data);
      setCurrentPath(path);
    } catch (err) {
      console.error('Error loading file:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialPath) {
      loadFile(initialPath);
    }
  }, [initialPath]);

  const handleNavigate = (newPath) => {
    loadFile(newPath);
  };

  const handleGoUp = () => {
    const parentPath = currentPath.split('/').slice(0, -1).join('/');
    if (parentPath) {
      loadFile(parentPath);
    }
  };

  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div 
        className="bg-white rounded-xl shadow-2xl max-w-5xl w-full max-h-[90vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="bg-slate-800 text-white p-4 flex items-center justify-between">
          <div className="flex-1 min-w-0 flex items-center gap-2">
            {currentPath && currentPath !== '/' && (
              <button
                onClick={handleGoUp}
                className="px-3 py-1 bg-slate-700 hover:bg-slate-600 rounded text-sm flex-shrink-0"
              >
                ← Up
              </button>
            )}
            <div className="flex-1 min-w-0">
              <h2 className="text-lg font-bold truncate">{currentPath.split('/').pop()}</h2>
              <p className="text-xs text-slate-300 truncate font-mono">{currentPath}</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="text-white hover:text-gray-300 text-2xl leading-none ml-4 flex-shrink-0"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading && (
            <div className="flex items-center justify-center h-64">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
                <p className="mt-4 text-gray-600">Loading file...</p>
              </div>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <span className="text-2xl">❌</span>
                <div>
                  <h3 className="font-bold text-red-800 mb-1">Error Loading File</h3>
                  <p className="text-red-600 text-sm">{error}</p>
                </div>
              </div>
            </div>
          )}

          {!loading && !error && fileData && (
            <>
              {/* Directory Listing */}
              {fileData.type === 'directory' && (
                <div>
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                    <p className="text-blue-800 font-semibold">
                      📁 Directory with {fileData.files.length} items
                    </p>
                  </div>
                  <div className="space-y-2">
                    {fileData.files.map((file, idx) => {
                      const fullPath = `${currentPath}${currentPath.endsWith('/') ? '' : '/'}${file.name}`;
                      return (
                        <button
                          key={idx}
                          onClick={() => handleNavigate(fullPath)}
                          className="w-full flex items-center gap-3 p-3 bg-gray-50 rounded-lg hover:bg-blue-50 hover:border-blue-300 border border-gray-200 transition-all cursor-pointer"
                        >
                          <span className="text-2xl">{file.isDirectory ? '📁' : '📄'}</span>
                          <div className="flex-1 text-left">
                            <div className="font-medium text-gray-800">{file.name}</div>
                            {!file.isDirectory && (
                              <div className="text-xs text-gray-500">
                                {(file.size / 1024).toFixed(1)} KB
                              </div>
                            )}
                          </div>
                          <span className="text-gray-400">→</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Image Display */}
              {fileData.type === 'image' && (
                <div>
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 mb-4">
                    <p className="text-slate-700">
                      <strong>Type:</strong> {fileData.mimeType} • 
                      <strong className="ml-2">Size:</strong> {(fileData.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                  <div className="flex justify-center bg-slate-100 rounded-lg p-4">
                    <img 
                      src={fileData.data} 
                      alt={filePath} 
                      className="max-w-full max-h-[600px] object-contain rounded shadow-lg"
                    />
                  </div>
                </div>
              )}

              {/* Text Content */}
              {fileData.type === 'text' && (
                <div>
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 mb-4 flex items-center justify-between">
                    <div className="text-slate-700">
                      <strong>Extension:</strong> {fileData.extension} • 
                      <strong className="ml-2">Lines:</strong> {fileData.lines} • 
                      <strong className="ml-2">Size:</strong> {(fileData.size / 1024).toFixed(1)} KB
                    </div>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(fileData.content);
                        alert('Copied to clipboard!');
                      }}
                      className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
                    >
                      Copy
                    </button>
                  </div>
                  <pre className="bg-slate-900 text-green-400 p-4 rounded-lg overflow-x-auto text-sm font-mono">
                    {fileData.content}
                  </pre>
                </div>
              )}

              {/* Binary File */}
              {fileData.type === 'binary' && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
                  <div className="text-6xl mb-4">📦</div>
                  <h3 className="text-lg font-bold text-yellow-800 mb-2">Binary File</h3>
                  <p className="text-yellow-700">{fileData.message}</p>
                  <p className="text-sm text-yellow-600 mt-2">
                    Size: {(fileData.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default App
