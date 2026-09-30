const TZ = 'Asia/Bangkok'

const moneyFmt = new Intl.NumberFormat('th-TH', { maximumFractionDigits: 2 })
const intFmt = new Intl.NumberFormat('th-TH')
const timeFmt = new Intl.DateTimeFormat('th-TH', { hour: '2-digit', minute: '2-digit', timeZone: TZ })
const dateTimeFmt = new Intl.DateTimeFormat('th-TH', {
  day: 'numeric', month: 'short', year: '2-digit', hour: '2-digit', minute: '2-digit', timeZone: TZ,
})
const dateFmt = new Intl.DateTimeFormat('th-TH', { day: 'numeric', month: 'short', timeZone: TZ })
const longDateFmt = new Intl.DateTimeFormat('th-TH', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: TZ })

export const baht = (v) => `฿${moneyFmt.format(v ?? 0)}`
export const int = (v) => intFmt.format(v ?? 0)
export const time = (v) => (v ? timeFmt.format(new Date(v)) : '–')
export const dateTime = (v) => (v ? dateTimeFmt.format(new Date(v)) : '–')
export const shortDate = (v) => dateFmt.format(new Date(`${v}T00:00:00+07:00`))
export const longDate = (v = new Date()) => longDateFmt.format(v)

export function duration(minutes) {
  if (minutes == null) return '–'
  const m = Math.max(0, Math.floor(minutes))
  const d = Math.floor(m / 1440)
  const h = Math.floor((m % 1440) / 60)
  const mm = m % 60
  const parts = []
  if (d) parts.push(`${d} วัน`)
  if (h) parts.push(`${h} ชม.`)
  if (mm || !parts.length) parts.push(`${mm} นาที`)
  return parts.join(' ')
}

export function minutesSince(iso, now = Date.now()) {
  return Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60000))
}

/** Local (Bangkok) calendar date as YYYY-MM-DD, offset by `days`. */
export function localISODate(days = 0) {
  const d = new Date(Date.now() + days * 86400000)
  return new Intl.DateTimeFormat('en-CA', { timeZone: TZ }).format(d)
}

export const ROLE_LABEL = { owner: 'เจ้าของ', manager: 'ผู้จัดการ', staff: 'พนักงาน' }
export const METHOD_LABEL = { cash: 'เงินสด', qr: 'QR / โอน' }
export const SLOT_STATUS_LABEL = { available: 'ว่าง', occupied: 'มีรถจอด', maintenance: 'ปิดปรับปรุง' }
