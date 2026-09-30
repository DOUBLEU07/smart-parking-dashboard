<script setup>
import { computed, ref, watch } from 'vue'
import Icon from '../Icon.vue'

const props = defineProps({
  traces: { type: Array, required: true }, // newest first: { id, label, method, path, status, duration_ms, steps }
  events: { type: Array, required: true }, // WebSocket events, newest first
  status: { type: Object, default: null }, // /api/demo/status
  connection: { type: String, default: 'offline' },
})
const emit = defineEmits(['probe', 'clear'])

const TIER = {
  edge: { label: 'NGINX', cls: 'bg-[#B4501F] text-white' },
  api: { label: 'API', cls: 'bg-[#5A6660] text-white' },
  auth: { label: 'AUTH', cls: 'bg-[#6B4FA0] text-white' },
  logic: { label: 'LOGIC', cls: 'bg-[#2F6B5E] text-white' },
  db: { label: 'DB', cls: 'bg-[#2E5E8C] text-white' },
  realtime: { label: 'WS', cls: 'bg-[#C4862A] text-[#16211D]' },
}

// Everything the one-pager promises, grouped as the review board will ask about it.
const FEATURES = [
  { group: 'Solution', items: ['แสดงจำนวนช่องว่าง / ช่องที่ถูกใช้งาน', 'แสดงรถเข้า–ออก', 'แสดงรายได้ปัจจุบัน', 'Dashboard สรุปข้อมูลสำคัญ', 'แจ้งเตือนเมื่อพื้นที่จอดใกล้เต็ม', 'ดูประวัติการจอดและรายได้'] },
  { group: 'Architecture & Security', items: ['Two-tier network', 'REST API', 'Authentication', 'Authorization', 'Transaction + Validation', 'Real-time (WebSocket)'] },
]
const seen = computed(() => {
  const s = new Set()
  // A rejected request also proves the control works (e.g. RBAC blocking staff), so count both.
  for (const t of props.traces) for (const st of t.steps) if (st.feature) s.add(st.feature)
  if (props.events.length) s.add('Real-time (WebSocket)')
  return s
})
const coverage = computed(() => {
  const all = FEATURES.flatMap((g) => g.items)
  return `${all.filter((f) => seen.value.has(f)).length}/${all.length}`
})

const showSql = ref(false)
const open = ref(new Set())
const toggle = (id) => { const s = new Set(open.value); s.has(id) ? s.delete(id) : s.add(id); open.value = s }
watch(() => props.traces[0]?.id, (id) => { if (id) open.value = new Set([id]) })

function visibleSteps(t) {
  return showSql.value ? t.steps : t.steps.filter((s) => !(s.tier === 'db' && s.title.startsWith('SQL')))
}
const sqlCount = (t) => t.steps.filter((s) => s.tier === 'db' && s.title.startsWith('SQL')).length

// Light up the hops the latest request actually crossed.
const hop = ref(-1)
let timer
watch(() => props.traces[0]?.id, () => {
  const t = props.traces[0]
  if (!t) return
  const path = [0, 1, 2]
  if (t.steps.some((s) => s.tier === 'db')) path.push(3)
  path.push(2, 1, 0)
  clearInterval(timer)
  let i = 0
  hop.value = path[0]
  timer = setInterval(() => {
    i++
    if (i >= path.length) { clearInterval(timer); hop.value = -1; return }
    hop.value = path[i]
  }, 260)
})

const nodes = computed(() => [
  { name: 'Browser', sub: 'Internet', ip: props.status?.client_ip, zone: 'internet' },
  { name: 'Nginx', sub: 'Public subnet · :80', ip: props.status?.proxy_ip, zone: 'public' },
  { name: 'FastAPI', sub: 'Private subnet · :8000', ip: props.status?.backend_ips?.join(' '), zone: 'private' },
  { name: 'PostgreSQL', sub: 'Private DB subnet · :5432', ip: props.status?.db_ips?.join(' '), zone: 'private' },
])
const time = (ms) => new Date(ms).toLocaleTimeString('th-TH', { hour12: false })
</script>

