<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api } from '../api'
import { baht, dateTime, duration, METHOD_LABEL } from '../format'
import { useParking } from '../stores/parking'
import { useToast } from '../stores/toast'
import Icon from './Icon.vue'
import Modal from './Modal.vue'

const props = defineProps({ sessionId: { type: Number, required: true } })
const emit = defineEmits(['close', 'done'])
const parking = useParking()
const toast = useToast()

const quote = ref(null)
const method = ref('cash')
const received = ref('')
const saving = ref(false)
const error = ref('')
const notice = ref('')
const receipt = ref(null)
let timer

async function loadQuote() {
  try {
    const q = await api.get(`/sessions/${props.sessionId}/quote`)
    if (quote.value && q.amount !== quote.value.amount) notice.value = `ค่าจอดอัปเดตเป็น ${baht(q.amount)} (เวลาผ่านไปเข้าชั่วโมงใหม่)`
    quote.value = q
  } catch (e) {
    error.value = e.message
    clearInterval(timer)
  }
}

onMounted(() => {
  loadQuote()
  timer = setInterval(loadQuote, 30_000)
})
onUnmounted(() => clearInterval(timer))

const change = computed(() => {
  const r = Number(received.value)
  return received.value !== '' && quote.value ? r - quote.value.amount : null
})
const free = computed(() => quote.value?.amount === 0)

async function confirm() {
  error.value = ''
  if (method.value === 'cash' && !free.value && change.value !== null && change.value < 0) {
    return (error.value = 'จำนวนเงินที่รับมาน้อยกว่าค่าจอด')
  }
  saving.value = true
  try {
    receipt.value = await api.post(`/sessions/${props.sessionId}/check-out`, {
      method: method.value,
      expected_amount: quote.value.amount,
    })
    clearInterval(timer)
    toast.success(`รถ ${receipt.value.session.plate_number} ออกแล้ว รับเงิน ${baht(receipt.value.session.fee)}`)
    parking.refresh()
    emit('done', receipt.value)
  } catch (e) {
    if (e.detail?.code === 'fee_changed') {
      quote.value = { ...quote.value, amount: e.detail.amount }
      notice.value = e.message
    } else {
      error.value = e.message
    }
  } finally {
    saving.value = false
  }
}

const printReceipt = () => window.print()
</script>

