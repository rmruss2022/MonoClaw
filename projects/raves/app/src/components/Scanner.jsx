import React, { useState, useEffect, useMemo } from 'react'
import { authFetch } from '../auth.js'
import { parseDate, todayStr } from '../dateUtils.js'
import GoingModal from './GoingModal.jsx'
import MaybeModal from './MaybeModal.jsx'

const PERIODS = [
  { label: '2 WK', days: 14 },
  { label: '1 MO', days: 30 },
  { label: '3 MO', days: 90 },
  { label: 'ALL', days: 365 },
]

function weekLabel(dateStr) {
  const dt = parseDate(dateStr)
  const mon = new Date(dt)
  mon.setDate(dt.getDate() - ((dt.getDay() + 6) % 7))
  const sun = new Date(mon)
  sun.setDate(mon.getDate() + 6)
  const fmt = d => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  return `${fmt(mon)} – ${fmt(sun)}`
}

function weekKey(dateStr) {
  const dt = parseDate(dateStr)
  const mon = new Date(dt)
  mon.setDate(dt.getDate() - ((dt.getDay() + 6) % 7))
  const y = mon.getFullYear()
  const m = String(mon.getMonth() + 1).padStart(2, '0')
  const d = String(mon.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

const INTEREST_LABELS = { going: 'GOING', maybe: 'MAYBE', interested: 'INTERESTED' }
const GENRE_COLORS = ['#2A2A2A', '#2A2A2A', '#2A2A2A', '#2A2A2A', '#2A2A2A']

export default function Scanner({ events: allEvents, onUpdate }) {
  const [period, setPeriod] = useState(14)
  const [search, setSearch] = useState('')
  const [filterInterest, setFilterInterest] = useState('all')
  const [lastScan, setLastScan] = useState(null)

  useEffect(() => {
    authFetch('/api/scans').then(r => r.json()).then(d => {
      if (d.success && d.scans.length > 0) setLastScan(d.scans[0])
    }).catch(() => {})
  }, [])

  const today = todayStr()
  const cutoffDate = new Date(today + 'T12:00:00')
  cutoffDate.setDate(cutoffDate.getDate() + period)
  const cutoffStr = cutoffDate.toISOString().slice(0, 10)

  const upcoming = useMemo(() => {
    let list = (allEvents || []).filter(e => e.date >= today && e.date <= cutoffStr)
    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter(e =>
        e.name.toLowerCase().includes(q) ||
        (e.venue || '').toLowerCase().includes(q) ||
        (e.genres || []).some(g => g.toLowerCase().includes(q))
      )
    }
    if (filterInterest !== 'all') {
      if (filterInterest === 'none') list = list.filter(e => !e.interest)
      else list = list.filter(e => e.interest === filterInterest)
    }
    return list.sort((a, b) => a.date.localeCompare(b.date))
  }, [allEvents, period, search, filterInterest, today, cutoffStr])

  // Group by week
  const weeks = useMemo(() => {
    const groups = {}
    for (const e of upcoming) {
      const k = weekKey(e.date)
      if (!groups[k]) groups[k] = { key: k, label: weekLabel(e.date), events: [] }
      groups[k].events.push(e)
    }
    return Object.values(groups).sort((a, b) => a.key.localeCompare(b.key))
  }, [upcoming])

  return (
    <div className="upcoming-wrap">
      {/* Header */}
      <div className="upcoming-header">
        <div>
          <h2>Upcoming Shows</h2>
          {lastScan && (
            <div className="upcoming-last-scan">
              Last scan: {new Date(lastScan.scanned_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
              &nbsp;·&nbsp;{lastScan.total} events found
            </div>
          )}
        </div>
        <div className="upcoming-count">{upcoming.length} show{upcoming.length !== 1 ? 's' : ''}</div>
      </div>

      {/* Period filter */}
      <div className="upcoming-periods">
        {PERIODS.map(p => (
          <button
            key={p.days}
            className={`period-btn ${period === p.days ? 'active' : ''}`}
            onClick={() => setPeriod(p.days)}
          >{p.label}</button>
        ))}
      </div>

      {/* Search + interest filter */}
      <div className="upcoming-toolbar">
        <input
          className="upcoming-search"
          placeholder="Search shows, venues, genres…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <select
          className="upcoming-filter"
          value={filterInterest}
          onChange={e => setFilterInterest(e.target.value)}
        >
          <option value="all">All</option>
          <option value="going">Going</option>
          <option value="maybe">Maybe</option>
          <option value="interested">Interested</option>
          <option value="none">Untagged</option>
        </select>
      </div>

      {/* Results */}
      {upcoming.length === 0 && (
        <div className="upcoming-empty">
          <div className="upcoming-empty-icon">—</div>
          <div>No shows in this period</div>
          <div className="upcoming-empty-sub">Events are scanned weekly and added automatically</div>
        </div>
      )}

      {weeks.map(week => (
        <div key={week.key} className="upcoming-week">
          <div className="upcoming-week-label">{week.label}</div>
          <div className="upcoming-week-events">
            {week.events.map(e => (
              <UpcomingCard key={e.id} event={e} onUpdate={onUpdate} />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function UpcomingCard({ event: e, onUpdate }) {
  const [saving, setSaving] = useState(false)
  const [showGoing, setShowGoing] = useState(false)
  const [showMaybe, setShowMaybe] = useState(false)

  async function setInterest(level) {
    setSaving(true)
    const next = e.interest === level ? null : level
    try {
      await authFetch(`/api/events/${e.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ interest: next })
      })
      onUpdate(e.id, { interest: next })
    } catch (err) {
      console.error('update failed', err)
    }
    setSaving(false)
  }

  async function handleGoingConfirm(patch) {
    setSaving(true)
    try {
      await authFetch(`/api/events/${e.id}`, {
        method: 'PATCH',
        body: JSON.stringify(patch)
      })
      onUpdate(e.id, patch)
    } catch (err) {
      console.error('update failed', err)
    }
    setSaving(false)
    setShowGoing(false)
  }

  async function handleMaybeConfirm(patch) {
    setSaving(true)
    try {
      await authFetch(`/api/events/${e.id}`, {
        method: 'PATCH',
        body: JSON.stringify(patch)
      })
      onUpdate(e.id, patch)
    } catch (err) {
      console.error('update failed', err)
    }
    setSaving(false)
    setShowMaybe(false)
  }

  const interestClass = e.interest || 'none'
  const _dt = parseDate(e.date)
  const dayNum = _dt.getDate()
  const monthShort = _dt.toLocaleDateString('en-US', { month: 'short' }).toUpperCase()
  const dow = _dt.toLocaleDateString('en-US', { weekday: 'short' }).toUpperCase()

  return (
    <div className={`upcoming-card ${interestClass}`}>
      <div className="upcoming-card-date">
        <div className="upcoming-card-dow">{dow}</div>
        <div className="upcoming-card-day">{dayNum}</div>
        <div className="upcoming-card-month">{monthShort}</div>
      </div>
      <div className="upcoming-card-body">
        <div className="upcoming-card-name">{e.name}</div>
        <div className="upcoming-card-venue">{e.venue || 'TBA'}</div>
        {(e.genres || []).length > 0 && (
          <div className="upcoming-card-genres">
            {e.genres.slice(0, 3).map((g, i) => (
              <span key={g} className="genre-tag" style={{ borderColor: GENRE_COLORS[i % GENRE_COLORS.length] }}>{g}</span>
            ))}
          </div>
        )}
        {e.cost > 0 && <div className="upcoming-card-cost">${e.cost}</div>}
      </div>
      <div className="upcoming-card-actions">
        <button
          className={`uc-btn going ${e.interest === 'going' ? 'on' : ''}`}
          onClick={() => e.interest === 'going' ? setInterest('going') : setShowGoing(true)}
          disabled={saving}
          title="Going"
        >GO</button>
        <button
          className={`uc-btn maybe ${e.interest === 'maybe' ? 'on' : ''}`}
          onClick={() => e.interest === 'maybe' ? setInterest('maybe') : setShowMaybe(true)}
          disabled={saving}
          title="Maybe"
        >MB</button>
      </div>

      {showGoing && (
        <GoingModal
          event={e}
          onConfirm={handleGoingConfirm}
          onCancel={() => setShowGoing(false)}
        />
      )}
      {showMaybe && (
        <MaybeModal
          event={e}
          onConfirm={handleMaybeConfirm}
          onCancel={() => setShowMaybe(false)}
        />
      )}
    </div>
  )
}
