<template>
  <section class="card repfilters" aria-label="خيارات التقرير">
    <label class="field">
      <span class="lbl">السنة</span>
      <select v-model.number="f.year" class="sel">
        <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
      </select>
    </label>
    <div class="seg" role="group" aria-label="نوع المستند">
      <button v-for="o in DOCS" :key="o.key" type="button" :class="{ on: f.document_type === o.key }"
        :aria-pressed="f.document_type === o.key" @click="f.document_type = o.key">{{ o.label }}</button>
    </div>
    <div class="seg" role="group" aria-label="المبلغ">
      <button v-for="o in AMOUNTS" :key="o.key" type="button" :class="{ on: f.amount === o.key }"
        :aria-pressed="f.amount === o.key" @click="f.amount = o.key">{{ o.label }}</button>
    </div>
    <label class="field">
      <span class="lbl">تحديد المندوب</span>
      <select v-model="f.mode" class="sel">
        <option v-for="o in MODES" :key="o.key" :value="o.key">{{ o.label }}</option>
      </select>
    </label>
    <label v-if="f.document_type === 'Sales Invoice'" class="field check">
      <input v-model="f.include_returns" type="checkbox" />
      <span>خصم المرتجعات</span>
    </label>
    <button type="button" class="btn no-print" :disabled="!data || !!exporting" @click="exportExcel">{{ exporting ? 'جارٍ التصدير…' : 'تصدير Excel' }}</button>
    <span v-if="exportError" class="lbl neg" role="alert">{{ exportError }}</span>
  </section>

  <ViewState :loading="loading" :error="error" :has-data="!!data" @retry="load">
    <template v-if="data">
      <section class="grid-kpi">
        <KpiCard :label="`إجمالي ${docLabel} ${data.filters.year}`" :value="data.total"
          :note="f.amount === 'net' ? 'الصافي قبل الضريبة' : 'الإجمالي شامل الضريبة'" tone="neu" />
        <KpiCard label="المندوبون" :value="int(people.length)" unit="مندوباً"
          :note="people.length ? `متوسط ${amtStr(data.total / people.length)} للمندوب` : ''" tone="neu" />
        <KpiCard v-if="people[0]" label="الأعلى مبيعاً" :value="people[0].total"
          :note="`${people[0].name} · ${pct(people[0].share)}`" tone="pos" />
        <KpiCard v-if="bestMonth" label="أفضل شهر" :value="bestMonth.value" :note="bestMonth.name" tone="neu" />
        <KpiCard v-if="unassigned" label="غير محدد" :value="unassigned.total"
          :note="`${pct(unassigned.share)} من الإجمالي بلا مندوب`" tone="warn" />
      </section>

      <section class="rowwrap">
        <div class="card f2">
          <div class="card-head">
            <h2>{{ docLabel }} شهرياً حسب المندوب</h2>
            <div class="legend">
              <span v-for="s in stackSeries" :key="s.name"><i class="dot" :style="{ background: s.color }"></i>{{ s.name }}</span>
            </div>
          </div>
          <EChart :option="chart" height="320px" :label="`${docLabel} شهرياً حسب المندوب`" />
        </div>
        <div class="card f1">
          <h2>الحصة من الإجمالي</h2>
          <BarList :rows="shareRows" />
          <div v-if="people.length > 10" class="line-row lbl">
            <span>مندوبون آخرون ({{ int(people.length - 10) }})</span><span class="num">{{ amtStr(othersTotal) }}</span>
          </div>
        </div>
      </section>

      <section class="card">
        <div class="card-head">
          <h2>التفصيل الشهري — {{ docLabel }} {{ data.filters.year }}</h2>
          <span class="lbl">لون الخلية يزداد قتامة كلما ارتفعت القيمة</span>
        </div>
        <div class="table-wrap matrix-wrap">
          <table class="tbl matrix">
            <thead>
              <tr>
                <th class="sticky">المندوب</th>
                <th v-for="m in data.month_names" :key="m" class="c">{{ m }}</th>
                <th class="c">الإجمالي</th>
                <th class="c">النسبة</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in data.rows" :key="r.name" :class="{ unassigned: r.unassigned }">
                <td class="sticky">
                  <div class="person">
                    <span class="rank num">{{ r.unassigned ? '—' : i + 1 }}</span>
                    <span class="who">
                      <span class="nm">{{ r.name }}</span>
                      <span v-if="r.code" class="lbl num">{{ r.code }}</span>
                    </span>
                  </div>
                </td>
                <td v-for="(v, m) in r.months" :key="m" class="c num" :style="heat(v)" :title="`${r.name} · ${data.month_names[m]}: ${money(v)}`">
                  {{ v ? amtStr(v) : '' }}
                </td>
                <td class="c num strong">{{ money(r.total) }}</td>
                <td class="c num">{{ pct(r.share) }}</td>
              </tr>
            </tbody>
            <tfoot>
              <tr>
                <td class="sticky strong">الإجمالي</td>
                <td v-for="(v, m) in data.month_totals" :key="m" class="c num strong">{{ v ? amtStr(v) : '' }}</td>
                <td class="c num strong">{{ money(data.total) }}</td>
                <td class="c num strong">100%</td>
              </tr>
              <tr>
                <td class="sticky lbl">النسبة المئوية</td>
                <td v-for="(v, m) in data.month_totals" :key="m" class="c num lbl">{{ data.total && v ? pct((v / data.total) * 100) : '' }}</td>
                <td class="c num lbl">100%</td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
        <div v-if="!data.rows.length" class="empty">لا توجد مستندات في هذه السنة</div>
      </section>

      <section v-if="data.sources.length" class="card">
        <h2>كيف حُدّد المندوب في الوضع الذكي</h2>
        <div class="stack">
          <div v-for="s in srcRows" :key="s.key" :style="{ width: s.share + '%', background: s.color }" :title="s.label"></div>
        </div>
        <div class="srcgrid">
          <div v-for="s in srcRows" :key="s.key" class="line-row">
            <span style="display: flex; align-items: center; gap: 8px"><i class="dot" :style="{ background: s.color }"></i>{{ s.label }}</span>
            <span><span class="lbl num">{{ int(s.count) }} مستند</span> · <b class="num">{{ pct(s.share, 0) }}</b></span>
          </div>
        </div>
        <span class="lbl">يؤخذ المندوب من حقل المندوب في المستند، فإن كان فارغاً أو بصيغة غير موجودة في قائمة المندوبين انتقل إلى المصدر التالي. كل مستند يُحسب مرة واحدة والإجمالي مطابق للسجل.</span>
      </section>
    </template>
  </ViewState>
