<template>
  <ViewState :loading="loading" :error="error" :has-data="!!data" @retry="load">
    <template v-if="data">
      <section class="grid-kpi" aria-label="مراحل دورة المبيعات">
        <a v-for="(s, i) in data.stages" :key="s.key" class="card stage" :href="listUrl(s.route)" target="_blank" rel="noopener">
          <span class="lbl">المرحلة {{ i + 1 }}</span>
          <span style="font-size: 16px; font-weight: 600">{{ s.label }}</span>
          <div class="kpi-value"><span class="num">{{ amt(s.value).n }}</span><span class="lbl">{{ amt(s.value).u }} ر.س</span></div>
          <span class="lbl">{{ int(s.count) }} {{ COUNT_LABEL[s.key] }}</span>
        </a>
      </section>

      <section class="rowwrap">
        <div class="card f2">
          <div class="card-head">
            <h2>عروض الأسعار وأوامر البيع — شهرياً</h2>
            <div class="legend">
              <span><i class="dot" style="background: var(--s1)"></i>عروض الأسعار</span>
              <span><i class="dot" style="background: var(--s2)"></i>أوامر البيع</span>
            </div>
          </div>
          <EChart :option="qtChart" height="280px" label="قيمة عروض الأسعار وأوامر البيع شهرياً" />
        </div>
        <div class="card f1">
          <h2>مصير عروض الأسعار</h2>
          <div class="kpi-value">
            <span class="num" style="font-size: 40px; color: var(--s1)">{{ pct(data.quotations.conversion, 0) }}</span>
            <span class="lbl">نسبة التحويل إلى أمر بيع</span>
          </div>
          <div class="stack">
            <div v-for="r in qtRows" :key="r.key" :style="{ width: r.share + '%', background: r.color }"></div>
          </div>
          <div v-for="r in qtRows" :key="r.key" class="line-row">
            <span style="display: flex; align-items: center; gap: 8px"><i class="dot" :style="{ background: r.color }"></i>{{ r.label }}</span>
            <span><span class="lbl num">{{ amtStr(r.value) }}</span> · <b class="num">{{ int(r.count) }}</b></span>
          </div>
        </div>
      </section>

      <section class="rowwrap">
        <div class="card f2">
          <h2>أوامر البيع حسب حالة الفوترة</h2>
          <div class="tiles">
            <div class="tile" style="background: var(--soft)">
              <span class="lbl">مفوترة بالكامل</span>
              <span class="num">{{ amtStr(bill.full?.value) }}</span>
              <span class="lbl">{{ int(bill.full?.count || 0) }} أمر</span>
            </div>
            <div class="tile">
              <span class="lbl">مفوترة جزئياً</span>
              <span class="num">{{ amtStr(bill.partial?.value) }}</span>
              <span class="lbl">{{ int(bill.partial?.count || 0) }} أمر · المتبقي {{ amtStr(bill.partial?.unbilled || 0) }}</span>
            </div>
            <div class="tile" style="background: var(--negsoft)">
              <span class="lbl">غير مفوترة</span>
              <span class="num">{{ amtStr(bill.none?.value) }}</span>
              <span class="lbl">{{ int(bill.none?.count || 0) }} أمر</span>
            </div>
          </div>
          <span class="lbl">نسبة الفوترة لأوامر كل شهر (بالقيمة)</span>
          <EChart :option="billChart" height="200px" label="نسبة فوترة أوامر البيع لكل شهر" />
        </div>
      </section>

      <section class="rowwrap">
        <div class="card f2">
          <div class="card-head">
            <h2>المبيعات حسب المندوب (صافي)</h2>
            <div class="legend">
              <span><i class="dot" style="background: var(--s1)"></i>مؤكد</span>
              <span><i class="dot hatch"></i>تقديري من بطاقة العميل</span>
            </div>
          </div>
          <BarList :rows="reps" />
          <div v-if="sp.others.count" class="line-row lbl">
            <span>مندوبون آخرون ({{ int(sp.others.count) }})</span><span class="num">{{ amtStr(sp.others.v) }}</span>
          </div>
          <div v-if="sp.unassigned" class="line-row" style="color: var(--warn)">
            <span>غير محدد</span><span class="num">{{ amtStr(sp.unassigned) }}</span>
          </div>
          <div class="line-row" style="font-weight: 700; padding-top: 8px; border-top: 1px solid var(--line)">
            <span>الإجمالي — مطابق لسجل المبيعات</span><span class="num">{{ money(sp.total) }}</span>
          </div>
        </div>
        <div class="card f1">
          <h2>من أين حُدّد المندوب؟</h2>
          <div class="stack">
            <div v-for="s in srcRows" :key="s.key" :style="{ width: s.share + '%', background: s.color }"></div>
          </div>
          <div v-for="s in srcRows" :key="s.key" class="line-row">
            <span style="display: flex; align-items: center; gap: 8px"><i class="dot" :style="{ background: s.color }"></i>{{ s.label }}</span>
            <span><span class="lbl num">{{ int(s.count) }} فاتورة</span> · <b class="num">{{ pct(s.share, 0) }}</b></span>
          </div>
          <span class="lbl">كل فاتورة تُنسب مرة واحدة من أول مصدر متوفر بهذا الترتيب، والفواتير المشتركة تُقسم حسب النسبة.</span>
        </div>
      </section>

      <section class="card">
        <h2>أكبر العملاء — مبيعات الفترة</h2>
        <BarList :rows="customers" />
      </section>
    </template>
  </ViewState>
