import React from 'react'
import { parseDate, today as localToday } from '../dateUtils.js'

export default function StatsBar({ events }) {
  const stats = React.useMemo(() => {
    const td = localToday()
    const goingList = events.filter(e => e.interest === 'going' && !e.attended && parseDate(e.date) >= td)
    const maybeList = events.filter(e => e.interest === 'maybe' && parseDate(e.date) >= td)
    const attendedList = events.filter(e => e.attended)
    const upcoming = events.filter(e => parseDate(e.date) >= td)

    // SPENT = sum of cost on attended shows
    const spent = attendedList.reduce((s, e) => s + (e.cost || 0), 0)
    // COMMITTED = sum of cost on future Going shows (not yet attended)
    const committed = goingList.reduce((s, e) => s + (e.cost || 0), 0)

    return {
      going: goingList.length,
      maybe: maybeList.length,
      attended: attendedList.length,
      upcoming: upcoming.length,
      spent,
      committed
    }
  }, [events])

  return (
    <div className="statsbar">
      <div className="stat">
        <div className={`stat-val ${stats.going > 0 ? 'has-value' : ''}`}>{stats.going}</div>
        <div className="stat-label">GOING</div>
      </div>
      <div className="stat">
        <div className={`stat-val ${stats.maybe > 0 ? 'has-value' : ''}`}>{stats.maybe}</div>
        <div className="stat-label">MAYBE</div>
      </div>
      <div className="stat">
        <div className={`stat-val ${stats.attended > 0 ? 'has-value' : ''}`}>{stats.attended}</div>
        <div className="stat-label">ATTENDED</div>
      </div>
      <div className="stat">
        <div className={`stat-val ${stats.committed > 0 ? 'has-value' : ''}`}>${stats.committed}</div>
        <div className="stat-label">COMMITTED</div>
      </div>
      <div className="stat">
        <div className={`stat-val ${stats.spent > 0 ? 'has-value' : ''}`}>${stats.spent}</div>
        <div className="stat-label">SPENT</div>
      </div>
    </div>
  )
}
