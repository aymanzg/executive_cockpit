<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" :stroke-width="stroke"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path :d="PATHS[name]" />
  </svg>
</template>

<script setup>
defineProps({ name: String, size: { type: Number, default: 20 }, stroke: { type: Number, default: 1.8 } })
const PATHS = {
  overview: 'M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z',
  sales: 'M3 5h18l-7 8v6l-4 2v-8z',
  collection: 'M3 7h15a3 3 0 0 1 3 3v7a3 3 0 0 1-3 3H3zM3 7l12-4v4M16 14h2',
  profit: 'M3 17l6-6 4 4 8-8M15 7h6v6',
  hr: 'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM2 21v-1a6 6 0 0 1 12 0v1M16 3.5a4 4 0 0 1 0 7.5M22 21v-1a6 6 0 0 0-4-5.6',
  reps: 'M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM2 16v-1a5 5 0 0 1 9-3M14 21v-6M18 21V11M22 21v-9',
  vat: 'M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6M9 16h3',
  moon: 'M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z',
  sun: 'M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M5.6 18.4l-1.4 1.4M19.8 4.2l-1.4 1.4M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z',
  refresh: 'M21 12a9 9 0 1 1-2.6-6.4M21 4v5h-5',
  logo: 'M3 20h18M6 16V9M11 16V5M16 16v-5M21 16V8',
  desk: 'M4 5h16v11H4zM8 20h8M12 16v4',
  arrow: 'M15 6l-6 6 6 6',
}
</script>
