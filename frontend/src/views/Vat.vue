<template>
  <section class="card repfilters" aria-label="الفترة الضريبية">
    <label class="field">
      <span class="lbl">السنة</span>
      <select v-model.number="f.year" class="sel">
        <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
      </select>
    </label>
    <div class="seg" role="group" aria-label="نوع الفترة">
      <button v-for="o in TYPES" :key="o.key" type="button" :class="{ on: f.period_type === o.key }"
        :aria-pressed="f.period_type === o.key" @click="setType(o.key)">{{ o.label }}</button>
    </div>
    <label class="field">
      <span class="lbl">{{ f.period_type === 'quarter' ? 'الربع' : 'الشهر' }}</span>
      <select v-model.number="f.num" class="sel">
        <option v-for="(n, i) in periodNames" :key="n" :value="i + 1">{{ n }}</option>
      </select>
    </label>
    <div class="exports">
      <button v-for="e in EXPORTS" :key="e.kind" type="button" class="btn" :class="{ primary: e.kind === 'all' }"
        :disabled="!data || !!exporting" @click="exportExcel(e.kind)">{{ exporting === e.kind ? 'جارٍ التصدير…' : e.label }}</button>
    </div>
    <span v-if="exportError" class="lbl neg" role="alert">{{ exportError }}</span>
  </section>

  <ViewState :loading="loading" :error="error" :has-data="!!data" @retry="load">
    <template v-if="data">
      <section class="grid-kpi">
        <KpiCard label="ضريبة المخرجات (المبيعات)" :value="data.totals.output" :note="`${int(data.counts.sales_vat)} مستند عليه ضريبة`" tone="neu" />
        <KpiCard label="ضريبة المدخلات (المشتريات)" :value="data.totals.input" :note="`${int(data.counts.purchases_vat)} مستند عليه ضريبة`" tone="neu" />
        <KpiCard :label="box16.vat >= 0 ? 'صافي الضريبة المستحقة' : 'صافي الضريبة المستردة'" :value="Math.abs(box16.vat)"
          :note="`البند 16 · ${data.filters.label}`" :tone="box16.vat >= 0 ? 'warn' : 'pos'" />
        <div class="card kpi match" :class="matched ? 'ok' : 'bad'">
          <span class="lbl">المطابقة مع ميزان المراجعة</span>
          <div class="kpi-value">
            <span class="num">{{ matched ? 'مطابق' : 'غير مطابق' }}</span>
          </div>
          <span class="kpi-note" :class="matched ? 'pos' : 'neg'">
            {{ matched ? 'الفرق 0.00 ر.س في الحسابين' : `فرق ${money2(maxDiff)} ر.س` }}
          </span>
        </div>
      </section>

      <section class="card">
        <div class="card-head">
          <h2>إقرار ضريبة القيمة المضافة — {{ data.filters.label }}</h2>
          <span class="lbl">الرقم الضريبي للمنشأة: <b class="num">{{ data.filters.company_vat || '—' }}</b></span>
        </div>
        <div class="table-wrap">
          <table class="tbl ret">
            <thead>
              <tr>
                <th class="no">البند</th>
                <th>الوصف</th>
                <th class="c">المبلغ (ر.س)</th>
                <th class="c">التعديلات (ر.س)</th>
                <th class="c">ضريبة القيمة المضافة (ر.س)</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="b in data.boxes" :key="b.no">
                <tr v-if="SECTION[b.no]" class="section"><td colspan="5">{{ SECTION[b.no] }}</td></tr>
                <tr :class="{ total: TOTALS.includes(b.no), dim: isEmpty(b) }">
                  <td class="no num">{{ b.no }}</td>
                  <td>{{ b.label }}</td>
                  <td class="c num">{{ Number(b.no) <= 12 ? money2(b.amount) : '' }}</td>
                  <td class="c num" :class="{ neg: b.adjustment < 0 }">{{ Number(b.no) <= 12 ? money2(b.adjustment) : '' }}</td>
                  <td class="c num strong">{{ money2(b.vat) }}</td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <span class="lbl">
          المبالغ قبل الضريبة، والمرتجعات وإشعارات الدائن في عمود التعديلات. مبلغ البندين 1 و7 = الضريبة ÷ 15% كما تحسبه بوابة الزكاة. البنود 2 و5 و8 و9 و11 و14 و15 لا تُستخرج من النظام وتُعبّأ يدوياً في بوابة الزكاة عند وجودها.
          البند 10 يشمل كل فواتير المشتريات بلا ضريبة.
        </span>
      </section>

      <section class="rowwrap">
        <div class="card f2">
          <h2>المطابقة مع ميزان المراجعة</h2>
          <div class="table-wrap">
            <table class="tbl">
              <thead>
                <tr><th>الحساب</th><th class="c">رصيد أول المدة</th><th class="c">مدين الفترة</th><th class="c">دائن الفترة</th><th class="c">رصيد آخر المدة</th></tr>
              </thead>
              <tbody>
                <tr v-for="t in data.trial_balance" :key="t.key">
                  <td>
                    <div class="acc"><b>{{ ACC_LABEL[t.key] }}</b><span class="lbl">{{ t.account }}</span></div>
                  </td>
                  <td class="c num">{{ dc(t.opening) }}</td>
                  <td class="c num">{{ money2(t.debit) }}</td>
                  <td class="c num">{{ money2(t.credit) }}</td>
                  <td class="c num">{{ dc(t.closing) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="recon">
            <div v-for="r in recon" :key="r.key" class="recon-row">
              <span class="recon-title">{{ r.title }}</span>
              <span class="recon-eq num">
                {{ money2(r.movement) }} <span class="lbl">حركة الحساب قبل قيد التسوية</span>
                <span class="op">=</span>
                {{ money2(r.report) }} <span class="lbl">التقرير</span>
              </span>
              <span class="badge" :class="r.diff ? 'bad' : 'ok'">{{ r.diff ? `فرق ${money2(r.diff)}` : 'مطابق ✓' }}</span>
            </div>
          </div>
          <span class="lbl">كل سطر في السجلين مأخوذ من قيود حسابي الضريبة نفسها، لذلك مجموع السجل يساوي حركة الحساب في الميزان. قيد التسوية الشهري الذي يقفل الحسابين على حساب التسوية مستبعد من الحركة.</span>
        </div>
        <div class="card f1">
          <h2>قيد التسوية الشهري مقابل التقرير</h2>
          <div v-for="m in data.monthly" :key="m.month" class="settle">
            <div class="line-row"><b>{{ monthName(m.month) }} {{ m.month.slice(0, 4) }}</b>
              <span class="lbl num">{{ m.vouchers.join('، ') || 'لم يُسجّل قيد التسوية بعد' }}</span>
            </div>
            <template v-if="m.vouchers.length">
              <div v-for="s in settleRows(m)" :key="s.label" class="line-row">
                <span>{{ s.label }}</span>
                <span :class="s.diff ? 'warn' : 'pos'" class="num">{{ s.diff ? `فرق ${money2(s.diff)}` : 'مطابق ✓' }}</span>
              </div>
            </template>
            <div v-else class="line-row lbl">
              <span>المبلغ المتوقع في قيد التسوية</span><span class="num">{{ money2(m.output - m.input) }}</span>
            </div>
          </div>
          <div v-if="!data.monthly.length" class="empty">لا توجد حركة ضريبية في هذه الفترة</div>
          <span class="lbl">الفرق يعني أن قيد التسوية سُجّل بمبلغ يختلف عن حركة الحساب في ذلك الشهر، ويبقى الفرق رصيداً في حساب الضريبة.</span>
        </div>
      </section>

      <section class="card">
        <h2>ملاحظات قبل تقديم الإقرار</h2>
        <div class="checks">
          <div v-for="c in data.checks" :key="c.key" class="alert" :class="LEVEL[c.level]">
            <i class="dot"></i>
            <div style="display: flex; flex-direction: column; gap: 2px; flex: 1">
              <span style="font-size: 14px; font-weight: 600">{{ c.title }}</span>
              <span class="lbl">{{ c.level === 'ok' ? 'لا يوجد' : c.desc }}</span>
            </div>
            <div v-if="c.count" class="chk-num">
              <b class="num">{{ int(c.count) }}</b>
              <span class="lbl num">ضريبة {{ money2(c.vat) }}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="card">
        <div class="card-head">
          <div class="seg" role="tablist" aria-label="السجل">
            <button v-for="t in REGS" :key="t.key" type="button" role="tab" :class="{ on: reg.kind === t.key }"
              :aria-selected="reg.kind === t.key" @click="reg.kind = t.key">{{ t.label }}
              <span class="lbl num">({{ int(data.register_totals[t.key].count) }})</span></button>
          </div>
          <input v-model="reg.q" type="search" class="sel search" placeholder="بحث برقم المستند أو الاسم أو الرقم الضريبي" aria-label="بحث في السجل" />
        </div>
        <div v-if="reg.loading" class="state">جارٍ تحميل السجل…</div>
        <div v-else-if="reg.error" class="state neg">{{ reg.error }}</div>
        <template v-else-if="regRows">
          <div class="table-wrap reg-wrap">
            <table class="tbl reg">
              <thead>
                <tr>
                  <th>المستند</th>
                  <th>التاريخ</th>
                  <th v-if="reg.kind === 'purchases'">فاتورة المورد</th>
                  <th>النوع</th>
                  <th>{{ reg.kind === 'sales' ? 'العميل' : 'المورد / البيان' }}</th>
                  <th>الرقم الضريبي</th>
                  <th class="c">الخاضع 15%</th>
                  <th class="c">صفري / غير خاضع</th>
                  <th class="c">الضريبة</th>
                  <th class="c">الإجمالي</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in pageRows" :key="r.doctype + r.name">
                  <td><a :href="docUrl(r)" target="_blank" rel="noopener" class="num">{{ r.name }}</a>
                    <div v-if="r.ref" class="lbl num">على {{ r.ref }}</div></td>
                  <td class="num nowrap">{{ r.date }}</td>
                  <td v-if="reg.kind === 'purchases'" class="num">{{ r.bill_no || '—' }}</td>
                  <td class="nowrap">{{ r.kind }}
                    <div v-if="r.category !== 'standard'" class="lbl">{{ CAT[r.category] }}</div></td>
                  <td class="party">{{ r.party || '—' }}</td>
                  <td class="num" :class="{ warn: !r.vat_no && r.vat && reg.kind === 'purchases' }">{{ r.vat_no || '—' }}</td>
                  <td class="c num">{{ money2(r.std) }}<span v-if="r.estimated" class="lbl" title="محسوب من الضريبة ÷ 15%"> *</span></td>
                  <td class="c num">{{ r.zero ? money2(r.zero) : '' }}</td>
                  <td class="c num strong" :class="{ neg: r.vat < 0 }">{{ money2(r.vat) }}</td>
                  <td class="c num">{{ money2(r.total) }}</td>
                </tr>
              </tbody>
              <tfoot>
                <tr>
                  <td :colspan="reg.kind === 'purchases' ? 6 : 5" class="strong">
                    {{ reg.q ? `إجمالي نتائج البحث (${int(filtered.length)})` : `إجمالي السجل (${int(regRows.length)} مستند)` }}
                  </td>
                  <td class="c num strong">{{ money2(sumOf('std')) }}</td>
                  <td class="c num strong">{{ money2(sumOf('zero')) }}</td>
                  <td class="c num strong">{{ money2(sumOf('vat')) }}</td>
                  <td class="c num strong">{{ money2(sumOf('total')) }}</td>
                </tr>
              </tfoot>
            </table>
          </div>
          <div v-if="!filtered.length" class="empty">لا توجد نتائج</div>
          <div v-if="pages > 1" class="pager">
            <button type="button" class="btn" :disabled="reg.page <= 1" @click="reg.page--">السابق</button>
            <span class="lbl num">صفحة {{ reg.page }} من {{ pages }}</span>
            <button type="button" class="btn" :disabled="reg.page >= pages" @click="reg.page++">التالي</button>
          </div>
          <span v-if="reg.kind === 'purchases'" class="lbl">* قيود يومية وسندات صرف عليها ضريبة: الضريبة من القيد، والمبلغ الخاضع محسوب منها.</span>
        </template>
      </section>
    </template>
  </ViewState>
</template>

<script setup>
import { computed, reactive, ref, watch, onMounted } from 'vue'
import { call, download } from '../api'
import { store } from '../store'
import KpiCard from '../components/KpiCard.vue'
import ViewState from '../components/ViewState.vue'
import { int, money2, monthName, deskUrl } from '../format'

const MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
const QUARTERS = ['الربع الأول', 'الربع الثاني', 'الربع الثالث', 'الربع الرابع']
const TYPES = [
  { key: 'month', label: 'شهري' },
  { key: 'quarter', label: 'ربع سنوي' },
]
const EXPORTS = [
  { kind: 'all', label: 'الإقرار والسجلات Excel' },
  { kind: 'sales', label: 'سجل المبيعات' },
  { kind: 'purchases', label: 'سجل المشتريات' },
]
const REGS = [
  { key: 'sales', label: 'سجل المبيعات' },
  { key: 'purchases', label: 'سجل المشتريات' },
]
const SECTION = { 1: 'ضريبة القيمة المضافة على المبيعات', 7: 'ضريبة القيمة المضافة على المشتريات', 13: 'صافي الضريبة' }
const TOTALS = ['6', '12', '13', '16']
const ACC_LABEL = { output: 'ضريبة المخرجات', input: 'ضريبة المدخلات', settlement: 'حساب تسوية الضريبة' }
const LEVEL = { high: 'high', warn: 'medium', info: 'info', ok: 'okay' }
const CAT = { standard: 'أساسية 15%', mixed: 'أساسية وصفرية', zero: 'صفرية / غير خاضعة', export: 'صادرات', adjustment: 'قيد على حساب الضريبة' }
const DOC_SLUG = { 'Sales Invoice': 'sales-invoice', 'Purchase Invoice': 'purchase-invoice', 'Journal Entry': 'journal-entry', 'Payment Entry': 'payment-entry' }
const PAGE = 50

// default: the last completed month (the one being filed)
const now = new Date()
const last = new Date(now.getFullYear(), now.getMonth() - 1, 1)
const KEY = 'executive_cockpit_vat'
let saved = {}
try {
  saved = JSON.parse(localStorage.getItem(KEY) || '{}')
} catch (e) {
  /* storage unavailable */
}
const f = reactive({
  year: saved.year || last.getFullYear(),
  period_type: saved.period_type || 'month',
  num: saved.num || last.getMonth() + 1,
})

const data = ref(null)
const loading = ref(false)
const error = ref(null)

async function load() {
  if (!store.company) return
  loading.value = true
  error.value = null
  try {
    data.value = await call('get_vat', { company: store.company, ...f, refresh: store.forceRefresh ? 1 : 0 })
    regCache.clear()
    loadRegister()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
    store.forceRefresh = false
  }
}
onMounted(load)
watch(() => [store.company, store.refreshTick, f.year, f.period_type, f.num], load)
watch(f, () => {
  try {
    localStorage.setItem(KEY, JSON.stringify(f))
  } catch (e) {
    /* storage unavailable */
  }
})

function setType(t) {
  if (f.period_type === t) return
  // keep the same point in the year when switching month <-> quarter
  f.num = t === 'quarter' ? Math.ceil(f.num / 3) : (f.num - 1) * 3 + 1
  f.period_type = t
}

const years = computed(() => {
  const ys = new Set(data.value?.years || [])
  ys.add(now.getFullYear())
  ys.add(f.year)
  return [...ys].sort((a, b) => b - a)
})
const periodNames = computed(() => (f.period_type === 'quarter' ? QUARTERS : MONTHS))
const box16 = computed(() => data.value.boxes.find((b) => b.no === '16'))
const isEmpty = (b) => !b.amount && !b.adjustment && !b.vat

const tb = computed(() => Object.fromEntries(data.value.trial_balance.map((t) => [t.key, t])))
const recon = computed(() =>
  [
    { key: 'output', title: 'ضريبة المخرجات', report: data.value.totals.output },
    { key: 'input', title: 'ضريبة المدخلات', report: data.value.totals.input },
  ].map((r) => {
    const movement = tb.value[r.key]?.movement ?? 0
    return { ...r, movement, diff: Math.round((movement - r.report) * 100) / 100 }
  })
)
const maxDiff = computed(() => Math.max(...recon.value.map((r) => Math.abs(r.diff))))
const matched = computed(() => maxDiff.value === 0)

// debit-positive balance shown with its side
const dc = (v) => (Math.abs(v) < 0.005 ? '0.00' : `${money2(Math.abs(v))} ${v > 0 ? 'مدين' : 'دائن'}`)

function settleRows(m) {
  const r2 = (v) => Math.round(v * 100) / 100
  return [
    { label: `المخرجات ${money2(m.settle_output)}`, diff: r2(m.settle_output - m.output) },
    { label: `المدخلات ${money2(m.settle_input)}`, diff: r2(m.settle_input - m.input) },
  ]
}

// ---- registers (loaded separately; the purchase register can be thousands of rows)
const regCache = new Map()
const reg = reactive({ kind: 'sales', q: '', page: 1, loading: false, error: '' })
const regRows = ref(null)

async function loadRegister() {
  const key = `${store.company}|${f.year}|${f.period_type}|${f.num}|${reg.kind}`
  if (regCache.has(key)) {
    regRows.value = regCache.get(key)
    return
  }
  reg.loading = true
  reg.error = ''
  try {
    const res = await call('get_vat_register', { company: store.company, ...f, kind: reg.kind })
    regCache.set(key, res.rows)
    regRows.value = res.rows
  } catch (e) {
    reg.error = e.message
  } finally {
    reg.loading = false
  }
}
watch(() => reg.kind, () => {
  reg.page = 1
  loadRegister()
})
watch(() => reg.q, () => (reg.page = 1))

const filtered = computed(() => {
  const rows = regRows.value || []
  const q = reg.q.trim().toLowerCase()
  if (!q) return rows
  return rows.filter((r) => [r.name, r.party, r.vat_no, r.bill_no, r.ref].some((x) => x && String(x).toLowerCase().includes(q)))
})
const pages = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE)))
const pageRows = computed(() => filtered.value.slice((reg.page - 1) * PAGE, reg.page * PAGE))
// sum in halalas to avoid float drift
const sumOf = (k) => filtered.value.reduce((s, r) => s + Math.round(r[k] * 100), 0) / 100
const docUrl = (r) => deskUrl(`${DOC_SLUG[r.doctype] || r.doctype.toLowerCase().replace(/ /g, '-')}/${encodeURIComponent(r.name)}`)

