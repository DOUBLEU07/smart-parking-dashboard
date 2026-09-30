<script setup>
import { computed } from 'vue'
import { baht, duration, minutesSince } from '../../format'
import { useParking } from '../../stores/parking'
import CarTop from './CarTop.vue'

const props = defineProps({
  slots: { type: Array, required: true },
  queue: { type: Array, required: true }, // [{ key, plate }]
  selectedQueue: { type: String, default: null }, // queue key
  selectedSlot: { type: Number, default: null }, // slot id
  arriving: { type: Number, default: null }, // slot id animating in
  leaving: { type: Number, default: null }, // slot id animating out
  exited: { type: Object, default: null }, // { plate, fee } last car through the exit
  busy: Boolean,
})
const emit = defineEmits(['pick-queue', 'pick-slot', 'add-car'])
const parking = useParking()

const ROW = 10
const rows = computed(() => {
  const out = []
  for (let i = 0; i < props.slots.length; i += ROW) out.push(props.slots.slice(i, i + ROW))
  return out
})
const placing = computed(() => props.selectedQueue !== null)

function bayClass(slot) {
  if (slot.status === 'maintenance') return 'bay-closed cursor-not-allowed'
  if (slot.status === 'available') {
    return placing.value ? 'bay-target cursor-pointer' : 'cursor-default'
  }
  return props.selectedSlot === slot.id ? 'bay-selected cursor-pointer' : 'cursor-pointer hover:bg-white/5'
}
function clickBay(slot) {
  if (props.busy || slot.status === 'maintenance') return
  if (slot.status === 'available' && !placing.value) return
  emit('pick-slot', slot)
}
</script>

