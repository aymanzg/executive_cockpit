<template>
  <ViewState :loading="loading" :error="error" :has-data="!!data" @retry="load">
    <template v-if="data">
      <section class="grid-kpi">
        <KpiCard label="صافي الذمم المدينة" :value="k.net_receivable" note="بعد خصم الدفعات والمرتجعات" tone="neu" />
        <KpiCard label="رصيد الفواتير المفتوحة" :value="k.invoice_open"
          :note="k.unallocated > 0 ? `${amtStr(k.unallocated)} دفعات غير مخصّصة لفواتير` : 'كل الدفعات مخصّصة'"
          :tone="k.unallocated > 0 ? 'warn' : 'pos'" />
        <KpiCard label="متوسط أيام التحصيل" :value="k.dso ?? '—'" unit="يوماً"
          :note="`المستهدف ${k.dso_target} يوماً`" :tone="k.dso === null ? 'neu' : k.dso <= k.dso_target ? 'pos' : 'neg'" />
        <KpiCard label="عملاء عليهم أرصدة" :value="int(k.customers_with_balance)" unit="عميلاً"
          :note="k.top10_share !== null ? `أكبر 10 عملاء يمثّلون ${pct(k.top10_share, 0)}` : ''" tone="neu" />
        <KpiCard label="المحصّل في الفترة" :value="k.collected" tone="neu" />
      </section>

      <div v-if="k.unallocated > 0" class="alert medium" role="note">
        <i class="dot"></i>
        <div style="display: flex; flex-direction: column; gap: 2px">
          <span style="font-size: 14px; font-weight: 600">الفواتير تبدو أكثر تأخراً مما هي عليه</span>
          <span class="lbl">يوجد {{ amtStr(k.unallocated) }} ر.س من سندات القبض والمرتجعات غير مربوطة بفواتير، لذلك تظهر فواتير مسدّدة كأنها مفتوحة.
            ربط السندات بالفواتير (مطابقة الدفعات) سيجعل أعمار الذمم دقيقة.</span>
        </div>
      </div>

      <section class="rowwrap">
        <div class="card f2">
          <div class="card-head">
            <h2>أعمار الفواتير المفتوحة</h2>
            <a class="lbl" :href="arReport" target="_blank" rel="noopener">تقرير الذمم المدينة ←</a>
          </div>
          <div class="stack" style="height: 18px">
            <div v-for="a in data.aging" :key="a.key" :style="{ width: a.pct + '%', background: AGING_COLORS[a.key] }"></div>
          </div>
          <div class="table-wrap">
            <table class="tbl">
              <thead><tr><th>الفئة</th><th>عدد الفواتير</th><th>المبلغ</th><th>النسبة</th></tr></thead>
              <tbody>
                <tr v-for="a in data.aging" :key="a.key">
                  <td><span style="display: inline-flex; align-items: center; gap: 8px"><i class="dot" :style="{ background: AGING_COLORS[a.key] }"></i>{{ a.label }}</span></td>
                  <td class="num">{{ int(a.count) }}</td>
                  <td class="num" style="font-weight: 600">{{ money(a.amount) }}</td>
                  <td class="num">{{ pct(a.pct) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="card f1">
          <h2>أكبر المدينين (صافي الرصيد)</h2>
          <div class="table-wrap">
            <table class="tbl">
              <thead><tr><th>العميل</th><th>الرصيد</th><th>أقدم فاتورة</th></tr></thead>
              <tbody>
                <tr v-for="d in data.debtors" :key="d.customer">
                  <td><a :href="deskUrl(`customer/${encodeURIComponent(d.customer)}`)" target="_blank" rel="noopener">{{ d.customer_name }}</a></td>
                  <td class="num" style="font-weight: 600">{{ amtStr(d.balance) }}</td>
                  <td class="num" :class="d.oldest_days > 90 ? 'neg' : 'neu'">{{ d.oldest_days !== null ? `${d.oldest_days} يوماً` : '—' }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="!data.debtors.length" class="empty">لا توجد أرصدة مدينة</div>
          </div>
        </div>
      </section>

      <section class="card">
        <div class="card-head">
          <h2>الفوترة مقابل التحصيل — آخر 12 شهراً</h2>
          <div class="legend">
            <span><i class="dot" style="background: var(--s1)"></i>الفواتير (شامل الضريبة)</span>
            <span><i class="dot" style="background: var(--s2)"></i>التحصيل</span>
            <span><i class="dot" style="background: var(--ink); height: 3px; width: 14px"></i>نسبة التحصيل</span>
          </div>
        </div>
        <EChart :option="trendChart" height="300px" label="الفوترة والتحصيل ونسبة التحصيل شهرياً" />
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
import ViewState from '../components/ViewState.vue'
import { monthChart } from '../charts'
import { amtStr, int, money, pct, deskUrl } from '../format'

const { data, loading, error, load } = useView('get_collection')
const k = computed(() => data.value?.kpis)
const AGING_COLORS = { not_due: 'var(--pos)', '0_30': 'var(--s1)', '31_60': 'var(--s3)', '61_90': 'var(--warn)', '90_plus': 'var(--neg)' }
const arReport = computed(() => deskUrl('query-report/Accounts Receivable', { company: store.company, report_date: data.value.filters.to }))

const trendChart = computed(() =>
  monthChart(data.value.months, [
    { name: 'الفواتير', data: data.value.trend.invoiced, color: 'var(--s1)' },
    { name: 'التحصيل', data: data.value.trend.collected, color: 'var(--s2)' },
    { name: 'نسبة التحصيل', data: data.value.trend.rate, type: 'line', axis: 1, color: 'var(--ink)' },
  ])
)
</script>
