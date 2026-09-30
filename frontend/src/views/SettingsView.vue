<script setup>
import { onMounted, ref, watch } from 'vue'
import { api } from '../api'
import { baht, dateTime, duration } from '../format'
import { useToast } from '../stores/toast'

const toast = useToast()
const form = ref(null)
const hasCap = ref(true)
const saving = ref(false)
const error = ref('')
const updatedAt = ref(null)

const SAMPLE_MINUTES = [10, 15, 16, 60, 61, 150, 300, 600, 1440, 1500]
const preview = ref([])

onMounted(async () => {
  try {
    const s = await api.get('/settings')
    updatedAt.value = s.updated_at
    hasCap.value = s.daily_cap !== null
    form.value = { lot_name: s.lot_name, free_minutes: s.free_minutes, hourly_rate: s.hourly_rate,
                   daily_cap: s.daily_cap ?? 200, alert_threshold: s.alert_threshold }
  } catch (e) {
    error.value = e.message
  }
})

const body = () => ({
  lot_name: form.value.lot_name,
  free_minutes: Number(form.value.free_minutes),
  hourly_rate: Number(form.value.hourly_rate),
  daily_cap: hasCap.value ? Number(form.value.daily_cap) : null,
  alert_threshold: Number(form.value.alert_threshold),
})

// Preview uses the server's pricing code so what you see is exactly what gets charged.
let debounce
watch([form, hasCap], () => {
  clearTimeout(debounce)
  debounce = setTimeout(async () => {
    try {
      preview.value = await api.post('/settings/preview', { rule: body(), durations: SAMPLE_MINUTES })
    } catch { preview.value = [] }
  }, 300)
}, { deep: true })

async function save() {
  error.value = ''
  saving.value = true
  try {
    const s = await api.put('/settings', body())
    updatedAt.value = s.updated_at
    toast.success('บันทึกการตั้งค่าแล้ว มีผลกับรถที่ออกหลังจากนี้ทันที')
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div v-if="form" class="grid lg:grid-cols-[1fr_380px] gap-6 items-start">
    <form class="card p-5 sm:p-6 space-y-6" @submit.prevent="save">
      <section>
        <h2 class="h-title text-lg mb-3">ข้อมูลลาน</h2>
        <label class="label" for="s-name">ชื่อลานจอด (แสดงบนใบเสร็จ)</label>
        <input id="s-name" v-model="form.lot_name" class="input" maxlength="100" required />
      </section>

      <section class="pt-5 border-t border-line-2">
        <h2 class="h-title text-lg">อัตราค่าจอด</h2>
        <p class="text-sm text-muted mb-4">คิดรายชั่วโมง เศษของชั่วโมงปัดขึ้นเป็น 1 ชั่วโมง</p>
        <div class="grid sm:grid-cols-2 gap-4">
          <div>
            <label class="label" for="s-free">จอดฟรี (นาที)</label>
            <input id="s-free" v-model="form.free_minutes" type="number" min="0" max="1440" class="input num" required />
          </div>
          <div>
            <label class="label" for="s-rate">ค่าจอดต่อชั่วโมง (บาท)</label>
            <input id="s-rate" v-model="form.hourly_rate" type="number" min="0" step="1" class="input num" required />
          </div>
          <div class="sm:col-span-2">
            <label class="flex items-center gap-2 text-sm font-medium text-ink-2 mb-1.5">
              <input v-model="hasCap" type="checkbox" class="accent-pine size-4" /> กำหนดเพดานค่าจอดต่อวัน (ต่อ 24 ชม.)
            </label>
            <input v-if="hasCap" v-model="form.daily_cap" type="number" min="0" step="1" class="input num sm:w-1/2" aria-label="เพดานต่อวัน (บาท)" />
          </div>
        </div>
      </section>

      <section class="pt-5 border-t border-line-2">
        <h2 class="h-title text-lg">การแจ้งเตือน</h2>
        <label class="label mt-3" for="s-alert">แจ้งเตือนเมื่อใช้งานถึง <b class="text-ink">{{ form.alert_threshold }}%</b> ของช่องที่เปิดใช้</label>
        <input id="s-alert" v-model="form.alert_threshold" type="range" min="50" max="100" step="5" class="w-full accent-rust" />
        <div class="flex justify-between text-xs text-muted"><span>50%</span><span>100%</span></div>
      </section>

      <p v-if="error" class="text-sm text-danger bg-danger-soft rounded-lg px-3 py-2">{{ error }}</p>
      <div class="flex items-center justify-between gap-3">
        <span class="text-xs text-muted">แก้ไขล่าสุด {{ dateTime(updatedAt) }}</span>
        <button class="btn btn-primary" :disabled="saving">{{ saving ? 'กำลังบันทึก…' : 'บันทึกการตั้งค่า' }}</button>
      </div>
    </form>

    <aside class="card p-5">
      <h2 class="h-title text-lg">ตัวอย่างค่าจอด</h2>
      <p class="text-xs text-muted mb-3">คำนวณจากค่าที่กรอกอยู่ (ยังไม่บันทึก)</p>
      <table class="table">
        <thead><tr><th>จอดนาน</th><th class="text-right!">คิด</th><th class="text-right!">ค่าจอด</th></tr></thead>
        <tbody>
          <tr v-for="p in preview" :key="p.minutes">
            <td>{{ duration(p.minutes) }}</td>
            <td class="text-right text-xs">{{ p.billable_hours ? `${p.billable_hours} ชม.` : 'ฟรี' }}</td>
            <td class="text-right num font-semibold text-ink">{{ baht(p.amount) }}</td>
          </tr>
        </tbody>
      </table>
    </aside>
  </div>
  <p v-else-if="error" class="text-danger">{{ error }}</p>
</template>
