<template>
  <div ref="el" class="echart" :style="{ height }" role="img" :aria-label="label"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { store } from '../store'

echarts.use([BarChart, LineChart, PieChart, GridComponent, TooltipComponent, MarkLineComponent, CanvasRenderer])

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '280px' },
  label: { type: String, default: '' },
})

const el = ref(null)
let chart = null
let ro = null

// Resolve 'var(--token)' strings against the current theme so charts follow light/dark.
function resolve(v, css) {
  if (typeof v === 'string') {
    return v.replace(/var\((--[\w-]+)\)/g, (_, name) => css.getPropertyValue(name).trim() || '#888')
  }
  if (Array.isArray(v)) return v.map((x) => resolve(x, css))
  if (v && typeof v === 'object' && !(v instanceof Function)) {
    const o = {}
    for (const k in v) o[k] = resolve(v[k], css)
    return o
  }
  return v
}

function render() {
  if (!chart) return
  const css = getComputedStyle(document.documentElement)
  chart.setOption(resolve(props.option, css), true)
}

onMounted(() => {
  chart = echarts.init(el.value, null, { renderer: 'canvas' })
  render()
  ro = new ResizeObserver(() => chart && chart.resize())
  ro.observe(el.value)
})
onBeforeUnmount(() => {
  ro && ro.disconnect()
  chart && chart.dispose()
  chart = null
})
watch(() => props.option, render, { deep: true })
watch(() => store.dark, () => requestAnimationFrame(render))
</script>

<style scoped>
.echart { width: 100%; }
</style>
