// Groundfloor service worker — push + caching
// Cache version — bump this to force all clients to refresh
const CACHE = 'groundfloor-v' + (self.registration?.scope || Date.now()).toString().slice(-6)
const STATIC_CACHE = 'groundfloor-static-v3'

self.addEventListener('install', e => {
  // Pre-cache shell only
  e.waitUntil(
    caches.open(STATIC_CACHE)
      .then(c => c.addAll(['/', '/index.html']))
      .catch(() => {})
  )
  // Take over immediately
  self.skipWaiting()
})

self.addEventListener('activate', e => {
  // Delete ALL old caches on activate — ensures stale Safari caches get nuked
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => k !== STATIC_CACHE)
          .map(k => { console.log('[SW] Deleting old cache:', k); return caches.delete(k); })
      )
    ).then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url)

  // Never intercept API calls
  if (url.pathname.startsWith('/api/')) return

  // Network-first for HTML (always get fresh index.html)
  if (url.pathname === '/' || url.pathname.endsWith('.html')) {
    e.respondWith(
      fetch(e.request)
        .then(res => {
          if (res.ok) {
            const clone = res.clone()
            caches.open(STATIC_CACHE).then(c => c.put(e.request, clone)).catch(() => {})
          }
          return res
        })
        .catch(() => caches.match(e.request))
    )
    return
  }

  // Cache-first for hashed assets (JS/CSS have content hashes in filename)
  if (url.pathname.match(/\.(js|css|woff2?|png|svg|ico)$/)) {
    e.respondWith(
      caches.match(e.request).then(cached => {
        if (cached) return cached
        return fetch(e.request).then(res => {
          if (res.ok) {
            const clone = res.clone()
            caches.open(STATIC_CACHE).then(c => c.put(e.request, clone)).catch(() => {})
          }
          return res
        })
      })
    )
    return
  }

  // Default: network with cache fallback
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  )
})

// ===================== PUSH NOTIFICATIONS =====================
self.addEventListener('push', e => {
  let data = {}
  try { data = e.data?.json() || {} } catch {}

  const title = data.title || 'Groundfloor'
  const options = {
    body: data.body || '',
    tag: data.tag || 'groundfloor',
    data: { url: data.url || '/' },
    vibrate: [200, 100, 200],
    requireInteraction: false,
  }
  if (data.icon)  options.icon  = data.icon
  if (data.badge) options.badge = data.badge
  e.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', e => {
  e.notification.close()
  const url = e.notification.data?.url || '/'
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      const existing = list.find(c => c.url.includes(self.registration.scope))
      if (existing) { existing.focus(); existing.navigate(url); }
      else clients.openWindow(url)
    })
  )
})