</template>

<script setup>
import { computed } from 'vue'
import { useView } from '../api'
import { store } from '../store'
import EChart from '../components/EChart.vue'
import BarList from '../components/BarList.vue'
import ViewState from '../components/ViewState.vue'
import { monthChart } from '../charts'
import { amt, amtStr, int, money, pct, QUOTATION_STATUS, deskUrl } from '../format'

const { data, loading, error, load } = useView('get_sales')
const COUNT_LABEL = { quotation: 'عرض سعر', order: 'أمر بيع', invoice: 'فاتورة', payment: 'سند قبض' }
const Q_COLORS = { Ordered: 'var(--s1)', 'Partially Ordered': 'var(--s3)', Expired: 'var(--s2)', Open: 'var(--line)', Replied: 'var(--line)', Lost: 'var(--neg)' }

const listUrl = (route) => `${route}?company=${encodeURIComponent(store.company)}`
const bill = computed(() => data.value.orders.billing || {})

const qtRows = computed(() => {
  const st = data.value.quotations.status
  const total = data.value.quotations.count || 1
  return Object.keys(st)
    .sort((a, b) => st[b].count - st[a].count)
    .map((key) => ({
      key, label: QUOTATION_STATUS[key] || key, count: st[key].count, value: st[key].value,
      share: (st[key].count / total) * 100, color: Q_COLORS[key] || 'var(--muted)',
    }))
})

const qtChart = computed(() =>
  monthChart(data.value.months, [
    { name: 'عروض الأسعار', data: data.value.quotations.trend, color: 'var(--s1)' },
    { name: 'أوامر البيع', data: data.value.orders.trend, color: 'var(--s2)' },
  ])
)
const billChart = computed(() =>
  monthChart(
    data.value.months,
    [{ name: 'نسبة الفوترة', data: data.value.orders.billed_pct_trend.map((v) => (v ? Math.round(v) : null)), color: 'var(--s1)' }],
    { fmt: (v) => pct(v, 0) }
  )
)
const sp = computed(() => data.value.sales_persons)
const reps = computed(() =>
  sp.value.rows.map((r) => ({
    label: r.sales_person, value: r.v, extra: `${int(r.n)} فاتورة`,
    part: r.estimated > 0 && r.v > 0 ? r.estimated : 0,
    partLabel: `تقديري: ${amtStr(r.estimated)}`,
  }))
)
const SRC_COLORS = { doc_field: 'var(--s1)', doc_team: '#2F8F6B', order_field: 'var(--s3)', quotation: '#9B59B6', order_team: '#5D6D7E', creator: 'var(--s2)', customer: 'var(--warn)', none: 'var(--neg)' }
const srcRows = computed(() => {
  const total = sp.value.sources.reduce((s, x) => s + Math.abs(x.value), 0) || 1
  return sp.value.sources.map((s) => ({ ...s, share: (Math.abs(s.value) / total) * 100, color: SRC_COLORS[s.key] || 'var(--muted)' }))
})
const customers = computed(() =>
  data.value.top_customers.map((r) => ({
    label: r.customer_name, value: r.v, extra: `${int(r.n)} فاتورة`, href: deskUrl(`customer/${encodeURIComponent(r.customer)}`),
  }))
)
</script>
