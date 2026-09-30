import { defineStore } from 'pinia'
import { api, getToken } from '../api'
import { useToast } from './toast'

const POLL_FALLBACK_MS = 10_000 // while the socket is down
const POLL_SAFETY_MS = 60_000 // even while live, in case an event was missed
const PING_MS = 25_000

// Timers and the socket live outside the store so Pinia never wraps them in a proxy.
const rt = { started: false, ws: null, inflight: null, again: false, clock: null, safety: null, poll: null, ping: null, retry: null, backoff: 1000 }

/**
 * Live lot state shared by every page. A WebSocket tells us *that* something
 * changed; we then refetch summary + slots so the UI always shows server truth.
 */
export const useParking = defineStore('parking', {
  state: () => ({
    summary: null,
    slots: [],
    connection: 'offline', // offline | connecting | live | polling
    lastUpdated: null,
    now: Date.now(),
    version: 0, // bumps on every change event; pages watch it to reload their own data
    events: [], // recent WebSocket events, newest first (Demo Mode debug feed)
  }),
  actions: {
    async refresh() {
      if (rt.inflight) { rt.again = true; return rt.inflight }
      rt.inflight = (async () => {
        try {
          const [summary, slots] = await Promise.all([api.get('/dashboard/summary'), api.get('/slots')])
          this.checkAlert(summary)
          this.summary = summary
          this.slots = slots
          this.lastUpdated = Date.now()
        } catch { /* keep last known state; connection badge shows the problem */ }
      })()
      await rt.inflight
      rt.inflight = null
      if (rt.again) { rt.again = false; await this.refresh() }
    },

    checkAlert(next) {
      const prev = this.summary
      if (!prev) return
      const toast = useToast()
      if (next.is_full && !prev.is_full) toast.error('ลานจอดเต็มแล้ว ไม่มีช่องว่าง')
      else if (next.near_full && !prev.near_full)
        toast.warn(`ลานจอดใกล้เต็ม: ใช้งานแล้ว ${next.occupancy_rate}% (เหลือ ${next.available} ช่อง)`)
    },

    start() {
      if (rt.started) return
      rt.started = true
      this.refresh()
      rt.clock = setInterval(() => { this.now = Date.now() }, 30_000)
      rt.safety = setInterval(() => this.refresh(), POLL_SAFETY_MS)
      rt.backoff = 1000
      this.connect()
    },

    stop() {
      rt.started = false
      clearInterval(rt.clock)
      clearInterval(rt.safety)
      clearInterval(rt.poll)
      clearInterval(rt.ping)
      clearTimeout(rt.retry)
      rt.poll = null
      if (rt.ws) { rt.ws.onclose = null; rt.ws.close() }
      rt.ws = null
      this.connection = 'offline'
      this.summary = null
      this.slots = []
    },

    connect() {
      if (!rt.started) return
      this.connection = this.connection === 'polling' ? 'polling' : 'connecting'
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      let ws
      try {
        ws = new WebSocket(`${proto}://${location.host}/api/ws`)
      } catch {
        this.scheduleReconnect()
        return
      }
      rt.ws = ws
      ws.onopen = () => ws.send(JSON.stringify({ type: 'auth', token: getToken() }))
      ws.onmessage = (e) => {
        let msg
        try { msg = JSON.parse(e.data) } catch { return }
        if (msg.type === 'ready') {
          this.connection = 'live'
          rt.backoff = 1000
          clearInterval(rt.poll)
          rt.poll = null
          clearInterval(rt.ping)
          rt.ping = setInterval(() => ws.readyState === 1 && ws.send('ping'), PING_MS)
          this.refresh()
        } else if (msg.type === 'parking.updated') {
          this.events = [{ ...msg, at: Date.now() }, ...this.events].slice(0, 30)
          this.version++
          this.refresh()
        }
      }
      ws.onclose = () => {
        clearInterval(rt.ping)
        this.scheduleReconnect()
      }
    },

    scheduleReconnect() {
      if (!rt.started) return
      this.connection = 'polling'
      if (!rt.poll) rt.poll = setInterval(() => { this.version++; this.refresh() }, POLL_FALLBACK_MS)
      clearTimeout(rt.retry)
      rt.retry = setTimeout(() => this.connect(), rt.backoff)
      rt.backoff = Math.min(rt.backoff * 2, 30_000)
    },
  },
})
