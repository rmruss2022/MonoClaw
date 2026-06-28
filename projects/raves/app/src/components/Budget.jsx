import React, { useState, useEffect } from 'react'
import { authFetch } from '../auth.js'
import { parseDate } from '../dateUtils.js'

export default function Budget({ events, onUpdate }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [editingLimit, setEditingLimit] = useState(false)
  const [limitVal, setLimitVal] = useState('')

  useEffect(() => {
    load()
  }, [events])

  async function load() {
    setLoading(true)
    try {
      const r = await authFetch('/api/budget')
      const d = await r.json()
      setData(d)
      setLimitVal(String(d.config.monthly_limit))
    } catch (e) {
      console.error('Failed to load budget', e)
    }
    setLoading(false)
  }

  async function saveLimit() {
    try {
      const r = await authFetch('/api/budget/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ monthly_limit: Number(limitVal) })
      })
      if (r.ok) {
        setEditingLimit(false)
        load()
      }
    } catch (e) {
      console.error('Save limit failed', e)
    }
  }

  async function setEventCost(eventId, cost) {
    try {
      const r = await authFetch(`/api/events/${eventId}/cost`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cost: Number(cost) || 0 })
      })
      if (r.ok) {
        onUpdate(eventId, { cost: Number(cost) || 0 })
        load()
      }
    } catch (e) {
      console.error('Save cost failed', e)
    }
  }

  if (loading) return <div className="loading">Loading budget...</div>
  if (!data) return <div className="loading">Failed to load</div>

  const limit = data.config.monthly_limit
  const spent = data.thisMonth.spent
  const committed = data.thisMonth.committed
  const projected = data.thisMonth.projected
  const remaining = limit - projected
  const overBudget = projected > limit

  const goingEvents = events.filter(e => e.interest === 'going' || e.interest === 'attended')
    .sort((a, b) => a.date.localeCompare(b.date))

  return (
    <div className="budget-wrap">
      <div className="budget-header">
        <h2>💸 Rave Budget</h2>
        <p>Monthly spend tracking · {new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}</p>
      </div>

      <div className="budget-stats">
        <div className="budget-card">
          <div className="budget-card-label">SPENT (ATTENDED)</div>
          <div className="budget-card-val" style={{ color: 'var(--neon-green)' }}>${spent.toFixed(0)}</div>
        </div>
        <div className="budget-card">
          <div className="budget-card-label">COMMITTED (GOING)</div>
          <div className="budget-card-val" style={{ color: 'var(--neon-pink)' }}>${committed.toFixed(0)}</div>
        </div>
        <div className="budget-card">
          <div className="budget-card-label">PROJECTED TOTAL</div>
          <div className="budget-card-val" style={{ color: overBudget ? '#ff4444' : 'var(--neon-yellow)' }}>
            ${projected.toFixed(0)}
          </div>
        </div>
        <div className="budget-card">
          <div className="budget-card-label">
            {overBudget ? 'OVER BY' : 'REMAINING'}
          </div>
          <div className="budget-card-val" style={{ color: overBudget ? '#ff4444' : 'var(--neon-cyan)' }}>
            ${Math.abs(remaining).toFixed(0)}
          </div>
        </div>
      </div>

      <div className="budget-limit">
        {editingLimit ? (
          <>
            <span>Monthly limit: $</span>
            <input
              type="number"
              value={limitVal}
              onChange={e => setLimitVal(e.target.value)}
              autoFocus
              style={{ width: 80 }}
            />
            <button className="btn-save" onClick={saveLimit}>Save</button>
            <button className="btn-cancel" onClick={() => setEditingLimit(false)}>Cancel</button>
          </>
        ) : (
          <>
            <span>Monthly limit: <b>${limit}</b></span>
            <button className="btn-edit" onClick={() => setEditingLimit(true)}>Edit</button>
          </>
        )}
      </div>

      <div className="budget-bar">
        <div className="bar-spent" style={{ width: `${Math.min(100, spent/limit*100)}%` }}></div>
        <div className="bar-committed" style={{ width: `${Math.min(100 - spent/limit*100, committed/limit*100)}%` }}></div>
        {overBudget && <div className="bar-over"></div>}
      </div>
      <div className="budget-bar-legend">
        <span><span className="dot" style={{ background: 'var(--neon-green)' }}></span>Spent</span>
        <span><span className="dot" style={{ background: 'var(--neon-pink)' }}></span>Committed</span>
        <span><span className="dot" style={{ background: overBudget ? '#ff4444' : 'var(--concrete-light)' }}></span>{overBudget ? 'Over budget' : 'Remaining'}</span>
      </div>

      <div className="budget-section">
        <h3>🎫 Cost per show</h3>
        <p className="section-help">Set cost on Going/Attended shows to track your spending accurately.</p>
        <div className="cost-list">
          {goingEvents.length === 0 && <div className="empty">No Going or Attended shows yet.</div>}
          {goingEvents.map(e => (
            <CostRow key={e.id} event={e} onSave={setEventCost} />
          ))}
        </div>
      </div>

      <div className="budget-section">
        <h3>📊 Spend by venue</h3>
        {data.byVenue.length === 0 ? (
          <div className="empty">Add ticket prices to your Going shows to see venue spend.</div>
        ) : (
          <div className="bar-list">
            {data.byVenue.map(v => {
              const max = Math.max(...data.byVenue.map(x => x.total))
              return (
                <div key={v.venue} className="bar-row">
                  <span className="bar-row-label">{v.venue} <em>({v.count})</em></span>
                  <div className="bar-row-track">
                    <div className="bar-row-fill" style={{ width: `${v.total/max*100}%` }}></div>
                  </div>
                  <span className="bar-row-val">${v.total.toFixed(0)}</span>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div className="budget-section">
        <h3>🎵 Spend by genre</h3>
        {data.byGenre.length === 0 ? (
          <div className="empty">Add ticket prices to your Going shows to see genre spend.</div>
        ) : (
          <div className="bar-list">
            {data.byGenre.map(g => {
              const max = Math.max(...data.byGenre.map(x => x.total))
              return (
                <div key={g.name} className="bar-row">
                  <span className="bar-row-label">{g.name}</span>
                  <div className="bar-row-track">
                    <div className="bar-row-fill" style={{ width: `${g.total/max*100}%`, background: 'var(--neon-cyan)' }}></div>
                  </div>
                  <span className="bar-row-val">${g.total.toFixed(0)}</span>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

function CostRow({ event, onSave }) {
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState(String(event.cost || ''))

  function save() {
    onSave(event.id, val)
    setEditing(false)
  }

  const dt = parseDate(event.date)
  const dateStr = dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  const interest = event.interest || 'none'
  const attended = event.attended

  return (
    <div className={`cost-row ${interest} ${attended ? 'attended' : ''}`}>
      <div className="cost-row-date">{dateStr}</div>
      <div className="cost-row-info">
        <div className="cost-row-name">{event.name}</div>
        <div className="cost-row-venue">{event.venue}</div>
      </div>
      <div className="cost-row-status">
        {attended ? '✅ Attended' : interest === 'going' ? '🎯 Going' : '—'}
      </div>
      <div className="cost-row-cost">
        {editing ? (
          <>
            <input
              type="number"
              value={val}
              onChange={e => setVal(e.target.value)}
              autoFocus
              placeholder="0"
              onKeyDown={e => e.key === 'Enter' && save()}
            />
            <button className="btn-save btn-tiny" onClick={save}>✓</button>
            <button className="btn-cancel btn-tiny" onClick={() => { setEditing(false); setVal(String(event.cost || '')) }}>×</button>
          </>
        ) : (
          <span className="cost-display" onClick={() => setEditing(true)}>
            {event.cost ? `$${event.cost}` : <em>+ set</em>}
          </span>
        )}
      </div>
    </div>
  )
}