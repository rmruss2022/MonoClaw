import React, { useState } from 'react'
import { parseDate, today as localToday } from '../dateUtils.js'
import EditEventModal from './EditEventModal.jsx'
import GoingModal from './GoingModal.jsx'
import MaybeModal from './MaybeModal.jsx'
import Chat from './Chat.jsx'

function sourceUrlForEvent(event) {
  // Stored URL if present (future), otherwise none
  if (event.source_url) return event.source_url
  if (event.sourceUrl) return event.sourceUrl
  return null
}

function formatCreated(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso.includes('T') ? iso : iso.replace(' ', 'T') + 'Z')
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  } catch { return '' }
}

export default function ShowDetailModal({ event, onClose, onUpdate, onDelete }) {
  const [editing, setEditing] = useState(false)
  const [showGoing, setShowGoing] = useState(false)
  const [showMaybe, setShowMaybe] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)

  if (!event) return null
  const interest = event.interest || 'none'
  const dt = parseDate(event.date)
  const isPast = dt < localToday()
  const sourceUrl = sourceUrlForEvent(event)

  function handleGoing() {
    if (interest === 'going') {
      onUpdate(event.id, { interest: null })
    } else {
      setShowGoing(true)
    }
  }

  function handleMaybe() {
    if (interest === 'maybe') {
      onUpdate(event.id, { interest: null })
    } else {
      setShowMaybe(true)
    }
  }

  const costLabel = event.cost > 0
    ? `$${event.cost}`
    : (event.cost === 0 && event.interest === 'going' ? 'Free' : 'No price listed')

  const statusLabel = event.attended
    ? 'Attended'
    : interest === 'going' ? 'Going ✓'
    : interest === 'maybe' ? 'Maybe ?'
    : interest === 'interested' ? 'Watching'
    : 'Not going'

  return (
    <>
      <div className="detail-backdrop" onClick={onClose}>
        <div className="detail-modal" onClick={e => e.stopPropagation()}>
          <button className="detail-close" onClick={onClose} aria-label="Close">×</button>

          <div className="detail-head">
            <h2 className="detail-name">{event.name}</h2>
            <div className="detail-venue">{event.venue}</div>
            <div className="detail-date">
              {dt.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
            </div>
            {(event.genres || []).length > 0 && (
              <div className="detail-genres">
                {event.genres.map(g => <span key={g} className="genre-tag">{g}</span>)}
              </div>
            )}
          </div>

          {event.description && (
            <>
              <div className="detail-divider" />
              <div className="detail-section">
                <div className="detail-label">DESCRIPTION</div>
                <p className="detail-desc">{event.description}</p>
              </div>
            </>
          )}

          <div className="detail-divider" />
          <div className="detail-section">
            <div className="detail-label">DETAILS</div>
            <div className="detail-grid">
              <div className="detail-grid-row">
                <span className="detail-grid-key">Cost</span>
                <span className="detail-grid-val">{costLabel}</span>
              </div>
              <div className="detail-grid-row">
                <span className="detail-grid-key">Status</span>
                <span className="detail-grid-val">{statusLabel}</span>
              </div>
              {isPast && (
                <div className="detail-grid-row">
                  <span className="detail-grid-key">Attended</span>
                  <span className="detail-grid-val">{event.attended ? 'Yes' : 'No'}</span>
                </div>
              )}
              {event.created_at && (
                <div className="detail-grid-row">
                  <span className="detail-grid-key">Added</span>
                  <span className="detail-grid-val">{formatCreated(event.created_at)}</span>
                </div>
              )}
              {event.topPick && (
                <div className="detail-grid-row">
                  <span className="detail-grid-key">Tag</span>
                  <span className="detail-grid-val">Top pick</span>
                </div>
              )}
            </div>
          </div>

          {event.notes && (
            <>
              <div className="detail-divider" />
              <div className="detail-section">
                <div className="detail-label">NOTES</div>
                <p className="detail-notes">{event.notes}</p>
              </div>
            </>
          )}

          <div className="detail-divider" />
          <div className="detail-section">
            <button
              className="chat-section-toggle"
              onClick={() => setChatOpen(v => !v)}
              aria-expanded={chatOpen}
            >
              <span className="detail-label">CHAT</span>
              <span className="chat-section-caret">{chatOpen ? '−' : '+'}</span>
            </button>
            {chatOpen && (
              <div className="chat-section-body">
                <Chat eventId={event.id} />
              </div>
            )}
          </div>

          <div className="detail-divider" />
          <div className="detail-actions">
            {interest !== 'going' && (
              <button className="detail-btn-primary" onClick={handleGoing}>GOING</button>
            )}
            {interest === 'going' && (
              <button className="detail-btn-danger" onClick={handleGoing}>CANCEL GOING</button>
            )}
            <button
              className={`detail-btn-secondary ${interest === 'maybe' ? 'on' : ''}`}
              onClick={handleMaybe}
            >MAYBE</button>
            <button className="detail-btn-secondary" onClick={() => setEditing(true)}>EDIT</button>
          </div>

          {sourceUrl && (
            <a className="detail-source-link" href={sourceUrl} target="_blank" rel="noopener noreferrer">
              VIEW ORIGINAL →
            </a>
          )}
        </div>
      </div>

      {editing && (
        <EditEventModal
          event={event}
          onClose={() => setEditing(false)}
          onUpdate={onUpdate}
          onDelete={(id) => { onDelete && onDelete(id); onClose(); }}
        />
      )}

      {showGoing && (
        <GoingModal
          event={event}
          onConfirm={patch => { onUpdate(event.id, patch); setShowGoing(false) }}
          onCancel={() => setShowGoing(false)}
        />
      )}

      {showMaybe && (
        <MaybeModal
          event={event}
          onConfirm={patch => { onUpdate(event.id, patch); setShowMaybe(false) }}
          onCancel={() => setShowMaybe(false)}
        />
      )}
    </>
  )
}
