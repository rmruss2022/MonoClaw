import React, { useMemo } from 'react'
import EventCard from './EventCard.jsx'
import { parseDate } from '../dateUtils.js'

function getMonday(d) {
  const date = parseDate(d)
  const day = date.getDay()
  const diff = date.getDate() - day + (day === 0 ? -6 : 1)
  date.setDate(diff)
  date.setHours(0, 0, 0, 0)
  return date
}

export default function WeekScan({ events, onUpdate, onDelete }) {
  // Build list of weeks: current + next 3 (4 weeks total)
  const weeks = useMemo(() => {
    const now = new Date()
    const result = []
    const thisMon = getMonday(now)
    for (let i = 0; i < 4; i++) {
      const start = new Date(thisMon)
      start.setDate(start.getDate() + i * 7)
      const end = new Date(start)
      end.setDate(end.getDate() + 6)
      const startStr = start.toISOString().split('T')[0]
      const endStr = end.toISOString().split('T')[0]
      const weekEvents = events.filter(e => {
        const ed = parseDate(e.date)
        return ed >= start && ed <= end
      })
      result.push({
        start, end, startStr, endStr,
        events: weekEvents,
        label: i === 0 ? 'THIS WEEK' : i === 1 ? 'NEXT WEEK' : `WEEK +${i}`
      })
    }
    return result
  }, [events])

  return (
    <div className="week-scan">
      <div className="ws-intro">
        <h2>🔍 Week Scan</h2>
        <p>Looking ahead 4 weeks. Triaged shows show as <span className="legend-going">GOING</span>, <span className="legend-maybe">MAYBE</span>, or untriaged. Pick what you actually want to hit.</p>
      </div>
      {weeks.map(w => (
        <div key={w.startStr} className="ws-week">
          <div className="ws-week-head">
            <div>
              <span className="ws-week-label">{w.label}</span>
              <h3>
                {w.start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                {' – '}
                {w.end.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              </h3>
            </div>
            <div className="ws-week-stats">
              <span className="ws-stat going">🎯 {w.events.filter(e => e.interest === 'going').length} going</span>
              <span className="ws-stat maybe">🤔 {w.events.filter(e => e.interest === 'maybe').length} maybe</span>
              <span className="ws-stat open">👀 {w.events.length - w.events.filter(e => e.interest).length} untriaged</span>
            </div>
          </div>
          {w.events.length === 0 ? (
            <div className="ws-empty">No shows scheduled this week.</div>
          ) : (
            <div className="event-grid">
              {w.events.map(e => <EventCard key={e.id} event={e} onUpdate={onUpdate} onDelete={onDelete} />)}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}