<template>
  <Modal :title="receipt ? 'ใบเสร็จค่าจอด' : 'รถออก + ชำระเงิน'" @close="emit('close')">
    <!-- Step 2: receipt -->
    <div v-if="receipt">
      <div class="print-area rounded-xl border border-dashed border-line-strong p-5 font-sans text-ink">
        <div class="text-center">
          <div class="font-serif text-lg font-bold">{{ receipt.lot_name }}</div>
          <div class="text-xs text-muted">ใบเสร็จค่าจอดรถ #{{ receipt.session.id }}</div>
        </div>
        <dl class="mt-4 space-y-1.5 text-sm">
          <div class="flex justify-between"><dt class="text-muted">ทะเบียน</dt><dd class="plate">{{ receipt.session.plate_number }}</dd></div>
          <div class="flex justify-between"><dt class="text-muted">ช่องจอด</dt><dd>{{ receipt.session.slot_number }}</dd></div>
          <div class="flex justify-between"><dt class="text-muted">เวลาเข้า</dt><dd>{{ dateTime(receipt.session.entry_time) }}</dd></div>
          <div class="flex justify-between"><dt class="text-muted">เวลาออก</dt><dd>{{ dateTime(receipt.session.exit_time) }}</dd></div>
          <div class="flex justify-between"><dt class="text-muted">ระยะเวลา</dt><dd>{{ duration(receipt.session.duration_minutes) }}</dd></div>
          <div class="flex justify-between"><dt class="text-muted">คิดเงิน</dt><dd>{{ receipt.billable_hours }} ชม.</dd></div>
          <div class="flex justify-between"><dt class="text-muted">ชำระโดย</dt>
            <dd>{{ receipt.session.payment ? METHOD_LABEL[receipt.session.payment.method] : 'ไม่มีค่าใช้จ่าย' }}</dd></div>
        </dl>
        <div class="mt-4 pt-3 border-t border-line flex justify-between items-baseline">
          <span class="font-semibold">รวม</span>
          <span class="font-serif text-2xl font-bold num">{{ baht(receipt.session.fee) }}</span>
        </div>
        <p class="text-center text-xs text-muted mt-3">ขอบคุณที่ใช้บริการ</p>
      </div>
      <div class="flex justify-end gap-2 mt-4">
        <button class="btn btn-ghost" @click="printReceipt"><Icon name="print" :size="16" /> พิมพ์</button>
        <button class="btn btn-dark" data-autofocus @click="emit('close')">เสร็จสิ้น</button>
      </div>
    </div>

    <!-- Step 1: quote + payment -->
    <div v-else-if="quote" class="space-y-4">
      <div class="rounded-xl bg-paper p-4">
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="eyebrow">ทะเบียน</div>
            <div class="text-2xl font-bold tracking-wide">{{ quote.plate_number }}</div>
          </div>
          <div class="text-right">
            <div class="eyebrow">ช่อง</div>
            <div class="font-mono text-lg font-semibold">{{ quote.slot_number }}</div>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-3 mt-3 text-sm">
          <div><div class="text-muted text-xs">เวลาเข้า</div>{{ dateTime(quote.entry_time) }}</div>
          <div><div class="text-muted text-xs">ระยะเวลา</div>{{ duration(quote.duration_minutes) }}</div>
        </div>
      </div>

      <div class="text-center py-1">
        <div class="eyebrow">ค่าจอดที่ต้องชำระ</div>
        <div class="font-serif text-4xl font-bold num mt-1">{{ baht(quote.amount) }}</div>
        <div class="text-xs text-muted mt-1">{{ free ? 'อยู่ในช่วงจอดฟรี' : `คิด ${quote.billable_hours} ชั่วโมง` }}</div>
      </div>

      <p v-if="notice" class="text-sm text-rust-dark bg-rust-soft rounded-lg px-3 py-2">{{ notice }}</p>

      <template v-if="!free">
        <div class="grid grid-cols-2 gap-2" role="radiogroup" aria-label="วิธีชำระเงิน">
          <button v-for="m in ['cash', 'qr']" :key="m" type="button" role="radio" :aria-checked="method === m"
                  :class="['h-14 rounded-xl border-2 flex items-center justify-center gap-2 font-semibold cursor-pointer transition-colors',
                           method === m ? 'border-pine bg-pine-soft text-pine' : 'border-line text-ink-2 hover:border-line-strong']"
                  @click="method = m">
            <Icon :name="m" /> {{ METHOD_LABEL[m] }}
          </button>
        </div>
        <div v-if="method === 'cash'" class="grid grid-cols-2 gap-3 items-end">
          <div>
            <label class="label" for="co-recv">รับเงินมา (บาท)</label>
            <input id="co-recv" v-model="received" type="number" min="0" step="1" inputmode="numeric" class="input num" placeholder="ไม่บังคับ" />
          </div>
          <div class="h-10 flex items-center justify-end text-sm">
            <span v-if="change !== null" :class="change < 0 ? 'text-danger' : 'text-ink'">
              เงินทอน <b class="num text-base">{{ baht(Math.max(change, 0)) }}</b>
            </span>
          </div>
        </div>
        <p v-else class="text-sm text-muted">ให้ลูกค้าสแกนจ่าย และตรวจสอบยอดเงินเข้าก่อนกดยืนยัน</p>
      </template>

      <p v-if="error" class="text-sm text-danger bg-danger-soft rounded-lg px-3 py-2">{{ error }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="btn btn-ghost" @click="emit('close')">ยกเลิก</button>
        <button class="btn btn-accent min-w-40" :disabled="saving" @click="confirm">
          {{ saving ? 'กำลังบันทึก…' : free ? 'ยืนยันรถออก' : `รับเงิน ${baht(quote.amount)} และปล่อยรถ` }}
        </button>
      </div>
    </div>

    <p v-else-if="error" class="text-sm text-danger">{{ error }}</p>
    <div v-else class="py-10 text-center text-muted text-sm">กำลังคำนวณค่าจอด…</div>
  </Modal>
</template>
