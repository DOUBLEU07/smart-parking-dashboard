<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import CheckOutModal from '../components/CheckOutModal.vue'
import Icon from '../components/Icon.vue'
import Modal from '../components/Modal.vue'
import { baht, duration, minutesSince, time } from '../format'
import { useParking } from '../stores/parking'
import { useToast } from '../stores/toast'

const parking = useParking()
const toast = useToast()

// ---- check-in form (inline: this is the staff's main screen) ----
const plate = ref('')
const slotId = ref(null)
const saving = ref(false)
const inError = ref('')
const plateInput = ref(null)
const available = computed(() => parking.slots.filter((s) => s.status === 'available'))

async function checkIn() {
  inError.value = ''
  if (plate.value.trim().length < 2) return (inError.value = 'กรุณากรอกทะเบียนรถ')
  saving.value = true
  try {
    const s = await api.post('/sessions/check-in', { plate_number: plate.value, slot_id: slotId.value })
    toast.success(`บันทึกรถเข้าแล้ว: ${s.plate_number} → ช่อง ${s.slot_number}`)
    plate.value = ''
    slotId.value = null
    parking.refresh()
    loadActive()
    plateInput.value?.focus()
  } catch (e) {
    inError.value = e.message
  } finally {
    saving.value = false
  }
}

// ---- cars currently in the lot ----
const q = ref('')
const active = ref([])
const loading = ref(true)

async function loadActive() {
  try {
    active.value = await api.get('/sessions/active', { q: q.value })
  } catch (e) {
    toast.error(e.message)
  } finally {
    loading.value = false
  }
}
let debounce
watch(q, () => { clearTimeout(debounce); debounce = setTimeout(loadActive, 250) })
watch(() => parking.version, loadActive)
onMounted(loadActive)

const checkOutId = ref(null)
function onCheckedOut() { loadActive() }

// Fee shown in the list ticks with the shared clock; the modal fetches the authoritative quote.
const rows = computed(() => active.value.map((s) => ({ ...s, minutes: minutesSince(s.entry_time, parking.now) })))

// ---- fix a mistyped plate ----
const edit = ref(null)
async function savePlate() {
  try {
    await api.patch(`/sessions/${edit.value.id}`, { plate_number: edit.value.plate })
    toast.success('แก้ไขทะเบียนแล้ว')
    edit.value = null
    loadActive()
    parking.refresh()
  } catch (e) {
    edit.value.error = e.message
  }
}
</script>

<template>
  <div class="grid lg:grid-cols-[360px_1fr] gap-6 items-start">
    <!-- Check-in -->
    <section class="card p-5 lg:sticky lg:top-24">
      <div class="flex items-center gap-2 mb-4">
        <span class="size-8 rounded-lg bg-pine-soft text-pine flex items-center justify-center"><Icon name="in" :size="16" /></span>
        <h2 class="h-title text-lg">รถเข้าลาน</h2>
      </div>
      <form class="space-y-4" @submit.prevent="checkIn">
        <div>
          <label class="label" for="g-plate">ทะเบียนรถ</label>
          <input id="g-plate" ref="plateInput" v-model="plate" class="input h-14 text-2xl font-semibold tracking-wide text-center"
                 placeholder="กข 1234" maxlength="20" autocomplete="off" />
        </div>
        <div>
          <label class="label" for="g-slot">ช่องจอด</label>
          <select id="g-slot" v-model="slotId" class="input">
            <option :value="null">อัตโนมัติ: {{ available[0]?.slot_number ?? 'ไม่มีช่องว่าง' }}</option>
            <option v-for="s in available" :key="s.id" :value="s.id">{{ s.slot_number }}</option>
          </select>
        </div>
        <p v-if="inError" class="text-sm text-danger bg-danger-soft rounded-lg px-3 py-2">{{ inError }}</p>
        <button class="btn btn-primary w-full h-12 text-base" :disabled="saving || !available.length">
          {{ !available.length ? 'ลานจอดเต็ม' : saving ? 'กำลังบันทึก…' : 'บันทึกรถเข้า' }}
        </button>
        <p class="text-xs text-muted text-center">ว่าง {{ available.length }} จาก {{ parking.summary?.capacity ?? '–' }} ช่อง</p>
      </form>
    </section>

    <!-- Active cars -->
    <section class="card">
      <div class="flex flex-wrap items-center gap-3 p-4 sm:p-5 border-b border-line">
        <div class="flex items-center gap-2 flex-1">
          <span class="size-8 rounded-lg bg-rust-soft text-rust flex items-center justify-center"><Icon name="out" :size="16" /></span>
          <h2 class="h-title text-lg">รถในลาน <span class="text-muted font-sans text-sm font-normal">({{ active.length }} คัน)</span></h2>
        </div>
        <div class="relative w-full sm:w-64">
          <Icon name="search" :size="16" class="absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
          <input v-model="q" class="input pl-9" placeholder="ค้นหาทะเบียน" aria-label="ค้นหาทะเบียน" />
        </div>
      </div>

      <div v-if="loading" class="p-10 text-center text-muted text-sm">กำลังโหลด…</div>
      <div v-else-if="!rows.length" class="p-10 text-center text-muted text-sm">
        {{ q ? 'ไม่พบทะเบียนที่ค้นหา' : 'ไม่มีรถในลาน' }}
      </div>
      <ul v-else class="divide-y divide-line-2">
        <li v-for="s in rows" :key="s.id" class="flex items-center gap-3 sm:gap-4 px-4 sm:px-5 py-3">
          <span class="font-mono text-sm font-semibold w-10 sm:w-12 shrink-0 text-muted">{{ s.slot_number }}</span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-1.5">
              <span class="plate text-base">{{ s.plate_number }}</span>
              <button class="text-faint hover:text-ink p-1 cursor-pointer" :aria-label="`แก้ไขทะเบียน ${s.plate_number}`"
                      @click="edit = { id: s.id, plate: s.plate_number, error: '' }">
                <Icon name="edit" :size="14" />
              </button>
            </div>
            <div class="text-xs text-muted">เข้า {{ time(s.entry_time) }} · {{ duration(s.minutes) }}</div>
          </div>
          <div class="flex flex-col sm:flex-row items-end sm:items-center gap-1.5 sm:gap-4 shrink-0">
            <div class="text-right sm:w-24">
              <div class="hidden sm:block text-xs text-muted">ค่าจอดตอนนี้</div>
              <div class="font-semibold num">{{ baht(s.current_fee) }}</div>
            </div>
            <button class="btn btn-accent btn-sm" @click="checkOutId = s.id">ปล่อยรถ</button>
          </div>
        </li>
      </ul>
    </section>

    <CheckOutModal v-if="checkOutId" :session-id="checkOutId" @close="checkOutId = null" @done="onCheckedOut" />

    <Modal v-if="edit" title="แก้ไขทะเบียนรถ" @close="edit = null">
      <form class="space-y-4" @submit.prevent="savePlate">
        <input v-model="edit.plate" class="input h-12 text-xl font-semibold text-center" maxlength="20" aria-label="ทะเบียนรถ" />
        <p v-if="edit.error" class="text-sm text-danger">{{ edit.error }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="btn btn-ghost" @click="edit = null">ยกเลิก</button>
          <button class="btn btn-primary">บันทึก</button>
        </div>
      </form>
    </Modal>
  </div>
</template>
