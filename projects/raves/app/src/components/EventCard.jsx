import React, { useState } from 'react'
import { parseDate, today as localToday } from '../dateUtils.js'
import EditEventModal from './EditEventModal.jsx'
import GoingModal from './GoingModal.jsx'
import MaybeModal from './MaybeModal.jsx'

export default function EventCard({ event, onUpdate, onDelete }) {
  const [editingNote, setEditingNote] = useState(false)
  const [noteText, setNoteText] = useState(event.notes || '')
  const [editing, setEditing] = useState(false)
  const [showGoingModal, setShowGoingModal] = useState(false)
  const [showMaybeModal, setShowMaybeModal] = useState(false)
  const interest = event.interest || 'none'

  function handleGoingClick() {
    if (interest === 'going') {
      // Toggle off — no modal needed
      onUpdate(event.id, { interest: null })
    } else {
      setShowGoingModal(true)
    }
  }

  function handleMaybeClick() {
    if (interest === 'maybe') {
      // Toggle off
      onUpdate(event.id, { interest: null })
    } else {
      setShowMaybeModal(true)
    }
  }

  function handleGoingConfirm(patch) {
    onUpdate(event.id, patch)
    setShowGoingModal(false)
  }

  function handleMaybeConfirm(patch) {
    onUpdate(event.id, patch)
    setShowMaybeModal(false)
  }

  function saveNote() {
    onUpdate(event.id, { notes: noteText })
    setEditingNote(false)
  }

  const dt = parseDate(event.date)
  const isPast = dt < localToday()

  return (
    <>
      <div className={`event-card ${interest} ${isPast ? 'past' : ''}`}>
        <div className="ec-head">
          <div className="ec-date-block">
            <div className="ec-month">{dt.toLocaleDateString('en-US', { month: 'short' }).toUpperCase()}</div>
            <div className="ec-day">{dt.getDate()}</div>
            <div className="ec-dow">{dt.toLocaleDateString('en-US', { weekday: 'short' }).toUpperCase()}</div>
          </div>
          <div className="ec-info">
            <h3 className="ec-name">{event.name}</h3>
            <div className="ec-venue">{event.venue}</div>
            <div className="ec-genres">
              {(event.genres || []).map(g => <span key={g} className="genre-tag">{g}</span>)}
            </div>
          </div>
          {event.topPick && <div className="ec-top-pick">TOP PICK</div>}
          <button className="edit-btn" onClick={() => setEditing(true)} title="Edit or delete">EDIT</button>
        </div>

        <p className="ec-desc">{event.description}</p>

        {event.cost > 0 && (
          <div className="ec-cost">${event.cost}</div>
        )}

        {event.notes && !editingNote && (
          <div className="ec-note">
            <span className="ec-note-label">NOTE</span>
            {event.notes}
          </div>
        )}
        {editingNote && (
          <div className="ec-note-edit">
            <textarea
              value={noteText}
              onChange={e => setNoteText(e.target.value)}
              placeholder="Who's going? What time? Set reminder…"
              rows={3}
            />
            <div className="ec-note-actions">
              <button className="btn-save" onClick={saveNote}>Save</button>
              <button className="btn-cancel" onClick={() => { setEditingNote(false); setNoteText(event.notes || '') }}>Cancel</button>
            </div>
          </div>
        )}

        <div className="ec-actions">
          <button
            className={`interest-btn going ${interest === 'going' ? 'on' : ''}`}
            onClick={handleGoingClick}
          >GOING</button>
          <button
            className={`interest-btn maybe ${interest === 'maybe' ? 'on' : ''}`}
            onClick={handleMaybeClick}
          >MAYBE</button>
          <button
            className={`interest-btn interested ${interest === 'interested' ? 'on' : ''}`}
            onClick={() => onUpdate(event.id, { interest: interest === 'interested' ? null : 'interested' })}
          >WATCH</button>
          <button
            className={`attend-btn ${event.attended ? 'on' : ''}`}
            onClick={() => onUpdate(event.id, { attended: !event.attended })}
          >{event.attended ? 'ATTENDED' : 'MARK ATTENDED'}</button>
          <button className="note-btn" onClick={() => setEditingNote(true)}>NOTE</button>
        </div>
      </div>

      {editing && (
        <EditEventModal
          event={event}
          onClose={() => setEditing(false)}
          onUpdate={onUpdate}
          onDelete={onDelete}
        />
      )}

      {showGoingModal && (
        <GoingModal
          event={event}
          onConfirm={handleGoingConfirm}
          onCancel={() => setShowGoingModal(false)}
        />
      )}

      {showMaybeModal && (
        <MaybeModal
          event={event}
          onConfirm={handleMaybeConfirm}
          onCancel={() => setShowMaybeModal(false)}
        />
      )}
    </>
  )
}
