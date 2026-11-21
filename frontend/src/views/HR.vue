<template>
  <ViewState :loading="loading" :error="error" :has-data="!!data" @retry="load">
    <template v-if="data">
      <section class="grid-kpi">
        <KpiCard label="الموظفون النشطون" :value="int(data.employees.active)" unit="موظفاً" :note="statusNote" tone="neu" />
        <KpiCard v-if="pay" label="صافي الرواتب" :value="pay.net" :trend="data.payroll.trend_net"
          :note="`${monthName(pay.month)} · ${int(pay.count)} قسيمة`" :tone="pay.months_behind >= 2 ? 'warn' : 'neu'"
          :sub="payDelta" />
        <KpiCard label="سلف لم تُسوَّ" :value="data.advances.outstanding"
          :note="data.advances.unpaid ? `+ ${amtStr(data.advances.unpaid)} معتمدة لم تُصرف` : ''" tone="warn" />
        <KpiCard label="أرصدة العُهد" :value="data.custody.total" :note="`${int(data.custody.count)} عهدة مفتوحة`" tone="neu" />
        <KpiCard label="مطالبات مصروفات غير مدفوعة" :value="data.expense_claims.unpaid_amount"
          :note="`${int(data.expense_claims.unpaid_count)} مطالبة`" :tone="data.expense_claims.unpaid_count ? 'neg' : 'pos'" />
      </section>

      <div v-if="pay && pay.months_behind >= 2" class="alert high" role="note">
        <i class="dot"></i>
        <div style="display: flex; flex-direction: column; gap: 2px">
          <span style="font-size: 14px; font-weight: 600">مسير الرواتب غير محدّث في النظام</span>
          <span class="lbl">آخر مسير مكتمل هو {{ monthName(pay.month) }} {{ pay.month.slice(0, 4) }}، أي قبل {{ pay.months_behind }} أشهر من نهاية الفترة.</span>
        </div>
      </div>

      <section class="rowwrap">
        <div class="card f2">
          <div class="card-head">
            <h2>الرواتب — آخر 12 شهراً</h2>
            <div class="legend">
              <span><i class="dot" style="background: var(--s1)"></i>صافي الرواتب</span>
              <span><i class="dot" style="background: var(--s2); height: 3px; width: 14px"></i>عدد القسائم</span>
            </div>
          </div>
          <EChart :option="payChart" height="260px" label="صافي الرواتب وعدد القسائم شهرياً" />
        </div>
        <div class="card f1">
          <h2>الرواتب حسب الإدارة<span v-if="pay" class="lbl"> · {{ monthName(pay.month) }}</span></h2>
          <BarList :rows="depts" />
        </div>
      </section>

      <section class="rowwrap">
        <div class="card f1">
          <h2>الإجازات المعتمدة في الفترة</h2>
          <div style="display: flex; align-items: center; gap: 16px; flex-wrap: wrap">
            <div style="position: relative; width: 150px; height: 150px; flex: none">
              <EChart :option="leaveChart" height="150px" label="الإجازات حسب النوع" />
              <div style="position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; pointer-events: none">
                <span class="num" style="font-size: 24px; font-weight: 700">{{ int(data.leaves.total) }}</span>
                <span class="lbl">إجازة</span>
              </div>
            </div>
            <div style="display: flex; flex-direction: column; gap: 8px; flex: 1; min-width: 160px">
              <div v-for="(l, i) in data.leaves.by_type" :key="l.leave_type" class="line-row">
                <span style="display: flex; align-items: center; gap: 8px"><i class="dot" :style="{ background: PALETTE[i % PALETTE.length] }"></i>{{ l.leave_type }}</span>
                <span><b class="num">{{ int(l.n) }}</b> <span class="lbl num">· {{ int(l.days) }} يوم</span></span>
              </div>
            </div>
          </div>
        </div>
        <div class="card f1">
          <div class="card-head">
            <h2>في إجازة اليوم</h2>
            <span class="num" style="font-size: 22px; font-weight: 700">{{ int(data.leaves.on_leave.length) }}</span>
          </div>
          <div class="table-wrap" v-if="data.leaves.on_leave.length">
            <table class="tbl">
              <thead><tr><th>الموظف</th><th>النوع</th><th>حتى</th></tr></thead>
              <tbody>
                <tr v-for="l in data.leaves.on_leave" :key="l.employee + l.from_date">
                  <td>{{ l.employee_name }}</td><td>{{ l.leave_type }}</td><td class="num">{{ dateAr(l.to_date) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="empty">لا يوجد موظفون في إجازة اليوم</div>
          <span class="lbl">إجازات تبدأ خلال 14 يوماً: <b class="num">{{ int(data.leaves.upcoming.length) }}</b></span>
        </div>
      </section>

      <section class="rowwrap">
        <div class="card f1">
          <h2>سلف الموظفين</h2>
          <div v-for="a in advances" :key="a.status" class="line-row tile" :style="{ background: a.bg, flexDirection: 'row' }">
            <span style="display: flex; flex-direction: column; gap: 2px">
              <span style="font-weight: 600">{{ a.label }}</span><span class="lbl">{{ int(a.n) }} سلفة · أصلها {{ amtStr(a.amount) }}</span>
            </span>
            <span class="num" style="font-weight: 700; font-size: 16px">{{ amtStr(a.outstanding) }}</span>
          </div>
          <template v-if="data.advances.top.length">
            <span class="lbl" style="margin-top: 4px">أعلى الأرصدة لدى الموظفين</span>
            <BarList :rows="advTop" color="var(--s2)" />
          </template>
        </div>
        <div class="card f1">
          <div class="card-head">
            <h2>العُهد</h2>
            <span class="lbl">مطالبات مدفوعة في الفترة: <b class="num">{{ int(data.expense_claims.paid_count) }} · {{ amtStr(data.expense_claims.paid_amount) }}</b></span>
          </div>
          <div class="table-wrap">
            <table class="tbl">
              <thead><tr><th>العهدة</th><th>الرصيد</th><th>آخر حركة</th></tr></thead>
              <tbody>
                <tr v-for="c in data.custody.accounts" :key="c.account">
                  <td><a :href="glUrl(c.account)" target="_blank" rel="noopener">{{ c.label }}</a></td>
                  <td class="num" style="font-weight: 600" :class="c.balance < 0 ? 'neg' : ''">{{ money(c.balance) }}</td>
                  <td class="num" :class="c.idle_days > 60 ? 'warn' : 'neu'">{{ c.idle_days !== null ? `قبل ${c.idle_days} يوماً` : '—' }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="!data.custody.accounts.length" class="empty">لا توجد عُهد مفتوحة. حدّد حساب العُهد في إعدادات لوحة القيادة.</div>
          </div>
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
import { monthChart, donut, PALETTE } from '../charts'
import { amtStr, int, money, monthName, dateAr, deltaNote, ADVANCE_STATUS, EMPLOYEE_STATUS, deskUrl } from '../format'

const { data, loading, error, load } = useView('get_hr')
const pay = computed(() => data.value?.payroll.latest)

const statusNote = computed(() => {
  const s = data.value.employees.by_status
  return Object.keys(s).filter((k) => k !== 'Active').map((k) => `${int(s[k])} ${EMPLOYEE_STATUS[k] || k}`).join(' · ')
})
const payDelta = computed(() => {
  if (!pay.value?.prev_net) return ''
  return deltaNote(((pay.value.net - pay.value.prev_net) / pay.value.prev_net) * 100, 'عن الشهر السابق').text
})
const payChart = computed(() =>
  monthChart(
    data.value.months,
    [
      { name: 'صافي الرواتب', data: data.value.payroll.trend_net, color: 'var(--s1)' },
      { name: 'عدد القسائم', data: data.value.payroll.trend_count, type: 'line', axis: 1, color: 'var(--s2)', fmt: (v) => int(v) },
    ],
    { fmt2: (v) => int(v) }
  )
)
const depts = computed(() =>
  data.value.payroll.departments.map((d) => ({ label: d.department.replace(/\s*-\s*\w+$/, ''), value: d.v, extra: `${int(d.n)} موظف` }))
)
const leaveChart = computed(() =>
  donut(data.value.leaves.by_type.map((l, i) => ({ name: l.leave_type, value: l.n, color: PALETTE[i % PALETTE.length] })))
)
const ADV_BG = { Paid: 'var(--negsoft)', Unpaid: 'var(--warnsoft)' }
const advances = computed(() =>
  data.value.advances.by_status
    .map((a) => ({ ...a, label: ADVANCE_STATUS[a.status] || a.status, bg: ADV_BG[a.status] || 'var(--hover)' }))
    .sort((a, b) => b.outstanding - a.outstanding)
)
const advTop = computed(() => data.value.advances.top.map((a) => ({ label: a.employee_name, value: a.v, extra: `${int(a.n)} سلفة` })))
const glUrl = (account) =>
  deskUrl('query-report/General Ledger', { company: store.company, account: JSON.stringify([account]), from_date: data.value.filters.from, to_date: data.value.filters.to })
</script>
