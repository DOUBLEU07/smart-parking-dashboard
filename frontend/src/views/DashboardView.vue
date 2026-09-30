<script setup>
import { computed, ref } from 'vue'
import CheckInModal from '../components/CheckInModal.vue'
import CheckOutModal from '../components/CheckOutModal.vue'
import Icon from '../components/Icon.vue'
import SlotGrid from '../components/SlotGrid.vue'
import { baht, int, longDate, time } from '../format'
import { useParking } from '../stores/parking'

const parking = useParking()
const s = computed(() => parking.summary)

const checkInSlot = ref(null) // {} = open without preset slot
const checkOutId = ref(null)

function onSelect(slot) {
  if (slot.status === 'available') checkInSlot.value = slot
  else if (slot.session) checkOutId.value = slot.session.id
}

const barColor = computed(() => {
  if (!s.value) return 'bg-pine'
  if (s.value.is_full) return 'bg-danger'
  return s.value.near_full ? 'bg-rust' : 'bg-pine'
})
</script>

<template>
  <div v-if="!s" class="py-24 text-center text-muted">กำลังโหลดข้อมูลลานจอด…</div>

  <div v-else class="space-y-6">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <p class="text-sm text-muted">{{ longDate() }} · อัปเดตล่าสุด {{ time(s.generated_at) }}</p>
      <div class="flex gap-2">
        <button class="btn btn-primary" :disabled="s.is_full" @click="checkInSlot = {}">
          <Icon name="in" :size="16" /> บันทึกรถเข้า
        </button>
        <RouterLink to="/gate" class="btn btn-accent"><Icon name="out" :size="16" /> รถออก + ชำระเงิน</RouterLink>
      </div>
    </div>

    <!-- KPIs -->
    <section class="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
      <div class="card p-4 sm:p-5 bg-pine-soft! border-pine-line!">
        <div class="eyebrow text-pine!">ช่องว่าง</div>
        <div class="mt-2 flex items-baseline gap-1.5">
          <span class="font-serif text-4xl sm:text-5xl font-bold text-pine num">{{ int(s.available) }}</span>
          <span class="text-sm text-muted">/ {{ int(s.capacity) }} ช่อง</span>
        </div>
      </div>
      <div class="card p-4 sm:p-5">
        <div class="eyebrow">มีรถจอด</div>
        <div class="mt-2 font-serif text-4xl sm:text-5xl font-bold num">{{ int(s.occupied) }}</div>
        <div v-if="s.maintenance" class="text-xs text-muted mt-1">ปิดปรับปรุง {{ s.maintenance }} ช่อง</div>
      </div>
      <div class="card p-4 sm:p-5">
        <div class="eyebrow">อัตราการใช้งาน</div>
        <div class="mt-2 font-serif text-4xl sm:text-5xl font-bold num" :class="s.near_full ? 'text-rust' : ''">
          {{ s.occupancy_rate }}<span class="text-2xl">%</span>
        </div>
        <div class="relative mt-3 h-2 rounded-full bg-paper-2" role="meter" :aria-valuenow="s.occupancy_rate" aria-valuemin="0" aria-valuemax="100"
             aria-label="อัตราการใช้งาน">
          <div :class="['h-full rounded-full transition-all duration-500', barColor]" :style="{ width: `${s.occupancy_rate}%` }" />
          <div class="absolute -top-1 -bottom-1 w-0.5 bg-ink/60" :style="{ left: `${s.alert_threshold}%` }"
               :title="`เกณฑ์แจ้งเตือน ${s.alert_threshold}%`" />
        </div>
      </div>
      <div class="card p-4 sm:p-5">
        <div class="eyebrow">รายได้วันนี้</div>
        <div class="mt-2 font-serif text-3xl sm:text-4xl font-bold num">{{ baht(s.today_revenue) }}</div>
        <div class="text-xs text-muted mt-1.5">รถเข้า {{ int(s.today_entries) }} · ออก {{ int(s.today_exits) }} คัน</div>
      </div>
    </section>

    <div class="grid xl:grid-cols-[1fr_320px] gap-6">
      <!-- Slot map -->
      <section class="card p-4 sm:p-5">
        <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h2 class="h-title text-lg">ผังช่องจอด</h2>
          <div class="flex flex-wrap gap-3 text-xs text-ink-2">
            <span class="flex items-center gap-1.5"><span class="size-3 rounded-sm bg-pine-soft border border-pine-line" />ว่าง (กดเพื่อรับรถเข้า)</span>
            <span class="flex items-center gap-1.5"><span class="size-3 rounded-sm bg-ink" />มีรถจอด (กดเพื่อปล่อยรถ)</span>
            <span class="flex items-center gap-1.5"><span class="size-3 rounded-sm border border-line-strong bg-paper-2" />ปิดปรับปรุง</span>
          </div>
        </div>
        <SlotGrid :slots="parking.slots" @select="onSelect" />
        <p v-if="!parking.slots.length" class="text-sm text-muted py-8 text-center">ยังไม่มีช่องจอด ให้ผู้จัดการเพิ่มในหน้า “จัดการช่องจอด”</p>
      </section>

      <!-- Activity -->
      <section class="card p-4 sm:p-5">
        <h2 class="h-title text-lg mb-3">ความเคลื่อนไหวล่าสุด</h2>
        <ol class="space-y-0.5">
          <li v-for="(a, i) in s.recent_activity" :key="i" class="flex items-center gap-3 py-2 border-b border-line-2 last:border-0">
            <span :class="['size-8 rounded-lg flex items-center justify-center shrink-0',
                           a.kind === 'entry' ? 'bg-pine-soft text-pine' : 'bg-rust-soft text-rust']">
              <Icon :name="a.kind === 'entry' ? 'in' : 'out'" :size="16" />
            </span>
            <div class="flex-1 min-w-0">
              <div class="plate text-sm truncate">{{ a.plate_number }}</div>
              <div class="text-xs text-muted">{{ a.kind === 'entry' ? 'เข้า' : 'ออก' }} · ช่อง {{ a.slot_number }}</div>
            </div>
            <div class="text-right">
              <div v-if="a.kind === 'exit'" class="text-sm font-semibold num">+{{ baht(a.amount) }}</div>
              <div class="text-xs text-muted num">{{ time(a.at) }}</div>
            </div>
          </li>
        </ol>
        <p v-if="!s.recent_activity.length" class="text-sm text-muted">ยังไม่มีรายการ</p>
      </section>
    </div>

    <CheckInModal v-if="checkInSlot" :slot="checkInSlot.id ? checkInSlot : null"
                  @close="checkInSlot = null" @done="checkInSlot = null" />
    <CheckOutModal v-if="checkOutId" :session-id="checkOutId" @close="checkOutId = null" />
  </div>
</template>
