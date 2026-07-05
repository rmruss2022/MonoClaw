import React, { useState, useEffect, useCallback } from 'react'
import { authFetch } from '../auth.js'
import { parseDate } from '../dateUtils.js'
import GoingModal from './GoingModal.jsx'
import MaybeModal from './MaybeModal.jsx'

const DATE_RANGES = [
  { key: 'week', label: 'THIS WEEK' },
  { key: 'month', label: 'THIS MONTH' },
  { key: 'all', label: 'ALL' }
]

const PRICE_OPTIONS = [
  { key: 'any', label: 'ANY', value: null },
  { key: 'free', label: 'FREE', value: 0 },
  { key: '30', label: 'UNDER $30', value: 30 },
  { key: '50', label: 'UNDER $50', value: 50 }
]

export default function Explore({ onUpdate, onShowDetail }) {
  const [events, setEvents] = useState([])
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [filterVenues, setFilterVenues] = useState([])
  const [filterGenres, setFilterGenres] = useState([])

  const [genre, setGenre] = useState('')
  const [venue, setVenue] = useState('')
  const [dateRange, setDateRange] = useState('all')
  const [priceKey, setPriceKey] = useState('any')

  const [goingTarget, setGoingTarget] = useState(null)
  const [maybeTarget, setMaybeTarget] = useState(null)

  const fetchEvents = useCallback(async (pageNum = 1, append = false) => {
    if (pageNum === 1) setLoading(true)
    else setLoadingMore(true)
    try {
      const priceOpt = PRICE_OPTIONS.find(p => p.key === priceKey)
      const params = new URLSearchParams()
      params.set('page', String(pageNum))
      params.set('limit', '20')
      params.set('dateRange', dateRange)
      if (genre) params.set('genre', genre)
      if (venue) params.set('venue', venue)
      if (priceOpt && priceOpt.value !== null) params.set('maxPrice', String(priceOpt.value))

      const r = await fetch(`/api/explore?${params.toString()}`)
      const d = await r.json()
      if (d.success) {
        setEvents(prev => append ? [...prev, ...(d.events || [])] : (d.events || []))
        setHasMore(!!d.hasMore)
        setTotal(d.total || 0)
        setFilterVenues(d.filters?.venues || [])
        setFilterGenres(d.filters?.genres || [])
        setPage(pageNum)
      }
    } catch (e) {
      console.error('explore load failed', e)
    }
    setLoading(false)
    setLoadingMore(false)
  }, [genre, venue, dateRange, priceKey])

  useEffect(() => { fetchEvents(1, false) }, [fetchEvents])

  async function skip(eventId, ev) {
    ev.stopPropagation()
    setEvents(prev => prev.filter(e => e.id !== eventId))
    try {
      // 'skip' is just a local removal — mark interest 'skip' so it stays gone
      await authFetch(`/api/events/${encodeURIComponent(eventId)}`, {
        method: 'PATCH',
        body: JSON.stringify({ interest: 'skip' })
      })
      onUpdate && onUpdate(eventId, { interest: 'skip' })
    } catch (e) {
      console.error('skip failed', e)
    }
  }

  function openGoing(event, ev) {
    ev.stopPropagation()
    setGoingTarget(event)
  }

  function openMaybe(event, ev) {
    ev.stopPropagation()
    setMaybeTarget(event)
  }

  function handleConfirm(patch, kind) {
    const target = kind === 'going' ? goingTarget : maybeTarget
    if (!target) return
    onUpdate(target.id, patch)
    setEvents(prev => prev.filter(e => e.id !== target.id))
    if (kind === 'going') setGoingTarget(null)
    else setMaybeTarget(null)
  }

  return (
    <>
      {goingTarget && (
        <GoingModal
          event={goingTarget}
          onConfirm={p => handleConfirm(p, 'going')}
          onCancel={() => setGoingTarget(null)}
        />
      )}
      {maybeTarget && (
        <MaybeModal
          event={maybeTarget}
          onConfirm={p => handleConfirm(p, 'maybe')}
          onCancel={() => setMaybeTarget(null)}
        />
      )}

      <div className="explore-wrap">
        <div className="explore-header">
          <h2>EXPLORE</h2>
          <p>Upcoming shows you haven't decided on.</p>
        </div>

        <div className="explore-filters">
          <div className="explore-filter-group">
            <div className="explore-filter-label">WHEN</div>
            <div className="explore-pill-row">
              {DATE_RANGES.map(d => (
                <button
                  key={d.key}
                  className={`explore-pill ${dateRange === d.key ? 'on' : ''}`}
                  onClick={() => setDateRange(d.key)}
                >{d.label}</button>
              ))}
            </div>
          </div>

          <div className="explore-filter-group">
            <div className="explore-filter-label">PRICE</div>
            <div className="explore-pill-row">
              {PRICE_OPTIONS.map(p => (
                <button
                  key={p.key}
                  className={`explore-pill ${priceKey === p.key ? 'on' : ''}`}
                  onClick={() => setPriceKey(p.key)}
                >{p.label}</button>
              ))}
            </div>
          </div>

          <div className="explore-filter-group">
            <div className="explore-filter-label">GENRE</div>
            <select
              className="explore-select"
              value={genre}
              onChange={e => setGenre(e.target.value)}
            >
              <option value="">ALL GENRES</option>
              {filterGenres.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          </div>

          <div className="explore-filter-group">
            <div className="explore-filter-label">VENUE</div>
            <select
              className="explore-select"
              value={venue}
              onChange={e => setVenue(e.target.value)}
            >
              <option value="">ALL VENUES</option>
              {filterVenues.map(v => <option key={v} value={v}>{v}</option>)}
            </select>
          </div>
        </div>

        <div className="explore-count">
          {loading ? 'Loading…' : `${total} show${total === 1 ? '' : 's'}`}
        </div>

        {loading && <div className="loading">Loading shows…</div>}

        {!loading && events.length === 0 && (
          <div className="rec-empty-card">
            <div className="rec-empty-title">No upcoming events</div>
            <p className="rec-empty-sub">
              Run a scan to discover new shows, or adjust your filters.
            </p>
          </div>
        )}

        {!loading && events.length > 0 && (
          <div className="explore-list">
            {events.map(e => {
              const dt = parseDate(e.date)
              return (
                <div
                  key={e.id}
                  className="explore-card"
                  onClick={() => onShowDetail && onShowDetail(e)}
                >
                  <div className="explore-date-block">
                    <div className="explore-date-mon">{dt.toLocaleDateString('en-US', { month: 'short' }).toUpperCase()}</div>
                    <div className="explore-date-day">{dt.getDate()}</div>
                    <div className="explore-date-dow">{dt.toLocaleDateString('en-US', { weekday: 'short' }).toUpperCase()}</div>
                  </div>

                  <div className="explore-body">
                    <h3 className="explore-name">{e.name}</h3>
                    <div className="explore-venue">{e.venue}</div>
                    {(e.genres || []).length > 0 && (
                      <div className="explore-genres">
                        {e.genres.slice(0, 3).map(g => <span key={g} className="genre-tag">{g}</span>)}
                      </div>
                    )}
                    {e.cost > 0 && <div className="explore-cost">${e.cost}</div>}
                  </div>

                  <div className="explore-actions">
                    <button className="explore-btn going" onClick={ev => openGoing(e, ev)}>GOING</button>
                    <button className="explore-btn maybe" onClick={ev => openMaybe(e, ev)}>MAYBE</button>
                    <button className="explore-btn skip" onClick={ev => skip(e.id, ev)}>SKIP</button>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {!loading && hasMore && (
          <button
            className="explore-load-more"
            disabled={loadingMore}
            onClick={() => fetchEvents(page + 1, true)}
          >
            {loadingMore ? 'LOADING…' : 'LOAD MORE'}
          </button>
        )}
      </div>
    </>
  )
}
