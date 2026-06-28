import React, { useState } from 'react'
import { parseDate, today as localToday } from '../dateUtils.js'
import GoingModal from './GoingModal.jsx'
import MaybeModal from './MaybeModal.jsx'

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

function formatDateRange(startStr, endStr) {
  const s = parseDate(startStr)
  const label = `${MONTHS[s.getMonth()]} ${s.getDate()}`
  if (!endStr) return label
  const e = parseDate(endStr)
  if (s.getMonth() === e.getMonth()) {
    return `${MONTHS[s.getMonth()]} ${s.getDate()}–${e.getDate()}`
  }
  return `${MONTHS[s.getMonth()]} ${s.getDate()} – ${MONTHS[e.getMonth()]} ${e.getDate()}`
}

function daysUntil(dateStr) {
  const today = localToday()
  const dt = parseDate(dateStr)
  const diff = Math.round((dt - today) / 86400000)
  if (diff < 0) return null
  if (diff === 0) return 'Today'
  if (diff === 1) return 'Tomorrow'
  if (diff < 7) return `${diff} days`
  if (diff < 30) return `${Math.round(diff/7)}w away`
  if (diff < 365) return `${Math.round(diff/30)}mo away`
  return `${Math.round(diff/365)}y away`
}

export default function FestivalView({ events, onUpdate }) {
  const [goingTarget, setGoingTarget] = useState(null)
  const [maybeTarget, setMaybeTarget] = useState(null)
  const [showAddHint, setShowAddHint] = useState(false)
  const today = localToday()

  // Separate festivals from local multi-day events
  const festivals = events
    .filter(e => e.isFestival)
    .sort((a, b) => a.date.localeCompare(b.date))

  const upcoming = festivals.filter(e => {
    const end = e.festivalEndDate ? parseDate(e.festivalEndDate) : parseDate(e.date)
    return end >= today
  })
  const past = festivals.filter(e => {
    const end = e.festivalEndDate ? parseDate(e.festivalEndDate) : parseDate(e.date)
    return end < today
  })

  function handleGoing(event) {
    if (event.interest === 'going') {
      onUpdate(event.id, { interest: null })
    } else {
      setGoingTarget(event)
    }
  }

  function handleMaybe(event) {
    if (event.interest === 'maybe') {
      onUpdate(event.id, { interest: null })
    } else {
      setMaybeTarget(event)
    }
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

      <div className="festival-wrap">
        <div className="festival-header">
          <h2 className="festival-title">FESTIVALS</h2>
          <p className="festival-sub">Multi-day events · Travel · International</p>
        </div>

        {upcoming.length === 0 && past.length === 0 ? (
          <div className="festival-empty">
            <div className="festival-empty-icon">🌍</div>
            <div className="festival-empty-title">No festivals tracked yet</div>
            <div className="festival-empty-sub">
              Add a festival event and check "Multi-day / Festival" to see it here.
              <br />Dekmantel, Movement, Boiler Room, EDC — any multi-day event qualifies.
            </div>
          </div>
        ) : null}

        {upcoming.length > 0 && (
          <div className="festival-section">
            <div className="festival-section-label">UPCOMING</div>
            {upcoming.map(e => <FestivalCard key={e.id} event={e} onGoing={handleGoing} onMaybe={handleMaybe} />)}
          </div>
        )}

        {past.length > 0 && (
          <div className="festival-section">
            <div className="festival-section-label">PAST</div>
            {past.map(e => <FestivalCard key={e.id} event={e} onGoing={handleGoing} onMaybe={handleMaybe} isPast />)}
          </div>
        )}
      </div>
    </>
  )
}

function FestivalCard({ event: e, onGoing, onMaybe, isPast }) {
  const dateLabel = formatDateRange(e.date, e.festivalEndDate)
  const countdown = !isPast ? daysUntil(e.date) : null
  const interest = e.interest || 'none'
  const attended = e.attended

  // Duration
  let duration = null
  if (e.festivalEndDate) {
    const s = parseDate(e.date)
    const end = parseDate(e.festivalEndDate)
    const days = Math.round((end - s) / 86400000) + 1
    duration = `${days} days`
  }

  return (
    <div className={`festival-card ${interest} ${isPast ? 'past' : ''} ${attended ? 'attended' : ''}`}>
      {/* Top row: dates + countdown */}
      <div className="festival-card-top">
        <div className="festival-card-dates">
          <span className="festival-date-range">{dateLabel}</span>
          {duration && <span className="festival-duration">{duration}</span>}
        </div>
        {countdown && (
          <span className={`festival-countdown ${interest === 'going' ? 'going' : ''}`}>
            {countdown}
          </span>
        )}
        {isPast && attended && <span className="festival-attended-badge">✓ ATTENDED</span>}
      </div>

      {/* Name + location */}
      <div className="festival-card-name">{e.name}</div>
      <div className="festival-card-location">
        {e.locationCity && <span className="festival-city">📍 {e.locationCity}</span>}
        {e.venue && e.venue !== e.locationCity && (
          <span className="festival-venue">{e.venue}</span>
        )}
      </div>

      {/* Genres */}
      {(e.genres || []).length > 0 && (
        <div className="festival-card-genres">
          {e.genres.slice(0, 4).map(g => (
            <span key={g} className="genre-tag">{g}</span>
          ))}
        </div>
      )}

      {/* Cost */}
      {e.cost > 0 && (
        <div className="festival-card-cost">${e.cost}</div>
      )}

      {/* Description */}
      {e.description && (
        <div className="festival-card-desc">{e.description.slice(0, 160)}{e.description.length > 160 ? '…' : ''}</div>
      )}

      {/* Actions */}
      {!isPast && (
        <div className="festival-card-actions">
          <button
            className={`interest-btn going ${interest === 'going' ? 'on' : ''}`}
            onClick={() => onGoing(e)}
          >GOING</button>
          <button
            className={`interest-btn maybe ${interest === 'maybe' ? 'on' : ''}`}
            onClick={() => onMaybe(e)}
          >MAYBE</button>
        </div>
      )}
    </div>
  )
}
