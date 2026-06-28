import React, { useState, useEffect, useMemo } from 'react'
import Calendar from './components/Calendar.jsx'
import EventCard from './components/EventCard.jsx'
import StatsBar from './components/StatsBar.jsx'
import AddEventModal from './components/AddEventModal.jsx'
import RaveCard from './components/RaveCard.jsx'
import Budget from './components/Budget.jsx'
import Social from './components/Social.jsx'
import Scanner from './components/Scanner.jsx'
import Login from './components/Login.jsx'
import { API_BASE } from './auth.js'
import { registerPushNotifications } from './pushNotifications.js'

const TABS = [
  { id: 'calendar',  label: 'Calendar', icon: 'CAL' },
  { id: 'upcoming',  label: 'Upcoming', icon: 'UP' },
  { id: 'social',    label: 'Scene',    icon: 'SC' },
  { id: 'card',      label: 'Card',     icon: 'ID' },
  { id: 'budget',    label: 'Budget',   icon: '$' },
  { id: 'add',       label: 'Add',      icon: '+' },
]

function AuthenticatedApp({ user, onLogout }) {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('calendar')
  const [pushState, setPushState] = useState('idle') // idle | asking | granted | denied
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)

  useEffect(() => { loadEvents() }, [])

  async function loadEvents() {
    setLoading(true)
    try {
      const r = await fetch(`${API_BASE}/api/events`)
      const d = await r.json()
      setEvents(d.events || [])
    } catch (e) {
      console.error('loadEvents failed', e)
    }
    setLoading(false)
  }

  async function updateEvent(id, patch) {
    if (patch && patch.id) {
      setEvents(prev =>
        prev.map(e => e.id === id ? { ...patch } : e)
            .sort((a, b) => a.date.localeCompare(b.date))
      )
    } else {
      setEvents(prev => prev.map(e => e.id === id ? { ...e, ...patch } : e))
    }
    if (patch && !patch.id) {
      try {
        await authedFetch(`/api/events/${id}`, {
          method: 'PATCH',
          body: JSON.stringify(patch)
        })
      } catch (e) {
        console.error('update failed', e)
        loadEvents()
      }
    }
  }

  function createEvent(event) {
    setEvents(prev => [...prev, event].sort((a, b) => a.date.localeCompare(b.date)))
  }

  function deleteEvent(id) {
    setEvents(prev => prev.filter(e => e.id !== id))
  }

  async function authedFetch(url, options = {}) {
    const token = localStorage.getItem('rave_token')
    const headers = {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
      ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    }
    const fullUrl = url.startsWith('http') ? url : `${API_BASE}${url}`
    return fetch(fullUrl, { ...options, headers })
  }

  // Calendar search filter only
  const filtered = useMemo(() => {
    if (!search.trim()) return events
    const q = search.toLowerCase()
    return events.filter(e =>
      e.name.toLowerCase().includes(q) ||
      (e.venue || '').toLowerCase().includes(q) ||
      (e.description || '').toLowerCase().includes(q)
    )
  }, [events, search])

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-icon">GF</span>
          <div className="brand-text">
            <h1>GROUNDFLOOR</h1>
            <div className="brand-sub">NYC · Underground</div>
          </div>
        </div>
        <div className="topbar-right">
          <input
            className="search"
            placeholder="Search shows, venues…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {'Notification' in window && Notification.permission !== 'granted' && pushState !== 'denied' && (
            <button
              className="push-opt-in-btn"
              title="Get show notifications"
              onClick={async () => {
                setPushState('asking')
                const ok = await registerPushNotifications()
                setPushState(ok ? 'granted' : 'denied')
              }}
            >
              {pushState === 'asking' ? '…' : '🔔'}
            </button>
          )}
          {pushState === 'granted' && <span className="push-granted" title="Notifications on">🔔✓</span>}
          <div className="user-menu" onClick={onLogout} title="Log out">
            <span className="user-avatar">{user.displayName?.[0]?.toUpperCase() || user.username?.[0]?.toUpperCase()}</span>
            <span className="user-name">{user.displayName || user.username}</span>
          </div>
        </div>
      </header>

      <StatsBar events={events} />

      <nav className="tabs">
        {TABS.map(t => (
          <button
            key={t.id}
            className={`tab ${tab === t.id ? 'active' : ''} ${t.id === 'add' ? 'tab-add' : ''}`}
            onClick={() => t.id === 'add' ? setShowAdd(true) : setTab(t.id)}
          >
            <span className="tab-icon">{t.icon}</span>
            <span className="tab-label">{t.label}</span>
          </button>
        ))}
      </nav>

      <div className="main-content">
        {loading && <div className="loading">Loading shows…</div>}

        {!loading && tab === 'calendar' && (
          <Calendar events={filtered} onUpdate={updateEvent} />
        )}

        {!loading && tab === 'upcoming' && (
          <Scanner events={events} onUpdate={updateEvent} />
        )}

        {!loading && tab === 'social' && (
          <Social onUpdate={updateEvent} />
        )}

        {!loading && tab === 'card' && (
          <RaveCard />
        )}

        {!loading && tab === 'budget' && (
          <Budget events={events} onUpdate={updateEvent} />
        )}

        <footer className="footer">
          <span>GROUNDFLOOR · {events.length} shows tracked</span>
        </footer>
      </div>

      {showAdd && (
        <AddEventModal
          onClose={() => setShowAdd(false)}
          onCreate={createEvent}
        />
      )}
    </div>
  )
}

export default function App() {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('rave_user')
    return saved ? JSON.parse(saved) : null
  })
  const [token, setToken] = useState(() => localStorage.getItem('rave_token'))

  function handleLogin(user, token) {
    setUser(user)
    setToken(token)
  }

  function handleLogout() {
    if (token) {
      fetch(`${API_BASE}/api/auth/logout`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      }).catch(() => {})
    }
    localStorage.removeItem('rave_token')
    localStorage.removeItem('rave_user')
    setUser(null)
    setToken(null)
  }

  if (!user) {
    return <Login onLogin={handleLogin} />
  }

  return <AuthenticatedApp user={user} onLogout={handleLogout} />
}
