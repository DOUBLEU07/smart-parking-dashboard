<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api'
import BarChart from '../components/BarChart.vue'
import { baht, duration, int, localISODate, shortDate } from '../format'
import { useParking } from '../stores/parking'
import { useToast } from '../stores/toast'

const parking = useParking()
const toast = useToast()

const PRESETS = [
  { key: 'today', label: 'วันนี้', from: 0 },
  { key: '7d', label: '7 วัน', from: -6 },
  { key: '30d', label: '30 วัน', from: -29 },
]
const preset = ref('7d')
const range = reactive({ date_from: localISODate(-6), date_to: localISODate(0) })
const report = ref(null)
const loading = ref(false)
const showTable = ref(false)

function applyPreset(p) {
  preset.value = p.key
  range.date_from = localISODate(p.from)
  range.date_to = localISODate(0)
}

async function load() {
  if (!range.date_from || !range.date_to) return
  loading.value = true
  try {
    report.value = await api.get('/reports/summary', range)
  } catch (e) {
    toast.error(e.message)
  } finally {
    loading.value = false
  }
}
watch(range, load)
watch(() => parking.version, load)
onMounted(load)

const r = computed(() => report.value)
const methodTotal = computed(() => (r.value ? r.value.revenue_by_method.cash + r.value.revenue_by_method.qr : 0))
const pct = (v) => (methodTotal.value ? Math.round((v / methodTotal.value) * 100) : 0)
const hourLabels = Array.from({ length: 24 }, (_, h) => String(h).padStart(2, '0'))
const bestDay = computed(() => {
  if (!r.value?.daily.length) return -1
  const vals = r.value.daily.map((d) => d.revenue)
  const max = Math.max(...vals)
  return max > 0 ? vals.indexOf(max) : -1
})
</script>

