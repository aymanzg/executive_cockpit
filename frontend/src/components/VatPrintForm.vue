<template>
  <article class="vp" dir="rtl">
    <header class="vp-head">
      <div class="vp-title">
        <span class="vp-kicker">VAT RETURN · إقرار ضريبي</span>
        <h1>إقرار ضريبة القيمة المضافة</h1>
        <div class="vp-company">{{ d.filters.company_name || d.filters.company }}</div>
      </div>
      <div class="vp-meta">
        <div><span>الرقم الضريبي</span><b class="num">{{ d.filters.company_vat || '—' }}</b></div>
        <div><span>الفترة الضريبية</span><b>{{ d.filters.label }}</b></div>
        <div><span>من — إلى</span><b class="num">{{ d.filters.from }} — {{ d.filters.to }}</b></div>
      </div>
    </header>

    <section class="vp-sum">
      <div class="out"><span>ضريبة المخرجات (المبيعات)</span><b class="num">{{ money2(d.totals.output) }}</b></div>
      <div class="in"><span>ضريبة المدخلات (المشتريات)</span><b class="num">{{ money2(d.totals.input) }}</b></div>
      <div class="net" :class="{ refund: box16.vat < 0 }"><span>{{ box16.vat >= 0 ? 'صافي الضريبة المستحقة' : 'صافي الضريبة المستردة' }}</span><b class="num">{{ money2(Math.abs(box16.vat)) }}</b></div>
    </section>

    <h2>بنود الإقرار</h2>
    <table class="vp-tbl">
      <thead>
        <tr><th class="no">البند</th><th>الوصف</th><th class="c">المبلغ (ر.س)</th><th class="c">التعديلات (ر.س)</th><th class="c">الضريبة (ر.س)</th></tr>
      </thead>
      <tbody>
        <template v-for="b in d.boxes" :key="b.no">
          <tr v-if="SECTION[b.no]" class="sec"><td colspan="5">{{ SECTION[b.no] }}</td></tr>
          <tr :class="{ tot: TOTALS.includes(b.no) }">
            <td class="no num">{{ b.no }}</td>
            <td>{{ b.label }}</td>
            <td class="c num">{{ Number(b.no) <= 12 ? money2(b.amount) : '' }}</td>
            <td class="c num">{{ Number(b.no) <= 12 ? money2(b.adjustment) : '' }}</td>
            <td class="c num b">{{ money2(b.vat) }}</td>
          </tr>
        </template>
      </tbody>
    </table>
    <p class="vp-note">
      المبالغ قبل الضريبة، والمرتجعات وإشعارات الدائن في عمود التعديلات. البنود 2 و5 و8 و9 و11 و14 و15 لا تُستخرج من النظام وتُعبّأ يدوياً في بوابة الزكاة عند وجودها.
    </p>

    <div class="vp-keep">
      <h2>المطابقة مع ميزان المراجعة</h2>
      <table class="vp-tbl">
        <thead>
          <tr><th>الحساب</th><th class="c">رصيد أول المدة</th><th class="c">مدين</th><th class="c">دائن</th><th class="c">رصيد آخر المدة</th></tr>
        </thead>
        <tbody>
          <tr v-for="t in d.trial_balance" :key="t.key">
            <td>{{ ACC_LABEL[t.key] }}<div class="sub">{{ t.account }}</div></td>
            <td class="c num">{{ dc(t.opening) }}</td>
            <td class="c num">{{ money2(t.debit) }}</td>
            <td class="c num">{{ money2(t.credit) }}</td>
            <td class="c num">{{ dc(t.closing) }}</td>
          </tr>
        </tbody>
      </table>
      <table class="vp-tbl vp-recon">
        <thead>
          <tr><th>الضريبة</th><th class="c">حركة الحساب قبل قيد التسوية</th><th class="c">الإقرار</th><th class="c">الفرق</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in recon" :key="r.key">
            <td>{{ r.title }}</td>
            <td class="c num">{{ money2(r.movement) }}</td>
            <td class="c num">{{ money2(r.report) }}</td>
            <td class="c"><span class="pill" :class="r.diff ? 'bad' : 'ok'">{{ r.diff ? `فرق ${money2(r.diff)}` : 'مطابق ✓' }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="d.monthly.length" class="vp-keep">
      <h2>قيد التسوية الشهري</h2>
      <table class="vp-tbl">
        <thead>
          <tr><th>الشهر</th><th>القيد</th><th class="c">المخرجات في القيد</th><th class="c">المدخلات في القيد</th><th class="c">الحالة</th></tr>
        </thead>
        <tbody>
          <tr v-for="m in d.monthly" :key="m.month">
            <td>{{ monthName(m.month) }} {{ m.month.slice(0, 4) }}</td>
            <td class="num">{{ m.vouchers.join('، ') || 'لم يُسجّل بعد' }}</td>
            <td class="c num">{{ m.vouchers.length ? money2(m.settle_output) : '' }}</td>
            <td class="c num">{{ m.vouchers.length ? money2(m.settle_input) : '' }}</td>
            <td class="c"><span class="pill" :class="settleTone(m)">{{ settleStatus(m) }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="issues.length" class="vp-keep">
      <h2>ملاحظات المراجعة</h2>
      <div class="vp-issues">
        <div v-for="c in issues" :key="c.key" class="issue" :class="c.level">
          <b>{{ c.title }}</b>
          <span><span class="num">{{ int(c.count) }}</span> مستند · ضريبة <span class="num">{{ money2(c.vat) }}</span></span>
        </div>
      </div>
    </div>

    <section class="vp-sign">
      <div v-for="s in SIGNS" :key="s">
        <b>{{ s }}</b>
        <span>الاسم: </span>
        <span>التوقيع: </span>
        <span>التاريخ: </span>
      </div>
    </section>

    <footer class="vp-foot">
      <span>طُبع من نظام ERPNext بواسطة {{ printedBy }}</span>
      <span class="num">{{ printedAt }}</span>
    </footer>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { int, money2, monthName } from '../format'

const props = defineProps({ d: { type: Object, required: true }, printedBy: { type: String, default: '' } })

const SECTION = { 1: 'ضريبة القيمة المضافة على المبيعات', 7: 'ضريبة القيمة المضافة على المشتريات', 13: 'صافي الضريبة' }
const TOTALS = ['6', '12', '13', '16']
const ACC_LABEL = { output: 'ضريبة المخرجات', input: 'ضريبة المدخلات', settlement: 'حساب تسوية الضريبة' }
const SIGNS = ['أعدّه (المحاسب)', 'راجعه (المدير المالي)', 'اعتمده (المدير العام)']
const r2 = (v) => Math.round(v * 100) / 100

const box16 = computed(() => props.d.boxes.find((b) => b.no === '16'))
const recon = computed(() => {
  const tb = Object.fromEntries(props.d.trial_balance.map((t) => [t.key, t]))
  return [
    { key: 'output', title: 'ضريبة المخرجات', report: props.d.totals.output },
    { key: 'input', title: 'ضريبة المدخلات', report: props.d.totals.input },
  ].map((r) => {
    const movement = tb[r.key]?.movement ?? 0
    return { ...r, movement, diff: r2(movement - r.report) }
  })
})
const issues = computed(() => (props.d.checks || []).filter((c) => c.level !== 'ok' && c.count))
const dc = (v) => (Math.abs(v) < 0.005 ? '0.00' : `${money2(Math.abs(v))} ${v > 0 ? 'مدين' : 'دائن'}`)
function settleTone(m) {
  if (!m.vouchers.length) return 'info'
  return !r2(m.settle_output - m.output) && !r2(m.settle_input - m.input) ? 'ok' : 'bad'
}
function settleStatus(m) {
  if (!m.vouchers.length) return `المتوقع ${money2(m.output - m.input)}`
  const a = r2(m.settle_output - m.output)
  const b = r2(m.settle_input - m.input)
  return !a && !b ? 'مطابق ✓' : `فرق ${money2(a || b)}`
}
const printedAt = new Date().toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' })
</script>

<style scoped>
.vp {
  --brand: #0F5F73; --brand2: #1B8AA0; --tint: #E8F3F6; --tint2: #F4F9FA; --line: #D5E3E8; --ink: #14232B; --muted: #5B6B73;
  --orange: #C2560C; --green: #0F7B4B; --red: #B42318; --amber: #B7791F;
  color: var(--ink); background: #fff; font-size: 10.5pt; line-height: 1.45;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
.vp .num { font-variant-numeric: tabular-nums; direction: ltr; unicode-bidi: isolate; }
.vp h1 { font-size: 19pt; margin: 2px 0 2px; color: #fff; }
.vp h2 { display: flex; align-items: center; gap: 8px; font-size: 12pt; margin: 16px 0 8px; color: var(--brand); }
.vp h2::before { content: ''; width: 5px; height: 16px; border-radius: 3px; background: linear-gradient(var(--brand2), var(--brand)); }

.vp-head {
  display: flex; justify-content: space-between; align-items: center; gap: 16px;
  padding: 16px 20px; border-radius: 14px; color: #fff;
  background: linear-gradient(135deg, var(--brand) 0%, var(--brand2) 100%);
}
.vp-kicker { font-size: 8pt; letter-spacing: .08em; opacity: .8; }
.vp-company { font-size: 12pt; font-weight: 600; opacity: .95; }
.vp-meta { display: flex; flex-direction: column; gap: 5px; }
.vp-meta div { display: flex; justify-content: space-between; gap: 14px; background: rgba(255, 255, 255, .14); border-radius: 8px; padding: 4px 10px; }
.vp-meta span { font-size: 8.5pt; opacity: .85; }
.vp-meta b { font-size: 9.5pt; }

.vp-sum { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 14px 0 2px; }
.vp-sum div { position: relative; overflow: hidden; border-radius: 12px; padding: 10px 14px 10px; display: flex; flex-direction: column; gap: 4px; background: var(--tint2); border: 1px solid var(--line); }
.vp-sum div::before { content: ''; position: absolute; inset-inline-start: 0; top: 0; bottom: 0; width: 5px; }
.vp-sum .out::before { background: var(--brand); }
.vp-sum .in::before { background: #7C8CA0; }
.vp-sum span { font-size: 9pt; color: var(--muted); }
.vp-sum b { font-size: 15pt; text-align: start; }
.vp-sum .net { background: linear-gradient(135deg, #D9681A, var(--orange)); border-color: transparent; color: #fff; }
.vp-sum .net.refund { background: linear-gradient(135deg, #18965D, var(--green)); }
.vp-sum .net span { color: rgba(255, 255, 255, .88); }

.vp-tbl { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 9.5pt; border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
.vp-tbl th, .vp-tbl td { padding: 5px 8px; vertical-align: top; border-bottom: 1px solid var(--line); }
.vp-tbl tbody tr:last-child td { border-bottom: 0; }
.vp-tbl thead th { background: var(--brand); color: #fff; font-weight: 600; font-size: 9pt; text-align: start; }
.vp-tbl tbody tr:nth-child(even) td { background: var(--tint2); }
.vp-tbl .no { width: 40px; text-align: center; }
.vp-tbl td.no { color: var(--brand); font-weight: 700; }
.vp-tbl .c { text-align: left; white-space: nowrap; }
.vp-tbl thead th.c { text-align: left; }
.vp-tbl .b { font-weight: 700; }
.vp-tbl .sec td { background: var(--tint) !important; color: var(--brand); font-weight: 700; font-size: 9pt; }
.vp-tbl .tot td { font-weight: 700; background: #DCEDF2 !important; color: var(--ink); }
.vp-tbl .sub { font-size: 8pt; color: var(--muted); }
.vp-tbl tr { break-inside: avoid; }
.vp-recon { margin-top: 8px; }
.pill { display: inline-block; padding: 1px 10px; border-radius: 99px; font-size: 8.5pt; font-weight: 700; }
.pill.ok { background: #DFF3E8; color: var(--green); }
.pill.bad { background: #FCE4E2; color: var(--red); }
.pill.info { background: var(--tint); color: var(--brand); }
.vp-note { font-size: 8pt; color: var(--muted); margin: 5px 2px 0; }
.vp-keep { break-inside: avoid; }

.vp-issues { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.issue { display: flex; flex-direction: column; gap: 2px; padding: 8px 12px; border-radius: 10px; font-size: 9pt; background: #FDF4E3; border-inline-start: 4px solid var(--amber); }
.issue.high { background: #FCE9E7; border-color: var(--red); }
.issue.info { background: var(--tint2); border-color: var(--brand); }
.issue span { color: var(--muted); }

.vp-sign { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 26px; break-inside: avoid; }
.vp-sign div { display: flex; flex-direction: column; gap: 14px; font-size: 9.5pt; padding: 12px 14px 16px; border: 1px solid var(--line); border-radius: 12px; background: var(--tint2); }
.vp-sign b { color: var(--brand); }
.vp-sign span { border-bottom: 1px dashed #9FB4BC; padding-bottom: 2px; color: var(--muted); }
.vp-foot { display: flex; justify-content: space-between; margin-top: 16px; padding-top: 6px; border-top: 2px solid var(--brand); font-size: 8pt; color: var(--muted); }
</style>
