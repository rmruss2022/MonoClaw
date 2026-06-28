import React, { useState, useMemo, useEffect, useRef } from 'react'
import { parseDate, today as localToday } from '../dateUtils.js'
import GoingModal from './GoingModal.jsx'
import MaybeModal from './MaybeModal.jsx'
import FestivalView from './FestivalView.jsx'

const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December']
const DOW = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']

export default function Calendar({ events, onUpdate }) {
  const today = localToday()
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth())
  const [selectedDay, setSelectedDay] = useState(today.getDate())
  const [view, setView] = useState('going') // 'going' | 'all' | 'festivals'
  const [goingTarget, setGoingTarget] = useState(null)   // event pending going modal
  const [maybeTarget, setMaybeTarget] = useState(null)   // event pending maybe modal
  const todayRef = useRef(null)

  useEffect(() => {
    if (todayRef.current) {
      todayRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [])

  // Filter events based on view tab
  const filteredEvents = useMemo(() => {
    if (view === 'going') return events.filter(e => e.interest === 'going' && !e.isFestival)
    if (view === 'all') return events.filter(e => !e.isFestival)
    return events // festivals handled separately in FestivalView
  }, [events, view])

  // Build calendar grid
  const grid = useMemo(() => {
    const first = new Date(year, month, 1)
    const startDay = first.getDay()
    const daysInMonth = new Date(year, month + 1, 0).getDate()
    const cells = []
    for (let i = 0; i < startDay; i++) cells.push(null)
    for (let d = 1; d <= daysInMonth; d++) cells.push(d)
    while (cells.length < 42) cells.push(null)
    return cells
  }, [year, month])

  // Index filtered events by day
  const eventsByDay = useMemo(() => {
    const m = {}
    for (const e of filteredEvents) {
      const dt = parseDate(e.date)
      if (dt.getFullYear() === year && dt.getMonth() === month) {
        const d = dt.getDate()
        if (!m[d]) m[d] = []
        m[d].push(e)
      }
    }
    return m
  }, [filteredEvents, year, month])

  const INTEREST_ORDER = { going: 0, maybe: 1, interested: 2 }
  function sortEvents(list) {
    return [...list].sort((a, b) => {
      const ai = INTEREST_ORDER[a.interest] ?? 3
      const bi = INTEREST_ORDER[b.interest] ?? 3
      return ai - bi || a.name.localeCompare(b.name)
    })
  }
  const selectedDayEvents = sortEvents(selectedDay ? (eventsByDay[selectedDay] || []) : [])

  function prev() {
    if (month === 0) { setYear(y => y - 1); setMonth(11) }
    else setMonth(m => m - 1)
    setSelectedDay(null)
  }
  function next() {
    if (month === 11) { setYear(y => y + 1); setMonth(0) }
    else setMonth(m => m + 1)
    setSelectedDay(null)
  }
  function goToday() {
    setYear(today.getFullYear())
    setMonth(today.getMonth())
    setSelectedDay(today.getDate())
    setTimeout(() => {
      if (todayRef.current) todayRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 50)
  }
  const isCurrentMonth = year === today.getFullYear() && month === today.getMonth()

  function quickSetInterest(event, interest, ev) {
    ev.stopPropagation()
    if (interest === 'going') {
      setGoingTarget(event)
    } else if (interest === 'maybe') {
      setMaybeTarget(event)
    } else {
      onUpdate(event.id, { interest })
    }
  }

  // Count going events in current month for tab badge
  const goingThisMonth = useMemo(() => {
    return events.filter(e => {
      if (e.interest !== 'going') return false
      const dt = parseDate(e.date)
      return dt.getFullYear() === year && dt.getMonth() === month
    }).length
  }, [events, year, month])

  const allThisMonth = useMemo(() => {
    return events.filter(e => {
      if (e.isFestival) return false
      const dt = parseDate(e.date)
      return dt.getFullYear() === year && dt.getMonth() === month
    }).length
  }, [events, year, month])

  const festivalCount = useMemo(() => {
    return events.filter(e => e.isFestival).length
  }, [events])

  // If festival view, render FestivalView instead of calendar grid
  if (view === 'festivals') {
    return (
      <>
        {goingTarget && (
          <GoingModal
            event={goingTarget}
            onConfirm={patch => { onUpdate(goingTarget.id, patch); setGoingTarget(null) }}
            onCancel={() => setGoingTarget(null)}
          />
        )}
        {maybeTarget && (
          <MaybeModal
            event={maybeTarget}
            onConfirm={patch => { onUpdate(maybeTarget.id, patch); setMaybeTarget(null) }}
            onCancel={() => setMaybeTarget(null)}
          />
        )}
        <div className="cal-wrap">
          <div className="cal-tabs">
            <button className="cal-tab" onClick={() => setView('going')}>My Shows</button>
            <button className="cal-tab" onClick={() => setView('all')}>All Local</button>
            <button className="cal-tab active">
              Festivals
              {festivalCount > 0 && <span className="cal-tab-badge">{festivalCount}</span>}
            </button>
          </div>
          <FestivalView events={events} onUpdate={onUpdate} />
        </div>
      </>
    )
  }

  return (
    <>
    {goingTarget && (
      <GoingModal
        event={goingTarget}
        onConfirm={patch => { onUpdate(goingTarget.id, patch); setGoingTarget(null) }}
        onCancel={() => setGoingTarget(null)}
      />
    )}
    {maybeTarget && (
      <MaybeModal
        event={maybeTarget}
        onConfirm={patch => { onUpdate(maybeTarget.id, patch); setMaybeTarget(null) }}
        onCancel={() => setMaybeTarget(null)}
      />
    )}
    <div className="cal-wrap">
      {/* View tab selector */}
      <div className="cal-tabs">
        <button
          className={`cal-tab ${view === 'going' ? 'active' : ''}`}
          onClick={() => setView('going')}
        >
          My Shows
          {goingThisMonth > 0 && <span className="cal-tab-badge">{goingThisMonth}</span>}
        </button>
        <button
          className={`cal-tab ${view === 'all' ? 'active' : ''}`}
          onClick={() => setView('all')}
        >
          All Local
          {allThisMonth > 0 && <span className="cal-tab-badge cal-tab-badge-muted">{allThisMonth}</span>}
        </button>
        <button
          className={`cal-tab ${view === 'festivals' ? 'active' : ''}`}
          onClick={() => setView('festivals')}
        >
          Festivals
          {festivalCount > 0 && <span className="cal-tab-badge cal-tab-badge-muted">{festivalCount}</span>}
        </button>
      </div>

      <div className="cal-header">
        <button className="cal-nav" onClick={prev}>‹</button>
        <div className="cal-header-center">
          <h2>{MONTHS[month]} {year}</h2>
          {!isCurrentMonth && (
            <button className="cal-today-btn" onClick={goToday}>Today</button>
          )}
        </div>
        <button className="cal-nav" onClick={next}>›</button>
      </div>

      <div className="cal-grid">
        {DOW.map(d => <div key={d} className="cal-dow">{d}</div>)}
        {grid.map((day, i) => {
          if (!day) return <div key={i} className="cal-day empty"></div>
          const isToday = day === today.getDate() && month === today.getMonth() && year === today.getFullYear()
          const isSelected = day === selectedDay
          const dayEvents = sortEvents(eventsByDay[day] || [])
          const hasGoing = dayEvents.some(e => e.interest === 'going')
          const hasMaybe = dayEvents.some(e => e.interest === 'maybe')
          return (
            <div
              key={i}
              ref={isToday ? todayRef : null}
              className={`cal-day ${isToday ? 'today' : ''} ${isSelected ? 'selected' : ''} ${dayEvents.length ? 'has-events' : ''}`}
              onClick={() => setSelectedDay(day)}
            >
              <div className="cal-day-num">{day}</div>
              <div className="cal-day-events">
                {dayEvents.slice(0, 3).map(e => (
                  <div
                    key={e.id}
                    className="cal-evt-dot"
                    title={`${e.name} — ${e.venue}`}
                  >
                    <span className="cal-evt-name">{e.name}</span>
                  </div>
                ))}
                {dayEvents.length > 3 && <div className="cal-evt-more">+{dayEvents.length - 3} more</div>}
              </div>
              {(hasGoing || hasMaybe) && (
                <div className="cal-day-marks">
                  {hasGoing && <span className="dot going" title="Going"></span>}
                  {hasMaybe && <span className="dot maybe" title="Maybe"></span>}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {selectedDay && (
        <div className="cal-day-detail">
          <div className="cal-day-detail-head">
            <h3>{MONTHS[month]} {selectedDay}, {year}</h3>
            <button className="close" onClick={() => setSelectedDay(null)}>×</button>
          </div>
          {selectedDayEvents.length === 0 && (
            <div className="empty">
              {view === 'going'
                ? <span>No shows you're going to this day. <button className="link-btn" onClick={() => setView('all')}>See all local shows →</button></span>
                : 'No shows this day.'}
            </div>
          )}
          {selectedDayEvents.map(e => (
            <div key={e.id} className="cal-day-evt">
              <div className="cal-day-evt-info">
                <div className="cal-day-evt-name">{e.name}</div>
                <div className="cal-day-evt-meta">{e.venue} · {e.dayOfWeek} · {(e.genres || []).join(', ')}</div>
                <div className="cal-day-evt-desc">{e.description}</div>
              </div>
              <div className="cal-day-evt-actions">
                <button
                  className={`interest-btn going ${e.interest === 'going' ? 'on' : ''}`}
                  onClick={(ev) => quickSetInterest(e, e.interest === 'going' ? null : 'going', ev)}
                >GOING</button>
                <button
                  className={`interest-btn maybe ${e.interest === 'maybe' ? 'on' : ''}`}
                  onClick={(ev) => quickSetInterest(e, e.interest === 'maybe' ? null : 'maybe', ev)}
                >MAYBE</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
    </>
  )
}
