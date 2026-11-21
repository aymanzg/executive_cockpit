import { reactive, watch } from 'vue'

const KEY = 'executive_cockpit_prefs'

function load() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '{}')
  } catch (e) {
    return {}
  }
}

const saved = load()

export const store = reactive({
  boot: null,
  company: saved.company || null,
  period: saved.period || 'ytd',
  asOf: null,
  fromDate: saved.fromDate || null,
  toDate: saved.toDate || null,
  dark: typeof saved.dark === 'boolean' ? saved.dark : window.matchMedia?.('(prefers-color-scheme: dark)').matches,
  refreshTick: 0,
  busy: false, // a view is (re)loading its data
  forceRefresh: false,
})

export function applyTheme() {
  document.documentElement.dataset.theme = store.dark ? 'dark' : 'light'
}

watch(
  () => [store.company, store.period, store.dark, store.fromDate, store.toDate],
  () => {
    try {
      localStorage.setItem(
        KEY,
        JSON.stringify({
          company: store.company,
          period: store.period,
          dark: store.dark,
          fromDate: store.fromDate,
          toDate: store.toDate,
        })
      )
    } catch (e) {
      /* storage unavailable: preferences just won't persist */
    }
    applyTheme()
  }
)

export function filterParams() {
  const p = { company: store.company, period: store.period, as_of: store.asOf }
  if (store.period === 'custom') {
    p.from_date = store.fromDate
    p.to_date = store.toDate
  }
  return p
}

/** Whether the signed-in user may open a section (route name) of the dashboard. */
export function can(section) {
  return !!store.boot?.sections?.includes(section)
}