// ---- Excel (normal browser download; the server builds and names the file)
const exporting = ref('')
const exportError = ref('')
function exportExcel(kind) {
  exportError.value = ''
  exporting.value = kind
  try {
    download('export_vat_excel', { company: store.company, ...f, kind })
  } catch (e) {
    exportError.value = 'تعذّر بدء التنزيل'
  }
  // the file is generated on the server; keep the button busy for a moment so it isn't clicked twice
  setTimeout(() => (exporting.value = ''), 4000)
}
</script>

<style scoped>
.repfilters { flex-direction: row; flex-wrap: wrap; align-items: center; gap: 12px; padding: 14px 16px; }
.exports { display: flex; flex-wrap: wrap; gap: 8px; margin-inline-start: auto; }
.btn {
  border: 1px solid var(--line); background: var(--card); color: var(--ink);
  border-radius: 10px; padding: 8px 14px; min-height: 40px; cursor: pointer; font-size: 14px;
}
.btn.primary { background: var(--s1); border-color: var(--s1); color: #fff; }
.btn:hover:not(:disabled) { filter: brightness(.97); }
.btn:disabled { opacity: .5; cursor: default; }

.match .num { font-size: 26px; }
.match.ok { background: var(--possoft); }
.match.bad { background: var(--negsoft); }

.ret { font-size: 14px; }
.ret .no { width: 56px; text-align: center; }
.ret .c, .tbl .c { text-align: left; white-space: nowrap; }
.ret .section td { background: var(--hover); font-weight: 700; font-size: 13px; color: var(--muted); padding: 8px; }
.ret .total td { font-weight: 700; background: color-mix(in srgb, var(--s1) 7%, transparent); }
.ret .dim td { color: var(--muted); }
.strong { font-weight: 700; }
.nowrap { white-space: nowrap; }

.acc { display: flex; flex-direction: column; gap: 2px; }
.recon { display: flex; flex-direction: column; gap: 8px; }
.recon-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; padding: 10px 12px; border-radius: 10px; background: var(--hover); }
.recon-title { font-weight: 600; min-width: 110px; }
.recon-eq { flex: 1; font-weight: 600; }
.recon-eq .op { margin: 0 8px; color: var(--muted); }
.badge { padding: 4px 10px; border-radius: 99px; font-size: 13px; font-weight: 600; }
.badge.ok { background: var(--possoft); color: var(--pos); }
.badge.bad { background: var(--negsoft); color: var(--neg); }

.settle { display: flex; flex-direction: column; gap: 4px; padding-bottom: 8px; border-bottom: 1px solid var(--line); }
.settle:last-of-type { border-bottom: 0; }

.checks { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 10px; }
.alert.info { background: var(--hover); }
.alert.info .dot { background: var(--s1); }
.alert.okay { background: var(--possoft); }
.alert.okay .dot { background: var(--pos); }
.chk-num { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; white-space: nowrap; }
.chk-num b { font-size: 18px; }

.search { min-width: 260px; flex: 1; max-width: 420px; }
.reg-wrap { max-height: 70vh; overflow: auto; }
.reg { font-size: 13px; min-width: 1050px; }
.reg th, .reg td { padding: 8px 6px; }
.reg thead th { position: sticky; top: 0; background: var(--card); z-index: 1; }
.reg tfoot td { position: sticky; bottom: 0; background: var(--hover); border-top: 1px solid var(--line); }
.party { max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pager { display: flex; align-items: center; justify-content: center; gap: 12px; }
@media (max-width: 640px) {
  .exports { margin-inline-start: 0; width: 100%; }
  .search { min-width: 0; max-width: none; width: 100%; }
}
</style>
