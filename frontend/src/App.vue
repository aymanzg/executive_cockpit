<template>
  <div v-if="bootError" class="state" style="min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px">
    <strong style="font-size: 18px; color: var(--ink)">تعذّر فتح لوحة القيادة</strong>
    <span>{{ bootError }}</span>
    <a href="/app">العودة إلى النظام</a>
  </div>

  <div v-else class="shell">
    <div class="topbar-progress" :class="{ on: store.busy }" aria-hidden="true"></div>
    <aside class="sidebar" aria-label="أقسام اللوحة">
      <div class="brand">
        <div class="brand-mark"><Icon name="logo" :size="22" :stroke="2" /></div>
        <div style="display: flex; flex-direction: column; min-width: 0">
          <span style="font-weight: 700; font-size: 16px">لوحة القيادة</span>
          <span class="lbl" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{{ companyShort }}</span>
        </div>
      </div>
      <nav class="nav">
        <router-link v-for="r in navRoutes" :key="r.path" :to="r.path">
          <Icon :name="r.meta.icon" />
          <span>{{ r.meta.title }}</span>
        </router-link>
      </nav>
      <div class="freshness" :class="{ stale: isStale }">
        <span style="font-size: 13px; font-weight: 600">حداثة البيانات</span>
        <span class="lbl" style="line-height: 1.6">آخر فاتورة مبيعات: <span class="num">{{ dateAr(lastInvoice) }}</span></span>
        <a href="/app" class="lbl" style="display: inline-flex; align-items: center; gap: 6px; margin-top: 4px">
          <Icon name="desk" :size="16" /> فتح النظام
        </a>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div style="display: flex; flex-direction: column; gap: 4px">
          <h1>{{ route.meta.title }}</h1>
          <span class="lbl" style="font-size: 14px">{{ route.meta.sub }}<template v-if="!route.meta.ownPeriod"> · <span class="num">{{ rangeText }}</span></template></span>
        </div>
        <div class="filters">
          <label class="field">
            <span class="lbl">الشركة</span>
            <select v-model="store.company" class="sel">
              <option v-for="c in store.boot?.companies || []" :key="c.name" :value="c.name">{{ c.name }}</option>
            </select>
          </label>
          <template v-if="!route.meta.ownPeriod">
          <div class="seg" role="group" aria-label="الفترة">
            <button v-for="p in PERIODS" :key="p.key" type="button" :class="{ on: store.period === p.key }"
              :aria-pressed="store.period === p.key" @click="store.period = p.key">{{ p.label }}</button>
          </div>
          <template v-if="store.period === 'custom'">
            <label class="field"><span class="lbl">من</span><input v-model="store.fromDate" type="date" class="date" /></label>
            <label class="field"><span class="lbl">إلى</span><input v-model="store.toDate" type="date" class="date" /></label>
          </template>
          <label v-else class="field">
            <span class="lbl">حتى تاريخ</span>
            <input v-model="store.asOf" type="date" class="date" :max="store.boot?.today" />
          </label>
          </template>
          <button type="button" class="iconbtn" :class="{ spin: refreshing || store.busy }" :disabled="store.busy" aria-label="تحديث الأرقام" title="تحديث الأرقام" @click="refresh">
            <Icon name="refresh" />
          </button>
          <button type="button" class="iconbtn" :aria-label="store.dark ? 'الوضع الفاتح' : 'الوضع الداكن'" @click="store.dark = !store.dark">
            <Icon :name="store.dark ? 'sun' : 'moon'" />
          </button>
        </div>
      </header>

      <router-view v-if="store.boot && store.company && can(route.name)" v-slot="{ Component }">
        <component :is="Component" :key="route.path" />
      </router-view>
      <div v-else class="grid-kpi"><div v-for="i in 6" :key="i" class="skeleton"></div></div>

      <footer class="footer lbl">
        <span>{{ store.boot?.full_name }} · لوحة القيادة التنفيذية</span>
        <span>المبالغ بالريال السعودي · المصدر: ERPNext</span>
      </footer>
    </main>

    <nav class="tabbar" aria-label="التنقل">
      <router-link v-for="r in navRoutes" :key="r.path" :to="r.path">
        <Icon :name="r.meta.icon" :size="22" />
        <span>{{ r.meta.short }}</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Icon from './components/Icon.vue'
import { routes } from './router'
import { store, can } from './store'
import { call } from './api'
import { dateAr } from './format'

const route = useRoute()
const router = useRouter()
const navRoutes = computed(() => routes.filter((r) => r.meta?.title && can(r.name)))

// a user only opens the sections allowed to them; anything else goes to their first section
watch(
  () => [store.boot, route.name],
  () => {
    if (!store.boot || !route.name || can(route.name)) return
    const first = navRoutes.value[0]
    if (first) router.replace(first.path)
  }
)
const PERIODS = [
  { key: 'month', label: 'الشهر' },
  { key: 'quarter', label: 'الربع' },
  { key: 'ytd', label: 'منذ بداية السنة' },
  { key: 'custom', label: 'مخصّص' },
]
const bootError = ref(null)
const refreshing = ref(false)

onMounted(async () => {
  try {
    const boot = await call('get_boot')
    store.boot = boot
    store.asOf = boot.today
    if (!store.company || !boot.companies.some((c) => c.name === store.company)) store.company = boot.default_company
  } catch (e) {
    bootError.value = e.message
  }
})

const lastInvoice = computed(() => store.boot?.last_invoice_date?.[store.company])
const isStale = computed(() => {
  if (!lastInvoice.value || !store.boot) return false
  return (new Date(store.boot.today) - new Date(lastInvoice.value)) / 864e5 > 30
})
const companyShort = computed(() => (store.company || '').replace(/^شركة\s+/, '').replace(/\s+للوحات.*?(\d+)$/, ' $1'))

const rangeText = computed(() => {
  if (store.period === 'custom') return store.fromDate && store.toDate ? `${dateAr(store.fromDate)} – ${dateAr(store.toDate)}` : 'اختر الفترة'
  const d = store.asOf ? new Date(store.asOf) : new Date()
  const label = { month: 'الشهر الحالي', quarter: 'الربع الحالي', ytd: 'منذ بداية السنة المالية' }[store.period]
  return `${label} حتى ${dateAr(store.asOf)}`
})

async function refresh() {
  refreshing.value = true
  store.forceRefresh = true
  store.refreshTick++
  setTimeout(() => (refreshing.value = false), 400)
}
</script>
