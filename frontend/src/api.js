import { ref, watch, onMounted } from 'vue'
import { store, filterParams } from './store'

export async function call(method, params = {}) {
  const res = await fetch(`/api/method/executive_cockpit.api.${method}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      'X-Frappe-CSRF-Token': window.csrf_token || '',
    },
    body: JSON.stringify(params),
    credentials: 'same-origin',
  })
  let body = {}
  try {
    body = await res.json()
  } catch (e) {
    /* non-JSON error page */
  }
  if (!res.ok) {
    if (res.status === 403 && /login/i.test(body.exc_type || '')) window.location.href = '/login?redirect-to=/executive'
    throw new Error(serverMessage(body) || `خطأ في الخادم (${res.status})`)
  }
  return body.message
}

function serverMessage(body) {
  try {
    const msgs = JSON.parse(body._server_messages || '[]')
    return msgs.map((m) => JSON.parse(m).message).join(' — ')
  } catch (e) {
    return body.exception || ''
  }
}

/** Load a dashboard view and reload it whenever the global filters change. */
export function useView(method) {
  const data = ref(null)
  const loading = ref(false)
  const error = ref(null)

  async function load() {
    if (!store.company) return
    if (store.period === 'custom' && !(store.fromDate && store.toDate)) return
    loading.value = true
    error.value = null
    try {
      data.value = await call(method, { ...filterParams(), refresh: store.forceRefresh ? 1 : 0 })
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
      store.forceRefresh = false
    }
  }

  onMounted(load)
  watch(
    () => [store.company, store.period, store.asOf, store.fromDate, store.toDate, store.refreshTick],
    load
  )
  return { data, loading, error, load }
}

/**
 * Download a file from a whitelisted method as a normal browser download
 * (GET link, the server names the file). Works in every browser, including
 * embedded / mobile ones where blob downloads are blocked.
 */
export function download(method, params = {}) {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null) q.set(k, v)
  const a = document.createElement('a')
  a.href = `/api/method/executive_cockpit.api.${method}?${q.toString()}`
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
}
