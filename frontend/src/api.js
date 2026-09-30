const TOKEN_KEY = 'sp_token'

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}
export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch { /* storage unavailable: session lasts until reload */ }
}

export class ApiError extends Error {
  constructor(status, message, detail, traceId = null) {
    super(message)
    this.status = status
    this.detail = detail
    this.traceId = traceId
  }
}

let onUnauthorized = () => {}
export function setUnauthorizedHandler(fn) { onUnauthorized = fn }

function messageFrom(detail, status) {
  if (typeof detail === 'string') return detail
  if (detail && typeof detail.message === 'string') return detail.message
  if (status >= 500) return 'เซิร์ฟเวอร์ขัดข้อง กรุณาลองใหม่อีกครั้ง'
  return 'เกิดข้อผิดพลาด'
}

function query(params) {
  if (!params) return ''
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') q.set(k, v)
  }
  const s = q.toString()
  return s ? `?${s}` : ''
}

async function request(method, path, { body, params, raw, trace } = {}) {
  const headers = { Accept: 'application/json' }
  if (trace) headers['X-Debug-Trace'] = '1'
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  let res
  try {
    res = await fetch(`/api${path}${query(params)}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ กรุณาตรวจสอบเครือข่าย')
  }

  if (res.status === 401 && path !== '/auth/login') onUnauthorized()
  if (raw && res.ok) return res
  const traceId = res.headers.get('X-Trace-Id')
  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) {
    const detail = data?.detail
    throw new ApiError(res.status, messageFrom(detail, res.status), detail, traceId)
  }
  return trace ? { data, traceId } : data
}

export const api = {
  get: (path, params) => request('GET', path, { params }),
  post: (path, body) => request('POST', path, { body }),
  put: (path, body) => request('PUT', path, { body }),
  patch: (path, body) => request('PATCH', path, { body }),
  del: (path) => request('DELETE', path),
  download: (path, params) => request('GET', path, { params, raw: true }),
  /** Demo Mode: asks the backend to record a trace; resolves to { data, traceId }. */
  traced: (method, path, body) => request(method, path, { body, trace: true }),
}
