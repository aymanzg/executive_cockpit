<template>
  <article class="vp" dir="rtl">
    <header class="vp-head">
      <div>
        <h1>إقرار ضريبة القيمة المضافة</h1>
        <div class="vp-company">{{ d.filters.company_name || d.filters.company }}</div>
      </div>
      <table class="vp-meta">
        <tr><th>الرقم الضريبي</th><td class="num">{{ d.filters.company_vat || '—' }}</td></tr>
        <tr><th>الفترة الضريبية</th><td>{{ d.filters.label }}</td></tr>
        <tr><th>من — إلى</th><td class="num">{{ d.filters.from }} — {{ d.filters.to }}</td></tr>
      </table>
    </header>

    <section class="vp-sum">
      <div><span>ضريبة المخرجات (المبيعات)</span><b class="num">{{ money2(d.totals.output) }}</b></div>
      <div><span>ضريبة المدخلات (المشتريات)</span><b class="num">{{ money2(d.totals.input) }}</b></div>
      <div class="net"><span>{{ box16.vat >= 0 ? 'صافي الضريبة المستحقة' : 'صافي الضريبة المستردة' }}</span><b class="num">{{ money2(Math.abs(box16.vat)) }}</b></div>
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
            <td class="c num b">{{ r.diff ? money2(r.diff) : 'مطابق' }}</td>
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
            <td class="c">{{ settleStatus(m) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="issues.length" class="vp-keep">
      <h2>ملاحظات المراجعة</h2>
      <ul class="vp-issues">
        <li v-for="c in issues" :key="c.key"><b>{{ c.title }}</b> — <span class="num">{{ int(c.count) }}</span> مستند، ضريبة <span class="num">{{ money2(c.vat) }}</span></li>
      </ul>
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
function settleStatus(m) {
  if (!m.vouchers.length) return `المتوقع ${money2(m.output - m.input)}`
  const a = r2(m.settle_output - m.output)
  const b = r2(m.settle_input - m.input)
  return !a && !b ? 'مطابق' : `فرق ${money2(a || b)}`
}
const printedAt = new Date().toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' })
</script>

<style scoped>
.vp { color: #000; background: #fff; font-size: 11pt; line-height: 1.45; }
.vp .num { font-variant-numeric: tabular-nums; direction: ltr; unicode-bidi: isolate; }
.vp h1 { font-size: 18pt; margin: 0 0 4px; }
.vp h2 { font-size: 12pt; margin: 14px 0 6px; padding-bottom: 3px; border-bottom: 1.5px solid #000; }
.vp-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; padding-bottom: 10px; border-bottom: 3px double #000; }
.vp-company { font-size: 13pt; font-weight: 700; }
.vp-meta { border-collapse: collapse; font-size: 10pt; }
.vp-meta th { text-align: start; font-weight: 400; color: #444; padding: 2px 0 2px 12px; white-space: nowrap; }
.vp-meta td { font-weight: 700; padding: 2px 0; }
.vp-sum { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 12px 0 4px; }
.vp-sum div { border: 1px solid #000; padding: 6px 10px; display: flex; flex-direction: column; gap: 2px; }
.vp-sum span { font-size: 9.5pt; color: #333; }
.vp-sum b { font-size: 14pt; text-align: start; }
.vp-sum .net { background: #eee; }
.vp-tbl { width: 100%; border-collapse: collapse; font-size: 10pt; }
.vp-tbl th, .vp-tbl td { border: 1px solid #777; padding: 4px 6px; vertical-align: top; }
.vp-tbl thead th { background: #e6e6e6; font-weight: 700; }
.vp-tbl .no { width: 40px; text-align: center; }
.vp-tbl .c { text-align: left; white-space: nowrap; }
.vp-tbl .b { font-weight: 700; }
.vp-tbl .sec td { background: #f3f3f3; font-weight: 700; }
.vp-tbl .tot td { font-weight: 700; background: #f7f7f7; border-top: 1.5px solid #000; }
.vp-tbl .sub { font-size: 8.5pt; color: #555; }
.vp-tbl tr { break-inside: avoid; }
.vp-recon { margin-top: 6px; }
.vp-note { font-size: 8.5pt; color: #444; margin: 4px 0 0; }
.vp-keep { break-inside: avoid; }
.vp-issues { margin: 0; padding-inline-start: 18px; font-size: 10pt; }
.vp-sign { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 28px; break-inside: avoid; }
.vp-sign div { display: flex; flex-direction: column; gap: 14px; font-size: 10pt; }
.vp-sign span { border-bottom: 1px dotted #000; padding-bottom: 2px; }
.vp-foot { display: flex; justify-content: space-between; margin-top: 18px; padding-top: 6px; border-top: 1px solid #999; font-size: 8.5pt; color: #555; }
</style>
