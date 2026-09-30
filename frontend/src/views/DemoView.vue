<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api, getToken } from '../api'
import DebugPanel from '../components/demo/DebugPanel.vue'
import LotScene from '../components/demo/LotScene.vue'
import Icon from '../components/Icon.vue'
import { baht, duration, int, METHOD_LABEL } from '../format'
import { useAuth } from '../stores/auth'
import { useParking } from '../stores/parking'
import { useToast } from '../stores/toast'

const auth = useAuth()
const parking = useParking()
const toast = useToast()

const demoOn = ref(true)
const status = ref(null)
const busy = ref(false)

// ---------- traces ----------
const traces = ref([])
async function pushTrace(traceId, label) {
  if (!traceId) return
  try {
    const t = await api.get(`/demo/traces/${traceId}`)
    traces.value = [{ ...t, label }, ...traces.value].slice(0, 40)
  } catch { /* trace expired from the ring buffer */ }
}
async function traced(label, method, path, body) {
  try {
    const { data, traceId } = await api.traced(method, path, body)
    await pushTrace(traceId, label)
    return data
  } catch (e) {
    await pushTrace(e.traceId, label)
    throw e
  }
}
const refreshSummary = () => traced('Dashboard อัปเดตตัวเลข', 'GET', '/dashboard/summary').catch(() => {})

// ---------- demo flow stepper (from the one-pager) ----------
const STEPS = ['Login', 'Parking Dashboard', 'ดูช่องจอดว่าง / ไม่ว่าง', 'รถเข้าลาน', 'จำนวนช่องว่างลดลง', 'รถออก + ชำระเงิน', 'รายได้เพิ่มขึ้น']
const done = ref(new Set([0]))
const mark = (...i) => { done.value = new Set([...done.value, ...i]) }
const current = computed(() => STEPS.findIndex((_, i) => !done.value.has(i)))
const HINT = {
  3: 'เลือกรถในคิวที่ทางเข้า แล้วกดช่องที่เรืองแสงสีเขียวเพื่อจอด หรือกด “จอดช่องว่างแรก” ให้ระบบเลือกให้',
  4: 'ดูตัวเลข “ช่องว่าง” ด้านบนที่ลดลงทันที',
  5: 'กดรถที่จอดอยู่ในลาน → กด ⏩ เลื่อนเวลาให้เกินช่วงจอดฟรี → เลือกวิธีชำระ → ปล่อยรถ',
  6: 'ดู “รายได้วันนี้” ที่เพิ่มขึ้นตามยอดที่รับ',
}

// ---------- KPIs with change chips ----------
const s = computed(() => parking.summary)
const delta = reactive({ available: 0, revenue: 0 })
let deltaTimer
watch(s, (next, prev) => {
  if (!next || !prev) return
  const da = next.available - prev.available
  const dr = next.today_revenue - prev.today_revenue
  if (!da && !dr) return
  delta.available = da
  delta.revenue = dr
  clearTimeout(deltaTimer)
  deltaTimer = setTimeout(() => { delta.available = 0; delta.revenue = 0 }, 4000)
})

// ---------- entrance queue ----------
const PREFIX = ['กข', 'กท', 'ขค', 'จฉ', 'ชซ', 'ถท', 'นบ', 'ปผ', 'พฟ', 'มย', 'รล', 'วศ', 'สห']
let seq = 0
const newCar = () => ({ key: `c${++seq}`, plate: `${PREFIX[Math.floor(Math.random() * PREFIX.length)]} ${1000 + Math.floor(Math.random() * 9000)}` })
const queue = ref([newCar(), newCar(), newCar()])
const selectedQueue = ref(null)
const queuedCar = computed(() => queue.value.find((c) => c.key === selectedQueue.value))

function pickQueue(car) {
  selectedSlot.value = null
  selectedQueue.value = selectedQueue.value === car.key ? null : car.key
}

// ---------- park ----------
const arriving = ref(null)
async function park(slot = null) {
  const car = queuedCar.value
  if (!car || busy.value) return
  busy.value = true
  try {
    const session = await traced(`รถ ${car.plate} เข้าลาน`, 'POST', '/sessions/check-in', {
      plate_number: car.plate, slot_id: slot?.id ?? null,
    })
    queue.value = queue.value.filter((c) => c.key !== car.key)
    if (queue.value.length < 3) queue.value.push(newCar())
    selectedQueue.value = null
    await parking.refresh()
    arriving.value = session.slot_id
    setTimeout(() => { arriving.value = null }, 800)
    mark(3, 4)
    await refreshSummary()
  } catch (e) {
    toast.error(e.message)
  } finally {
    busy.value = false
  }
}

