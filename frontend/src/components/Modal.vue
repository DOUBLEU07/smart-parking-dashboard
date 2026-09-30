<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import Icon from './Icon.vue'

const props = defineProps({
  title: String,
  width: { type: String, default: 'max-w-md' },
  closable: { type: Boolean, default: true },
})
const emit = defineEmits(['close'])
const panel = ref(null)

function onKey(e) {
  if (e.key === 'Escape' && props.closable) emit('close')
}
onMounted(() => {
  document.addEventListener('keydown', onKey)
  document.body.style.overflow = 'hidden'
  panel.value?.querySelector('input:not([type=hidden]), select, button[data-autofocus]')?.focus()
})
onUnmounted(() => {
  document.removeEventListener('keydown', onKey)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-40 flex items-end sm:items-center justify-center bg-ink/40 p-0 sm:p-4"
         @mousedown.self="closable && emit('close')">
      <div ref="panel" role="dialog" aria-modal="true" :aria-label="title"
           :class="['w-full bg-card sm:rounded-2xl rounded-t-2xl shadow-xl max-h-[92vh] overflow-y-auto', width]">
        <div class="flex items-center justify-between px-5 pt-5 pb-3">
          <h2 class="h-title text-lg">{{ title }}</h2>
          <button v-if="closable" class="text-muted hover:text-ink p-1 cursor-pointer" aria-label="ปิด" @click="emit('close')">
            <Icon name="close" />
          </button>
        </div>
        <div class="px-5 pb-5">
          <slot />
        </div>
      </div>
    </div>
  </Teleport>
</template>