</template>

<script setup>
import { computed, reactive, ref, watch, onMounted } from 'vue'
import { call, download } from '../api'
import { store } from '../store'
import KpiCard from '../components/KpiCard.vue'
import EChart from '../components/EChart.vue'
import BarList from '../components/BarList.vue'
import ViewState from '../components/ViewState.vue'
import { monthChart, PALETTE } from '../charts'
import { amtStr, int, money, pct } from '../format'

const DOCS = [
  { key: 'Sales Invoice', label: 'الفواتير' },
  { key: 'Sales Order', label: 'أوامر البيع' },
]
const AMOUNTS = [
  { key: 'net', label: 'صافي' },
  { key: 'grand', label: 'شامل الضريبة' },
]
const MODES = [
  { key: 'smart', label: 'ذكي — كل المصادر (موصى به)' },
  { key: 'field', label: 'حقل المندوب فقط (qout ownar)' },
  { key: 'team', label: 'فريق المبيعات (Sales Team)' },
  { key: 'creator', label: 'المستخدم الذي أنشأ المستند' },
]
const KEY = 'executive_cockpit_reps'
const thisYear = new Date().getFullYear()
let saved = {}
try {
  saved = JSON.parse(localStorage.getItem(KEY) || '{}')
} catch (e) {
  /* storage unavailable */
}
const f = reactive({
  year: saved.year || thisYear,
  document_type: saved.document_type || 'Sales Invoice',
  amount: saved.amount || 'net',
  mode: saved.mode || 'smart',
  include_returns: saved.include_returns ?? true,
})

const data = ref(null)
const loading = ref(false)
const error = ref(null)

async function load() {
  if (!store.company) return
  loading.value = true
  error.value = null
  try {
    data.value = await call('get_reps', {
      company: store.company, ...f, include_returns: f.include_returns ? 1 : 0, refresh: store.forceRefresh ? 1 : 0,
    })
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
    store.forceRefresh = false
  }
}
onMounted(load)
watch(() => [store.company, store.refreshTick, f.year, f.document_type, f.amount, f.mode, f.include_returns], load)
watch(f, () => {
  try {
    localStorage.setItem(KEY, JSON.stringify(f))
  } catch (e) {
    /* storage unavailable */
  }
})

