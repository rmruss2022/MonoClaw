import React, { useState } from 'react'
import { authFetch } from '../auth.js'

function dayOfWeek(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T12:00:00')
  return d.toLocaleDateString('en-US', { weekday: 'long' })
}

export default function EditEventModal({ event, onClose, onUpdate, onDelete }) {
  const [form, setForm] = useState({
    name: event.name || '',
    venue: event.venue || '',
    date: event.date || '',
    genres: (event.genres || []).join(', '),
    description: event.description || '',
    topPick: !!event.topPick,
    cost: event.cost || 0,
    interest: event.interest || null,
    attended: !!event.attended,
    notes: event.notes || ''
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  function update(k, v) {
    setForm(prev => ({ ...prev, [k]: v }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!form.name.trim() || !form.venue.trim() || !form.date) {
      setError('Name, venue, and date are required')
      return
    }
    setSaving(true)
    try {
      const r = await authFetch(`/api/events/${event.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: form.name.trim(),
          venue: form.venue.trim(),
          date: form.date,
          dayOfWeek: dayOfWeek(form.date),
          genres: form.genres.split(',').map(g => g.trim()).filter(Boolean),
          description: form.description.trim(),
          topPick: form.topPick,
          cost: Number(form.cost) || 0,
          interest: form.interest,
          attended: form.attended,
          notes: form.notes
        })
      })
      const d = await r.json()
      if (!d.success) throw new Error(d.error || 'Failed to update')
      // Pass back (id, fullUpdatedEvent) so parent can replace the event in state
      onUpdate(event.id, d.event)
      onClose()
    } catch (e) {
      setError(e.message)
    }
    setSaving(false)
  }

  async function handleDelete() {
    setError('')
    setSaving(true)
    try {
      const r = await authFetch(`/api/events/${event.id}`, {
        method: 'DELETE'
      })
      const d = await r.json()
      if (!d.success) throw new Error(d.error || 'Failed to delete')
      onDelete(event.id)
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
          <h2>✏️ Edit show</h2>
          <button className="close" onClick={onClose}>×</button>
        </div>

        {confirmDelete ? (
          <div className="delete-confirm">
            <div className="delete-icon">⚠️</div>
            <h3>Delete this show?</h3>
            <p className="delete-msg">
              <b>{event.name}</b> at {event.venue} on {event.date}
            </p>
            <p className="delete-warn">This can't be undone. All notes and history will be lost.</p>
            <div className="modal-actions">
              <button className="btn-cancel" onClick={() => setConfirmDelete(false)} disabled={saving}>
                Cancel
              </button>
              <button className="btn-delete" onClick={handleDelete} disabled={saving}>
                {saving ? 'Deleting…' : '🗑 Delete forever'}
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="modal-form">
            <label>
              <span>Show name *</span>
              <input
                autoFocus
                value={form.name}
                onChange={e => update('name', e.target.value)}
              />
            </label>

            <label>
              <span>Venue *</span>
              <input
                value={form.venue}
                onChange={e => update('venue', e.target.value)}
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
              />
            </label>

            <label>
              <span>Description</span>
              <textarea
                value={form.description}
                onChange={e => update('description', e.target.value)}
                rows={2}
              />
            </label>

            <div className="form-row">
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={form.topPick}
                  onChange={e => update('topPick', e.target.checked)}
                />
                <span>⭐ Top pick</span>
              </label>

              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={form.attended}
                  onChange={e => update('attended', e.target.checked)}
                />
                <span>✅ Attended</span>
              </label>

              <label className="cost-field">
                <span>Cost: $</span>
                <input
                  type="number"
                  value={form.cost}
                  onChange={e => update('cost', e.target.value)}
                  style={{ width: 80 }}
                />
              </label>
            </div>

            <label>
              <span>Interest</span>
              <select value={form.interest || ''} onChange={e => update('interest', e.target.value || null)}>
                <option value="">— none —</option>
                <option value="going">🎯 Going</option>
                <option value="maybe">🤔 Maybe</option>
                <option value="interested">👀 Watching</option>
              </select>
            </label>

            <label>
              <span>Notes</span>
              <textarea
                value={form.notes}
                onChange={e => update('notes', e.target.value)}
                rows={2}
                placeholder="Who's going, set times, etc."
              />
            </label>

            {error && <div className="modal-error">{error}</div>}

            <div className="modal-actions">
              <button
                type="button"
                className="btn-delete-ghost"
                onClick={() => setConfirmDelete(true)}
              >
                🗑 Delete
              </button>
              <div className="modal-actions-right">
                <button type="button" className="btn-cancel" onClick={onClose}>Cancel</button>
                <button type="submit" className="btn-save" disabled={saving}>
                  {saving ? 'Saving…' : 'Save changes'}
                </button>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}