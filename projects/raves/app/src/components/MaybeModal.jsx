import React from 'react'

export default function MaybeModal({ event, onConfirm, onCancel }) {
  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal going-modal" onClick={e => e.stopPropagation()}>
        <div className="going-modal-icon">👀</div>
        <div className="going-modal-title">On the radar</div>
        <div className="going-modal-event">{event.name}</div>
        <div className="going-modal-venue">{event.venue}</div>
        <div className="going-modal-sub">We'll keep it on your watchlist</div>
        <div className="going-modal-actions">
          <button className="going-maybe-btn" onClick={() => onConfirm({ interest: 'maybe' })}>
            Yeah, maybe
          </button>
          <button className="going-cancel-btn" onClick={onCancel}>
            Nah
          </button>
        </div>
      </div>
    </div>
  )
}
