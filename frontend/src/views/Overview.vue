<template>
  <ViewState :loading="loading" :error="error" :has-data="!!data" @retry="load">
    <template v-if="data">
      <section class="grid-kpi" aria-label="المؤشرات الرئيسية">
        <KpiCard label="المبيعات (صافي)" :value="k.sales.value" :trend="k.sales.trend" :to="link('sales')"
          v-bind="note(k.sales.delta)" />
        <KpiCard label="صافي الربح" :value="k.net_profit.value" :trend="k.net_profit.trend" :to="link('profit')"
          :note="k.net_profit.margin !== null ? `هامش ${pct(k.net_profit.margin)}` : ''"
          :tone="k.net_profit.value >= 0 ? 'pos' : 'neg'" :sub="note(k.net_profit.delta).note" />
        <KpiCard label="التحصيل" :value="k.collected.value" :trend="k.collected.trend" :to="link('collection')"
          :note="k.collected.rate !== null ? `${pct(k.collected.rate, 0)} من قيمة الفواتير` : ''"
          :tone="k.collected.rate >= 80 ? 'pos' : k.collected.rate >= 50 ? 'warn' : 'neg'" :sub="note(k.collected.delta).note" />
        <KpiCard label="صافي الذمم المدينة" :value="k.receivable.value" :to="link('collection')"
          :note="`رصيد الفواتير المفتوحة ${amtStr(k.receivable.invoice_open)}`"
          :tone="k.receivable.unallocated > 0 ? 'warn' : 'neu'"
          :sub="k.receivable.unallocated > 0 ? `منها ${amtStr(k.receivable.unallocated)} دفعات غير مخصّصة` : ''" />
        <KpiCard label="أوامر بيع لم تُفوتر" :value="k.unbilled_orders.value" :to="link('sales')"
          :note="`${int(k.unbilled_orders.count)} أمر بيع مفتوح`" tone="neu" />
        <KpiCard v-if="k.payroll" label="صافي الرواتب الشهرية" :value="k.payroll.value" :trend="k.payroll.trend" :to="link('hr')"
          :note="`${int(k.payroll.count)} قسيمة · ${monthName(k.payroll.month)}`" tone="neu" />
      </section>

      <section class="rowwrap">
        <div class="card f2">
          <div class="card-head">
            <h2>المبيعات مقابل التحصيل — آخر 12 شهراً</h2>
            <div class="legend">
              <span><i class="dot" style="background: var(--s1)"></i>المبيعات (صافي)</span>
              <span><i class="dot" style="background: var(--s2)"></i>التحصيل</span>
            </div>
          </div>
          <EChart :option="chart" height="300px" label="المبيعات مقابل التحصيل شهرياً" />
        </div>
        <div class="card f1">
          <h2>تنبيهات تحتاج انتباهك</h2>
          <component :is="can(a.route.split('/').pop()) ? 'router-link' : 'div'" v-for="(a, i) in data.alerts" :key="i" :to="a.route.replace('/executive', '')" class="alert" :class="a.level">
            <i class="dot"></i>
            <div style="display: flex; flex-direction: column; gap: 2px">
              <span style="font-size: 14px; font-weight: 600">{{ a.title }}</span>
              <span class="lbl">{{ a.desc }}</span>
            </div>
          </component>
          <div v-if="!data.alerts.length" class="empty">لا توجد تنبيهات في هذه الفترة</div>
        </div>
      </section>

      <section class="card">
        <div class="card-head">
          <h2>الإيرادات والمصروفات — آخر 12 شهراً</h2>
          <div class="legend">
            <span><i class="dot" style="background: var(--s1)"></i>الإيرادات</span>
            <span><i class="dot" style="background: var(--s2)"></i>المصروفات</span>
          </div>
        </div>
        <EChart :option="plChart" height="240px" label="الإيرادات والمصروفات شهرياً" />
      </section>
    </template>
  </ViewState>
</template>

<script setup>
import { computed } from 'vue'
import { useView } from '../api'
import { can } from '../store'
import KpiCard from '../components/KpiCard.vue'
import EChart from '../components/EChart.vue'
import ViewState from '../components/ViewState.vue'
import { monthChart } from '../charts'
import { amtStr, int, pct, monthName, deltaNote } from '../format'

const { data, loading, error, load } = useView('get_overview')
const k = computed(() => data.value?.kpis)
// cards link to their section only when the user may open it
const link = (section) => (can(section) ? `/${section}` : undefined)

function note(delta, higherIsBetter = true) {
  const d = deltaNote(delta, 'عن الفترة المقابلة', higherIsBetter)
  return { note: d.text, tone: d.tone }
}

const chart = computed(() =>
  monthChart(data.value.months, [
    { name: 'المبيعات (صافي)', data: data.value.chart.sales, color: 'var(--s1)' },
    { name: 'التحصيل', data: data.value.chart.collected, color: 'var(--s2)' },
  ])
)
const plChart = computed(() =>
  monthChart(data.value.months, [
    { name: 'الإيرادات', data: data.value.chart.income, color: 'var(--s1)' },
    { name: 'المصروفات', data: data.value.chart.expense, color: 'var(--s2)' },
  ])
)
</script>
