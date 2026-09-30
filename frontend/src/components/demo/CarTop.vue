<script setup>
import { computed } from 'vue'

const props = defineProps({ plate: { type: String, default: '' }, horizontal: Boolean })

// Muted real-world car paints; picked from the plate so a car keeps its colour.
const PAINTS = ['#D9D4C8', '#3E4A52', '#8C2F25', '#2F5E7A', '#F2EFE8', '#5B6B4E', '#23282A', '#9A7B4F', '#6E7D86', '#B8452C']
const paint = computed(() => {
  let h = 0
  for (const ch of props.plate) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return PAINTS[h % PAINTS.length]
})
</script>

<template>
  <svg :viewBox="horizontal ? '0 0 72 40' : '0 0 40 72'" aria-hidden="true" class="drop-shadow-[0_2px_2px_rgba(0,0,0,0.45)]">
    <g :transform="horizontal ? 'rotate(90 20 20) translate(0 -32)' : ''">
      <rect x="3" y="2" width="34" height="68" rx="10" :fill="paint" />
      <rect x="7" y="15" width="26" height="14" rx="4" fill="#15201C" opacity="0.78" />
      <rect x="8" y="50" width="24" height="9" rx="3" fill="#15201C" opacity="0.62" />
      <rect x="7" y="31" width="26" height="17" rx="2" fill="#FFFFFF" opacity="0.10" />
      <rect x="6" y="3" width="7" height="3" rx="1.5" fill="#FFF6D6" opacity="0.9" />
      <rect x="27" y="3" width="7" height="3" rx="1.5" fill="#FFF6D6" opacity="0.9" />
      <rect x="6" y="66" width="7" height="3" rx="1.5" fill="#E0442B" opacity="0.9" />
      <rect x="27" y="66" width="7" height="3" rx="1.5" fill="#E0442B" opacity="0.9" />
    </g>
  </svg>
</template>