const years = computed(() => {
  const ys = new Set(data.value?.years || [])
  ys.add(thisYear)
  ys.add(f.year)
  return [...ys].sort((a, b) => b - a)
})
const docLabel = computed(() => (f.document_type === 'Sales Order' ? 'أوامر البيع' : 'المبيعات'))
const people = computed(() => data.value.rows.filter((r) => !r.unassigned))
const unassigned = computed(() => data.value.rows.find((r) => r.unassigned))
const bestMonth = computed(() => {
  const t = data.value.month_totals
  const i = t.indexOf(Math.max(...t))
  return t[i] > 0 ? { name: data.value.month_names[i], value: t[i] } : null
})
const othersTotal = computed(() => people.value.slice(10).reduce((s, r) => s + r.total, 0))
const shareRows = computed(() =>
  people.value.slice(0, 10).map((r) => ({
    label: r.name, value: r.total, extra: pct(r.share, 0),
    part: r.estimated > 0 && r.total > 0 ? r.estimated : 0, partLabel: `تقديري: ${amtStr(r.estimated)}`,
  }))
)

const months = computed(() => Array.from({ length: 12 }, (_, i) => `${data.value.filters.year}-${String(i + 1).padStart(2, '0')}`))
const stackSeries = computed(() => {
  const top = data.value.rows.filter((r) => !r.unassigned).slice(0, 6)
  const rest = data.value.rows.filter((r) => !top.includes(r))
  const series = top.map((r, i) => ({ name: r.name, data: r.months, color: PALETTE[i % PALETTE.length] }))
  if (rest.length) {
    series.push({
      name: rest.length === 1 ? rest[0].name : 'الباقون',
      data: Array.from({ length: 12 }, (_, m) => rest.reduce((s, r) => s + r.months[m], 0)),
      color: 'var(--track)',
    })
  }
  return series
})
const chart = computed(() => monthChart(months.value, stackSeries.value, { stack: true }))

const cellMax = computed(() => Math.max(1, ...people.value.flatMap((r) => r.months.map(Math.abs))))
function heat(v) {
  if (!v) return {}
  if (v < 0) return { color: 'var(--neg)' }
  const a = Math.round(6 + (v / cellMax.value) * 44)
  return { background: `color-mix(in srgb, var(--s1) ${a}%, transparent)`, color: a > 34 ? '#fff' : undefined }
}

const SRC_COLORS = {
  doc_field: 'var(--s1)', doc_team: '#2F8F6B', order_field: 'var(--s3)', quotation: '#9B59B6',
  order_team: '#5D6D7E', creator: 'var(--s2)', customer: 'var(--warn)', none: 'var(--neg)',
}
const srcRows = computed(() => {
  const total = data.value.sources.reduce((s, x) => s + Math.abs(x.value), 0) || 1
  return data.value.sources.map((s) => ({ ...s, share: (Math.abs(s.value) / total) * 100, color: SRC_COLORS[s.key] || 'var(--muted)' }))
})

const exporting = ref(false)
const exportError = ref('')
function exportExcel() {
  exportError.value = ''
  exporting.value = true
  try {
    download('export_reps_excel', { company: store.company, ...f, include_returns: f.include_returns ? 1 : 0 })
  } catch (e) {
    exportError.value = 'تعذّر بدء التنزيل'
  }
  setTimeout(() => (exporting.value = false), 3000)
}
</script>

<style scoped>
.repfilters { flex-direction: row; flex-wrap: wrap; align-items: center; gap: 12px; padding: 14px 16px; }
.check { gap: 6px; font-size: 14px; cursor: pointer; }
.check input { width: 18px; height: 18px; accent-color: var(--s1); }
.btn {
  margin-inline-start: auto; border: 1px solid var(--line); background: var(--card); color: var(--ink);
  border-radius: 10px; padding: 8px 16px; min-height: 40px; cursor: pointer; font-size: 14px;
}
.btn:hover:not(:disabled) { background: var(--hover); }
.btn:disabled { opacity: .5; cursor: default; }

.matrix-wrap { max-height: 70vh; overflow: auto; }
.matrix { font-size: 13px; min-width: 1100px; }
.matrix th, .matrix td { padding: 8px 6px; }
.matrix .c { text-align: center; white-space: nowrap; }
.matrix td.c { border-radius: 4px; }
.matrix thead th { position: sticky; top: 0; background: var(--card); z-index: 1; }
.matrix .sticky { position: sticky; right: 0; background: var(--card); z-index: 2; min-width: 190px; }
.matrix thead .sticky { z-index: 3; }
.person { display: flex; align-items: center; gap: 10px; }
.rank { width: 22px; height: 22px; border-radius: 6px; background: var(--track); font-size: 12px; display: inline-flex; align-items: center; justify-content: center; flex: none; }
.who { display: flex; flex-direction: column; min-width: 0; }
.nm { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 220px; }
.strong { font-weight: 700; }
.matrix tfoot td { border-top: 1px solid var(--line); border-bottom: 0; background: var(--hover); }
.matrix tfoot td.sticky { background: var(--hover); }
.unassigned td { color: var(--warn); }
.srcgrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 8px 24px; }
</style>
