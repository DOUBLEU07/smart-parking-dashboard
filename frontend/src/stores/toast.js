import { defineStore } from 'pinia'

let seq = 0

export const useToast = defineStore('toast', {
  state: () => ({ items: [] }),
  actions: {
    push(message, kind = 'info', timeout = 4000) {
      const id = ++seq
      this.items.push({ id, message, kind })
      if (timeout) setTimeout(() => this.dismiss(id), timeout)
      return id
    },
    success(message) { return this.push(message, 'success') },
    error(message) { return this.push(message, 'error', 6000) },
    warn(message) { return this.push(message, 'warn', 7000) },
    dismiss(id) { this.items = this.items.filter((t) => t.id !== id) },
  },
})
