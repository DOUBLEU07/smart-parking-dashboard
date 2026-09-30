<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'
import Icon from '../components/Icon.vue'
import Modal from '../components/Modal.vue'
import { dateTime, ROLE_LABEL } from '../format'
import { useAuth } from '../stores/auth'
import { useToast } from '../stores/toast'

const auth = useAuth()
const toast = useToast()
const users = ref([])

const ROLE_DESC = {
  owner: 'ทำได้ทุกอย่าง รวมถึงจัดการผู้ใช้และตั้งค่าค่าจอด',
  manager: 'ดูรายงานรายได้ จัดการช่องจอด และ export ข้อมูลได้',
  staff: 'บันทึกรถเข้า–ออก รับชำระเงิน และดูผังลาน',
}
const ROLE_CHIP = {
  owner: 'bg-ink text-paper border-ink',
  manager: 'bg-pine-soft text-pine border-pine-line',
  staff: 'bg-paper-2 text-ink-2 border-line',
}

async function load() {
  try { users.value = await api.get('/users') } catch (e) { toast.error(e.message) }
}
onMounted(load)

const form = ref(null)
function openCreate() {
  form.value = { id: null, username: '', full_name: '', role: 'staff', password: '', is_active: true, error: '', saving: false }
}
function openEdit(u) {
  form.value = { ...u, password: '', error: '', saving: false }
}

async function save() {
  const f = form.value
  f.error = ''
  if ((!f.id || f.password) && f.password.length < 8) return (f.error = 'รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร')
  f.saving = true
  try {
    if (f.id) {
      const body = { full_name: f.full_name, role: f.role, is_active: f.is_active }
      if (f.password) body.password = f.password
      await api.patch(`/users/${f.id}`, body)
      toast.success(`บันทึกข้อมูล ${f.username} แล้ว`)
    } else {
      await api.post('/users', { username: f.username, full_name: f.full_name, role: f.role, password: f.password })
      toast.success(`เพิ่มผู้ใช้ ${f.username} แล้ว`)
    }
    form.value = null
    load()
  } catch (e) {
    f.error = e.message
    f.saving = false
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex justify-between items-center gap-3">
      <p class="text-sm text-muted">ทั้งหมด {{ users.length }} บัญชี</p>
      <button class="btn btn-primary" @click="openCreate"><Icon name="plus" :size="16" /> เพิ่มผู้ใช้</button>
    </div>

    <div class="card overflow-x-auto">
      <table class="table min-w-[640px]">
        <thead><tr><th>ผู้ใช้</th><th>สิทธิ์</th><th>สถานะ</th><th>สร้างเมื่อ</th><th></th></tr></thead>
        <tbody>
          <tr v-for="u in users" :key="u.id" :class="u.is_active ? '' : 'opacity-60'">
            <td>
              <div class="font-semibold text-ink">{{ u.full_name || u.username }}</div>
              <div class="text-xs text-muted">{{ u.username }}<span v-if="u.id === auth.user?.id"> · คุณ</span></div>
            </td>
            <td><span :class="['chip', ROLE_CHIP[u.role]]">{{ ROLE_LABEL[u.role] }}</span></td>
            <td>
              <span v-if="u.is_active" class="chip border-pine-line bg-pine-soft text-pine">ใช้งาน</span>
              <span v-else class="chip border-line bg-paper-2 text-muted">ปิดใช้งาน</span>
            </td>
            <td class="text-xs num">{{ dateTime(u.created_at) }}</td>
            <td class="text-right"><button class="btn btn-ghost btn-sm" @click="openEdit(u)"><Icon name="edit" :size="14" /> แก้ไข</button></td>
          </tr>
        </tbody>
      </table>
    </div>

    <Modal v-if="form" :title="form.id ? `แก้ไขผู้ใช้ ${form.username}` : 'เพิ่มผู้ใช้'" @close="form = null">
      <form class="space-y-4" @submit.prevent="save">
        <div v-if="!form.id">
          <label class="label" for="u-name">ชื่อผู้ใช้ (ใช้ login)</label>
          <input id="u-name" v-model="form.username" class="input" pattern="[a-zA-Z0-9_.\-]{3,50}" autocomplete="off" required
                 title="ภาษาอังกฤษ ตัวเลข _ . - อย่างน้อย 3 ตัว" />
        </div>
        <div>
          <label class="label" for="u-full">ชื่อที่แสดง</label>
          <input id="u-full" v-model="form.full_name" class="input" maxlength="100" />
        </div>
        <fieldset>
          <legend class="label">สิทธิ์การใช้งาน</legend>
          <div class="space-y-2">
            <label v-for="r in ['staff', 'manager', 'owner']" :key="r"
                   :class="['flex gap-3 p-3 rounded-lg border cursor-pointer', form.role === r ? 'border-pine bg-pine-soft' : 'border-line']">
              <input v-model="form.role" type="radio" :value="r" class="mt-1 accent-pine" />
              <span><span class="font-semibold text-sm">{{ ROLE_LABEL[r] }}</span><br /><span class="text-xs text-muted">{{ ROLE_DESC[r] }}</span></span>
            </label>
          </div>
        </fieldset>
        <div>
          <label class="label" for="u-pw">{{ form.id ? 'ตั้งรหัสผ่านใหม่ (เว้นว่างถ้าไม่เปลี่ยน)' : 'รหัสผ่าน (อย่างน้อย 8 ตัว)' }}</label>
          <input id="u-pw" v-model="form.password" type="password" class="input" autocomplete="new-password" :required="!form.id" />
        </div>
        <label v-if="form.id" class="flex items-center gap-2 text-sm">
          <input v-model="form.is_active" type="checkbox" class="accent-pine size-4" /> เปิดใช้งานบัญชีนี้
        </label>
        <p v-if="form.error" class="text-sm text-danger bg-danger-soft rounded-lg px-3 py-2">{{ form.error }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="btn btn-ghost" @click="form = null">ยกเลิก</button>
          <button class="btn btn-primary" :disabled="form.saving">บันทึก</button>
        </div>
      </form>
    </Modal>
  </div>
</template>