<template>
  <div class="space-y-6">
    <!-- Filters: one row above the charts -->
    <div class="flex flex-wrap items-end gap-3">
      <div class="flex rounded-lg border border-line bg-card p-0.5" role="group" aria-label="ช่วงเวลา">
        <button v-for="p in PRESETS" :key="p.key"
                :class="['px-3 h-9 rounded-md text-sm font-medium cursor-pointer', preset === p.key ? 'bg-ink text-paper' : 'text-ink-2 hover:bg-paper-2']"
                @click="applyPreset(p)">{{ p.label }}</button>
      </div>
      <div>
        <label class="label" for="r-from">ตั้งแต่</label>
        <input id="r-from" v-model="range.date_from" type="date" class="input w-40" :max="range.date_to" @input="preset = ''" />
      </div>
      <div>
        <label class="label" for="r-to">ถึง</label>
        <input id="r-to" v-model="range.date_to" type="date" class="input w-40" :min="range.date_from" @input="preset = ''" />
      </div>
      <span v-if="loading" class="text-sm text-muted h-10 flex items-center">กำลังโหลด…</span>
    </div>

    <template v-if="r">
      <!-- Headline numbers -->
      <section class="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <div class="card p-5">
          <div class="eyebrow">รายได้รวม</div>
          <div class="mt-2 font-serif text-3xl sm:text-4xl font-bold num">{{ baht(r.total_revenue) }}</div>
        </div>
        <div class="card p-5">
          <div class="eyebrow">รถเข้า / ออก</div>
          <div class="mt-2 font-serif text-3xl sm:text-4xl font-bold num">{{ int(r.total_entries) }}<span class="text-xl text-muted"> / {{ int(r.total_exits) }}</span></div>
        </div>
        <div class="card p-5">
          <div class="eyebrow">ระยะจอดเฉลี่ย</div>
          <div class="mt-2 font-serif text-2xl sm:text-3xl font-bold">{{ duration(r.avg_duration_minutes) }}</div>
        </div>
        <div class="card p-5">
          <div class="eyebrow">ค่าจอดเฉลี่ยต่อคัน</div>
          <div class="mt-2 font-serif text-3xl sm:text-4xl font-bold num">{{ baht(r.avg_fee) }}</div>
        </div>
      </section>

      <div class="grid xl:grid-cols-[1fr_380px] gap-6">
        <section class="card p-5">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h2 class="h-title text-lg">รายได้รายวัน</h2>
              <p class="text-xs text-muted">บาท · แท่งสีส้มคือวันที่รายได้สูงสุด</p>
            </div>
            <button class="btn btn-ghost btn-sm" @click="showTable = !showTable">{{ showTable ? 'ดูกราฟ' : 'ดูตาราง' }}</button>
          </div>
          <BarChart v-if="!showTable" :labels="r.daily.map((d) => shortDate(d.date))" :values="r.daily.map((d) => d.revenue)"
                    :highlight="bestDay" :format="baht" :height="260" />
          <div v-else class="overflow-x-auto max-h-[260px]">
            <table class="table">
              <thead><tr><th>วันที่</th><th class="text-right!">รายได้</th><th class="text-right!">รถเข้า</th><th class="text-right!">รถออก</th></tr></thead>
              <tbody>
                <tr v-for="d in r.daily" :key="d.date">
                  <td>{{ shortDate(d.date) }}</td>
                  <td class="text-right num">{{ baht(d.revenue) }}</td>
                  <td class="text-right num">{{ int(d.entries) }}</td>
                  <td class="text-right num">{{ int(d.exits) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="card p-5">
          <h2 class="h-title text-lg">รายได้แยกตามวิธีชำระ</h2>
          <p class="text-xs text-muted mb-5">สัดส่วนจากรายได้รวม</p>
          <!-- Two-part share bar; each segment is direct-labelled below, so colour is never the only cue. -->
          <div class="flex h-4 gap-0.5 rounded-full overflow-hidden bg-paper-2" role="img"
               :aria-label="`เงินสด ${pct(r.revenue_by_method.cash)}% และ QR ${pct(r.revenue_by_method.qr)}%`">
            <div class="bg-cash" :style="{ width: `${pct(r.revenue_by_method.cash)}%` }" />
            <div class="bg-qr" :style="{ width: `${pct(r.revenue_by_method.qr)}%` }" />
          </div>
          <dl class="mt-5 space-y-3">
            <div v-for="m in [{ k: 'cash', l: 'เงินสด', c: 'bg-cash' }, { k: 'qr', l: 'QR / โอน', c: 'bg-qr' }]" :key="m.k"
                 class="flex items-center gap-3">
              <span :class="['size-3 rounded-sm', m.c]" />
              <dt class="flex-1 text-sm text-ink-2">{{ m.l }}</dt>
              <dd class="text-sm text-muted num w-10 text-right">{{ pct(r.revenue_by_method[m.k]) }}%</dd>
              <dd class="font-semibold num w-24 text-right">{{ baht(r.revenue_by_method[m.k]) }}</dd>
            </div>
          </dl>
        </section>
      </div>

      <section class="card p-5">
        <div class="mb-4">
          <h2 class="h-title text-lg">รถเข้าตามช่วงเวลา</h2>
          <p class="text-xs text-muted">
            จำนวนคันที่เข้าลานในแต่ละชั่วโมง (รวมทุกวันในช่วงที่เลือก)
            <template v-if="r.peak_hour !== null"> · ช่วงที่คนเข้ามากที่สุดคือ {{ String(r.peak_hour).padStart(2, '0') }}:00–{{ String(r.peak_hour + 1).padStart(2, '0') }}:00 น.</template>
          </p>
        </div>
        <BarChart :labels="hourLabels" :values="r.hourly_entries" :highlight="r.peak_hour ?? -1"
                  :format="(v) => `${int(v)} คัน`" :tooltip-title="(i) => `${hourLabels[i]}:00–${String(i + 1).padStart(2, '0')}:00 น.`"
                  :height="220" />
      </section>
    </template>
  </div>
</template>
