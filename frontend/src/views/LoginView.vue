<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const route = useRoute()
const router = useRouter()

const username = ref('')
const password = ref('')
const error = ref(route.query.expired ? 'เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง' : '')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    const next = typeof route.query.next === 'string' && route.query.next.startsWith('/') ? route.query.next : '/'
    router.replace(next)
  } catch (e) {
    error.value = e.status === 429 ? 'พยายามเข้าสู่ระบบบ่อยเกินไป กรุณารอสักครู่' : e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen grid lg:grid-cols-2">
    <section class="hidden lg:flex flex-col justify-between bg-ink text-paper p-12">
      <div class="font-serif text-2xl font-bold">Smart Parking</div>
      <div class="max-w-md">
        <h1 class="font-serif text-4xl font-bold leading-tight">รู้สถานะลานจอดทุกช่อง<br />และรายได้ทุกบาท แบบ Real-time</h1>
        <p class="mt-4 text-paper/70 leading-relaxed">
          ดูช่องว่าง บันทึกรถเข้า–ออก รับชำระเงิน และติดตามรายได้ได้ในที่เดียว ไม่ต้องจดบันทึกหรือใช้หลายระบบ
        </p>
        <div class="mt-8 grid grid-cols-6 gap-1.5 max-w-xs" aria-hidden="true">
          <span v-for="i in 18" :key="i"
                :class="['h-7 rounded', [2, 3, 5, 7, 8, 9, 11, 13, 14, 16].includes(i) ? 'bg-paper/85' : 'bg-pine/70 border border-pine-line/40']" />
        </div>
      </div>
      <div class="text-xs text-paper/50">Sprint 0 · Smart Parking Dashboard</div>
    </section>

    <section class="flex items-center justify-center p-6">
      <form class="w-full max-w-sm" @submit.prevent="submit">
        <div class="lg:hidden font-serif text-2xl font-bold mb-8">Smart Parking</div>
        <h2 class="h-title text-3xl">เข้าสู่ระบบ</h2>
        <p class="text-sm text-muted mt-1.5 mb-8">สำหรับเจ้าของ ผู้ดูแล และพนักงานประจำลาน</p>

        <label class="label" for="username">ชื่อผู้ใช้</label>
        <input id="username" v-model="username" class="input h-11" autocomplete="username" autofocus required />

        <label class="label mt-4" for="password">รหัสผ่าน</label>
        <input id="password" v-model="password" type="password" class="input h-11" autocomplete="current-password" required />

        <p v-if="error" class="mt-4 text-sm text-danger bg-danger-soft rounded-lg px-3 py-2" role="alert">{{ error }}</p>

        <button class="btn btn-dark w-full h-11 mt-6" :disabled="loading">
          {{ loading ? 'กำลังเข้าสู่ระบบ…' : 'เข้าสู่ระบบ' }}
        </button>
      </form>
    </section>
  </div>
</template>