// ---------- select a parked car / checkout ----------
const selectedSlot = ref(null)
const parkedSlot = computed(() => parking.slots.find((x) => x.id === selectedSlot.value && x.session))
const quote = ref(null)
const method = ref('cash')

async function loadQuote() {
  if (!parkedSlot.value) return
  try {
    quote.value = await traced(`ขอยอดค่าจอด ${parkedSlot.value.session.plate_number}`, 'GET', `/sessions/${parkedSlot.value.session.id}/quote`)
  } catch (e) {
    toast.error(e.message)
  }
}
function pickSlot(slot) {
  if (slot.status === 'available') return park(slot)
  selectedQueue.value = null
  if (selectedSlot.value === slot.id) { selectedSlot.value = null; return }
  selectedSlot.value = slot.id
  quote.value = null
  loadQuote()
}
// Another screen may release the car we are looking at.
watch(parkedSlot, (v) => { if (!v && selectedSlot.value && leaving.value === null) { selectedSlot.value = null; quote.value = null } })

async function advance(minutes) {
  if (!parkedSlot.value || busy.value) return
  busy.value = true
  try {
    await traced(`Demo: เลื่อนเวลา +${duration(minutes)}`, 'POST', `/demo/sessions/${parkedSlot.value.session.id}/advance`, { minutes })
    await parking.refresh()
    await loadQuote()
  } catch (e) {
    toast.error(e.message)
  } finally {
    busy.value = false
  }
}

const leaving = ref(null)
const exited = ref(null)
async function checkout() {
  const slot = parkedSlot.value
  if (!slot || !quote.value || busy.value) return
  busy.value = true
  try {
    const receipt = await traced(`รถ ${slot.session.plate_number} ออก + ชำระเงิน`, 'POST', `/sessions/${slot.session.id}/check-out`, {
      method: method.value, expected_amount: quote.value.amount,
    })
    leaving.value = slot.id
    exited.value = { key: Date.now(), plate: receipt.session.plate_number, fee: receipt.session.fee }
    selectedSlot.value = null
    quote.value = null
    setTimeout(async () => {
      leaving.value = null
      await parking.refresh()
    }, 700)
    mark(5)
    if (receipt.session.fee > 0) mark(6)
    await refreshSummary()
  } catch (e) {
    if (e.detail?.code === 'fee_changed') {
      quote.value = { ...quote.value, amount: e.detail.amount }
      toast.warn(e.message)
    } else {
      toast.error(e.message)
    }
  } finally {
    busy.value = false
  }
}

// ---------- security probes for Q&A ----------
async function probe(kind) {
  try {
    if (kind === 'bad-token') {
      const res = await fetch('/api/dashboard/summary', { headers: { Authorization: 'Bearer forged.jwt.token', 'X-Debug-Trace': '1' } })
      await pushTrace(res.headers.get('X-Trace-Id'), 'ทดสอบ: เรียก API ด้วย Token ปลอม')
    } else if (kind === 'rbac') {
      await traced(`ทดสอบ: เปิดรายงานรายได้ด้วยสิทธิ์ ${auth.user.role}`, 'GET', '/reports/summary')
    } else if (kind === 'bad-plate') {
      await traced('ทดสอบ: ส่งทะเบียนแปลกปลอม “DROP TABLE;”', 'POST', '/sessions/check-in', { plate_number: 'DROP TABLE;' })
    } else if (kind === 'duplicate') {
      const parked = parking.slots.find((x) => x.session)
      if (!parked) return toast.warn('ยังไม่มีรถในลาน')
      await traced(`ทดสอบ: จอดทะเบียนซ้ำ ${parked.session.plate_number}`, 'POST', '/sessions/check-in', { plate_number: parked.session.plate_number })
    } else if (kind === 'history') {
      await traced('ดูประวัติการจอด 5 รายการล่าสุด', 'GET', '/sessions?page_size=5')
    }
  } catch { /* the trace already shows why it was rejected */ }
}

