import React, { useState, useEffect } from 'react'
import { authFetch } from '../auth.js'

export default function RaveCard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    load()
  }, [])

  async function load() {
    setLoading(true)
    try {
      const r = await authFetch('/api/rave-card')
      const d = await r.json()
      setData(d)
    } catch (e) {
      console.error('Failed to load rave card', e)
    }
    setLoading(false)
  }

  if (loading) return <div className="loading">Loading Rave Card...</div>
  if (!data) return <div className="loading">Failed to load card</div>

  const { card, perks } = data

  return (
    <div className="rave-card-wrap">
      <div className="card-stage">
        <div className="card" style={{ '--tier-color': card.tierColor }}>
          <div className="card-glow"></div>
          <div className="card-header">
            <div className="card-brand">GROUNDFLOOR · NYC</div>
            <div className="card-tier" style={{ color: card.tierColor, textShadow: `0 0 12px ${card.tierColor}` }}>
              {card.tierEmoji} {card.tierLabel}
            </div>
          </div>
          <div className="card-emblem">
            <div className="card-emblem-glyph" style={{ color: card.tierColor, textShadow: `0 0 24px ${card.tierColor}` }}>
              {card.tierEmoji}
            </div>
            <div className="card-emblem-rings">
              <div className="card-ring r1"></div>
              <div className="card-ring r2"></div>
              <div className="card-ring r3"></div>
            </div>
          </div>
          <div className="card-name">MATTHEW</div>
          <div className="card-stats">
            <div className="card-stat">
              <div className="card-stat-val">{card.attended}</div>
              <div className="card-stat-lbl">SHOWS</div>
            </div>
            <div className="card-stat">
              <div className="card-stat-val">{card.venueCount}</div>
              <div className="card-stat-lbl">VENUES</div>
            </div>
            <div className="card-stat">
              <div className="card-stat-val">${card.totalSpent.toFixed(0)}</div>
              <div className="card-stat-lbl">SPENT</div>
            </div>
          </div>
          <div className="card-footer">
            <div>MEMBER SINCE {card.firstShow ? card.firstShow.slice(0, 7) : '—'}</div>
            <div>{card.lastShow ? `LAST: ${card.lastShow}` : 'NEW MEMBER'}</div>
          </div>
        </div>
      </div>

      <div className="card-progress">
        {card.nextTier && (
          <>
            <div className="progress-head">
              <span>Next tier: <b style={{ color: card.tierColor }}>{card.nextTier.label}</b></span>
              <span className="progress-remaining">{card.nextTier.remaining} more shows to level up</span>
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{
                width: `${Math.min(100, card.attended / (card.attended + card.nextTier.remaining) * 100)}%`,
                background: card.tierColor,
                boxShadow: `0 0 12px ${card.tierColor}`
              }}></div>
            </div>
          </>
        )}
        {!card.nextTier && (
          <div className="max-tier">
            🪩 MAX TIER REACHED — You're a Bushwick icon. 🪩
          </div>
        )}
      </div>

      <div className="card-tiers-reference">
        <h3>Tier Reference</h3>
        <div className="tier-grid">
          <div className="tier-ref" style={{ borderColor: '#888' }}>
            <span>🌱</span><b>ROOKIE</b><span>0–4 shows</span>
          </div>
          <div className="tier-ref" style={{ borderColor: '#00aaff' }}>
            <span>⚡</span><b>REGULAR</b><span>5–14</span>
          </div>
          <div className="tier-ref" style={{ borderColor: '#ff2d92' }}>
            <span>🔥</span><b>HEADLINER</b><span>15–29</span>
          </div>
          <div className="tier-ref" style={{ borderColor: '#a855f7' }}>
            <span>👑</span><b>LEGEND</b><span>30–59</span>
          </div>
          <div className="tier-ref" style={{ borderColor: '#fff700' }}>
            <span>🪩</span><b>ICON</b><span>60+</span>
          </div>
        </div>
      </div>

      <div className="card-perks">
        <h3>🎁 Your unlocked perks ({perks.length})</h3>
        <div className="perk-grid">
          {perks.map(p => (
            <div key={p.id} className="perk-card" data-tier={p.tier_required}>
              <div className="perk-tier" style={{
                background: p.tier_required === 'rookie' ? '#888' :
                            p.tier_required === 'regular' ? '#00aaff' :
                            p.tier_required === 'headliner' ? '#ff2d92' :
                            p.tier_required === 'legend' ? '#a855f7' : '#fff700',
                color: p.tier_required === 'legend' || p.tier_required === 'icon' ? '#000' : '#000'
              }}>{p.tier_required.toUpperCase()}</div>
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