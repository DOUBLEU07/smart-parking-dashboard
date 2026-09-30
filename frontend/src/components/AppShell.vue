<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { ROLE_LABEL } from '../format'
import { useAuth } from '../stores/auth'
import { useParking } from '../stores/parking'
import { useToast } from '../stores/toast'
import ConnectionBadge from './ConnectionBadge.vue'
import Icon from './Icon.vue'
import Modal from './Modal.vue'

const auth = useAuth()
const parking = useParking()
const toast = useToast()
const route = useRoute()
const router = useRouter()

const NAV = [
  { to: '/demo', label: 'Demo Mode', icon: 'play', demo: true },
  { to: '/', label: 'ภาพรวม', icon: 'dashboard' },
  { to: '/gate', label: 'รถเข้า–ออก', icon: 'gate' },
  { to: '/history', label: 'ประวัติการจอด', icon: 'history' },
  { to: '/reports', label: 'รายงานรายได้', icon: 'reports', role: 'manager' },
  { to: '/slots', label: 'จัดการช่องจอด', icon: 'slots', role: 'manager' },
  { to: '/users', label: 'ผู้ใช้งาน', icon: 'users', role: 'owner' },
  { to: '/settings', label: 'ตั้งค่า', icon: 'settings', role: 'owner' },
]
const demoMode = ref(false)
const nav = computed(() => NAV.filter((n) => (!n.role || auth.can(n.role)) && (!n.demo || demoMode.value)))
const drawer = ref(false)
watch(() => route.fullPath, () => { drawer.value = false })

onMounted(() => {
  parking.start()
  api.get('/demo/status').then(() => { demoMode.value = true }).catch(() => {})
})
onUnmounted(() => parking.stop())

function logout() {
  parking.stop()
  auth.logout()
  router.replace('/login')
}

const pw = reactive({ open: false, current: '', next: '', confirm: '', saving: false, error: '' })
async function changePassword() {
  pw.error = ''
  if (pw.next.length < 8) return (pw.error = 'รหัสผ่านใหม่ต้องมีอย่างน้อย 8 ตัวอักษร')
  if (pw.next !== pw.confirm) return (pw.error = 'ยืนยันรหัสผ่านไม่ตรงกัน')
  pw.saving = true
  try {
    await api.post('/auth/change-password', { current_password: pw.current, new_password: pw.next })
    toast.success('เปลี่ยนรหัสผ่านแล้ว')
    Object.assign(pw, { open: false, current: '', next: '', confirm: '' })
  } catch (e) {
    pw.error = e.message
  } finally {
    pw.saving = false
  }
}

const s = computed(() => parking.summary)
</script>

<template>
  <div class="min-h-screen lg:pl-60">
    <!-- Sidebar -->
    <aside :class="['fixed inset-y-0 left-0 z-30 w-60 bg-ink text-paper flex flex-col transition-transform lg:translate-x-0',
                    drawer ? 'translate-x-0' : '-translate-x-full']">
      <div class="px-5 pt-6 pb-5 border-b border-white/10">
        <div class="font-serif text-xl font-bold leading-tight">Smart Parking</div>
        <div class="text-xs text-paper/60 mt-0.5 truncate">{{ s?.lot_name || 'Dashboard' }}</div>
      </div>
      <nav class="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        <RouterLink v-for="n in nav" :key="n.to" :to="n.to"
                    :class="['flex items-center gap-3 rounded-lg px-3 h-10 text-sm transition-colors',
                             (n.to === '/' ? route.path === '/' : route.path.startsWith(n.to))
                               ? 'bg-white/12 text-white font-semibold' : 'text-paper/70 hover:bg-white/6 hover:text-white']">
          <Icon :name="n.icon" />
          {{ n.label }}
        </RouterLink>
      </nav>
      <div class="p-3 border-t border-white/10">
        <div class="px-3 py-2">
          <div class="text-sm font-semibold truncate">{{ auth.user?.full_name || auth.user?.username }}</div>
          <div class="text-xs text-paper/60">{{ auth.user?.username }} · {{ ROLE_LABEL[auth.user?.role] }}</div>
        </div>
        <button class="w-full flex items-center gap-3 rounded-lg px-3 h-9 text-sm text-paper/70 hover:bg-white/6 hover:text-white cursor-pointer"
                @click="pw.open = true">
          <Icon name="key" :size="16" /> เปลี่ยนรหัสผ่าน
        </button>
        <button class="w-full flex items-center gap-3 rounded-lg px-3 h-9 text-sm text-paper/70 hover:bg-white/6 hover:text-white cursor-pointer"
                @click="logout">
          <Icon name="logout" :size="16" /> ออกจากระบบ
        </button>
      </div>
    </aside>
    <div v-if="drawer" class="fixed inset-0 z-20 bg-ink/40 lg:hidden" @click="drawer = false" />

    <!-- Top bar -->
    <header class="sticky top-0 z-10 bg-paper/90 backdrop-blur border-b border-line-strong">
      <div class="flex items-center gap-3 px-4 sm:px-6 lg:px-8 h-16">
        <button class="lg:hidden -ml-1 p-1.5 text-ink cursor-pointer" aria-label="เมนู" @click="drawer = true">
          <Icon name="menu" :size="22" />
        </button>
        <h1 class="h-title text-xl sm:text-2xl truncate flex-1">{{ route.meta.title }}</h1>
        <ConnectionBadge />
      </div>
      <!-- Near-full banner is global: every role on every page should see it. -->
      <div v-if="s?.near_full" role="alert"
           :class="['px-4 sm:px-6 lg:px-8 py-2 text-sm flex items-center gap-2 font-medium',
                    s.is_full ? 'bg-danger text-white' : 'bg-rust text-white']">
        <Icon name="alert" :size="16" />
        <span v-if="s.is_full">ลานจอดเต็ม ไม่มีช่องว่าง ({{ s.occupied }}/{{ s.capacity }} ช่อง)</span>
        <span v-else>ลานจอดใกล้เต็ม ใช้งานแล้ว {{ s.occupancy_rate }}% เหลือ {{ s.available }} ช่อง (เกณฑ์แจ้งเตือน {{ s.alert_threshold }}%)</span>
      </div>
    </header>

    <main class="px-4 sm:px-6 lg:px-8 py-6 max-w-[1400px]">
      <RouterView />
    </main>

    <Modal v-if="pw.open" title="เปลี่ยนรหัสผ่าน" @close="pw.open = false">
      <form class="space-y-4" @submit.prevent="changePassword">
        <div>
          <label class="label" for="pw-cur">รหัสผ่านปัจจุบัน</label>
          <input id="pw-cur" v-model="pw.current" type="password" class="input" autocomplete="current-password" required />
        </div>
        <div>
          <label class="label" for="pw-new">รหัสผ่านใหม่ (อย่างน้อย 8 ตัว)</label>
          <input id="pw-new" v-model="pw.next" type="password" class="input" autocomplete="new-password" required />
        </div>
        <div>
          <label class="label" for="pw-cf">ยืนยันรหัสผ่านใหม่</label>
          <input id="pw-cf" v-model="pw.confirm" type="password" class="input" autocomplete="new-password" required />
        </div>
        <p v-if="pw.error" class="text-sm text-danger">{{ pw.error }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="btn btn-ghost" @click="pw.open = false">ยกเลิก</button>
          <button class="btn btn-primary" :disabled="pw.saving">บันทึก</button>
        </div>
      </form>
    </Modal>
  </div>
</template>
