import React, { useState, useEffect, useRef, useCallback } from 'react'
import { authFetch } from '../auth.js'

const MAX_LEN = 500
const POLL_MS = 5000

function timeAgo(iso) {
  if (!iso) return ''
  const d = new Date(iso.includes('T') ? iso : iso.replace(' ', 'T') + 'Z')
  const now = Date.now()
  const s = Math.max(1, Math.floor((now - d.getTime()) / 1000))
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const days = Math.floor(h / 24)
  if (days < 7) return `${days}d ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export default function Chat({ eventId, onClose, compact = false }) {
  const [thread, setThread] = useState(null)
  const [members, setMembers] = useState([])
  const [messages, setMessages] = useState([])
  const [body, setBody] = useState('')
  const [sending, setSending] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [currentUserId, setCurrentUserId] = useState(null)
  const [currentAuthorName, setCurrentAuthorName] = useState(null)
  const [isMember, setIsMember] = useState(false)
  const [eventName, setEventName] = useState('')

  const pollRef = useRef(null)
  const listRef = useRef(null)
  const textareaRef = useRef(null)
  const mountedRef = useRef(true)

  const fetchChat = useCallback(async () => {
    try {
      const r = await authFetch(`/api/events/${eventId}/chat`)
      if (!r || !r.ok) throw new Error(r ? `HTTP ${r.status}` : 'no response')
      const data = await r.json()
      if (!mountedRef.current) return
      setThread(data.thread)
      setMembers(data.members || [])
      setMessages(data.messages || [])
      setCurrentUserId(data.currentUserId ?? null)
      setCurrentAuthorName(data.currentAuthorName ?? null)
      setIsMember(!!data.isMember)
      setEventName(data.eventName || '')
      setError(null)
    } catch (e) {
      if (mountedRef.current) setError(e.message)
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }, [eventId])

  useEffect(() => {
    mountedRef.current = true
    fetchChat()
    pollRef.current = setInterval(fetchChat, POLL_MS)
    return () => {
      mountedRef.current = false
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [fetchChat])

  useEffect(() => {
    if (!listRef.current) return
    listRef.current.scrollTop = listRef.current.scrollHeight
  }, [messages.length])

  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    const line = 20
    const max = line * 4 + 12
    ta.style.height = Math.min(ta.scrollHeight, max) + 'px'
  }, [body])

  function isOwnMessage(m) {
    if (currentUserId != null && m.user_id != null) return m.user_id === currentUserId
    if (currentUserId == null && m.user_id == null) {
      return currentAuthorName ? m.author_name === currentAuthorName : true
    }
    return false
  }

  async function send() {
    const text = body.trim()
    if (!text || sending) return
    if (text.length > MAX_LEN) return
    setSending(true)
    setError(null)
    try {
      const r = await authFetch(`/api/events/${eventId}/chat`, {
        method: 'POST',
        body: JSON.stringify({ body: text })
      })
      if (!r || !r.ok) {
        const j = r ? await r.json().catch(() => ({})) : {}
        throw new Error(j.error || (r ? `HTTP ${r.status}` : 'no response'))
      }
      const data = await r.json()
      setMessages(prev => {
        if (prev.find(m => m.id === data.message.id)) return prev
        return [...prev, data.message]
      })
      setBody('')
      fetchChat()
    } catch (e) {
      setError(e.message)
    } finally {
      setSending(false)
    }
  }

  function onKeyDown(e) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      send()
    }
  }

  const memberCount = members.length
  const displayMessages = compact ? messages.slice(-3) : messages
  const remaining = MAX_LEN - body.length

  return (
    <div className={`chat-wrap ${compact ? 'compact' : ''}`}>
      {!compact && (
        <div className="chat-header">
          <div className="chat-header-title">{eventName || 'CHAT'}</div>
          <div className="chat-header-meta">
            <span className="chat-header-count">{memberCount} GOING</span>
            {onClose && (
              <button className="chat-close" onClick={onClose} aria-label="Close chat">×</button>
            )}
          </div>
        </div>
      )}

      <div className="chat-messages" ref={listRef}>
        {loading && messages.length === 0 && (
          <div className="chat-empty">Loading…</div>
        )}
        {!loading && messages.length === 0 && (
          <div className="chat-empty">No messages yet. Start the conversation.</div>
        )}
        {displayMessages.map(m => {
          const own = isOwnMessage(m)
          const isSystem = m.author_name === 'system' || m.is_system
          if (isSystem) {
            return (
              <div key={m.id} className="chat-message system">
                <span className="chat-body">{m.body}</span>
              </div>
            )
          }
          return (
            <div key={m.id} className={`chat-message ${own ? 'own' : 'incoming'} ${m.pinned ? 'pinned' : ''}`}>
              {m.pinned ? <span className="chat-pin-label">PINNED</span> : null}
              <div className="chat-meta">
                <span className="chat-author">{m.author_name || 'ANON'}</span>
                <span className="chat-time">{timeAgo(m.created_at)}</span>
              </div>
              <div className="chat-body">{m.body}</div>
            </div>
          )
        })}
      </div>

      {error && <div className="chat-error">{error}</div>}

      <div className="chat-input">
        <textarea
          ref={textareaRef}
          value={body}
          onChange={e => setBody(e.target.value.slice(0, MAX_LEN))}
          onKeyDown={onKeyDown}
          placeholder={isMember ? 'Message…' : 'Mark yourself GOING to post…'}
          rows={1}
          disabled={sending}
        />
        <div className="chat-input-row">
          <span className={`chat-counter ${remaining < 50 ? 'low' : ''}`}>{body.length}/{MAX_LEN}</span>
          <button
            className="chat-send"
            onClick={send}
            disabled={sending || !body.trim() || body.length > MAX_LEN}
          >{sending ? 'SENDING' : 'SEND'}</button>
        </div>
      </div>
    </div>
  )
}