<template>
  <div class="scene rounded-2xl p-3 sm:p-5 text-white select-none">
    <!-- Entrance + queue -->
    <div class="flex items-center gap-3 mb-3">
      <div class="gate shrink-0">
        <span class="gate-arm" :class="placing ? 'gate-open' : ''" />
        <span class="text-[10px] font-semibold tracking-wider">ทางเข้า</span>
      </div>
      <div class="flex-1 flex items-center gap-2 overflow-x-auto py-1 min-h-[58px]" aria-label="คิวรถรอเข้าลาน">
        <button v-for="car in queue" :key="car.key" type="button" :disabled="busy"
                :class="['queue-car shrink-0 rounded-lg px-1.5 py-1 flex flex-col items-center gap-0.5 transition',
                         selectedQueue === car.key ? 'ring-2 ring-[#7FD1B9] bg-white/10' : 'hover:bg-white/5']"
                :aria-pressed="selectedQueue === car.key" :aria-label="`รถทะเบียน ${car.plate} รอเข้าลาน`"
                @click="emit('pick-queue', car)">
          <CarTop :plate="car.plate" horizontal class="w-[58px] h-[32px]" />
          <span class="plate-tag">{{ car.plate }}</span>
        </button>
        <span v-if="!queue.length" class="text-xs text-white/50">ไม่มีรถรอ</span>
        <button type="button" class="shrink-0 h-10 px-3 rounded-lg border border-dashed border-white/30 text-xs text-white/70 hover:text-white hover:border-white/60 cursor-pointer"
                @click="emit('add-car')">+ รถมาใหม่</button>
      </div>
    </div>

    <!-- Lot -->
    <div class="rounded-xl bg-black/15 p-2 sm:p-3 space-y-3">
      <template v-for="(row, r) in rows" :key="r">
        <div class="grid grid-cols-5 sm:grid-cols-10 gap-0">
          <button v-for="slot in row" :key="slot.id" type="button"
                  :class="['bay relative h-[104px] sm:h-[112px] flex flex-col items-center justify-start pt-1 gap-0.5', bayClass(slot)]"
                  :aria-label="`ช่อง ${slot.slot_number} ${slot.session ? 'ทะเบียน ' + slot.session.plate_number : slot.status === 'available' ? 'ว่าง' : 'ปิด'}`"
                  @click="clickBay(slot)">
            <span class="text-[10px] leading-none font-mono text-white/55">{{ slot.slot_number }}</span>
            <template v-if="slot.session && slot.id !== leaving">
              <CarTop :plate="slot.session.plate_number"
                      :class="['w-[30px] sm:w-[34px] h-[54px] sm:h-[60px]', slot.id === arriving ? 'car-arrive' : '']" />
              <span class="plate-tag mt-0.5 max-w-full truncate">{{ slot.session.plate_number }}</span>
              <span class="text-[9px] text-white/55 num">{{ duration(minutesSince(slot.session.entry_time, parking.now)) }}</span>
            </template>
            <template v-else-if="slot.id === leaving">
              <CarTop :plate="exited?.plate || ''" class="w-[30px] sm:w-[34px] h-[54px] sm:h-[60px] car-leave" />
            </template>
            <span v-else-if="slot.status === 'available'" :class="['text-[11px] font-semibold mt-6', placing ? 'text-[#7FD1B9]' : 'text-white/35']">
              {{ placing ? 'จอดที่นี่' : 'ว่าง' }}
            </span>
            <span v-else class="text-[10px] text-white/50 mt-6">ปิดปรับปรุง</span>
          </button>
        </div>
        <div v-if="r < rows.length - 1" class="lane" aria-hidden="true" />
      </template>
    </div>

    <!-- Exit -->
    <div class="flex items-center gap-3 mt-3">
      <div class="flex-1 h-12 rounded-lg bg-black/15 flex items-center px-3 gap-3 overflow-hidden">
        <template v-if="exited">
          <CarTop :key="exited.key" :plate="exited.plate" horizontal class="w-[58px] h-[32px] car-exit" />
          <span class="text-sm"><b>{{ exited.plate }}</b> ออกจากลานแล้ว · ชำระ <b class="text-[#F2C46D]">{{ baht(exited.fee) }}</b></span>
        </template>
        <span v-else class="text-xs text-white/45">รถที่ชำระเงินแล้วจะออกทางนี้</span>
      </div>
      <div class="gate shrink-0">
        <span class="gate-arm" :class="exited ? 'gate-open' : ''" />
        <span class="text-[10px] font-semibold tracking-wider">ทางออก</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scene {
  background:
    radial-gradient(circle at 20% 10%, rgba(255,255,255,0.05), transparent 40%),
    #2B332F;
}
.bay {
  border-left: 2px solid rgba(255,255,255,0.55);
  border-bottom: 2px solid rgba(255,255,255,0.55);
}
.bay:last-child { border-right: 2px solid rgba(255,255,255,0.55); }
.bay-target { background: rgba(127,209,185,0.10); animation: pulse-bay 1.4s ease-in-out infinite; }
.bay-selected { background: rgba(242,196,109,0.16); box-shadow: inset 0 0 0 2px #F2C46D; }
.bay-closed { background: repeating-linear-gradient(135deg, rgba(255,255,255,0.08) 0 6px, transparent 6px 12px); }
.lane { height: 18px; background: repeating-linear-gradient(90deg, #D9B44A 0 18px, transparent 18px 34px) center / 100% 2px no-repeat; }
.plate-tag {
  font-size: 10px; line-height: 1; font-weight: 700; color: #16211D; background: #F6F4EE;
  border-radius: 3px; padding: 2px 4px; white-space: nowrap;
}
.gate { display: flex; flex-direction: column; align-items: center; gap: 6px; padding-top: 10px; width: 56px; color: rgba(255,255,255,0.8); }
.gate-arm {
  width: 48px; height: 5px; border-radius: 3px; transform-origin: left center;
  background: repeating-linear-gradient(90deg, #E0442B 0 8px, #F6F4EE 8px 16px);
  transition: transform 400ms ease;
}
.gate-open { transform: rotate(-60deg); }
.car-arrive { animation: arrive 700ms cubic-bezier(.2,.8,.2,1); }
.car-leave { animation: leave 700ms ease-in forwards; }
.car-exit { animation: exit 1200ms ease-out; }
@keyframes arrive { from { transform: translateY(-70px); opacity: 0; } to { transform: none; opacity: 1; } }
@keyframes leave { to { transform: translateY(80px); opacity: 0; } }
@keyframes exit { from { transform: translateX(-80px); opacity: 0; } to { transform: none; opacity: 1; } }
@keyframes pulse-bay { 50% { background: rgba(127,209,185,0.22); } }
@media (prefers-reduced-motion: reduce) {
  .car-arrive, .car-leave, .car-exit, .bay-target { animation: none; }
}
</style>
