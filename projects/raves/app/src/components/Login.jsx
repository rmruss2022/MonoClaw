import React, { useState } from 'react'
import { API_BASE } from '../auth.js'

export default function Login({ onLogin }) {
  const [mode, setMode] = useState('login') // 'login' or 'signup'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!username.trim() || !password) {
      setError('Username and password required')
      return
    }
    setLoading(true)
    try {
      const endpoint = mode === 'login' ? '/api/auth/login' : '/api/auth/signup'
      const body = mode === 'login'
        ? { username, password }
        : { username, password, displayName }
      const r = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })
      const d = await r.json()
      if (!d.success) throw new Error(d.error || 'Auth failed')
      // Save token + user
      localStorage.setItem('rave_token', d.token)
      localStorage.setItem('rave_user', JSON.stringify(d.user))
      onLogin(d.user, d.token)
    } catch (e) {
      setError(e.message)
    }
    setLoading(false)
  }

  return (
    <div className="login-page">
      <div className="login-bg-anim"></div>
      <div className="login-stage">
        <div className="login-card">
          <span className="login-emblem">GF</span>
          <h1 className="login-title">GROUNDFLOOR</h1>
          <div className="login-subtitle">NYC · Underground</div>

          <div className="login-tabs">
            <button
              className={`login-tab ${mode === 'login' ? 'active' : ''}`}
              onClick={() => setMode('login')}
              type="button"
            >Log in</button>
            <button
              className={`login-tab ${mode === 'signup' ? 'active' : ''}`}
              onClick={() => setMode('signup')}
              type="button"
            >Sign up</button>
          </div>

          <form onSubmit={handleSubmit} className="login-form">
            <label>
              <span>Username</span>
              <input
                autoFocus
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="ravekid"
                autoCapitalize="off"
                autoCorrect="off"
              />
            </label>

            {mode === 'signup' && (
              <label>
                <span>Display name <em>(optional)</em></span>
                <input
                  value={displayName}
                  onChange={e => setDisplayName(e.target.value)}
                  placeholder="What should we call you?"
                />
              </label>
            )}

            <label>
              <span>Password</span>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </label>

            {error && <div className="login-error">{error}</div>}

            <button type="submit" className="login-submit" disabled={loading}>
              {loading ? '...' : (mode === 'login' ? 'ENTER' : 'JOIN')}
            </button>
          </form>

          <div className="login-hint">
            {mode === 'login'
              ? <>New here? <a onClick={() => setMode('signup')}>Create an account</a></>
              : <>Already in? <a onClick={() => setMode('login')}>Log in</a></>
            }
          </div>
        </div>
      </div>
    </div>
  )
}