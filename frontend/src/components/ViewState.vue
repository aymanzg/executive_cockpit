<template>
  <div v-if="error" class="card state" role="alert">
    <strong style="color: var(--neg)">تعذّر تحميل البيانات</strong>
    <span>{{ error }}</span>
    <div><button class="iconbtn" style="width: auto; padding: 0 16px" @click="$emit('retry')">إعادة المحاولة</button></div>
  </div>
  <div v-else-if="loading && !hasData" class="grid-kpi" aria-busy="true" aria-label="جارٍ التحميل">
    <div v-for="i in 6" :key="i" class="skeleton"></div>
    <div class="skeleton" style="grid-column: 1 / -1; min-height: 300px"></div>
  </div>
  <div v-else class="vs-body" :class="{ 'vs-busy': showBusy }" :aria-busy="showBusy ? 'true' : 'false'">
    <slot />
  </div>
  <div class="vs-toast" :class="{ on: showBusy }" role="status" aria-live="polite">
    <span class="vs-spinner" aria-hidden="true"></span>
    <span>{{ showBusy ? 'جارٍ تحديث البيانات…' : '' }}</span>
  </div>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import { store } from '../store'

const props = defineProps({ loading: Boolean, error: String, hasData: Boolean })
defineEmits(['retry'])

// Show the "updating" state only if loading takes longer than a moment,
// so instant (cached) responses don't flash.
const showBusy = ref(false)
let timer = null
watch(
  () => props.loading,
  (on) => {
    store.busy = on
    clearTimeout(timer)
    if (on && props.hasData) timer = setTimeout(() => (showBusy.value = true), 150)
    else showBusy.value = false
  },
  { immediate: true }
)
onBeforeUnmount(() => {
  clearTimeout(timer)
  store.busy = false
})
</script>