async function resetDemo() {
  if (!confirm('รีเซ็ตข้อมูลเดโมกลับเป็นค่าเริ่มต้น (30 ช่อง ใช้งาน 80%)?')) return
  busy.value = true
  try {
    await traced('รีเซ็ตข้อมูลเดโม', 'POST', '/demo/reset')
    done.value = new Set([0, 1, 2])
    selectedQueue.value = selectedSlot.value = null
    quote.value = exited.value = null
    queue.value = [newCar(), newCar(), newCar()]
    await parking.refresh()
    await refreshSummary()
    toast.success('รีเซ็ตข้อมูลเดโมแล้ว')
  } catch (e) {
    toast.error(e.message)
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  try {
    status.value = await api.get('/demo/status')
  } catch (e) {
    if (e.status === 404) demoOn.value = false
    return
  }
  await refreshSummary()
  mark(1, 2)
})

const hasToken = computed(() => !!getToken())
</script>

<template>
  <div v-if="!demoOn" class="card p-8 text-center text-muted">
    Demo Mode ปิดอยู่ (ตั้ง <code class="font-mono">DEMO_MODE=true</code> ใน .env เพื่อเปิด)
  </div>

  <div v-else-if="hasToken" class="grid xl:grid-cols-[minmax(0,1fr)_440px] gap-6 items-start">
    <div class="space-y-4 min-w-0">
      <!-- Stepper -->
      <section class="card p-4">
        <ol class="flex flex-wrap gap-1.5 items-center">
          <template v-for="(label, i) in STEPS" :key="label">
            <li :class="['flex items-center gap-1.5 rounded-lg px-2.5 h-8 text-[12.5px] font-medium border transition-colors',
                         done.has(i) ? 'bg-pine text-white border-pine'
                           : current === i ? 'bg-rust-soft text-rust-dark border-rust/40 ring-2 ring-rust/20' : 'bg-card text-muted border-line']">
              <span class="text-[11px]">{{ done.has(i) ? '✓' : i + 1 }}</span>{{ label }}
            </li>
            <li v-if="i < STEPS.length - 1" class="text-faint text-sm" aria-hidden="true">›</li>
          </template>
        </ol>
        <p class="mt-3 text-sm text-ink-2 flex items-start gap-2">
          <Icon name="play" :size="14" class="mt-1 text-rust shrink-0" />
          <span v-if="current === -1"><b>ครบ Demo Flow แล้ว</b> ลองกดปุ่ม “ทดสอบความปลอดภัย” ใน Backend Debug ต่อได้ หรือเปิดหน้า
            <a href="/" target="_blank" class="underline">ภาพรวม</a> อีกจอเพื่อโชว์ Real-time</span>
          <span v-else>{{ HINT[current] || 'กำลังโหลด…' }}</span>
        </p>
      </section>

      <!-- KPIs -->
      <section v-if="s" class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div class="card p-4 bg-pine-soft! border-pine-line! relative">
          <div class="eyebrow text-pine!">ช่องว่าง</div>
          <div class="font-serif text-3xl font-bold text-pine num mt-1">{{ int(s.available) }}<span class="text-sm text-muted font-sans font-normal"> / {{ s.capacity }}</span></div>
          <span v-if="delta.available" class="delta" :class="delta.available < 0 ? 'bg-rust text-white' : 'bg-pine text-white'">{{ delta.available > 0 ? '+' : '' }}{{ delta.available }}</span>
        </div>
        <div class="card p-4">
          <div class="eyebrow">มีรถจอด</div>
          <div class="font-serif text-3xl font-bold num mt-1">{{ int(s.occupied) }}</div>
        </div>
        <div class="card p-4">
          <div class="eyebrow">อัตราการใช้งาน</div>
          <div :class="['font-serif text-3xl font-bold num mt-1', s.near_full ? 'text-rust' : '']">{{ s.occupancy_rate }}%</div>
          <div v-if="s.near_full" class="text-[11px] text-rust font-semibold">⚠ ถึงเกณฑ์แจ้งเตือน {{ s.alert_threshold }}%</div>
        </div>
        <div class="card p-4 relative">
          <div class="eyebrow">รายได้วันนี้</div>
          <div class="font-serif text-3xl font-bold num mt-1">{{ baht(s.today_revenue) }}</div>
          <span v-if="delta.revenue" class="delta bg-pine text-white">+{{ baht(delta.revenue) }}</span>
        </div>
      </section>

      <!-- Scene -->
      <section>
        <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
          <h2 class="h-title text-lg">ลานจอดจำลอง <span class="text-xs font-sans font-normal text-muted">ข้อมูลจริงจากระบบ ทุกการกดเรียก API จริง</span></h2>
          <button v-if="auth.can('manager')" class="btn btn-ghost btn-sm" :disabled="busy" @click="resetDemo">
            <Icon name="refresh" :size="14" /> รีเซ็ตเดโม
          </button>
        </div>
        <LotScene :slots="parking.slots" :queue="queue" :selected-queue="selectedQueue" :selected-slot="selectedSlot"
                  :arriving="arriving" :leaving="leaving" :exited="exited" :busy="busy"
                  @pick-queue="pickQueue" @pick-slot="pickSlot" @add-car="queue.push(newCar())" />
      </section>

      <!-- Action bar -->
      <section class="card p-4 min-h-[88px]">
        <div v-if="queuedCar" class="flex flex-wrap items-center gap-3">
          <Icon name="in" class="text-pine" />
          <p class="flex-1 basis-[calc(100%-2.5rem)] sm:basis-auto text-sm">รถ <b class="plate">{{ queuedCar.plate }}</b> รอเข้าลาน · กดช่องที่เรืองแสงสีเขียว หรือ</p>
          <button class="btn btn-ghost btn-sm" @click="selectedQueue = null">ยกเลิก</button>
          <button class="btn btn-primary" :disabled="busy || !s?.available" @click="park()">จอดช่องว่างแรก</button>
        </div>

        <div v-else-if="parkedSlot" class="space-y-3">
          <div class="flex flex-wrap items-start gap-4">
            <div class="flex-1 min-w-40">
              <div class="eyebrow">ช่อง {{ parkedSlot.slot_number }}</div>
              <div class="text-xl font-bold plate">{{ parkedSlot.session.plate_number }}</div>
              <div class="text-xs text-muted">จอดมาแล้ว {{ quote ? duration(quote.duration_minutes) : '…' }}</div>
            </div>
            <div class="text-right">
              <div class="eyebrow">ค่าจอด</div>
              <div class="font-serif text-3xl font-bold num">{{ quote ? baht(quote.amount) : '…' }}</div>
              <div class="text-xs text-muted">{{ quote ? (quote.billable_hours ? `คิด ${quote.billable_hours} ชม.` : 'อยู่ในช่วงจอดฟรี 15 นาที') : '' }}</div>
            </div>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-xs text-muted mr-1 flex items-center gap-1"><Icon name="fast" :size="14" /> จำลองเวลา:</span>
            <button v-for="m in [30, 60, 180]" :key="m" class="btn btn-ghost btn-sm" :disabled="busy" @click="advance(m)">+{{ duration(m) }}</button>
            <span class="flex-1" />
            <div class="flex rounded-lg border border-line p-0.5" role="radiogroup" aria-label="วิธีชำระ">
              <button v-for="m in ['cash', 'qr']" :key="m" role="radio" :aria-checked="method === m"
                      :class="['px-3 h-8 rounded-md text-sm cursor-pointer', method === m ? 'bg-ink text-paper' : 'text-ink-2']"
                      @click="method = m"><Icon :name="m" :size="14" class="inline -mt-0.5" /> {{ METHOD_LABEL[m] }}</button>
            </div>
            <button class="btn btn-accent" :disabled="busy || !quote" @click="checkout">
              {{ quote?.amount ? `รับ ${baht(quote.amount)} และปล่อยรถ` : 'ปล่อยรถ' }}
            </button>
          </div>
        </div>

        <p v-else class="text-sm text-muted flex items-center gap-2 h-full">
          <Icon name="car" class="text-faint" />
          กดรถในคิวที่ทางเข้าเพื่อพาเข้าลาน หรือกดรถที่จอดอยู่เพื่อคิดเงินและปล่อยออก
        </p>
      </section>
    </div>

    <DebugPanel class="xl:sticky xl:top-20 h-[640px] xl:h-[calc(100vh-6rem)]" :traces="traces" :events="parking.events"
                :status="status" :connection="parking.connection" @probe="probe" @clear="traces = []" />
  </div>
</template>

<style scoped>
.delta {
  position: absolute; top: 10px; right: 10px; font-size: 12px; font-weight: 700; padding: 1px 8px; border-radius: 999px;
  animation: pop 300ms ease-out;
}
@keyframes pop { from { transform: scale(0.6); opacity: 0; } }
</style>
