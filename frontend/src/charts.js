import { amtStr, monthLabels, pct } from './format'

const FONT = "'IBM Plex Sans Arabic', system-ui, sans-serif"

function tooltip(fmts) {
  return {
    trigger: 'axis',
    axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(127,127,127,.08)' } },
    backgroundColor: 'var(--card)',
    borderColor: 'var(--line)',
    textStyle: { color: 'var(--ink)', fontFamily: FONT, fontSize: 13 },
    formatter(params) {
      const head = `<div style="font-weight:600;margin-bottom:4px">${params[0].axisValueLabel}</div>`
      const rows = params
        .map(
          (p) =>
            `<div style="display:flex;justify-content:space-between;gap:16px;direction:rtl">` +
            `<span>${p.marker}${p.seriesName}</span>` +
            `<b style="direction:ltr">${p.value === null || p.value === undefined ? '—' : fmts[p.seriesIndex](p.value)}</b></div>`
        )
        .join('')
      return `<div style="direction:rtl;text-align:right">${head}${rows}</div>`
    },
  }
}

/**
 * Month-based bar/line chart laid out right-to-left (oldest month on the right).
 * series: [{ name, data, type: 'bar'|'line', color, axis: 0|1, fmt }]
 */
export function monthChart(months, series, { fmt = amtStr, fmt2 = (v) => pct(v, 0), stack = false } = {}) {
  const hasSecond = series.some((s) => s.axis === 1)
  return {
    textStyle: { fontFamily: FONT },
    grid: { top: 16, bottom: 28, left: hasSecond ? 48 : 12, right: 56, containLabel: false },
    tooltip: tooltip(series.map((s) => s.fmt || (s.axis === 1 ? fmt2 : fmt))),
    xAxis: {
      type: 'category',
      inverse: true,
      data: monthLabels(months),
      axisLine: { lineStyle: { color: 'var(--line)' } },
      axisTick: { show: false },
      axisLabel: { color: 'var(--muted)', fontSize: 11, fontFamily: FONT, interval: 0, hideOverlap: true },
    },
    yAxis: [
      {
        type: 'value',
        position: 'right',
        splitLine: { lineStyle: { color: 'var(--line)' } },
        axisLabel: { color: 'var(--muted)', fontSize: 11, formatter: (v) => fmt(v) },
      },
      ...(hasSecond
        ? [{ type: 'value', position: 'left', splitLine: { show: false }, axisLabel: { color: 'var(--muted)', fontSize: 11, formatter: (v) => fmt2(v) } }]
        : []),
    ],
    series: series.map((s) => ({
      name: s.name,
      type: s.type || 'bar',
      data: s.data,
      yAxisIndex: s.axis || 0,
      stack: stack && s.type !== 'line' ? 'a' : undefined,
      barMaxWidth: 22,
      barGap: '20%',
      smooth: s.type === 'line' ? 0.3 : undefined,
      symbolSize: 7,
      connectNulls: true,
      itemStyle: { color: s.color, borderRadius: s.type === 'line' ? 0 : [5, 5, 0, 0] },
      lineStyle: s.type === 'line' ? { width: 2.5, color: s.color } : undefined,
      markLine: s.markLine,
    })),
  }
}

export function donut(items) {
  return {
    textStyle: { fontFamily: FONT },
    tooltip: {
      trigger: 'item',
      backgroundColor: 'var(--card)',
      borderColor: 'var(--line)',
      textStyle: { color: 'var(--ink)', fontFamily: FONT },
      formatter: (p) => `<div style="direction:rtl">${p.marker}${p.name}: <b>${p.value}</b> (${p.percent}%)</div>`,
    },
    series: [
      {
        type: 'pie',
        radius: ['58%', '82%'],
        avoidLabelOverlap: true,
        label: { show: false },
        itemStyle: { borderColor: 'var(--card)', borderWidth: 2 },
        data: items.map((i) => ({ name: i.name, value: i.value, itemStyle: { color: i.color } })),
      },
    ],
  }
}

export const PALETTE = ['var(--s1)', 'var(--s2)', 'var(--s3)', '#2F8F6B', '#9B59B6', '#D4A017', '#C0392B', '#5D6D7E']
