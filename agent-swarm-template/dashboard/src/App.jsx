import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [data, setData] = useState(null);
  const [initialLoad, setInitialLoad] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [projectId, setProjectId] = useState(2); // Default to Password Generator
  const [projects, setProjects] = useState([]);

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
        <div className="lg:col-span-2">
          <KanbanBoard tasks={data.tasks} />
        </div>
        <div className="space-y-6">
          <ActiveAgents agents={data.agents.active} />
          <ActivityLog log={data.activity_log} />
        </div>
      </div>
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
function KanbanBoard({ tasks }) {
  const columns = [
    { id: 'todo', title: 'To Do', color: 'gray' },
    { id: 'in-progress', title: 'In Progress', color: 'blue' },
    { id: 'ready', title: 'Ready', color: 'purple' },
    { id: 'qa', title: 'QA', color: 'orange' },
    { id: 'complete', title: 'Complete', color: 'green' }
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
          />
        ))}
      </div>
    </div>
  );
}

function KanbanColumn({ column, tasks }) {
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
          tasks.map(task => <TaskCard key={task.id} task={task} />)
        )}
      </div>
    </div>
  );
}

function TaskCard({ task }) {
  const priorityColors = {
    low: 'bg-gray-100 text-gray-700',
    medium: 'bg-blue-100 text-blue-700',
    high: 'bg-orange-100 text-orange-700',
    critical: 'bg-red-100 text-red-700'
  };

  return (
    <div className="task-card bg-white border border-gray-200 rounded-md p-3 cursor-pointer hover:shadow-md transition-shadow">
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

  return (
    <div className="border border-gray-200 rounded-lg p-3 bg-gray-50">
      <div className="flex items-center justify-between mb-2">
        <span className="font-medium text-sm text-gray-900">{agent.agent_id}</span>
        <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full">
          {agent.status}
        </span>
      </div>
      <div className="text-xs text-gray-600">
        Task: <span className="font-medium">{agent.task_id}</span>
      </div>
      <div className="text-xs text-gray-500 mt-1">
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

export default App
