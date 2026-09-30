<script setup>
import { computed } from 'vue'
import { useParking } from '../stores/parking'

const parking = useParking()
const view = computed(() => ({
  live: { dot: 'bg-cash', text: 'Real-time', title: 'เชื่อมต่อแบบ Real-time (WebSocket)' },
  polling: { dot: 'bg-qr', text: 'อัปเดตทุก 10 วิ', title: 'WebSocket หลุด กำลังดึงข้อมูลเป็นระยะและพยายามเชื่อมต่อใหม่' },
  connecting: { dot: 'bg-faint animate-pulse', text: 'กำลังเชื่อมต่อ', title: 'กำลังเชื่อมต่อ' },
  offline: { dot: 'bg-faint', text: 'ออฟไลน์', title: 'ไม่ได้เชื่อมต่อ' },
}[parking.connection]))
</script>

<template>
  <span class="chip border-line bg-card text-ink-2" :title="view.title">
    <span class="relative flex size-2">
      <span v-if="parking.connection === 'live'" class="absolute inline-flex size-full rounded-full bg-cash opacity-60 animate-ping" />
      <span :class="['relative inline-flex size-2 rounded-full', view.dot]" />
    </span>
    {{ view.text }}
  </span>
</template>
