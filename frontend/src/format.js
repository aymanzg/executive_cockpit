const MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']

const nf0 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const nf1 = new Intl.NumberFormat('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const nf2 = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

/** Split an amount into a short number and an Arabic unit: 49685586 -> {n: '49.7', u: 'مليون'} */
export function amt(v) {
  if (v === null || v === undefined || isNaN(v)) return { n: '—', u: '' }
  const a = Math.abs(v)
  if (a >= 1e6) return { n: (a >= 1e8 ? nf0 : a >= 1e7 ? nf1 : nf2).format(v / 1e6), u: 'مليون' }
  if (a >= 1e3) return { n: (a >= 1e5 ? nf0 : nf1).format(v / 1e3), u: 'ألف' }
  return { n: nf0.format(v), u: 'ر.س' }
}

/** Amount as one string: "49.7 م" / "556 ألف" */
export function amtStr(v) {
  const x = amt(v)
  return x.u === 'مليون' ? `${x.n} م` : x.u === 'ألف' ? `${x.n} ألف` : x.n
}

export const int = (v) => (v === null || v === undefined ? '—' : nf0.format(v))
export const money = (v) => (v === null || v === undefined ? '—' : nf0.format(v))
/** Exact amount to the halala: 1,234,567.89 */
export const money2 = (v) => (v === null || v === undefined ? '—' : nf2.format(v))
export const pct = (v, d = 1) => (v === null || v === undefined ? '—' : `${(d ? nf1 : nf0).format(v)}%`)

export function monthName(ym, short = false) {
  const [y, m] = ym.split('-').map(Number)
  const n = MONTHS[m - 1]
  return short ? n.slice(0, 3) : n
}

export function monthLabels(months) {
  // add the year only where it changes, so a 12-month window spanning two years stays readable
  return months.map((ym, i) => {
    const [y] = ym.split('-')
    const prevY = i ? months[i - 1].split('-')[0] : null
    return i === 0 || y !== prevY ? `${monthName(ym)} ${y.slice(2)}` : monthName(ym)
  })
}

export function dateAr(d) {
  if (!d) return '—'
  const [y, m, day] = String(d).slice(0, 10).split('-').map(Number)
  return `${day} ${MONTHS[m - 1]} ${y}`
}

/** Delta note with tone. higherIsBetter=false flips colours (e.g. expenses). */
export function deltaNote(delta, label = 'عن الفترة السابقة', higherIsBetter = true) {
  if (delta === null || delta === undefined) return { text: 'لا توجد بيانات كافية للمقارنة', tone: 'neu' }
  const up = delta >= 0
  const good = higherIsBetter ? up : !up
  const arrow = up ? '▲' : '▼'
  return { text: `${arrow} ${nf1.format(Math.abs(delta))}% ${label}`, tone: Math.abs(delta) < 0.5 ? 'neu' : good ? 'pos' : 'neg' }
}

export const QUOTATION_STATUS = {
  Ordered: 'تحوّلت إلى أمر بيع',
  'Partially Ordered': 'تحوّلت جزئياً',
  Expired: 'انتهت صلاحيتها',
  Open: 'مفتوحة',
  Replied: 'تم الرد',
  Lost: 'خسرناها',
  Cancelled: 'ملغاة',
}

export const ADVANCE_STATUS = {
  Unpaid: 'معتمدة ولم تُصرف',
  Paid: 'مصروفة ولم تُسوَّ',
  Claimed: 'مسوّاة بمطالبة',
  Returned: 'مستردة',
  'Partly Claimed and Returned': 'مسوّاة جزئياً',
}

export const EMPLOYEE_STATUS = { Active: 'نشط', Inactive: 'غير نشط', Suspended: 'موقوف', Left: 'غادر' }

export function deskUrl(path, params) {
  const q = params ? '?' + new URLSearchParams(params).toString() : ''
  return `/app/${path}${q}`
}
