import React, { useState, useEffect } from 'react'
import { authFetch } from '../auth.js'
import { parseDate } from '../dateUtils.js'
import GoingModal from './GoingModal.jsx'

function ScoreSquares({ score }) {
  // Map 0..1 → 1..5 filled squares
  const filled = Math.max(1, Math.round(score * 5))
  return (
    <div className="rec-score" aria-label={`Match score ${filled}/5`}>
      {[0, 1, 2, 3, 4].map(i => (
        <span key={i} className={`rec-score-sq ${i < filled ? 'on' : ''}`} />
      ))}
    </div>
  )
}

export default function Recommended({ onUpdate, onShowDetail }) {
  const [items, setItems] = useState([])
  const [hasHistory, setHasHistory] = useState(true)
  const [attendedCount, setAttendedCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [goingTarget, setGoingTarget] = useState(null)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const r = await fetch('/api/recommendations')
      const d = await r.json()
      if (d.success) {
        setItems(d.items || [])
        setHasHistory(d.hasHistory)
        setAttendedCount(d.attendedCount || 0)
      }
    } catch (e) {
      console.error('recommendations load failed', e)
    }
    setLoading(false)
  }

  async function dismiss(eventId, ev) {
    ev.stopPropagation()
    setItems(prev => prev.filter(it => it.event.id !== eventId))
    try {
      await authFetch(`/api/recommendations/dismiss/${encodeURIComponent(eventId)}`, { method: 'POST' })
    } catch (e) {
      console.error('dismiss failed', e)
    }
  }

  function openGoing(event, ev) {
    ev.stopPropagation()
    setGoingTarget(event)
  }

  function handleGoingConfirm(patch) {
    if (!goingTarget) return
    onUpdate(goingTarget.id, patch)
    // Remove from recs list once committed
    setItems(prev => prev.filter(it => it.event.id !== goingTarget.id))
    setGoingTarget(null)
  }

  return (
    <>
      {goingTarget && (
        <GoingModal
          event={goingTarget}
          onConfirm={handleGoingConfirm}
          onCancel={() => setGoingTarget(null)}
        />
      )}

      <div className="rec-wrap">
        <div className="rec-header">
          <h2>FOR YOU</h2>
          <p>Picks tuned to your scene history.</p>
        </div>

        {loading && <div className="loading">Scoring shows…</div>}

        {!loading && !hasHistory && (
          <div className="rec-empty-card">
            <div className="rec-empty-title">No history yet</div>
            <p className="rec-empty-sub">
              Mark shows as attended to unlock recommendations tuned to your taste.
            </p>
          </div>
        )}

        {!loading && hasHistory && items.length === 0 && (
          <div className="rec-empty-card">
            <div className="rec-empty-title">All caught up</div>
            <p className="rec-empty-sub">
              You've already marked everything we'd suggest. Run a scan to discover new shows.
            </p>
          </div>
        )}

        {!loading && items.length > 0 && (
          <div className="rec-list">
            {items.map(it => {
              const e = it.event
              const dt = parseDate(e.date)
              return (
                <div
                  key={e.id}
                  className="rec-card"
                  onClick={() => onShowDetail && onShowDetail(e)}
                >
                  <div className="rec-date-block">
                    <div className="rec-date-mon">{dt.toLocaleDateString('en-US', { month: 'short' }).toUpperCase()}</div>
                    <div className="rec-date-day">{dt.getDate()}</div>
                    <div className="rec-date-dow">{dt.toLocaleDateString('en-US', { weekday: 'short' }).toUpperCase()}</div>
                  </div>

                  <div className="rec-body">
                    <h3 className="rec-name">{e.name}</h3>
                    <div className="rec-venue">{e.venue}</div>
                    {(e.genres || []).length > 0 && (
                      <div className="rec-genres">
                        {e.genres.map(g => <span key={g} className="genre-tag">{g}</span>)}
                      </div>
                    )}
                    <div className="rec-meta-row">
                      {it.reason && <span className="rec-reason">{it.reason}</span>}
                      <ScoreSquares score={it.score} />
                      {e.cost > 0 && <span className="rec-cost">${e.cost}</span>}
                    </div>
                  </div>

                  <div className="rec-actions">
                    <button
                      className="rec-btn-going"
                      onClick={(ev) => openGoing(e, ev)}
                    >GOING</button>
                    <button
                      className="rec-btn-dismiss"
                      onClick={(ev) => dismiss(e.id, ev)}
                    >DISMISS</button>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {!loading && hasHistory && (
          <div className="rec-foot">
            Scored against {attendedCount} attended show{attendedCount === 1 ? '' : 's'}.
          </div>
        )}
      </div>
    </>
  )
}
