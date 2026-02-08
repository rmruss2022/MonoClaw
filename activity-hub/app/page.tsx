'use client';

import { useState, useEffect } from 'react';

export default function Home() {
  const [activeView, setActiveView] = useState<'feed' | 'calendar' | 'search'>('feed');

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-gray-100">
      {/* Back Button - Floating Action Button */}
      <a 
        href="http://localhost:18795/hub"
        target="command-hub"
        className="fixed bottom-8 right-8 z-50 px-6 py-3 bg-[#00d9ff]/15 hover:bg-[#00d9ff]/25 border-2 border-[#00d9ff]/40 hover:border-[#00d9ff]/60 rounded-full text-[#00d9ff] font-semibold text-sm transition-all hover:-translate-y-1 shadow-[0_4px_15px_rgba(0,217,255,0.2)] hover:shadow-[0_6px_25px_rgba(0,217,255,0.4)] backdrop-blur-md"
      >
        ← Hub
      </a>
      
      {/* Header */}
      <header className="border-b border-gray-800 bg-black/50">
        <div className="container mx-auto px-6 py-4">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-[#00d9ff] to-[#00ff88] bg-clip-text text-transparent">
            🦞 Activity Hub
          </h1>
          <p className="text-sm text-gray-400 mt-1">Real-time activity tracking, cron calendar, and workspace search</p>
        </div>
      </header>

      {/* Navigation */}
      <nav className="border-b border-gray-800 bg-black/30">
        <div className="container mx-auto px-6">
          <div className="flex gap-1">
            <button
              onClick={() => setActiveView('feed')}
              className={`px-6 py-3 font-medium transition-colors ${
                activeView === 'feed'
                  ? 'text-[#00d9ff] border-b-2 border-[#00d9ff]'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              📊 Activity Feed
            </button>
            <button
              onClick={() => setActiveView('calendar')}
              className={`px-6 py-3 font-medium transition-colors ${
                activeView === 'calendar'
                  ? 'text-[#00d9ff] border-b-2 border-[#00d9ff]'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              📅 Calendar
            </button>
            <button
              onClick={() => setActiveView('search')}
              className={`px-6 py-3 font-medium transition-colors ${
                activeView === 'search'
                  ? 'text-[#00d9ff] border-b-2 border-[#00d9ff]'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              🔍 Search
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-8">
        {activeView === 'feed' && <ActivityFeed />}
        {activeView === 'calendar' && <CalendarView />}
        {activeView === 'search' && <GlobalSearch />}
      </main>
    </div>
  );
}

function ActivityFeed() {
  const [activities, setActivities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadActivities();
    // Refresh every 10 seconds
    const interval = setInterval(loadActivities, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadActivities = async () => {
    try {
      const response = await fetch('/api/activity/log');
      const data = await response.json();
      if (data.success) {
        setActivities(data.activities);
      }
    } catch (error) {
      console.error('Failed to load activities:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl">
        <div className="flex items-center justify-center py-12">
          <div className="text-gray-400">Loading activities...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-[#00d9ff]">Activity Feed</h2>
        <div className="text-sm text-gray-400">{activities.length} activities</div>
      </div>
      <div className="space-y-3">
        {activities.map((activity, i) => (
          <div
            key={i}
            className="bg-white/5 border border-gray-800 rounded-lg p-4 hover:bg-white/10 transition-colors"
          >
            <div className="flex items-start gap-4">
              <span className="text-[#00ff88] font-mono text-sm">{activity.time}</span>
              <div className="flex-1">
                <p className="text-gray-200">{activity.action}</p>
                <span className="inline-block mt-1 px-2 py-0.5 text-xs rounded bg-white/5 text-gray-400">
                  {activity.type}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-6 p-4 border border-[#00d9ff]/20 bg-[#00d9ff]/5 rounded-lg">
        <p className="text-sm text-gray-300">
          <strong>📡 Next:</strong> Connect to Convex for real-time activity streaming
        </p>
      </div>
    </div>
  );
}

function CalendarView() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/cron/list')
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setJobs(data.jobs);
        } else {
          setError(data.error || 'Failed to load cron jobs');
        }
      })
      .catch(err => {
        console.error('Failed to fetch cron jobs:', err);
        setError('Failed to connect to API');
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="max-w-4xl">
        <div className="flex items-center justify-center py-12">
          <div className="text-gray-400">Loading cron jobs...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl">
        <div className="p-4 border border-red-500/20 bg-red-500/5 rounded-lg">
          <p className="text-red-400">Error: {error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-[#00d9ff]">Scheduled Tasks</h2>
        <div className="text-sm text-gray-400">{jobs.length} jobs</div>
      </div>
      <div className="grid gap-4">
        {jobs.map((job, i) => (
          <div
            key={i}
            className="bg-white/5 border border-gray-800 rounded-lg p-5"
          >
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-100">{job.name}</h3>
                <p className="text-[#00ff88] font-mono text-sm mt-1">
                  {formatSchedule(job.schedule)}
                </p>
              </div>
              <div
                className={`px-3 py-1 rounded-full text-xs font-medium ${
                  job.status === 'active'
                    ? 'bg-[#00ff88]/20 text-[#00ff88]'
                    : job.status === 'disabled'
                    ? 'bg-gray-500/20 text-gray-400'
                    : 'bg-[#00d9ff]/20 text-[#00d9ff]'
                }`}
              >
                {job.status}
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-6 p-4 border border-[#00d9ff]/20 bg-[#00d9ff]/5 rounded-lg">
        <p className="text-sm text-gray-300">
          <strong>📅 Next:</strong> Build weekly calendar grid view with time slots
        </p>
      </div>
    </div>
  );
}

function formatSchedule(schedule: any): string {
  if (schedule.kind === 'cron' && schedule.expr) {
    return `Cron: ${schedule.expr}`;
  } else if (schedule.kind === 'every' && schedule.everyMs) {
    const minutes = Math.floor(schedule.everyMs / 60000);
    const hours = Math.floor(minutes / 60);
    if (hours > 0) {
      return `Every ${hours} hour${hours > 1 ? 's' : ''}`;
    }
    return `Every ${minutes} minute${minutes > 1 ? 's' : ''}`;
  } else if (schedule.kind === 'at' && schedule.atMs) {
    return `Once at ${new Date(schedule.atMs).toLocaleString()}`;
  }
  return 'Unknown schedule';
}

function GlobalSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    if (query.length < 2) return;
    
    setLoading(true);
    setSearched(true);
    
    try {
      const res = await fetch(`/api/search/query?q=${encodeURIComponent(query)}`);
      const data = await res.json();
      
      if (data.success) {
        setResults(data.results);
      } else {
        setResults([]);
      }
    } catch (err) {
      console.error('Search error:', err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <div className="max-w-4xl">
      <h2 className="text-2xl font-bold mb-6 text-[#00d9ff]">Global Search</h2>
      <div className="mb-6 flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Search memories, documents, tasks..."
          className="flex-1 px-4 py-3 bg-white/5 border border-gray-800 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-[#00d9ff] transition-colors"
        />
        <button
          onClick={handleSearch}
          disabled={query.length < 2 || loading}
          className="px-6 py-3 bg-[#00d9ff] text-black font-medium rounded-lg hover:bg-[#00d9ff]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>
      
      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="text-gray-400">Searching workspace...</div>
        </div>
      )}
      
      {!loading && searched && results.length > 0 && (
        <div className="space-y-3">
          {results.map((result, i) => (
            <div
              key={i}
              className="bg-white/5 border border-gray-800 rounded-lg p-4 hover:bg-white/10 transition-colors"
            >
              <div className="flex items-start justify-between mb-2">
                <div>
                  <h3 className="text-gray-100 font-medium">{result.path}</h3>
                  <span className="text-xs text-gray-500">{result.type}</span>
                </div>
              </div>
              <p className="text-sm text-gray-400 leading-relaxed">{result.snippet}</p>
            </div>
          ))}
        </div>
      )}
      
      {!loading && searched && results.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-400">No results found for "{query}"</p>
          <p className="text-sm text-gray-500 mt-2">Try different keywords or check spelling</p>
        </div>
      )}
      
      {!searched && (
        <div className="text-center text-gray-500 py-12">
          <p>🔍 Search across your entire workspace</p>
          <p className="text-sm mt-2">
            Searches: MEMORY.md, daily memories, workspace docs, and more
          </p>
        </div>
      )}
    </div>
  );
}
