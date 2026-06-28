// API base URL — empty for local dev (Vite proxy), Railway URL for production
const API_BASE = import.meta.env.VITE_API_URL || ''

// Helper to get auth token from localStorage
export function getToken() {
  return localStorage.getItem('rave_token')
}

// Authenticated fetch wrapper
export async function authFetch(url, options = {}) {
  const token = getToken()
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  }
  const fullUrl = url.startsWith('http') ? url : `${API_BASE}${url}`
  const r = await fetch(fullUrl, { ...options, headers })
  // If 401, clear auth and reload to show login
  if (r.status === 401) {
    localStorage.removeItem('rave_token')
    localStorage.removeItem('rave_user')
    window.location.reload()
    return
  }
  return r
}

export { API_BASE }