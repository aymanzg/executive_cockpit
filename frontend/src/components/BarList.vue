<template>
  <div class="barlist">
    <div v-for="(r, i) in rows" :key="i" class="barlist-row">
      <div class="line-row">
        <a v-if="r.href" :href="r.href" target="_blank" rel="noopener" class="barlist-label">{{ r.label }}</a>
        <span v-else class="barlist-label">{{ r.label }}</span>
        <span class="barlist-val">
          <span v-if="r.extra" class="lbl">{{ r.extra }}</span>
          <span class="num" style="font-weight: 600">{{ r.display ?? amtStr(r.value) }}</span>
        </span>
      </div>
      <div class="bar-track">
        <div class="bar-fill" :style="{ width: width(r.value) + '%', background: color, display: 'flex', justifyContent: 'flex-end' }">
          <div v-if="r.part" class="bar-part" :style="{ width: partPct(r) + '%' }" :title="r.partLabel"></div>
        </div>
      </div>
    </div>
    <div v-if="!rows.length" class="empty">لا توجد بيانات في هذه الفترة</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { amtStr } from '../format'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  color: { type: String, default: 'var(--s1)' },
})
const max = computed(() => Math.max(1, ...props.rows.map((r) => Math.abs(r.value || 0))))
const partPct = (r) => (r.value ? Math.min(100, Math.max(0, (r.part / r.value) * 100)) : 0)
const width = (v) => Math.max(1, Math.round((Math.abs(v || 0) / max.value) * 100))
</script>

<style scoped>
.barlist { display: flex; flex-direction: column; gap: 12px; }
.barlist-row { display: flex; flex-direction: column; gap: 6px; }
.barlist-label { color: var(--ink); text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
a.barlist-label:hover { color: var(--s1); text-decoration: underline; }
.bar-part { height: 100%; background: repeating-linear-gradient(-45deg, rgba(255,255,255,.55) 0 3px, transparent 3px 6px); }
.barlist-val { display: flex; gap: 10px; align-items: baseline; flex: none; }
</style>
