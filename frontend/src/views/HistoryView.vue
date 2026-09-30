<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api'
import Icon from '../components/Icon.vue'
import { baht, dateTime, duration, localISODate, METHOD_LABEL } from '../format'
import { useAuth } from '../stores/auth'
import { useParking } from '../stores/parking'
import { useToast } from '../stores/toast'

const auth = useAuth()
const parking = useParking()
const toast = useToast()

const f = reactive({ date_from: localISODate(-6), date_to: localISODate(0), q: '', state: '' })
const page = ref(1)
const PAGE_SIZE = 20
const data = ref({ items: [], total: 0 })
const loading = ref(false)

const params = computed(() => ({ ...f, state: f.state || undefined }))
const pages = computed(() => Math.max(1, Math.ceil(data.value.total / PAGE_SIZE)))

async function load() {
  loading.value = true
  try {
    data.value = await api.get('/sessions', { ...params.value, page: page.value, page_size: PAGE_SIZE })
  } catch (e) {
    toast.error(e.message)
  } finally {
    loading.value = false
  }
}

let debounce
watch(f, () => { page.value = 1; clearTimeout(debounce); debounce = setTimeout(load, 250) })
watch(page, load)
watch(() => parking.version, () => page.value === 1 && load())
onMounted(load)

async function exportCsv() {
  try {
    const res = await api.download('/sessions/export', params.value)
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = Object.assign(document.createElement('a'), { href: url, download: `parking-${f.date_from}_${f.date_to}.csv` })
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    toast.error(e.message)
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="card p-4 flex flex-wrap items-end gap-3">
      <div>
        <label class="label" for="h-from">ตั้งแต่วันที่</label>
        <input id="h-from" v-model="f.date_from" type="date" class="input w-40" :max="f.date_to" />
      </div>
      <div>
        <label class="label" for="h-to">ถึงวันที่</label>
        <input id="h-to" v-model="f.date_to" type="date" class="input w-40" :min="f.date_from" />
      </div>
      <div>
        <label class="label" for="h-state">สถานะ</label>
        <select id="h-state" v-model="f.state" class="input w-36">
          <option value="">ทั้งหมด</option>
          <option value="active">ยังอยู่ในลาน</option>
          <option value="completed">ออกแล้ว</option>
        </select>
      </div>
      <div class="flex-1 min-w-48">
        <label class="label" for="h-q">ทะเบียน</label>
        <input id="h-q" v-model="f.q" class="input" placeholder="ค้นหาทะเบียน" />
      </div>
      <button v-if="auth.can('manager')" class="btn btn-ghost" @click="exportCsv">
        <Icon name="download" :size="16" /> Export CSV
      </button>
    </div>

    <div class="card overflow-x-auto">
      <table class="table min-w-[760px]">
        <thead>
          <tr>
            <th>ทะเบียน</th><th>ช่อง</th><th>เวลาเข้า</th><th>เวลาออก</th><th>ระยะเวลา</th>
            <th class="text-right!">ค่าจอด</th><th>ชำระ</th><th>ผู้บันทึก</th>
          </tr>
        </thead>
        <tbody :class="loading ? 'opacity-50' : ''">
          <tr v-for="s in data.items" :key="s.id">
            <td class="plate">{{ s.plate_number }}</td>
            <td class="font-mono">{{ s.slot_number }}</td>
            <td class="num">{{ dateTime(s.entry_time) }}</td>
            <td class="num">
              <span v-if="s.exit_time">{{ dateTime(s.exit_time) }}</span>
              <span v-else class="chip border-pine-line bg-pine-soft text-pine">อยู่ในลาน</span>
            </td>
            <td>{{ duration(s.duration_minutes) }}</td>
            <td class="text-right num font-medium text-ink">
              <template v-if="s.fee !== null">{{ baht(s.fee) }}</template>
              <span v-else class="text-muted" title="ค่าจอดถ้าออกตอนนี้">~{{ baht(s.current_fee) }}</span>
            </td>
            <td>{{ s.payment ? METHOD_LABEL[s.payment.method] : s.exit_time ? 'ฟรี' : '–' }}</td>
            <td class="text-xs">{{ s.entered_by || '–' }}<span v-if="s.exited_by"> / {{ s.exited_by }}</span></td>
          </tr>
          <tr v-if="!loading && !data.items.length">
            <td colspan="8" class="text-center text-muted py-10">ไม่พบรายการในช่วงที่เลือก</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="flex items-center justify-between text-sm text-muted">
      <span>ทั้งหมด {{ data.total }} รายการ</span>
      <div class="flex items-center gap-2">
        <button class="btn btn-ghost btn-sm" :disabled="page <= 1" @click="page--">ก่อนหน้า</button>
        <span class="num">หน้า {{ page }} / {{ pages }}</span>
        <button class="btn btn-ghost btn-sm" :disabled="page >= pages" @click="page++">ถัดไป</button>
      </div>
    </div>
  </div>
</template>
