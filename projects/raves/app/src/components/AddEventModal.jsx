import React, { useState } from 'react'
import { authFetch } from '../auth.js'

const EMPTY = {
  name: '',
  venue: '',
  date: '',
  genres: '',
  description: '',
  topPick: false,
  isFestival: false,
  festivalEndDate: '',
  locationCity: '',
  cost: ''
}

function slugify(s) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

function dayOfWeek(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T12:00:00')
  return d.toLocaleDateString('en-US', { weekday: 'long' })
}

export default function AddEventModal({ onClose, onCreate }) {
  const [mode, setMode] = useState('manual') // 'manual' or 'link'
  const [link, setLink] = useState('')
  const [scraping, setScraping] = useState(false)
  const [scrapeError, setScrapeError] = useState('')
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  function update(k, v) {
    setForm(prev => ({ ...prev, [k]: v }))
  }

  async function handleScrape() {
    if (!link.trim()) {
      setScrapeError('Paste a URL first')
      return
    }
    setScraping(true)
    setScrapeError('')
    try {
      const r = await authFetch('/api/scrape-event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: link.trim() })
      })
      const d = await r.json()
      if (!d.success) throw new Error(d.error || 'Scrape failed')
      const ev = d.event
      // Pre-fill form
      setForm({
        name: ev.name || '',
        venue: ev.venue || '',
        date: ev.date || '',
        genres: (ev.genres || []).join(', '),
        description: ev.description || '',
        topPick: !!ev.topPick
      })
      setMode('manual') // Switch to form so user can review/edit
    } catch (e) {
      setScrapeError(e.message)
    }
    setScraping(false)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!form.name.trim() || !form.venue.trim() || !form.date) {
      setError('Name, venue, and date are required')
      return
    }
    setSaving(true)
    const payload = {
      id: `${form.date}-${slugify(form.name)}-${slugify(form.venue)}`,
      name: form.name.trim(),
      venue: form.venue.trim(),
      date: form.date,
      dayOfWeek: dayOfWeek(form.date),
      genres: form.genres.split(',').map(g => g.trim()).filter(Boolean),
      description: form.description.trim() || `${form.name} @ ${form.venue}`,
      topPick: form.topPick,
      cost: parseFloat(form.cost) || 0,
      is_festival: form.isFestival ? 1 : 0,
      festival_end_date: form.isFestival && form.festivalEndDate ? form.festivalEndDate : null,
      location_city: form.locationCity.trim() || null
    }
    try {
      const r = await authFetch('/api/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      const d = await r.json()
      if (!d.success) throw new Error(d.error || 'Failed to create')
      onCreate(d.event)
      onClose()
    } catch (e) {
      setError(e.message)
    }
    setSaving(false)
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-head">
          <h2>➕ Add a show</h2>
          <button className="close" onClick={onClose}>×</button>
        </div>

        <div className="mode-tabs">
          <button
            className={`mode-tab ${mode === 'manual' ? 'active' : ''}`}
            onClick={() => setMode('manual')}
          >✍️ Manual</button>
          <button
            className={`mode-tab ${mode === 'link' ? 'active' : ''}`}
            onClick={() => setMode('link')}
          >🔗 Paste Link</button>
        </div>

        {mode === 'link' && (
          <div className="link-mode">
            <p className="link-help">
              Paste an event URL (Resident Advisor, Dice, Elsewhere, House of Yes, etc.)
              and we'll scrape the details into the form for you to review.
            </p>
            <label>
              <span>Event URL</span>
              <input
                value={link}
                onChange={e => setLink(e.target.value)}
                placeholder="https://ra.co/events/1234567"
                onKeyDown={e => e.key === 'Enter' && handleScrape()}
              />
            </label>
            {scrapeError && <div className="modal-error">{scrapeError}</div>}
            <div className="modal-actions">
              <button type="button" className="btn-cancel" onClick={onClose}>Cancel</button>
              <button type="button" className="btn-save" onClick={handleScrape} disabled={scraping}>
                {scraping ? 'Scraping…' : '🔍 Scrape & Fill Form'}
              </button>
            </div>
          </div>
        )}

        {mode === 'manual' && (
          <form onSubmit={handleSubmit} className="modal-form">
            <label>
              <span>Show name *</span>
              <input
                autoFocus
                value={form.name}
                onChange={e => update('name', e.target.value)}
                placeholder="Honey Dijon, Boiler Room, etc."
              />
            </label>

            <label>
              <span>Venue *</span>
              <input
                value={form.venue}
                onChange={e => update('venue', e.target.value)}
                placeholder="House of Yes, Elsewhere, Basement, etc."
              />
            </label>

            <label>
              <span>Date *</span>
              <input
                type="date"
                value={form.date}
                onChange={e => update('date', e.target.value)}
              />
            </label>

            <label>
              <span>Genres <em>(comma separated)</em></span>
              <input
                value={form.genres}
                onChange={e => update('genres', e.target.value)}
                placeholder="House, Techno, Breakbeat"
              />
            </label>

            <label>
              <span>Description</span>
              <textarea
                value={form.description}
                onChange={e => update('description', e.target.value)}
                rows={3}
                placeholder="Lineup, vibe, anything notable…"
              />
            </label>

            <label className="checkbox">
              <input
                type="checkbox"
                checked={form.topPick}
                onChange={e => update('topPick', e.target.checked)}
              />
              <span>⭐ Mark as top pick</span>
            </label>

            <label className="checkbox">
              <input
                type="checkbox"
                checked={form.isFestival}
                onChange={e => update('isFestival', e.target.checked)}
              />
              <span>🌍 Multi-day / Festival</span>
            </label>

            {form.isFestival && (
              <>
                <label className="modal-label">
                  End Date
                  <input
                    type="date"
                    className="modal-input"
                    value={form.festivalEndDate}
                    onChange={e => update('festivalEndDate', e.target.value)}
                    min={form.date}
                  />
                </label>
                <label className="modal-label">
                  City / Location
                  <input
                    type="text"
                    className="modal-input"
                    placeholder="Amsterdam, Berlin, Detroit…"
                    value={form.locationCity}
                    onChange={e => update('locationCity', e.target.value)}
                  />
                </label>
              </>
            )}

            <label className="modal-label">
              Ticket Price (optional)
              <input
                type="number"
                className="modal-input"
                placeholder="$0"
                min="0"
                value={form.cost}
                onChange={e => update('cost', e.target.value)}
              />
            </label>

            {error && <div className="modal-error">{error}</div>}

            <div className="modal-actions">
              <button type="button" className="btn-cancel" onClick={onClose}>Cancel</button>
              <button type="submit" className="btn-save" disabled={saving}>
                {saving ? 'Saving…' : 'Add Show'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}