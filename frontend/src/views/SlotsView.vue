<script setup>
import { computed, reactive, ref } from 'vue'
import { api } from '../api'
import Icon from '../components/Icon.vue'
import Modal from '../components/Modal.vue'
import SlotGrid from '../components/SlotGrid.vue'
import { SLOT_STATUS_LABEL } from '../format'
import { useParking } from '../stores/parking'
import { useToast } from '../stores/toast'

const parking = useParking()
const toast = useToast()

const counts = computed(() => {
  const c = { available: 0, occupied: 0, maintenance: 0 }
  parking.slots.forEach((s) => c[s.status]++)
  return c
})

// ---- add slots ----
const add = reactive({ open: false, mode: 'bulk', prefix: 'P', count: 5, slot_number: '', error: '', saving: false })
async function submitAdd() {
  add.error = ''
  add.saving = true
  try {
    if (add.mode === 'bulk') {
      const created = await api.post('/slots/bulk', { prefix: add.prefix, count: Number(add.count) })
      toast.success(`เพิ่ม ${created.length} ช่อง (${created[0].slot_number}–${created.at(-1).slot_number})`)
    } else {
      const s = await api.post('/slots', { slot_number: add.slot_number })
      toast.success(`เพิ่มช่อง ${s.slot_number}`)
    }
    add.open = false
    parking.refresh()
  } catch (e) {
    add.error = e.message
  } finally {
    add.saving = false
  }
}

// ---- edit one slot ----
const edit = ref(null)
function open(slot) {
  edit.value = { ...slot, number: slot.slot_number, error: '', saving: false }
}
async function run(fn, okMsg) {
  edit.value.error = ''
  edit.value.saving = true
  try {
    await fn()
    toast.success(okMsg)
    edit.value = null
    parking.refresh()
  } catch (e) {
    edit.value.error = e.message
    edit.value.saving = false
  }
}
const rename = () => run(() => api.patch(`/slots/${edit.value.id}`, { slot_number: edit.value.number }), 'บันทึกเลขช่องแล้ว')
const toggleMaintenance = () => {
  const next = edit.value.status === 'maintenance' ? 'available' : 'maintenance'
  return run(() => api.patch(`/slots/${edit.value.id}`, { status: next }),
    next === 'maintenance' ? `ปิดช่อง ${edit.value.slot_number} ชั่วคราวแล้ว` : `เปิดใช้ช่อง ${edit.value.slot_number} แล้ว`)
}
const remove = () => {
  if (!confirm(`ลบช่อง ${edit.value.slot_number}?`)) return
  return run(() => api.del(`/slots/${edit.value.id}`), `ลบช่อง ${edit.value.slot_number} แล้ว`)
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-wrap gap-2 text-sm">
        <span class="chip border-line bg-card text-ink-2">ทั้งหมด <b class="num">{{ parking.slots.length }}</b></span>
        <span v-for="(n, k) in counts" :key="k" class="chip border-line bg-card text-ink-2">{{ SLOT_STATUS_LABEL[k] }} <b class="num">{{ n }}</b></span>
      </div>
      <button class="btn btn-primary" @click="Object.assign(add, { open: true, error: '' })"><Icon name="plus" :size="16" /> เพิ่มช่องจอด</button>
    </div>

    <section class="card p-4 sm:p-5">
      <p class="text-sm text-muted mb-4">กดที่ช่องเพื่อแก้ไขเลขช่อง ปิดปรับปรุงชั่วคราว หรือลบช่อง (ช่องที่มีรถจอดอยู่จะแก้ได้แค่เลขช่อง)</p>
      <SlotGrid :slots="parking.slots" compact manage @select="open" />
    </section>

    <Modal v-if="add.open" title="เพิ่มช่องจอด" @close="add.open = false">
      <form class="space-y-4" @submit.prevent="submitAdd">
        <div class="grid grid-cols-2 gap-2">
          <button v-for="m in [{ k: 'bulk', l: 'เพิ่มหลายช่อง' }, { k: 'single', l: 'เพิ่มทีละช่อง' }]" :key="m.k" type="button"
                  :class="['h-10 rounded-lg border text-sm font-medium cursor-pointer', add.mode === m.k ? 'border-pine bg-pine-soft text-pine' : 'border-line text-ink-2']"
                  @click="add.mode = m.k">{{ m.l }}</button>
        </div>
        <div v-if="add.mode === 'bulk'" class="grid grid-cols-2 gap-3">
          <div>
            <label class="label" for="a-prefix">ตัวอักษรนำหน้า</label>
            <input id="a-prefix" v-model="add.prefix" class="input uppercase" maxlength="4" />
          </div>
          <div>
            <label class="label" for="a-count">จำนวนช่อง</label>
            <input id="a-count" v-model="add.count" type="number" min="1" max="200" class="input" />
          </div>
          <p class="col-span-2 text-xs text-muted">ระบบจะรันเลขต่อจากช่องล่าสุดที่ขึ้นต้นด้วย “{{ add.prefix.toUpperCase() }}”</p>
        </div>
        <div v-else>
          <label class="label" for="a-num">เลขช่อง</label>
          <input id="a-num" v-model="add.slot_number" class="input uppercase" maxlength="10" placeholder="เช่น P31 หรือ VIP-1" required />
        </div>
        <p v-if="add.error" class="text-sm text-danger">{{ add.error }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="btn btn-ghost" @click="add.open = false">ยกเลิก</button>
          <button class="btn btn-primary" :disabled="add.saving">เพิ่ม</button>
        </div>
      </form>
    </Modal>

    <Modal v-if="edit" :title="`ช่อง ${edit.slot_number}`" @close="edit = null">
      <div class="space-y-4">
        <p class="text-sm">สถานะ: <b>{{ SLOT_STATUS_LABEL[edit.status] }}</b>
          <span v-if="edit.session"> · ทะเบียน {{ edit.session.plate_number }}</span></p>
        <form class="flex gap-2" @submit.prevent="rename">
          <input v-model="edit.number" class="input uppercase" maxlength="10" aria-label="เลขช่อง" />
          <button class="btn btn-ghost shrink-0" :disabled="edit.saving || edit.number.toUpperCase() === edit.slot_number">เปลี่ยนเลข</button>
        </form>
        <p v-if="edit.error" class="text-sm text-danger bg-danger-soft rounded-lg px-3 py-2">{{ edit.error }}</p>
        <div class="flex flex-wrap justify-between gap-2 pt-2 border-t border-line-2">
          <button class="btn btn-danger" :disabled="edit.saving || edit.status === 'occupied'" @click="remove">
            <Icon name="trash" :size="16" /> ลบช่อง
          </button>
          <button class="btn btn-dark" :disabled="edit.saving || edit.status === 'occupied'" @click="toggleMaintenance">
            <Icon name="wrench" :size="16" /> {{ edit.status === 'maintenance' ? 'เปิดใช้งานช่องนี้' : 'ปิดปรับปรุงชั่วคราว' }}
          </button>
        </div>
      </div>
    </Modal>
  </div>
</template>
