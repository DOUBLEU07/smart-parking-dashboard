<script setup>
import { duration, minutesSince, SLOT_STATUS_LABEL } from '../format'
import { useParking } from '../stores/parking'

// manage: maintenance slots stay clickable (slot administration screen).
defineProps({ slots: { type: Array, required: true }, compact: Boolean, manage: Boolean })
const emit = defineEmits(['select'])
const parking = useParking()

const STYLE = {
  available: 'bg-pine-soft border-pine-line text-pine hover:border-pine hover:bg-[#E3EEEA]',
  occupied: 'bg-ink border-ink text-paper hover:bg-ink-2',
  maintenance: 'border-line-strong text-muted bg-[repeating-linear-gradient(135deg,#EFE9DC_0_6px,#F6F4EE_6px_12px)]',
}
</script>

<template>
  <div class="grid gap-2" :class="compact ? 'grid-cols-[repeat(auto-fill,minmax(72px,1fr))]' : 'grid-cols-[repeat(auto-fill,minmax(92px,1fr))]'">
    <button v-for="slot in slots" :key="slot.id" type="button"
            :disabled="slot.status === 'maintenance' && !manage"
            :aria-label="`ช่อง ${slot.slot_number}: ${SLOT_STATUS_LABEL[slot.status]}${slot.session ? ' ทะเบียน ' + slot.session.plate_number : ''}`"
            :class="['relative rounded-lg border text-left transition-colors cursor-pointer disabled:cursor-not-allowed',
                     compact ? 'px-2 py-1.5 h-14' : 'px-3 py-2 h-[76px]', STYLE[slot.status]]"
            @click="emit('select', slot)">
      <div class="flex items-center justify-between">
        <span class="font-mono text-[13px] font-semibold">{{ slot.slot_number }}</span>
        <span v-if="slot.status === 'available'" class="size-1.5 rounded-full bg-pine" />
      </div>
      <template v-if="slot.session">
        <div :class="['truncate font-semibold', compact ? 'text-[11px] mt-0.5' : 'text-[13px] mt-1']">{{ slot.session.plate_number }}</div>
        <div v-if="!compact" class="text-[11px] text-paper/60 num">{{ duration(minutesSince(slot.session.entry_time, parking.now)) }}</div>
      </template>
      <div v-else :class="['text-muted', compact ? 'text-[11px] mt-0.5' : 'text-xs mt-1.5']"
           :style="slot.status === 'available' ? 'color: var(--color-pine)' : ''">
        {{ SLOT_STATUS_LABEL[slot.status] }}
      </div>
    </button>
  </div>
</template>
