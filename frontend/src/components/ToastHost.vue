<script setup>
import { useToast } from '../stores/toast'
import Icon from './Icon.vue'

const toast = useToast()
const STYLE = {
  success: 'bg-pine text-white',
  error: 'bg-danger text-white',
  warn: 'bg-rust text-white',
  info: 'bg-ink text-paper',
}
const ICON = { success: 'check', error: 'alert', warn: 'alert', info: 'check' }
</script>

<template>
  <div class="fixed z-50 bottom-4 right-4 left-4 sm:left-auto flex flex-col gap-2 items-stretch sm:items-end pointer-events-none"
       aria-live="polite">
    <TransitionGroup
      enter-from-class="opacity-0 translate-y-2" enter-active-class="transition duration-200"
      leave-to-class="opacity-0" leave-active-class="transition duration-150">
      <div v-for="t in toast.items" :key="t.id" role="status"
           :class="['pointer-events-auto flex items-start gap-2.5 rounded-lg px-4 py-3 shadow-lg text-sm sm:max-w-sm', STYLE[t.kind]]">
        <Icon :name="ICON[t.kind]" class="mt-0.5 shrink-0" />
        <span class="flex-1">{{ t.message }}</span>
        <button class="opacity-70 hover:opacity-100 cursor-pointer" aria-label="ปิด" @click="toast.dismiss(t.id)">
          <Icon name="close" :size="16" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>
