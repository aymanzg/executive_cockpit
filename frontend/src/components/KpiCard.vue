<template>
  <component :is="to ? 'router-link' : 'div'" :to="to" class="card kpi">
    <div class="kpi-top">
      <span class="lbl">{{ label }}</span>
      <svg v-if="path" width="96" height="32" viewBox="0 0 96 32" aria-hidden="true">
        <path :d="path" fill="none" stroke="var(--s1)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </div>
    <div class="kpi-value">
      <span class="num">{{ display.n }}</span>
      <span class="lbl">{{ display.u }}</span>
    </div>
    <span v-if="note" class="kpi-note" :class="tone">{{ note }}</span>
    <span v-if="sub" class="lbl">{{ sub }}</span>
  </component>
</template>

<script setup>
import { computed } from 'vue'
import { amt } from '../format'

const props = defineProps({
  label: String,
  value: [Number, String],
  unit: String, // when set, value is shown as-is with this unit
  note: String,
  tone: { type: String, default: 'neu' },
  sub: String,
  trend: Array,
  to: [String, Object],
})

const display = computed(() => {
  if (props.unit !== undefined) return { n: props.value ?? '—', u: props.unit }
  const a = amt(props.value)
  return { n: a.n, u: a.u === 'ر.س' ? 'ر.س' : `${a.u} ر.س` }
})

// Sparkline, oldest point on the right to match the RTL charts.
const path = computed(() => {
  const arr = (props.trend || []).filter((v) => v !== null && v !== undefined)
  if (arr.length < 2) return ''
  const w = 96, h = 32
  const mn = Math.min(...arr), mx = Math.max(...arr)
  return arr
    .map((v, i) => {
      const x = (w - 2 - i * ((w - 4) / (arr.length - 1))).toFixed(1)
      const y = (h - 3 - ((v - mn) / (mx - mn || 1)) * (h - 6)).toFixed(1)
      return `${i ? 'L' : 'M'}${x} ${y}`
    })
    .join(' ')
})
</script>
