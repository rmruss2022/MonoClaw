import React, { useState, useEffect } from 'react'
import { authFetch } from '../auth.js'
import { parseDate } from '../dateUtils.js'

const TIER_COLORS = {
  rookie: '#888',
  regular: '#00aaff',
  headliner: '#ff2d92',
  legend: '#a855f7',
  icon: '#fff700'
}

export default function Social({ onUpdate }) {
  const [feed, setFeed] = useState(null)
  const [loading, setLoading] = useState(true)
  const [perks, setPerks] = useState([])
  const [card, setCard] = useState(null)

  useEffect(() => {
    loadAll()
  }, [])

  async function loadAll() {
    setLoading(true)
    try {
      const [f, r] = await Promise.all([
        authFetch('/api/social').then(r => r.json()),
        authFetch('/api/rave-card').then(r => r.json())
      ])
      setFeed(f)
      setPerks(r.perks || [])
      setCard(r.card)
    } catch (e) {
      console.error('Load failed', e)
    }
    setLoading(false)
  }

  async function setInterest(eventId, level) {
    try {
      await authFetch(`/api/events/${eventId}`, {
        method: 'PATCH',
        body: JSON.stringify({ interest: level })
      })
      onUpdate(eventId, { interest: level })
      loadAll()
    } catch (e) {
      console.error(e)
    }
  }

  if (loading) return <div className="loading">Loading social feed...</div>
  if (!feed) return <div className="loading">Failed to load</div>

  return (
    <div className="social-wrap">
      <div className="social-header">
        <h2>🕺 Where the scene is going next</h2>
        <p>Trending shows this week · based on top picks and genre diversity</p>
      </div>

      {card && perks.length > 0 && (
        <div className="social-tier-banner" style={{ borderColor: card.tierColor }}>
          <div className="tier-banner-left">
            <span className="tier-banner-emoji">{card.tierEmoji}</span>
            <div>
              <div className="tier-banner-tier" style={{ color: card.tierColor }}>{card.tierLabel} MEMBER</div>
              <div className="tier-banner-sub">{perks.length} perks unlocked · {card.nextTier ? `${card.nextTier.remaining} to next tier` : 'Max tier'}</div>
            </div>
          </div>
          <div className="tier-banner-right">
            {perks.filter(p => p.tier_required === card.tier).slice(0, 2).map(p => (
              <div key={p.id} className="tier-banner-perk">
                <b>{p.venue}</b>: {p.title}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="social-feed">
        {feed.thisWeek.length === 0 && (
          <div className="empty">No upcoming shows this week.</div>
        )}
        {feed.thisWeek.map((e, i) => (
          <SocialEventCard key={e.id} event={e} rank={i + 1} onInterest={setInterest} />
        ))}
      </div>

      <div className="social-perks">
        <h3>🎁 Perks unlocked at your tier ({perks.length})</h3>
        <p className="section-help">Tap any perk to copy the code.</p>
        <div className="perk-grid">
          {perks.map(p => (
            <div
              key={p.id}
              className="perk-card"
              data-tier={p.tier_required}
              onClick={() => p.code && navigator.clipboard?.writeText(p.code)}
              title={p.code ? `Click to copy: ${p.code}` : ''}
            >
              <div className="perk-tier" style={{ background: TIER_COLORS[p.tier_required] }}>
                {p.tier_required.toUpperCase()}
              </div>
              <div className="perk-venue">📍 {p.venue}</div>
              <div className="perk-title">{p.title}</div>
              <div className="perk-desc">{p.description}</div>
              {p.code && (
                <div className="perk-code">
                  <span>CODE:</span> <code>{p.code}</code>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function SocialEventCard({ event, rank, onInterest }) {
  const dt = parseDate(event.date)
  const dateStr = dt.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
  const genres = event.genres || []

  return (
    <div className="social-evt">
      <div className="social-rank">#{rank}</div>
      <div className="social-evt-date">{dateStr}</div>
      <div className="social-evt-info">
        <div className="social-evt-name">{event.name}</div>
        <div className="social-evt-meta">
          <span>📍 {event.venue}</span>
          {event.cost > 0 && <span> · ${event.cost}</span>}
        </div>
        <div className="social-evt-genres">
          {genres.map(g => <span key={g} className="genre-tag">{g}</span>)}
        </div>
      </div>
      <div className="social-evt-actions">
        <button className="interest-btn going" onClick={() => onInterest(event.id, 'going')}>🎯 GOING</button>
        <button className="interest-btn maybe" onClick={() => onInterest(event.id, 'maybe')}>🤔 MAYBE</button>
      </div>
    </div>
  )
}