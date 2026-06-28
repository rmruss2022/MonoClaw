import { authFetch } from './auth.js'

const VAPID_KEY_URL = '/api/push/vapid-public-key'

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = atob(base64)
  return Uint8Array.from([...rawData].map(c => c.charCodeAt(0)))
}

export async function registerPushNotifications() {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    console.log('[push] Not supported')
    return false
  }

  // Request permission
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') {
    console.log('[push] Permission denied')
    return false
  }

  try {
    // Get VAPID public key
    const r = await authFetch(VAPID_KEY_URL)
    const { publicKey } = await r.json()

    // Get SW registration
    const reg = await navigator.serviceWorker.ready

    // Check if already subscribed
    const existing = await reg.pushManager.getSubscription()
    if (existing) {
      // Re-register in case server lost it
      await authFetch('/api/push/subscribe', {
        method: 'POST',
        body: JSON.stringify(existing.toJSON())
      })
      console.log('[push] Re-registered existing subscription')
      return true
    }

    // Create new subscription
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey)
    })

    // Save to server
    await authFetch('/api/push/subscribe', {
      method: 'POST',
      body: JSON.stringify(sub.toJSON())
    })

    console.log('[push] Subscribed successfully')
    return true
  } catch(e) {
    console.error('[push] Error:', e)
    return false
  }
}

export async function unregisterPushNotifications() {
  const reg = await navigator.serviceWorker.ready
  const sub = await reg.pushManager.getSubscription()
  if (!sub) return
  await authFetch('/api/push/subscribe', {
    method: 'DELETE',
    body: JSON.stringify({ endpoint: sub.endpoint })
  })
  await sub.unsubscribe()
}
