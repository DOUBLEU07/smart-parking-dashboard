<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { useParking } from '../stores/parking'
import { useToast } from '../stores/toast'
import Modal from './Modal.vue'

const props = defineProps({ slot: { type: Object, default: null } })
const emit = defineEmits(['close', 'done'])
const parking = useParking()
const toast = useToast()

const plate = ref('')
const slotId = ref(props.slot?.id ?? null)
const suggested = ref(null)
const saving = ref(false)
const error = ref('')

const available = computed(() => parking.slots.filter((s) => s.status === 'available'))

onMounted(async () => {
  if (slotId.value) return
  try {
    suggested.value = await api.get('/sessions/suggest-slot')
    slotId.value = suggested.value?.id ?? null
  } catch { /* the server still auto-assigns when slot_id is null */ }
})

async function submit() {
  error.value = ''
  if (plate.value.trim().length < 2) return (error.value = 'กรุณากรอกทะเบียนรถ')
  saving.value = true
  try {
    const s = await api.post('/sessions/check-in', { plate_number: plate.value, slot_id: slotId.value })
    toast.success(`บันทึกรถเข้าแล้ว: ${s.plate_number} → ช่อง ${s.slot_number}`)
    parking.refresh()
    emit('done', s)
  } catch (e) {
    error.value = e.message
    if (e.status === 409) {
      await parking.refresh()
      if (slotId.value && !available.value.some((s) => s.id === slotId.value)) slotId.value = available.value[0]?.id ?? null
    }
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Modal title="บันทึกรถเข้าลาน" @close="emit('close')">
    <form class="space-y-4" @submit.prevent="submit">
      <div>
        <label class="label" for="ci-plate">ทะเบียนรถ</label>
        <input id="ci-plate" v-model="plate" class="input h-14 text-2xl font-semibold tracking-wide text-center"
               placeholder="เช่น กข 1234" maxlength="20" autocomplete="off" required />
      </div>
      <div>
        <label class="label" for="ci-slot">ช่องจอด</label>
        <select id="ci-slot" v-model="slotId" class="input">
          <option :value="null">ให้ระบบเลือกช่องว่างแรก</option>
          <option v-for="s in available" :key="s.id" :value="s.id">
            {{ s.slot_number }}{{ suggested?.id === s.id ? ' (แนะนำ)' : '' }}
          </option>
        </select>
        <p class="text-xs text-muted mt-1.5">ว่างอยู่ {{ available.length }} ช่อง</p>
      </div>
      <p v-if="error" class="text-sm text-danger bg-danger-soft rounded-lg px-3 py-2">{{ error }}</p>
      <div class="flex justify-end gap-2 pt-1">
        <button type="button" class="btn btn-ghost" @click="emit('close')">ยกเลิก</button>
        <button class="btn btn-primary min-w-32" :disabled="saving || !available.length">
          {{ saving ? 'กำลังบันทึก…' : 'บันทึกรถเข้า' }}
        </button>
      </div>
    </form>
  </Modal>
</template>
