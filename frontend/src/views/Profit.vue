<template>
  <ViewState :loading="loading" :error="error" :has-data="!!data" @retry="load">
    <template v-if="data">
      <section class="grid-kpi">
        <KpiCard label="الإيرادات" :value="k.income.value" :trend="data.trend.income" v-bind="note(k.income.delta)" />
        <KpiCard label="المصروفات" :value="k.expense.value" :trend="data.trend.expense" v-bind="note(k.expense.delta, false)" />
        <KpiCard label="صافي الربح" :value="k.net.value" :trend="data.trend.net" v-bind="note(k.net.delta)" />
        <KpiCard label="هامش صافي الربح" :value="k.margin !== null ? pct(k.margin) : '—'" unit=""
          :note="k.prev_margin !== null ? `الفترة المقابلة ${pct(k.prev_margin)}` : 'لا توجد بيانات كافية للمقارنة'"
          :tone="k.margin === null ? 'neu' : k.margin >= 0 ? 'pos' : 'neg'" />
      </section>

      <section class="rowwrap">
        <div class="card f3">
          <div class="card-head">
            <h2>الإيرادات والمصروفات وصافي الربح — آخر 12 شهراً</h2>
            <div class="legend">
              <span><i class="dot" style="background: var(--s1)"></i>الإيرادات</span>
              <span><i class="dot" style="background: var(--s2)"></i>المصروفات</span>
              <span><i class="dot" style="background: var(--ink); height: 3px; width: 14px"></i>صافي الربح</span>
            </div>
          </div>
          <EChart :option="chart" height="320px" label="الإيرادات والمصروفات وصافي الربح شهرياً" />
        </div>
        <div class="card f2">
          <div class="card-head">
            <h2>قائمة الدخل المختصرة</h2>
            <a class="lbl" :href="plReport" target="_blank" rel="noopener">التقرير الكامل ←</a>
          </div>
          <div class="line-row" style="font-weight: 700; padding-bottom: 8px; border-bottom: 1px solid var(--line)">
            <span>الإيرادات</span><span class="num">{{ money(k.income.value) }}</span>
          </div>
          <BarList :rows="incomes" color="var(--s1)" />
          <div class="line-row" style="font-weight: 700; padding: 8px 0; border-bottom: 1px solid var(--line)">
            <span>المصروفات</span><span class="num">({{ money(k.expense.value) }})</span>
          </div>
          <BarList :rows="expenses" color="var(--s2)" />
          <div class="line-row" style="padding: 12px; border-radius: 10px; background: var(--soft); font-weight: 700">
            <span>صافي الربح</span><span class="num" :class="k.net.value < 0 ? 'neg' : ''">{{ money(k.net.value) }}</span>
          </div>
        </div>
      </section>

      <section class="card">
        <div class="card-head">
          <h2>الربحية حسب مركز التكلفة</h2>
          <span v-if="untagged" class="lbl warn">{{ pct(untagged, 0) }} من الإيرادات بلا مركز تكلفة محدد</span>
        </div>
        <div class="table-wrap">
          <table class="tbl">
            <thead><tr><th>مركز التكلفة</th><th>الإيرادات</th><th>المصروفات</th><th>صافي الربح</th><th>الهامش</th></tr></thead>
            <tbody>
              <tr v-for="c in data.cost_centers" :key="c.cost_center">
                <td>{{ c.cost_center }}</td>
                <td class="num">{{ money(c.income) }}</td>
                <td class="num">{{ money(c.expense) }}</td>
                <td class="num" :class="c.net < 0 ? 'neg' : 'pos'" style="font-weight: 600">{{ money(c.net) }}</td>
                <td class="num">{{ c.income ? pct((c.net / c.income) * 100) : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </ViewState>
</template>

<script setup>
import { computed } from 'vue'
import { useView } from '../api'
import { store } from '../store'
import KpiCard from '../components/KpiCard.vue'
import EChart from '../components/EChart.vue'
import BarList from '../components/BarList.vue'
import ViewState from '../components/ViewState.vue'
import { monthChart } from '../charts'
import { money, pct, deltaNote, deskUrl } from '../format'

const { data, loading, error, load } = useView('get_profit')
const k = computed(() => data.value?.kpis)

function note(delta, higherIsBetter = true) {
  const d = deltaNote(delta, 'عن الفترة المقابلة', higherIsBetter)
  return { note: d.text, tone: d.tone }
}

const share = (v) => (k.value.income.value ? ` ${pct((v / k.value.income.value) * 100, 0)}` : '')
const incomes = computed(() => data.value.incomes.map((r) => ({ label: r.label, value: r.value })))
const expenses = computed(() => data.value.expenses.map((r) => ({ label: r.label, value: r.value, extra: share(r.value) })))
const untagged = computed(() => {
  const total = data.value.cost_centers.reduce((s, c) => s + c.income, 0)
  const none = data.value.cost_centers.find((c) => c.cost_center === 'بدون مركز تكلفة')
  return none && total ? (none.income / total) * 100 : 0
})
const plReport = computed(() =>
  deskUrl('query-report/Profit and Loss Statement', {
    company: store.company, period_start_date: data.value.filters.from, period_end_date: data.value.filters.to,
    filter_based_on: 'Date Range', periodicity: 'Monthly',
  })
)
const chart = computed(() =>
  monthChart(data.value.months, [
    { name: 'الإيرادات', data: data.value.trend.income, color: 'var(--s1)' },
    { name: 'المصروفات', data: data.value.trend.expense, color: 'var(--s2)' },
    { name: 'صافي الربح', data: data.value.trend.net, type: 'line', color: 'var(--ink)' },
  ])
)
</script>
