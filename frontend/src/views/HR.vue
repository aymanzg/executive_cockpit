<template>
  <ViewState :loading="loading" :error="error" :has-data="!!data" @retry="load">
    <template v-if="data">
      <section class="grid-kpi">
        <KpiCard label="الموظفون النشطون" :value="int(data.employees.active)" unit="موظفاً" :note="statusNote" tone="neu" />
        <KpiCard v-if="pay" :to="tabLink('payroll')" label="صافي الرواتب" :value="pay.net" :trend="data.payroll.trend_net"
          :note="`${monthName(pay.month)} · ${int(pay.count)} قسيمة`" :tone="pay.months_behind >= 2 ? 'warn' : 'neu'"
          :sub="payDelta" />
        <KpiCard :to="tabLink('advances')" label="سلف لم تُسوَّ" :value="data.advances.outstanding"
          :note="data.advances.unpaid ? `+ ${amtStr(data.advances.unpaid)} معتمدة لم تُصرف` : ''" tone="warn" />
        <KpiCard :to="tabLink('custody')" label="عُهد لدى الموظفين" :value="data.custody.total" :note="`${int(data.custody.count)} موظف`" tone="neu"
          :sub="data.custody.owed ? `أرصدة دائنة للموظفين: ${amtStr(data.custody.owed)} (${int(data.custody.owed_count)})` : ''" />
        <KpiCard :to="tabLink('custody')" label="مطالبات مصروفات غير مدفوعة" :value="data.expense_claims.unpaid_amount"
          :note="`${int(data.expense_claims.unpaid_count)} مطالبة`" :tone="data.expense_claims.unpaid_count ? 'neg' : 'pos'" />
      </section>

      <div v-if="pay && pay.months_behind >= 2" class="alert high" role="note">
        <i class="dot"></i>
        <div style="display: flex; flex-direction: column; gap: 2px">
          <span style="font-size: 14px; font-weight: 600">مسير الرواتب غير محدّث في النظام</span>
          <span class="lbl">آخر مسير مكتمل هو {{ monthName(pay.month) }} {{ pay.month.slice(0, 4) }}، أي قبل {{ pay.months_behind }} أشهر من نهاية الفترة.</span>
        </div>
      </div>

      <div class="seg hr-tabs" role="tablist" aria-label="أقسام الموارد البشرية">
        <button v-for="t in tabs" :key="t.key" role="tab" :id="`hr-tab-${t.key}`" :aria-selected="tab === t.key"
          :aria-controls="`hr-panel-${t.key}`" :class="{ on: tab === t.key }" @click="setTab(t.key)">
          {{ t.label }}<span v-if="t.badge" class="tab-badge num">{{ t.badge }}</span>
        </button>
      </div>

      <section v-if="tab === 'payroll'" id="hr-panel-payroll" role="tabpanel" aria-labelledby="hr-tab-payroll" class="rowwrap">
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

      <section v-else-if="tab === 'leaves'" id="hr-panel-leaves" role="tabpanel" aria-labelledby="hr-tab-leaves" class="rowwrap">
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

      <section v-else-if="tab === 'advances'" id="hr-panel-advances" role="tabpanel" aria-labelledby="hr-tab-advances" class="rowwrap">
        <div class="card f1">
          <h2>سلف الموظفين حسب الحالة</h2>
          <div class="tiles">
            <div v-for="a in advances" :key="a.status" class="tile" :style="{ background: a.bg }">
              <span style="font-weight: 600">{{ a.label }}</span>
              <span class="num">{{ amtStr(a.outstanding) }}</span>
              <span class="lbl">{{ int(a.n) }} سلفة · أصلها {{ amtStr(a.amount) }}</span>
            </div>
          </div>
          <div v-if="!advances.length" class="empty">لا توجد سلف في الفترة</div>
        </div>
      </section>
      <section v-if="tab === 'advances' && data.advances.top.length" class="card">
        <h2>أعلى الأرصدة لدى الموظفين</h2>
        <BarList :rows="advTop" color="var(--s2)" />
      </section>

      <section v-if="tab === 'custody'" id="hr-panel-custody" role="tabpanel" aria-labelledby="hr-tab-custody" class="rowwrap">
        <div class="card f1">
          <div class="card-head">
            <h2>العُهد</h2>
            <span class="lbl">لدى الموظفين <b class="num">{{ amtStr(data.custody.total) }}</b> · دائنة للموظفين <b class="num neg">{{ amtStr(data.custody.owed) }}</b> · مطالبات مدفوعة في الفترة: <b class="num">{{ int(data.expense_claims.paid_count) }} · {{ amtStr(data.expense_claims.paid_amount) }}</b></span>
          </div>
          <div class="table-wrap">
            <table class="tbl">
              <thead><tr><th>{{ data.custody.accounts.some((c) => c.party) ? "الموظف" : "العهدة" }}</th><th>الرصيد</th><th>آخر حركة</th></tr></thead>
              <tbody>
                <tr v-for="c in data.custody.accounts" :key="c.account + c.party">
                  <td><a :href="glUrl(c)" target="_blank" rel="noopener">{{ c.label }}</a></td>
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
import { useRoute, useRouter } from 'vue-router'
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

// Sections live in top tabs instead of one long page; the open tab is kept in the
// URL (?tab=) so a refresh, the back button or a shared link land on the same tab.
const route = useRoute()
const router = useRouter()
const TAB_KEYS = ['payroll', 'leaves', 'advances', 'custody']
const tab = computed(() => (TAB_KEYS.includes(route.query.tab) ? route.query.tab : 'payroll'))
const setTab = (key) => router.replace(tabLink(key))
const tabLink = (key) => ({ query: { ...route.query, tab: key === 'payroll' ? undefined : key } })
const tabs = computed(() => [
  { key: 'payroll', label: 'الرواتب' },
  { key: 'leaves', label: 'الإجازات', badge: data.value.leaves.on_leave.length ? int(data.value.leaves.on_leave.length) : '' },
  { key: 'advances', label: 'السلف', badge: data.value.advances.top.length ? int(data.value.advances.top.length) : '' },
  { key: 'custody', label: 'العُهد', badge: data.value.custody.accounts.length ? int(data.value.custody.accounts.length) : '' },
])

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
const glUrl = (c) =>
  deskUrl('query-report/General Ledger', {
    company: store.company, account: JSON.stringify([c.account]), from_date: data.value.filters.from, to_date: data.value.filters.to,
    ...(c.party ? { party_type: c.party_type, party: JSON.stringify([c.party]) } : {}),
  })
</script>