<template>
  <div class="debug rounded-2xl text-[#E8EDE9] flex flex-col overflow-hidden">
    <div class="flex items-center gap-2 px-4 py-3 border-b border-white/10">
      <Icon name="bug" :size="18" class="text-[#7FD1B9]" />
      <h2 class="font-semibold flex-1">Backend Debug</h2>
      <span :class="['text-[11px] px-2 py-0.5 rounded-full', connection === 'live' ? 'bg-[#0E8A6A]/30 text-[#7FD1B9]' : 'bg-white/10 text-white/60']">
        WS {{ connection === 'live' ? 'live' : connection }}
      </span>
    </div>

    <!-- Architecture -->
    <section class="px-4 py-3 border-b border-white/10">
      <div class="text-[11px] uppercase tracking-wider text-white/50 mb-2">เส้นทางของ request ล่าสุด</div>
      <div class="grid grid-cols-4 gap-1.5 items-stretch">
        <div v-for="(n, i) in nodes" :key="n.name"
             :class="['rounded-lg px-2 py-2 border text-center transition-all duration-200',
                      n.zone === 'internet' ? 'border-dashed border-white/25' : n.zone === 'public' ? 'border-[#B4501F]/60 bg-[#B4501F]/10' : 'border-[#2E8C74]/60 bg-[#2E8C74]/10',
                      hop === i ? 'scale-105 ring-2 ring-[#F2C46D] bg-[#F2C46D]/20' : '']">
          <div class="text-[12px] font-semibold">{{ n.name }}</div>
          <div class="text-[9.5px] text-white/55 leading-tight mt-0.5">{{ n.sub }}</div>
          <div class="text-[9.5px] font-mono text-[#F2C46D]/80 mt-1 break-all leading-tight">{{ n.ip || '–' }}</div>
        </div>
      </div>
      <div class="flex items-center justify-between mt-2 text-[10.5px] text-white/55">
        <span>เปิดสู่ Internet แค่พอร์ตของ Nginx</span>
        <span>Internet <b class="text-[#FF7A5C]">✕</b> PostgreSQL</span>
      </div>
      <p v-if="status && !status.via_nginx" class="text-[10.5px] text-[#F2C46D] mt-1">โหมด dev: request ไม่ได้ผ่าน Nginx (รันผ่าน Docker เพื่อดูเส้นทางจริง)</p>
    </section>

    <!-- Feature coverage -->
    <section class="px-4 py-3 border-b border-white/10">
      <div class="flex items-center justify-between mb-2">
        <span class="text-[11px] uppercase tracking-wider text-white/50">Feature ที่ถูกเรียกใช้แล้ว</span>
        <span class="text-[11px] font-mono text-[#7FD1B9]">{{ coverage }}</span>
      </div>
      <div class="space-y-2">
        <div v-for="g in FEATURES" :key="g.group">
          <div class="text-[10px] text-white/40 mb-1">{{ g.group }}</div>
          <div class="flex flex-wrap gap-1">
            <span v-for="f in g.items" :key="f"
                  :class="['text-[10.5px] px-1.5 py-0.5 rounded border transition-colors',
                           seen.has(f) ? 'border-[#7FD1B9]/60 bg-[#7FD1B9]/15 text-[#BFEBDD]' : 'border-white/10 text-white/40']">
              {{ seen.has(f) ? '✓ ' : '' }}{{ f }}
            </span>
          </div>
        </div>
      </div>
      <div class="mt-3">
        <div class="text-[10px] text-white/40 mb-1">ทดสอบความปลอดภัย (สำหรับช่วง Q&A)</div>
        <div class="flex flex-wrap gap-1.5">
          <button class="probe" @click="emit('probe', 'bad-token')"><Icon name="shield" :size="12" /> Token ปลอม</button>
          <button class="probe" @click="emit('probe', 'rbac')"><Icon name="shield" :size="12" /> เปิดรายงาน (RBAC)</button>
          <button class="probe" @click="emit('probe', 'bad-plate')"><Icon name="shield" :size="12" /> ทะเบียนไม่ถูกต้อง</button>
          <button class="probe" @click="emit('probe', 'duplicate')"><Icon name="shield" :size="12" /> จอดทะเบียนซ้ำ</button>
          <button class="probe" @click="emit('probe', 'history')"><Icon name="history" :size="12" /> ดูประวัติ</button>
        </div>
      </div>
    </section>

    <!-- Trace feed -->
    <section class="flex-1 min-h-0 flex flex-col">
      <div class="flex items-center gap-3 px-4 py-2 border-b border-white/10 text-[11px]">
        <span class="uppercase tracking-wider text-white/50 flex-1">Trace ({{ traces.length }})</span>
        <label class="flex items-center gap-1.5 cursor-pointer text-white/70">
          <input v-model="showSql" type="checkbox" class="accent-[#7FD1B9]" /> แสดง SQL
        </label>
        <button class="text-white/50 hover:text-white cursor-pointer" @click="emit('clear')">ล้าง</button>
      </div>
      <div class="flex-1 overflow-y-auto px-3 py-2 space-y-2 debug-scroll">
        <p v-if="!traces.length && !events.length" class="text-xs text-white/45 px-1 py-6 text-center">
          ลองกดรถในคิว แล้วเลือกช่องจอด: ทุกขั้นที่ backend ทำจะแสดงที่นี่
        </p>

        <div v-for="t in traces" :key="t.id" class="rounded-lg bg-white/[0.04] border border-white/10">
          <button class="w-full text-left px-3 py-2 flex items-center gap-2 cursor-pointer" @click="toggle(t.id)">
            <span :class="['text-[10px] font-mono font-bold px-1.5 rounded', t.status < 400 ? 'bg-[#0E8A6A] text-white' : 'bg-[#C0392B] text-white']">{{ t.status }}</span>
            <span class="flex-1 min-w-0">
              <span class="block text-[12.5px] font-semibold truncate">{{ t.label }}</span>
              <span class="block text-[10.5px] font-mono text-white/50 truncate">{{ t.method }} {{ t.path }}</span>
            </span>
            <span class="text-[10.5px] font-mono text-white/55">{{ t.duration_ms }} ms</span>
          </button>
          <ol v-if="open.has(t.id)" class="px-3 pb-3 space-y-1.5 border-t border-white/5 pt-2">
            <li v-for="(s, i) in visibleSteps(t)" :key="i" class="flex gap-2 text-[11.5px] leading-snug">
              <span class="text-[9.5px] font-mono text-white/35 w-10 shrink-0 text-right pt-0.5">{{ s.t_ms }}ms</span>
              <span :class="['text-[9px] font-bold px-1 rounded h-4 leading-4 shrink-0 w-11 text-center', TIER[s.tier]?.cls]">{{ TIER[s.tier]?.label }}</span>
              <span class="min-w-0">
                <span :class="['block', s.ok ? '' : 'text-[#FF8A73] font-semibold']">{{ s.ok ? '' : '✕ ' }}{{ s.title }}</span>
                <span v-if="s.detail" :class="['block text-white/55 break-words', s.tier === 'db' ? 'font-mono text-[10.5px] text-[#9CC3E8]' : '']">{{ s.detail }}</span>
                <span v-if="s.feature" :class="['inline-block mt-0.5 text-[9.5px] px-1 rounded', s.ok ? 'bg-[#7FD1B9]/15 text-[#BFEBDD]' : 'bg-[#FF8A73]/15 text-[#FFC2B5]']">Feature: {{ s.feature }}{{ s.ok ? '' : ' (ป้องกันสำเร็จ)' }}</span>
              </span>
            </li>
            <li v-if="!showSql && sqlCount(t)" class="text-[10.5px] text-white/40 pl-12">+ SQL อีก {{ sqlCount(t) }} คำสั่ง (ติ๊ก “แสดง SQL”)</li>
          </ol>
        </div>

        <div v-if="events.length" class="pt-1">
          <div class="text-[10px] uppercase tracking-wider text-white/40 px-1 mb-1">WebSocket events ที่หน้าจอนี้ได้รับ</div>
          <div v-for="(e, i) in events.slice(0, 8)" :key="i" class="text-[11px] px-1 py-0.5 text-white/70 flex gap-2">
            <span class="font-mono text-white/35">{{ time(e.at) }}</span>
            <span>⚡ {{ e.reason }}<template v-if="e.slot_number"> · {{ e.slot_number }}</template><template v-if="e.plate_number"> · {{ e.plate_number }}</template></span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.debug { background: #121A17; }
.probe {
  display: inline-flex; align-items: center; gap: 4px; font-size: 10.5px; padding: 3px 8px; border-radius: 6px;
  border: 1px solid rgba(255,255,255,0.15); color: rgba(255,255,255,0.8); cursor: pointer;
}
.probe:hover { border-color: rgba(255,255,255,0.4); color: #fff; }
.debug-scroll { scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.2) transparent; }
</style>
