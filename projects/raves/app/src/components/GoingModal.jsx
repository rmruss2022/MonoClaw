import React, { useState } from 'react'

export default function GoingModal({ event, onConfirm, onCancel }) {
  const hasCost = event.cost > 0
  const [step, setStep] = useState(1)
  const [price, setPrice] = useState('')

  function handleConfirm() {
    if (hasCost) {
      // Price already known — go straight to paid confirmation
      setStep('confirm-cost')
    } else {
      setStep(2)
    }
  }

  function handleSavePrice() {
    const cost = parseFloat(price) || 0
    onConfirm({ interest: 'going', cost })
  }

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal going-modal" onClick={e => e.stopPropagation()}>

        {/* Step 1: You in? */}
        {step === 1 && (
          <>
            <div className="going-modal-icon">🎟</div>
            <div className="going-modal-title">You in?</div>
            <div className="going-modal-event">{event.name}</div>
            <div className="going-modal-venue">{event.venue}</div>
            {hasCost && (
              <div className="going-modal-cost-preview">
                <span className="going-cost-label">TICKET</span>
                <span className="going-cost-value">${event.cost}</span>
              </div>
            )}
            <div className="going-modal-actions">
              <button className="going-confirm-btn" onClick={handleConfirm}>
                I'm going
              </button>
              <button className="going-cancel-btn" onClick={onCancel}>
                Nah
              </button>
            </div>
          </>
        )}

        {/* Pre-loaded cost confirmation */}
        {step === 'confirm-cost' && (
          <>
            <div className="going-modal-icon">💸</div>
            <div className="going-modal-title">Ticket sorted?</div>
            <div className="going-modal-sub">This will add to your budget</div>
            <div className="going-price-row going-price-readonly">
              <span className="going-price-symbol">$</span>
              <span className="going-price-static">{event.cost}</span>
            </div>
            <div className="going-modal-actions">
              <button className="going-confirm-btn" onClick={() => onConfirm({ interest: 'going', cost: event.cost })}>
                Yep, paid
              </button>
              <button className="going-maybe-btn" onClick={() => onConfirm({ interest: 'going', cost: event.cost })}>
                Not yet
              </button>
            </div>
          </>
        )}

        {/* No cost — ask for price */}
        {step === 2 && (
          <>
            <div className="going-modal-icon">💰</div>
            <div className="going-modal-title">How much?</div>
            <div className="going-modal-sub">Ticket price (skip if free)</div>
            <div className="going-price-row">
              <span className="going-price-symbol">$</span>
              <input
                className="going-price-input"
                type="number"
                min="0"
                step="1"
                placeholder="0"
                value={price}
                onChange={e => setPrice(e.target.value)}
                autoFocus
                onKeyDown={e => e.key === 'Enter' && handleSavePrice()}
              />
            </div>
            <div className="going-modal-actions">
              <button className="going-confirm-btn" onClick={handleSavePrice}>
                Add to budget
              </button>
              <button className="going-maybe-btn" onClick={() => onConfirm({ interest: 'going', cost: 0 })}>
                It's free
              </button>
            </div>
          </>
        )}

      </div>
    </div>
  )
}
